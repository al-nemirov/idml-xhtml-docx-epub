"""
EPUB/RTF to XHTML Converter

Converts RTF files to clean XHTML format using pypandoc.
Extracts and organizes embedded images, separates CSS styles,
and removes unnecessary HTML elements (scripts, comments).

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import json
import base64
import pypandoc
from bs4 import BeautifulSoup, Comment

# Load configuration
with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r', encoding='utf-8') as f:
    config = json.load(f)

# Paths from configuration
input_folder = config['paths']['epub_dir']
output_folder = config['paths']['xhtml_dir']


def clean_html(html):
    """Remove HTML comments and script tags from the content."""
    soup = BeautifulSoup(html, 'html.parser')

    # Remove comments
    for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
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

    if not os.path.exists(css_folder):
        os.makedirs(css_folder)
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    # Convert RTF to HTML using pypandoc
    html_content = pypandoc.convert_file(rtf_path, 'html')

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Update image paths and extract embedded images
    for img in soup.find_all('img'):
        img_src = img['src']
        if img_src.startswith('data:'):
            # Handle embedded base64 images
            img_data = img_src.split(',', 1)[1]
            img_extension = img_src.split(';')[0].split('/')[1]
            img_name = f"{file_name}_{len(os.listdir(image_folder))}.{img_extension}"
            img_path = os.path.join(image_folder, img_name)
            with open(img_path, 'wb') as img_file:
                img_file.write(base64.b64decode(img_data))
            img['src'] = os.path.join(f"{file_name}-web-resources/image", img_name)

    # Extract and save inline styles to external CSS files
    for style in soup.find_all('style'):
        css_content = style.string
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


def convert_all_rtfs_in_folder(input_folder, output_folder):
    """Convert all RTF files in the input folder to XHTML."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for file_name in os.listdir(input_folder):
        if file_name.endswith('.rtf'):
            rtf_path = os.path.join(input_folder, file_name)
            convert_rtf_to_xhtml(rtf_path, output_folder)
            print(f"Converted: {file_name}")


# Convert all RTFs in the configured folder
convert_all_rtfs_in_folder(input_folder, output_folder)
