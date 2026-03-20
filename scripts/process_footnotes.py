"""
Footnote Processor

Processes XHTML files to convert InDesign-style footnotes into standard
endnote format. Rewrites footnote references and footnote body elements,
fixes cross-file footnote links, and copies associated image resources.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import re
import json
import shutil

# Load configuration
with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), 'r', encoding='utf-8') as f:
    config = json.load(f)

# Paths from configuration
input_dir = config['paths']['xhtml_dir']
output_dir = config['paths']['output_dir']
resource_dir = config['paths']['xhtml_dir']

# Create the output directory if it does not exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)


def process_footnotes(content):
    """Convert InDesign footnote markup to standard endnote format."""
    # Process footnote bodies: convert to endnote format
    content = re.sub(
        r'<div id="footnote-(\d+)" class="_idFootnote">\s*<p[^>]*>(.*?)</p>\s*</div>',
        lambda m: f'<div id="fn:{m.group(1)}" class="footnote">\n<p>{m.group(2)}</p>\n</div>',
        content,
        flags=re.DOTALL,
    )

    # Process footnote references: convert to endnote reference links
    content = re.sub(
        r'<span[^>]*><a[^>]*href="[^>]*#footnote-(\d+)">(\d+)</a></span>',
        lambda m: f'<a href="#fn:{m.group(1)}" class="footnote-ref">{m.group(2)}</a>',
        content,
    )

    # Remove unnecessary URL parts (not affecting images)
    content = re.sub(r'file:///.+?#fn:', '#fn:', content)

    return content


def process_file(input_path, output_path):
    """Process a single XHTML file: convert footnotes and write to output."""
    with open(input_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Process footnotes
    content = process_footnotes(content)

    # Write the processed file to the output directory
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(content)

    print(f'Processed {input_path} -> {output_path}')


# Process all XHTML files in the input directory
for filename in os.listdir(input_dir):
    if filename.endswith('.xhtml'):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        # Process the file
        process_file(input_path, output_path)

        # Copy the associated image resource directory
        image_dir = os.path.join(input_dir, filename.replace('.xhtml', '-web-resources'))
        new_image_dir = os.path.join(output_dir, filename.replace('.xhtml', '-web-resources'))

        if os.path.exists(image_dir):
            if not os.path.exists(new_image_dir):
                os.makedirs(new_image_dir)
            for image_file in os.listdir(image_dir):
                if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')):
                    image_path = os.path.join(image_dir, image_file)
                    new_image_path = os.path.join(new_image_dir, image_file)
                    shutil.copy2(image_path, new_image_path)

print('Footnote processing completed!')
