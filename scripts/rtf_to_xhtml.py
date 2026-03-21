"""
RTF to XHTML Converter

Converts RTF files to clean XHTML format using pypandoc.
Extracts and organizes embedded images, separates CSS styles,
and removes unnecessary HTML elements (scripts, comments).

Useful as a preprocessing step when source documents arrive in RTF format
instead of InDesign XHTML export.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import json
import logging
import sys
import base64
import pypandoc
from bs4 import BeautifulSoup, Comment

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


def clean_html(html):
    """Remove HTML comments and script tags from the content."""
    soup = BeautifulSoup(html, 'html.parser')

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove script tags
    for tag in soup(['script']):
        tag.decompose()

    return str(soup)


def convert_rtf_to_xhtml(rtf_path, output_folder):
    """Convert a single RTF file to XHTML, extracting images and styles."""
    file_name = os.path.basename(rtf_path).replace('.rtf', '')
    resources_folder = os.path.join(output_folder, f"{file_name}-web-resources")
    css_folder = os.path.join(resources_folder, 'css')
    image_folder = os.path.join(resources_folder, 'image')

    os.makedirs(css_folder, exist_ok=True)
    os.makedirs(image_folder, exist_ok=True)

    # Convert RTF to HTML using pypandoc
    try:
        html_content = pypandoc.convert_file(rtf_path, 'html')
    except Exception as e:
        logger.error('Error converting %s: %s', rtf_path, e)
        return False

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Update image paths and extract embedded images
    img_count = 0
    for img in soup.find_all('img'):
        img_src = img.get('src', '')
        if img_src.startswith('data:'):
            # Handle embedded base64 images
            try:
                img_data = img_src.split(',', 1)[1]
                img_extension = img_src.split(';')[0].split('/')[1]
                img_count += 1
                img_name = f"{file_name}_{img_count}.{img_extension}"
                img_path = os.path.join(image_folder, img_name)
                with open(img_path, 'wb') as img_file:
                    img_file.write(base64.b64decode(img_data))
                img['src'] = os.path.join(f"{file_name}-web-resources/image", img_name)
            except Exception as e:
                logger.warning('could not extract embedded image: %s', e)

    # Extract and save inline styles to external CSS files
    for style in soup.find_all('style'):
        css_content = style.string
        if css_content:
            css_file_name = f"{file_name}.css"
            css_path = os.path.join(css_folder, css_file_name)
            with open(css_path, 'w', encoding='utf-8') as css_file:
                css_file.write(css_content)
        style.decompose()

    # Clean the HTML content
    xhtml_content = clean_html(str(soup))

    # Write the output XHTML file
    xhtml_file_name = f"{file_name}.xhtml"
    output_path = os.path.join(output_folder, xhtml_file_name)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xhtml_content)

    return True


def main():
    """Main entry point: convert all RTF files in the configured directory."""
    config = load_config()

    input_folder = config['paths'].get('rtf_dir', config['paths']['epub_dir'])
    output_folder = config['paths']['xhtml_dir']

    if not os.path.exists(input_folder):
        logger.error('input directory not found: %s', input_folder)
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)

    rtf_files = [f for f in os.listdir(input_folder) if f.endswith('.rtf')]
    if not rtf_files:
        logger.warning('No .rtf files found in %s', input_folder)
        return

    logger.info('Processing %d RTF file(s)...', len(rtf_files))

    success = 0
    errors = 0

    for file_name in rtf_files:
        rtf_path = os.path.join(input_folder, file_name)
        if convert_rtf_to_xhtml(rtf_path, output_folder):
            logger.info('  Converted: %s', file_name)
            success += 1
        else:
            errors += 1

    logger.info('Conversion completed: %d successful, %d errors', success, errors)

    if errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
