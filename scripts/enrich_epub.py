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
import zipfile
import shutil
import lxml.etree as ET
import pandas as pd

# Load configuration
with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r', encoding='utf-8') as f:
    config = json.load(f)

# Paths from configuration
metadata_xlsx = config['metadata_file']
epub_dir = config['paths']['epub_dir']
output_dir = config['paths']['output_dir']
publisher = config.get('publisher', 'Your Publisher Name')
publisher_notice = f"(c) {publisher}"

# Create the output directory if it does not exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Load metadata from the Excel file
metadata_df = pd.read_excel(metadata_xlsx)


def adjust_titlepage(titlepage_path, metadata):
    """Add title, author, annotation, and publisher info to the EPUB title page."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(titlepage_path, parser)
    root = tree.getroot()

    body_elem = root.find('.//{http://www.w3.org/1999/xhtml}body')
    if body_elem is not None:
        metadata_div = ET.Element('div')
        title_elem = ET.SubElement(metadata_div, 'h1')
        title_elem.text = metadata.get('title', 'Unknown Title')
        author_elem = ET.SubElement(metadata_div, 'h2')
        author_elem.text = metadata.get('creator', 'Unknown Author')

        annotation_div = ET.SubElement(metadata_div, 'div', attrib={"style": "background-color: #f0f0f0; color: #333; padding: 1em;"})
        annotation_text = metadata.get('description', 'No annotation available')

        # Remove <p> and </p> tags from the annotation text
        annotation_text = annotation_text.replace("<p>", "").replace("</p>", "")
        annotation_div.text = annotation_text

        # Add translator information after the annotation if available
        if 'translator' in metadata and metadata['translator']:
            translator_div = ET.SubElement(metadata_div, 'div')
            translator_div.text = f"Translation: {metadata['translator']}"

        publisher_div = ET.SubElement(metadata_div, 'div')
        publisher_div.text = publisher_notice

        body_elem.append(metadata_div)

    tree.write(titlepage_path, encoding='utf-8', xml_declaration=True)


def add_metadata_to_opf(opf_path, metadata):
    """Add custom metadata entries (accessibility, etc.) to the OPF package file."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(opf_path, parser)
    root = tree.getroot()

    ns = {'dc': 'http://purl.org/dc/elements/1.1/',
          'opf': 'http://www.idpf.org/2007/opf'}

    metadata_elem = root.find('opf:metadata', ns)
    for key, value in metadata.items():
        new_element = ET.SubElement(metadata_elem, 'meta', attrib={'name': key, 'content': value})

    if 'xml:lang' not in root.attrib:
        root.set('{http://www.w3.org/XML/1998/namespace}lang', config.get('language', 'en'))

    tree.write(opf_path, encoding='utf-8', xml_declaration=True)


def add_aria_role_to_nav(nav_path):
    """Add ARIA doc-toc role to the navigation document for accessibility."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(nav_path, parser)
    root = tree.getroot()

    nav_elem = root.find('.//{http://www.w3.org/1999/xhtml}nav[@{http://www.idpf.org/2007/ops}type="toc"]')
    if nav_elem is not None:
        nav_elem.set('role', 'doc-toc')

    tree.write(nav_path, encoding='utf-8', xml_declaration=True)


def update_styles(filepath):
    """Append enhanced heading and link styles to the EPUB stylesheet."""
    new_styles = """
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
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(new_styles)


def remove_classes_from_headings(filepath):
    """Remove CSS class attributes from heading elements (h1-h6) in XHTML files."""
    parser = ET.XMLParser(ns_clean=True, recover=True)
    tree = ET.parse(filepath, parser)
    root = tree.getroot()

    for level in range(1, 7):
        for heading in root.iterfind(f'.//{{{" http://www.w3.org/1999/xhtml"}}}h{level}'.replace(" ", "")):
            if 'class' in heading.attrib:
                del heading.attrib['class']

    tree.write(filepath, encoding='utf-8', xml_declaration=True)


# Create temporary directory for EPUB extraction
temp_dir = config['paths']['temp_dir'] + '_opf'
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# Process all EPUB files in the directory
for filename in os.listdir(epub_dir):
    if filename.endswith('.epub'):
        epub_path = os.path.join(epub_dir, filename)
        output_path = os.path.join(output_dir, filename)
        print(f'Processing file: {filename}')
        with zipfile.ZipFile(epub_path, 'r') as epub_zip:
            epub_zip.extractall(temp_dir)

        # Get metadata for the current file by ISBN
        book_isbn = os.path.splitext(filename)[0]
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
                'description': metadata_row['Аннотация'],      # Annotation
                'translator': metadata_row['Переводчики'] if not pd.isna(metadata_row['Переводчики']) else ''  # Translators
            }
        else:
            custom_metadata = {
                'schema:accessibilityHazard': 'none',
                'schema:accessibilityFeature': 'alternativeText',
                'schema:accessMode': 'textual',
                'schema:accessModeSufficient': 'textual',
                'schema:accessibilitySummary': 'This book provides an accessible reading experience.'
            }

        opf_path = None
        nav_path = None
        titlepage_path = None
        stylesheet_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if file == 'nav.xhtml':
                    nav_path = os.path.join(root, file)
                    add_aria_role_to_nav(nav_path)
                if file.endswith('.opf'):
                    opf_path = os.path.join(root, file)
                elif file.endswith('.html') or file.endswith('.xhtml'):
                    if 'titlepage' in file_path:
                        titlepage_path = file_path
                elif file == 'stylesheet.css':
                    stylesheet_path = file_path

        if titlepage_path:
            adjust_titlepage(titlepage_path, custom_metadata)

        if opf_path:
            add_metadata_to_opf(opf_path, custom_metadata)

        if stylesheet_path:
            update_styles(stylesheet_path)

        # Remove classes from headings and update styles for all XHTML files
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(('.html', '.xhtml')):
                    filepath = os.path.join(root, file)
                    remove_classes_from_headings(filepath)

        # Create the new EPUB file
        with zipfile.ZipFile(output_path, 'w') as epub_zip:
            mimetype_path = os.path.join(temp_dir, 'mimetype')
            epub_zip.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

            # Add remaining files
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file != 'mimetype':
                        epub_zip.write(file_path, os.path.relpath(file_path, temp_dir))

        # Clean up the temporary directory
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                shutil.rmtree(os.path.join(root, dir))

print('Metadata enrichment completed!')
