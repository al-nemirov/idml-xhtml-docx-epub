"""
XHTML to DOCX Converter

Converts XHTML files exported from InDesign into DOCX format using Pandoc.
Performs cleanup of InDesign-specific tags, maps CSS classes to semantic HTML
heading elements, processes footnotes, and fixes image paths before conversion.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import re
import json
import subprocess
import tempfile
import sys


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


def clean_tags(content):
    """Remove unnecessary InDesign-generated CharOverride tags and empty paragraphs."""
    content = re.sub(
        r'<p class="CharOverride-\d+"[^>]*>(<span[^>]*>)?(.*?)(</span>)?</p>',
        r'\2', content, flags=re.DOTALL
    )
    content = re.sub(
        r'<span class="CharOverride-\d+"[^>]*>(.*?)</span>',
        r'\1', content, flags=re.DOTALL
    )
    content = re.sub(r'<p>\s*</p>', '', content)
    return content


def replace_tags(content):
    """Map InDesign CSS paragraph style classes to semantic HTML heading elements.

    Note: The Russian keys below are InDesign paragraph style names from the
    source documents. They must match the actual style names used in InDesign.
    Mapping: Part, Chapter, Heading 2-6, Subheading, Subtitle, Blockquote,
    Footnote, Footnote-ref, Footnote-back.
    """
    # Russian style names — these match InDesign paragraph styles and MUST stay as-is
    replacements = {
        "Часть": "h2",            # Part
        "Глава": "h3",            # Chapter
        "Заголовок 2": "h2",      # Heading 2
        "Подглавка": "h2",        # Subheading
        "Подзаголовок": "h2",     # Subtitle
        "Заголовок 3": "h3",      # Heading 3
        "Заголовок 4": "h4",      # Heading 4
        "Заголовок 5": "h5",      # Heading 5
        "Заголовок 6": "h6",      # Heading 6
        "Цитата": "blockquote",   # Blockquote
        "footnote-text": "footnote",
        "Сноска": "footnote-ref",  # Footnote reference
        "АСноска": "footnote-back" # Footnote back-link
    }

    for style, tag in replacements.items():
        pattern = re.compile(
            r'<p class="{}"[^>]*>(.*?)</p>'.format(re.escape(style)),
            re.DOTALL
        )
        content = pattern.sub(r'<{tag}>\1</{tag}>'.format(tag=tag), content)

    return content


def merge_headings(content):
    """Merge consecutive headings of the same level into a single heading."""
    for heading_level in range(2, 7):
        pattern = re.compile(
            rf'(<h{heading_level}[^>]*>.*?</h{heading_level}>)\s*'
            rf'(<h{heading_level}[^>]*>.*?</h{heading_level}>)',
            re.DOTALL
        )
        while pattern.search(content):
            content = pattern.sub(
                lambda m: m.group(1).replace(f'</h{heading_level}>', ' ')
                + m.group(2).replace(f'<h{heading_level}>', ''),
                content
            )
    return content


def process_footnotes(content):
    """Process InDesign footnotes: reformat references and footnote blocks."""
    # Replace footnote references while preserving backlinks
    content = re.sub(
        r'<a[^>]*href="([^"]*\.html)#footnote-(\d+)-backlink">(\d+)</a>',
        lambda m: (
            f'<a href="{m.group(1).replace(".html", ".docx")}'
            f'#footnote-{m.group(2)}-backlink">[{m.group(3)}]</a>'
        ),
        content
    )

    # Handle footnotes inside span elements
    content = re.sub(
        r'<span[^>]*><span id="footnote-(\d+)-backlink">'
        r'<a[^>]*href="#fn:(\d+)"[^>]*>(\d+)</a></span></span>',
        lambda m: (
            f'<span><span id="footnote-{m.group(1)}-backlink">'
            f'<a href="#fn:{m.group(2)}">[{m.group(3)}]</a></span></span>'
        ),
        content
    )

    # Replace footnote blocks while preserving backlinks
    content = re.sub(
        r'<div id="footnote-(\d+)" class="_idFootnote">\s*<p[^>]*>(.*?)</p>\s*</div>',
        lambda m: (
            f'<div id="footnote-{m.group(1)}" class="_idFootnote">'
            f'<p>[{m.group(1)}] {m.group(2)}</p></div>'
        ),
        content,
        flags=re.DOTALL
    )

    if '<ol class="footnotes-list">' not in content:
        content += '<ol class="footnotes-list">{footnotes}</ol>'

    return content


def fix_image_path(match, filename, resource_dir):
    """Fix image paths to point to the correct resource directory."""
    old_path = match.group(1)
    new_path = os.path.join(
        resource_dir,
        f"{filename}-web-resources",
        'image',
        os.path.basename(old_path)
    )
    new_path = new_path.replace(' ', '_')
    return f'src="{new_path}"'


def replace_html_links(content):
    """Replace all .html link references with .docx extensions."""
    content = re.sub(
        r'href="([^"]*\.html)"',
        lambda m: f'href="{m.group(1).replace(".html", ".docx")}"',
        content
    )
    return content


def process_file(input_path, output_path, resource_dir, reference_doc, lua_filter):
    """Process a single XHTML file: clean, transform, and convert to DOCX via Pandoc."""
    with open(input_path, 'r', encoding='utf-8') as file:
        content = file.read()

    filename = os.path.splitext(os.path.basename(input_path))[0]

    # Pipeline: clean -> replace styles -> merge headings -> footnotes -> fix links
    content = clean_tags(content)
    content = replace_tags(content)
    content = merge_headings(content)
    content = process_footnotes(content)
    content = replace_html_links(content)

    # Fix image paths
    content = re.sub(
        r'src="(.*?)"',
        lambda m: fix_image_path(m, filename, resource_dir),
        content
    )

    # Collect and insert footnotes
    footnotes = re.findall(
        r'<li id="fn:(\d+)">(.*?)<a href="#fnref:\1" class="footnote-back">↩</a></li>',
        content, re.DOTALL
    )
    footnotes_content = "\n".join([
        f'<li id="fn:{num}">{text} <a href="#fnref:{num}" class="footnote-back">↩</a></li>'
        for num, text in footnotes
    ])
    content = content.replace('{footnotes}', footnotes_content)

    # Write to a temporary file and convert via Pandoc
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.html', encoding='utf-8', delete=False
    ) as tmp:
        tmp.write(content)
        temp_path = tmp.name

    try:
        command = [
            'pandoc', temp_path, '-o', output_path,
            '--lua-filter=' + lua_filter,
            '--reference-doc', reference_doc,
            '--resource-path', resource_dir
        ]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  Pandoc error for {os.path.basename(input_path)}:')
            if result.stderr:
                print(f'  {result.stderr.strip()}')
            return False

        print(f'  Converted: {os.path.basename(input_path)} -> {os.path.basename(output_path)}')
        return True

    finally:
        # Always clean up the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    """Main entry point: process all XHTML files in the configured directory."""
    config = load_config()

    input_dir = config['paths']['xhtml_dir']
    output_dir = config['paths']['docx_dir']
    resource_dir = config['paths']['xhtml_dir']
    reference_doc = config['reference_doc']
    lua_filter = config['lua_filter']

    if not os.path.exists(input_dir):
        print(f'Error: input directory not found: {input_dir}')
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    xhtml_files = [f for f in os.listdir(input_dir) if f.endswith('.xhtml')]
    if not xhtml_files:
        print(f'No .xhtml files found in {input_dir}')
        return

    print(f'Processing {len(xhtml_files)} XHTML file(s)...')

    success = 0
    errors = 0

    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)
        output_filename = os.path.splitext(filename)[0] + '.docx'
        output_path = os.path.join(output_dir, output_filename)

        if process_file(input_path, output_path, resource_dir, reference_doc, lua_filter):
            success += 1
        else:
            errors += 1

    print(f'\nConversion completed: {success} successful, {errors} errors')


if __name__ == '__main__':
    main()
