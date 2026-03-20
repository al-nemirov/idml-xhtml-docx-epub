"""
EPUB Enrichment Tool

Enriches EPUB files with additional metadata, accessibility attributes,
title page adjustments, updated styles, and cleaned heading classes.
Reads metadata from an Excel spreadsheet and applies it to the EPUB's
OPF file, navigation document, title page, and stylesheets.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import json
import sys
import zipfile
import tempfile
import lxml.etree as ET
import pandas as pd

NS_XHTML = 'http://www.w3.org/1999/xhtml'
NS_OPF = 'http://www.idpf.org/2007/opf'
NS_DC = 'http://purl.org/dc/elements/1.1/'
NS_OPS = 'http://www.idpf.org/2007/ops'


def load_config():
    """Load configuration from config.json in the project root."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'Error: config.json not found at {os.path.abspath(config_path)}')
        print('Copy config.example.json to config.json and edit it.')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'Error: invalid JSON in config.json: {e}')
        sys.exit(1)


def adjust_titlepage(titlepage_path, metadata):
    """Add title, author, annotation, and publisher info to the EPUB title page."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(titlepage_path, parser)
    root = tree.getroot()

    body_elem = root.find(f'.//{{{NS_XHTML}}}body')
    if body_elem is not None:
        metadata_div = ET.Element('div')
        title_elem = ET.SubElement(metadata_div, 'h1')
        title_elem.text = metadata.get('title', 'Unknown Title')
        author_elem = ET.SubElement(metadata_div, 'h2')
        author_elem.text = metadata.get('creator', 'Unknown Author')

        annotation_div = ET.SubElement(
            metadata_div, 'div',
            attrib={"style": "background-color: #f0f0f0; color: #333; padding: 1em;"}
        )
        annotation_text = metadata.get('description', 'No annotation available')
        annotation_text = annotation_text.replace("<p>", "").replace("</p>", "")
        annotation_div.text = annotation_text

        # Add translator information after the annotation if available
        if 'translator' in metadata and metadata['translator']:
            translator_div = ET.SubElement(metadata_div, 'div')
            translator_div.text = f"Translation: {metadata['translator']}"

        publisher_div = ET.SubElement(metadata_div, 'div')
        publisher_div.text = metadata.get('publisher_notice', '')

        body_elem.append(metadata_div)

    tree.write(titlepage_path, encoding='utf-8', xml_declaration=True)


def add_metadata_to_opf(opf_path, metadata, language):
    """Add custom metadata entries (accessibility, etc.) to the OPF package file."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(opf_path, parser)
    root = tree.getroot()

    ns = {'dc': NS_DC, 'opf': NS_OPF}

    metadata_elem = root.find('opf:metadata', ns)
    if metadata_elem is not None:
        # Only add schema.org accessibility metadata (skip display fields)
        skip_keys = ('title', 'creator', 'description', 'translator', 'publisher_notice')
        for key, value in metadata.items():
            if key in skip_keys:
                continue
            ET.SubElement(metadata_elem, 'meta', attrib={'name': key, 'content': str(value)})

    if '{http://www.w3.org/XML/1998/namespace}lang' not in root.attrib:
        root.set('{http://www.w3.org/XML/1998/namespace}lang', language)

    tree.write(opf_path, encoding='utf-8', xml_declaration=True)


def add_aria_role_to_nav(nav_path):
    """Add ARIA doc-toc role to the navigation document for accessibility."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(nav_path, parser)
    root = tree.getroot()

    nav_elem = root.find(f'.//{{{NS_XHTML}}}nav[@{{{NS_OPS}}}type="toc"]')
    if nav_elem is not None:
        nav_elem.set('role', 'doc-toc')

    tree.write(nav_path, encoding='utf-8', xml_declaration=True)


HEADING_STYLES = """
h1 {
    color: #333;
    font-size: 2.5em;
    font-weight: bold;
    line-height: 1.2;
    margin-bottom: 0.5em;
}

h2 {
    color: #333;
    font-size: 2em;
    font-weight: bold;
    line-height: 1.2;
    margin-bottom: 0.5em;
}

h3 {
    color: #333;
    font-size: 1.75em;
    font-weight: bold;
    line-height: 1.2;
    margin-bottom: 0.5em;
}

h4 {
    color: #333;
    font-size: 1.5em;
    font-weight: bold;
    line-height: 1.2;
    margin-bottom: 0.5em;
}

h5 {
    color: #333;
    font-size: 1.25em;
    font-weight: bold;
    line-height: 1.2;
    margin-bottom: 0.5em;
}

a {
    color: #0056b3;
    text-decoration: none;
    padding-bottom: 2px;
    border-bottom: 1px dotted rgb(0,0,238);
}

.calibre3 {
    color: #0056b3;
    text-decoration: underline;
}
"""


def update_styles(filepath):
    """Append enhanced heading and link styles to the EPUB stylesheet."""
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(HEADING_STYLES)


def remove_classes_from_headings(filepath):
    """Remove CSS class attributes from heading elements (h1-h6) in XHTML files."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(filepath, parser)
    root = tree.getroot()

    for level in range(1, 7):
        for heading in root.iterfind(f'.//{{{NS_XHTML}}}h{level}'):
            if 'class' in heading.attrib:
                del heading.attrib['class']

    tree.write(filepath, encoding='utf-8', xml_declaration=True)


def process_epub(epub_path, output_path, metadata_df, config):
    """Process a single EPUB file: extract, enrich, repackage."""
    publisher = config.get('publisher', 'Your Publisher Name')
    publisher_notice = f"(c) {publisher}"
    language = config.get('language', 'en')

    book_isbn = os.path.splitext(os.path.basename(epub_path))[0]
    print(f'Processing: {os.path.basename(epub_path)}')

    # Use a temporary directory for EPUB extraction (auto-cleaned)
    with tempfile.TemporaryDirectory(prefix='epub_enrich_') as temp_dir:
        # Extract the EPUB
        with zipfile.ZipFile(epub_path, 'r') as epub_zip:
            epub_zip.extractall(temp_dir)

        # Build metadata from Excel
        matching_metadata = metadata_df[metadata_df['ISBN'].astype(str) == book_isbn]

        if not matching_metadata.empty:
            metadata_row = matching_metadata.iloc[0]
            custom_metadata = {
                'schema:accessibilityHazard': 'none',
                'schema:accessibilityFeature': 'alternativeText',
                'schema:accessMode': 'textual',
                'schema:accessModeSufficient': 'textual',
                'schema:accessibilitySummary': 'This book provides an accessible reading experience.',
                # Excel column names are in Russian to match the source spreadsheet
                'title': metadata_row['Произведение'],          # Title
                'creator': metadata_row['Авторы'],              # Authors
                'description': metadata_row['Аннотация'],       # Annotation
                'translator': (
                    metadata_row['Переводчики']
                    if not pd.isna(metadata_row['Переводчики'])
                    else ''
                ),  # Translators
                'publisher_notice': publisher_notice,
            }
        else:
            print(f'  Warning: no metadata found for ISBN {book_isbn}')
            custom_metadata = {
                'schema:accessibilityHazard': 'none',
                'schema:accessibilityFeature': 'alternativeText',
                'schema:accessMode': 'textual',
                'schema:accessModeSufficient': 'textual',
                'schema:accessibilitySummary': 'This book provides an accessible reading experience.',
                'publisher_notice': publisher_notice,
            }

        # Find and process key files
        opf_path = None
        nav_path = None
        titlepage_path = None
        stylesheet_path = None

        for dirpath, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(dirpath, file)
                if file == 'nav.xhtml':
                    nav_path = file_path
                    add_aria_role_to_nav(nav_path)
                if file.endswith('.opf'):
                    opf_path = file_path
                elif file.endswith(('.html', '.xhtml')):
                    if 'titlepage' in file_path:
                        titlepage_path = file_path
                elif file == 'stylesheet.css':
                    stylesheet_path = file_path

        if titlepage_path:
            adjust_titlepage(titlepage_path, custom_metadata)

        if opf_path:
            add_metadata_to_opf(opf_path, custom_metadata, language)

        if stylesheet_path:
            update_styles(stylesheet_path)

        # Remove classes from headings in all XHTML files
        for dirpath, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(('.html', '.xhtml')):
                    filepath = os.path.join(dirpath, file)
                    remove_classes_from_headings(filepath)

        # Repackage the EPUB (mimetype must be first entry, stored uncompressed)
        with zipfile.ZipFile(output_path, 'w') as epub_zip:
            mimetype_path = os.path.join(temp_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                epub_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

            for dirpath, _, files in os.walk(temp_dir):
                for file in files:
                    if file == 'mimetype':
                        continue
                    file_path = os.path.join(dirpath, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    epub_zip.write(file_path, arcname)

    print(f'  Enriched: {os.path.basename(output_path)}')


def main():
    """Main entry point: enrich all EPUB files in the configured directory."""
    config = load_config()

    metadata_xlsx = config['metadata_file']
    epub_dir = config['paths']['epub_dir']
    output_dir = config['paths']['output_dir']

    if not os.path.exists(epub_dir):
        print(f'Error: EPUB directory not found: {epub_dir}')
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # Load metadata
    try:
        metadata_df = pd.read_excel(metadata_xlsx)
        print(f'Loaded metadata: {len(metadata_df)} entries')
    except FileNotFoundError:
        print(f'Error: metadata file not found: {metadata_xlsx}')
        sys.exit(1)

    epub_files = [f for f in os.listdir(epub_dir) if f.endswith('.epub')]
    if not epub_files:
        print(f'No .epub files found in {epub_dir}')
        return

    print(f'Processing {len(epub_files)} EPUB file(s)...\n')

    for filename in epub_files:
        epub_path = os.path.join(epub_dir, filename)
        output_path = os.path.join(output_dir, filename)
        try:
            process_epub(epub_path, output_path, metadata_df, config)
        except Exception as e:
            print(f'  Error processing {filename}: {e}')

    print('\nMetadata enrichment completed!')


if __name__ == '__main__':
    main()
