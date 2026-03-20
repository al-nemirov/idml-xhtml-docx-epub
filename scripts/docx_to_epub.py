"""
DOCX to EPUB Converter

Converts DOCX files to EPUB format using Calibre's ebook-convert tool.
Reads book metadata (title, author, annotation, ISBN, translators) from
an Excel spreadsheet and applies it during conversion.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import json
import sys
import subprocess
import pandas as pd


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


def shorten_annotation(annotation):
    """Truncate annotation to the nearest period within 250 characters."""
    if not annotation or not isinstance(annotation, str):
        return ''
    if len(annotation) <= 250:
        return annotation
    shortened = annotation[:250]
    last_period = shortened.rfind('.')
    if last_period != -1:
        return shortened[:last_period + 1]
    return shortened


def convert_with_calibre(input_path, output_path, metadata, cover_image_path,
                         css_path, language, publisher, epub_version):
    """Convert a single DOCX file to EPUB using Calibre with metadata applied.

    Note: Excel column names below are in Russian to match the source spreadsheet.
    Column mapping: Аннотация=Annotation, Переводчики=Translators,
    Произведение=Title, Авторы=Authors, ISBN=ISBN.
    """
    comments = shorten_annotation(str(metadata['Аннотация']))  # Annotation
    comments = comments.replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n')
    translators = metadata['Переводчики'] if not pd.isna(metadata['Переводчики']) else ''  # Translators

    command = [
        'ebook-convert', input_path, output_path,
        '--title', str(metadata['Произведение']),   # Title
        '--authors', str(metadata['Авторы']),        # Authors
        '--language', language,
        '--publisher', publisher,
        '--comments', comments,
        '--isbn', str(metadata['ISBN']),
        '--extra-css', css_path,
        '--epub-version', epub_version,
        '--output-profile', 'tablet',
        '--level1-toc', '//*[(name()="h1" or name()="h2" or name()="h3") and re:test(@class, "chapter|section|part", "i")]',
        '--level2-toc', '//*[(name()="h2" or name()="h3" or name()="h4") and re:test(@class, "chapter|section|part", "i")]',
        '--level3-toc', '//*[(name()="h3" or name()="h4" or name()="h5") and re:test(@class, "chapter|section|part", "i")]'
    ]

    # Add cover image if it exists
    if os.path.exists(cover_image_path):
        command.extend(['--cover', cover_image_path])
    else:
        print(f'  Warning: cover image not found: {cover_image_path}')

    if translators:
        command.extend(['--translator', str(translators)])

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f'  Converted: {os.path.basename(input_path)} -> {os.path.basename(output_path)}')
        return True
    except subprocess.CalledProcessError as e:
        print(f'  Error converting {os.path.basename(input_path)}:')
        if e.stderr:
            # Show last 5 lines of error output
            for line in e.stderr.strip().split('\n')[-5:]:
                print(f'    {line}')
        return False
    except FileNotFoundError:
        print('  Error: ebook-convert not found. Is Calibre installed and in PATH?')
        return False


def main():
    """Main entry point: convert all DOCX files to EPUB."""
    config = load_config()

    input_dir = config['paths']['docx_dir']
    output_dir = config['paths']['epub_dir']
    cover_dir = config['paths']['cover_dir']
    metadata_xlsx = config['metadata_file']
    temp_dir = config['paths']['temp_dir']
    publisher = config.get('publisher', 'Your Publisher Name')
    language = config.get('language', 'en')
    epub_version = config.get('epub_version', '3')

    if not os.path.exists(input_dir):
        print(f'Error: input directory not found: {input_dir}')
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Load metadata
    try:
        metadata_df = pd.read_excel(metadata_xlsx)
        print(f'Loaded metadata: {len(metadata_df)} entries')
        print(f'Columns: {list(metadata_df.columns)}')
    except FileNotFoundError:
        print(f'Error: metadata file not found: {metadata_xlsx}')
        sys.exit(1)

    # Create CSS file for footnote styles
    css_content = """
sup {
    font-size: smaller;
    vertical-align: super;
}
"""
    css_path = os.path.join(temp_dir, 'styles.css')
    with open(css_path, 'w') as css_file:
        css_file.write(css_content)

    docx_files = [f for f in os.listdir(input_dir) if f.endswith('.docx')]
    if not docx_files:
        print(f'No .docx files found in {input_dir}')
        return

    print(f'Processing {len(docx_files)} DOCX file(s)...\n')

    success = 0
    errors = 0

    for filename in docx_files:
        book_name = os.path.splitext(filename)[0]
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, book_name + '.epub')

        # Match metadata by ISBN (filename = ISBN)
        matching_metadata = metadata_df[metadata_df['ISBN'].astype(str) == book_name]

        if matching_metadata.empty:
            print(f'  Warning: no metadata found for {book_name}, skipping')
            errors += 1
            continue

        metadata = matching_metadata.iloc[0]
        cover_image_path = os.path.join(cover_dir, str(metadata['ISBN']) + '.jpg')

        if convert_with_calibre(
            input_path, output_path, metadata, cover_image_path,
            css_path, language, publisher, epub_version
        ):
            success += 1
        else:
            errors += 1

    print(f'\nConversion completed: {success} successful, {errors} errors')


if __name__ == '__main__':
    main()
