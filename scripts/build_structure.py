"""
Build Structured JSON

Converts XHTML files into a structured.json intermediate format that serves
as the single source of truth for the book conversion pipeline. This format
captures paragraphs, headings, footnotes, and images in a normalized structure
that can be processed, reviewed, and converted to multiple output formats.

Based on Book Studio's structured.json approach.

Usage:
    python scripts/build_structure.py

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import re
import sys
import time
import logging
from datetime import datetime

# Add parent to path for utils import
sys.path.insert(0, os.path.dirname(__file__))
from utils.file_utils import save_json, load_json, backup_file

logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.json in the project root.

    Honors the PIPELINE_CONFIG environment variable to override the default
    config path (useful for testing without touching the root config.json).
    """
    import json
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


def parse_xhtml_to_elements(content, filename):
    """Parse XHTML content into a list of structured elements.

    Each element has:
    - id: unique integer
    - type: paragraph, heading, image, footnote, blockquote
    - text: cleaned text content
    - html: original HTML content
    - level: heading level (1-6) for headings
    - source_file: origin filename
    - frozen: whether this element should not be modified

    Returns:
        list of element dicts
    """
    elements = []
    elem_id = 0

    # Extract headings (h1-h6)
    heading_pattern = re.compile(
        r'<(h[1-6])(\s[^>]*)?>(.+?)</\1>',
        re.DOTALL
    )
    for match in heading_pattern.finditer(content):
        elem_id += 1
        tag = match.group(1)
        level = int(tag[1])
        html_content = match.group(3).strip()
        text = re.sub(r'<[^>]+>', '', html_content).strip()

        elements.append({
            'id': elem_id,
            'type': 'heading',
            'level': level,
            'text': text,
            'html': match.group(0),
            'source_file': filename,
            'position': match.start(),
            'frozen': False,
        })

    # Extract paragraphs
    para_pattern = re.compile(
        r'<p(\s[^>]*)?>(.+?)</p>',
        re.DOTALL
    )
    for match in para_pattern.finditer(content):
        elem_id += 1
        html_content = match.group(2).strip()
        text = re.sub(r'<[^>]+>', '', html_content).strip()

        if not text:
            continue

        # Determine subtype from class
        attrs = match.group(1) or ''
        css_class = ''
        class_match = re.search(r'class="([^"]*)"', attrs)
        if class_match:
            css_class = class_match.group(1)

        elements.append({
            'id': elem_id,
            'type': 'paragraph',
            'text': text,
            'html': match.group(0),
            'class': css_class,
            'source_file': filename,
            'position': match.start(),
            'frozen': False,
        })

    # Extract images (or {{img_N}} anchors)
    img_pattern = re.compile(r'<img\s+([^>]*?)(?:/\s*>|>)')
    for match in img_pattern.finditer(content):
        elem_id += 1
        attrs_str = match.group(1)
        src_match = re.search(r'src=["\']([^"\']+)["\']', attrs_str)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', attrs_str)

        elements.append({
            'id': elem_id,
            'type': 'image',
            'src': src_match.group(1) if src_match else '',
            'alt': alt_match.group(1) if alt_match else '',
            'html': match.group(0),
            'source_file': filename,
            'position': match.start(),
            'frozen': False,
        })

    # Extract {{img_N}} anchors (if images already extracted)
    anchor_pattern = re.compile(r'\{\{img_(\d+)\}\}')
    for match in anchor_pattern.finditer(content):
        elem_id += 1
        elements.append({
            'id': elem_id,
            'type': 'image_anchor',
            'anchor_id': int(match.group(1)),
            'text': match.group(0),
            'source_file': filename,
            'position': match.start(),
            'frozen': True,
        })

    # Extract {{footnote_N}} anchors (if footnotes already extracted)
    fn_anchor_pattern = re.compile(r'\{\{footnote_(\d+)\}\}')
    for match in fn_anchor_pattern.finditer(content):
        elem_id += 1
        elements.append({
            'id': elem_id,
            'type': 'footnote_anchor',
            'anchor_id': int(match.group(1)),
            'text': match.group(0),
            'source_file': filename,
            'position': match.start(),
            'frozen': True,
        })

    # Sort by position in the document
    elements.sort(key=lambda e: e.get('position', 0))

    # Remove position (internal use only) and re-number
    for idx, elem in enumerate(elements, 1):
        elem.pop('position', None)
        elem['id'] = idx

    return elements


def build_structure(config):
    """Build structured.json from all XHTML files."""
    start_time = time.time()

    input_dir = config['paths']['xhtml_dir']
    temp_dir = config['paths']['temp_dir']
    os.makedirs(temp_dir, exist_ok=True)

    structured_path = os.path.join(temp_dir, 'structured.json')

    # Backup existing structured.json if it exists
    if os.path.exists(structured_path):
        backup_file(structured_path, backup_dir=os.path.join(temp_dir, 'backups'))

    if not os.path.exists(input_dir):
        logger.error('input directory not found: %s', input_dir)
        return False

    xhtml_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.xhtml')])
    if not xhtml_files:
        logger.warning('No .xhtml files found in %s', input_dir)
        return False

    logger.info('%s', '=' * 60)
    logger.info('  BUILDING STRUCTURED JSON')
    logger.info('  Files: %d | Source: %s', len(xhtml_files), input_dir)
    logger.info('%s\n', '=' * 60)

    all_elements = []
    file_stats = {}

    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        elements = parse_xhtml_to_elements(content, filename)
        all_elements.extend(elements)

        # Count by type
        type_counts = {}
        for elem in elements:
            t = elem['type']
            type_counts[t] = type_counts.get(t, 0) + 1

        file_stats[filename] = type_counts
        parts = ', '.join(f'{v} {k}' for k, v in sorted(type_counts.items()))
        logger.info('  %s: %s', filename, parts)

    # Re-number all elements globally
    for idx, elem in enumerate(all_elements, 1):
        elem['id'] = idx

    # Count totals
    total_by_type = {}
    for elem in all_elements:
        t = elem['type']
        total_by_type[t] = total_by_type.get(t, 0) + 1

    structure = {
        'version': '1.0',
        'created': datetime.now().isoformat(),
        'updated': datetime.now().isoformat(),
        'description': 'Structured representation of book content.',
        'stats': {
            'total_elements': len(all_elements),
            'by_type': total_by_type,
            'files': len(xhtml_files),
        },
        'files': list(file_stats.keys()),
        'paragraphs': all_elements,
    }

    # Save with atomic write
    save_json(structured_path, structure)

    duration = time.time() - start_time

    logger.info('')
    logger.info('%s', '=' * 60)
    logger.info('  STRUCTURE BUILT')
    logger.info('%s', '=' * 60)
    logger.info('  Total elements: %d', len(all_elements))
    for t, c in sorted(total_by_type.items()):
        logger.info('    %s: %d', t, c)
    logger.info('  Output: %s', structured_path)
    logger.info('  Duration: %.1fs', duration)

    return True


def main():
    """Main entry point."""
    config = load_config()
    if not build_structure(config):
        sys.exit(1)


if __name__ == '__main__':
    main()
