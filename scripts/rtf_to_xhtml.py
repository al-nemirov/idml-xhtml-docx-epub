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
import sys
import base64
import pypandoc
from bs4 import BeautifulSoup, Comment


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
        print(f'  Error converting {rtf_path}: {e}')
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
                print(f'  Warning: could not extract embedded image: {e}')

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
        print(f'Error: input directory not found: {input_folder}')
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)

    rtf_files = [f for f in os.listdir(input_folder) if f.endswith('.rtf')]
    if not rtf_files:
        print(f'No .rtf files found in {input_folder}')
        return

    print(f'Processing {len(rtf_files)} RTF file(s)...')

    success = 0
    errors = 0

    for file_name in rtf_files:
        rtf_path = os.path.join(input_folder, file_name)
        if convert_rtf_to_xhtml(rtf_path, output_folder):
            print(f'  Converted: {file_name}')
            success += 1
        else:
            errors += 1

    print(f'\nConversion completed: {success} successful, {errors} errors')


if __name__ == '__main__':
    main()
