"""
DOCX to EPUB Converter

Converts DOCX files to EPUB format using Calibre's ebook-convert tool.
Reads book metadata (title, author, annotation, ISBN, translators) from
an Excel spreadsheet and applies it during conversion.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import json
import subprocess
import pandas as pd

# Load configuration
with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r', encoding='utf-8') as f:
    config = json.load(f)

# Paths from configuration
input_dir = config['paths']['docx_dir']
output_dir = config['paths']['epub_dir']
cover_dir = config['paths']['cover_dir']
metadata_xlsx = config['metadata_file']
temp_dir = config['paths']['temp_dir']
publisher = config.get('publisher', 'Your Publisher Name')
language = config.get('language', 'en')
epub_version = config.get('epub_version', '3')

# Create the output directory if it does not exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Create the temporary directory if it does not exist
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# Read metadata from the Excel file
metadata_df = pd.read_excel(metadata_xlsx)


def shorten_annotation(annotation):
    """Truncate annotation to the nearest period within 250 characters."""
    if len(annotation) <= 250:
        return annotation
    shortened = annotation[:250]
    last_period = shortened.rfind('.')
    if last_period != -1:
        return shortened[:last_period + 1]
    return shortened


# Print column headers and first rows for verification
print("Metadata columns:", metadata_df.columns)
print("First rows of metadata:")
print(metadata_df.head())

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


def convert_with_calibre(input_path, output_path, metadata, cover_image_path, css_path):
    """Convert a single DOCX file to EPUB using Calibre with metadata applied.

    Note: Excel column names below are in Russian to match the source spreadsheet.
    Column mapping: Аннотация=Annotation, Переводчики=Translators,
    Произведение=Title, Авторы=Authors, ISBN=ISBN.
    """
    comments = shorten_annotation(metadata['Аннотация']).replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n')  # Annotation
    translators = metadata['Переводчики'] if not pd.isna(metadata['Переводчики']) else ''  # Translators

    command = [
        'ebook-convert', input_path, output_path,
        '--title', str(metadata['Произведение']),   # Title
        '--authors', str(metadata['Авторы']),        # Authors
        '--language', language,
        '--publisher', publisher,
        '--comments', comments,
        '--isbn', str(metadata['ISBN']),
        '--cover', cover_image_path,
        '--extra-css', css_path,
        '--epub-version', epub_version,
        '--output-profile', 'tablet',
        '--level1-toc', '//*[(name()="h1" or name()="h2" or name()="h3") and re:test(@class, "chapter|section|part", "i")]',
        '--level2-toc', '//*[(name()="h2" or name()="h3" or name()="h4") and re:test(@class, "chapter|section|part", "i")]',
        '--level3-toc', '//*[(name()="h3" or name()="h4" or name()="h5") and re:test(@class, "chapter|section|part", "i")]'
    ]

    if translators:
        command.extend(['--translator', translators])

    try:
        subprocess.run(command, check=True)
        print(f'Successfully converted {input_path} to {output_path}')
    except subprocess.CalledProcessError as e:
        print(f'Error converting {input_path}: {e}')


# Process all DOCX files in the input directory
for filename in os.listdir(input_dir):
    if filename.endswith('.docx'):
        book_name = os.path.splitext(filename)[0]
        input_path = os.path.join(input_dir, filename)
        output_filename = book_name + '.epub'
        output_path = os.path.join(output_dir, output_filename)

        # Debug message
        print(f'Processing file: {filename}, book name: {book_name}')

        # Get metadata for the current file by ISBN
        matching_metadata = metadata_df[metadata_df['ISBN'].astype(str) == book_name]

        if matching_metadata.empty:
            print(f'No metadata found for {book_name}')
            continue

        metadata = matching_metadata.iloc[0]

        # Path to the cover image
        cover_image_path = os.path.join(cover_dir, str(metadata['ISBN']) + '.jpg')

        # Convert the file using Calibre
        convert_with_calibre(input_path, output_path, metadata, cover_image_path, css_path)

print('Conversion completed!')
