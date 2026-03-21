"""
DOCX to EPUB Converter

Converts DOCX files to EPUB format using Calibre's ebook-convert tool.
Reads book metadata (title, author, annotation, ISBN, translators) from
an Excel spreadsheet and applies it during conversion.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import json
import logging
import sys
import subprocess
import time
import pandas as pd

logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.json in the project root.

    Honors the PIPELINE_CONFIG environment variable to override the default
    config path (useful for testing without touching the root config.json).
    """
    config_path = os.environ.get(
        'PIPELINE_CONFIG',
        os.path.join(os.path.dirname(__file__), '..', 'config.json'),
    )
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error('config.json not found at %s', os.path.abspath(config_path))
        logger.error('Copy config.example.json to config.json and edit it.')
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error('invalid JSON in config.json: %s', e)
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


def _normalize_isbn(value):
    """Normalize ISBN value: strip trailing .0 from Excel float representation."""
    s = str(value).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s


def convert_with_calibre(input_path, output_path, metadata, cover_image_path,
                         css_path, language, publisher, epub_version):
    """Convert a single DOCX file to EPUB using Calibre with metadata applied.

    Excel column names: Title, Authors, Annotation, Translators, ISBN.
    """
    comments = shorten_annotation(str(metadata['Annotation']))
    comments = comments.replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n')
    translators = metadata['Translators'] if not pd.isna(metadata['Translators']) else ''

    command = [
        'ebook-convert', input_path, output_path,
        '--title', str(metadata['Title']),
        '--authors', str(metadata['Authors']),
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
        logger.warning('cover image not found: %s', cover_image_path)

    if translators:
        command.extend(['--translator', str(translators)])

    max_retries = 2
    timeout_seconds = 300
    for attempt in range(1, max_retries + 1):
        try:
            start_t = time.time()
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout_seconds,
            )
            elapsed = time.time() - start_t
            if result.returncode != 0:
                logger.error(
                    'ebook-convert error for %s (exit code %d, %.1fs):',
                    os.path.basename(input_path), result.returncode, elapsed,
                )
                if result.stderr:
                    for line in result.stderr.strip().split('\n')[-5:]:
                        logger.error('    %s', line)
                if attempt < max_retries:
                    logger.warning('  Retrying (%d/%d)...', attempt, max_retries)
                    time.sleep(1)
                    continue
                return False

            logger.info(
                '  Converted: %s -> %s (exit code 0, %.1fs)',
                os.path.basename(input_path), os.path.basename(output_path), elapsed,
            )
            return True

        except subprocess.TimeoutExpired:
            logger.error(
                'ebook-convert timed out after %ds for %s',
                timeout_seconds, os.path.basename(input_path),
            )
            if attempt < max_retries:
                logger.warning('  Retrying (%d/%d)...', attempt, max_retries)
                time.sleep(1)
                continue
            return False

        except FileNotFoundError:
            logger.error('ebook-convert not found. Is Calibre installed and in PATH?')
            return False

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
        logger.error('input directory not found: %s', input_dir)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Load metadata
    try:
        metadata_df = pd.read_excel(metadata_xlsx)
        logger.info('Loaded metadata: %d entries', len(metadata_df))
        logger.info('Columns: %s', list(metadata_df.columns))
    except FileNotFoundError:
        logger.error('metadata file not found: %s', metadata_xlsx)
        sys.exit(1)

    # Validate required columns
    required_columns = ['ISBN', 'Title', 'Authors', 'Annotation', 'Translators']
    missing_cols = [c for c in required_columns if c not in metadata_df.columns]
    if missing_cols:
        logger.error('missing required columns in %s: %s', metadata_xlsx, ', '.join(missing_cols))
        logger.error('Expected columns: %s', ', '.join(required_columns))
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
        logger.warning('No .docx files found in %s', input_dir)
        return

    logger.info('Processing %d DOCX file(s)...', len(docx_files))

    success = 0
    errors = 0

    for filename in docx_files:
        book_name = os.path.splitext(filename)[0]
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, book_name + '.epub')

        # Match metadata by ISBN (filename = ISBN)
        matching_metadata = metadata_df[metadata_df['ISBN'].apply(_normalize_isbn) == book_name]

        if matching_metadata.empty:
            logger.warning('no metadata found for %s, skipping', book_name)
            errors += 1
            continue

        metadata = matching_metadata.iloc[0]
        cover_image_path = os.path.join(cover_dir, _normalize_isbn(metadata['ISBN']) + '.jpg')

        if convert_with_calibre(
            input_path, output_path, metadata, cover_image_path,
            css_path, language, publisher, epub_version
        ):
            success += 1
        else:
            errors += 1

    logger.info('Conversion completed: %d successful, %d errors', success, errors)

    if errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
