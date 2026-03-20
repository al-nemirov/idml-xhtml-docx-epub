"""
Image Processor (Extract / Insert)

Processes XHTML files to handle images using a two-phase anchor approach
based on the Book Studio {{img_N}} technology:

  Phase 1 — EXTRACT:
    - Finds all <img> tags in XHTML content
    - Saves image metadata to image_map.json (src, alt, context, approved)
    - Replaces <img> tags with {{img_N}} anchors in the XHTML
    - Copies image files to a staging directory for optional processing

  Phase 2 — INSERT:
    - Reads the image map (possibly edited by the user)
    - Filters only approved images (approved=true by default)
    - Replaces {{img_N}} anchors with <img> tags using updated paths
    - Supports path remapping for processed/optimized images

Usage:
    python process_images.py extract   # Phase 1: extract images to map
    python process_images.py insert    # Phase 2: insert images back
    python process_images.py auto      # Both phases (no manual review)

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import re
import sys
import shutil
import time

# Add parent to path for utils import
sys.path.insert(0, os.path.dirname(__file__))
from utils.file_utils import load_json, save_json, backup_file


def load_config():
    """Load configuration from config.json in the project root."""
    import json
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


def _get_context(content, position, chars=150):
    """Extract surrounding text context around a position."""
    clean = re.sub(r'<[^>]+>', ' ', content)
    clean = re.sub(r'\s+', ' ', clean).strip()
    start = max(0, position - chars)
    end = min(len(clean), position + chars)
    return clean[start:end].strip()


# ═══════════════════════════════════════════════════════════════════════
# PHASE 1: EXTRACT IMAGES
# ═══════════════════════════════════════════════════════════════════════

def extract_images_from_content(content, filename):
    """Extract images from XHTML content.

    Finds all <img> tags, saves metadata, replaces with {{img_N}} anchors.

    Returns:
        tuple: (modified_content, list_of_image_entries)
    """
    images = []
    counter = [0]  # Mutable counter for closure

    img_pattern = re.compile(
        r'<img\s+([^>]*?)(?:/\s*>|>)',
        re.DOTALL
    )

    def replace_img(match):
        counter[0] += 1
        img_id = counter[0]
        attrs_str = match.group(1)

        # Parse src attribute
        src_match = re.search(r'src=["\']([^"\']+)["\']', attrs_str)
        src = src_match.group(1) if src_match else ''

        # Parse alt attribute
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', attrs_str)
        alt = alt_match.group(1) if alt_match else ''

        # Parse other attributes (width, height, class, etc.)
        width_match = re.search(r'width=["\']([^"\']+)["\']', attrs_str)
        height_match = re.search(r'height=["\']([^"\']+)["\']', attrs_str)
        class_match = re.search(r'class=["\']([^"\']+)["\']', attrs_str)

        anchor = f'{{{{img_{img_id}}}}}'
        context = _get_context(content, match.start())

        images.append({
            'id': img_id,
            'anchor': anchor,
            'src': src,
            'alt': alt,
            'width': width_match.group(1) if width_match else '',
            'height': height_match.group(1) if height_match else '',
            'class': class_match.group(1) if class_match else '',
            'source_file': filename,
            'context': context,
            'approved': True,
            'new_src': '',  # User can set a new path for processed images
        })

        return anchor

    content = img_pattern.sub(replace_img, content)
    return content, images


def extract_phase(config):
    """Phase 1: Extract images from all XHTML files into image_map.json."""
    start_time = time.time()

    input_dir = config['paths']['xhtml_dir']
    temp_dir = config['paths']['temp_dir']

    os.makedirs(temp_dir, exist_ok=True)

    if not os.path.exists(input_dir):
        print(f'Error: input directory not found: {input_dir}')
        return False

    all_images = []
    stats = {'images': 0, 'files': 0}

    xhtml_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.xhtml')])
    if not xhtml_files:
        print(f'No .xhtml files found in {input_dir}')
        return False

    print(f'{"=" * 60}')
    print(f'  IMAGE EXTRACTION')
    print(f'  Files: {len(xhtml_files)} | Source: {input_dir}')
    print(f'{"=" * 60}\n')

    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)

        # Backup XHTML before modification
        backup_file(input_path, backup_dir=os.path.join(temp_dir, 'backups'))

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        modified_content, file_images = extract_images_from_content(content, filename)

        if file_images:
            all_images.extend(file_images)
            stats['images'] += len(file_images)
            stats['files'] += 1
            print(f'  {filename}: {len(file_images)} images')

            # Save modified XHTML with anchors
            with open(input_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
        else:
            print(f'  {filename}: no images')

    # Build the image map
    map_data = {
        'version': '1.0',
        'description': 'Extracted images. Edit "approved", "alt", "new_src" fields as needed.',
        'stats': {
            'total_images': stats['images'],
            'files_processed': stats['files'],
        },
        'images': all_images,
    }

    map_path = os.path.join(temp_dir, 'image_map.json')
    save_json(map_path, map_data)

    duration = time.time() - start_time

    print(f'\n{"=" * 60}')
    print(f'  EXTRACTION RESULTS')
    print(f'{"=" * 60}')
    print(f'  Images found: {stats["images"]}')
    print(f'  Files processed: {stats["files"]}')
    print(f'  Map saved: {map_path}')
    print(f'  Backups: {os.path.join(temp_dir, "backups")}')
    print(f'  Duration: {duration:.1f}s')
    print(f'\n  You can now review/edit {map_path}')
    print(f'  Set "approved": false to skip specific images.')
    print(f'  Set "new_src" to remap image paths.')
    print(f'  Then run: python process_images.py insert')

    return True


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2: INSERT IMAGES
# ═══════════════════════════════════════════════════════════════════════

def insert_images_into_content(content, images, filename):
    """Insert images back into XHTML content from the map.

    Replaces {{img_N}} anchors with <img> tags using original or updated paths.

    Returns:
        tuple: (modified_content, stats_dict)
    """
    stats = {'replaced': 0, 'skipped': 0, 'not_found': 0}

    img_by_id = {}
    for img in images:
        img_id = img.get('id')
        if img_id is not None:
            img_by_id[img_id] = img

    anchor_pattern = re.compile(r'\{\{img_(\d+)\}\}')

    def replace_anchor(match):
        img_id = int(match.group(1))

        if img_id not in img_by_id:
            stats['not_found'] += 1
            return match.group(0)

        img = img_by_id[img_id]
        if not img.get('approved', True):
            stats['skipped'] += 1
            return ''  # Remove anchor for rejected images

        # Use new_src if provided, otherwise original src
        src = img.get('new_src', '').strip() or img.get('src', '')
        alt = img.get('alt', '')
        width = img.get('width', '')
        height = img.get('height', '')
        css_class = img.get('class', '')

        # Build <img> tag
        attrs = [f'src="{src}"']
        if alt:
            attrs.append(f'alt="{alt}"')
        if width:
            attrs.append(f'width="{width}"')
        if height:
            attrs.append(f'height="{height}"')
        if css_class:
            attrs.append(f'class="{css_class}"')

        stats['replaced'] += 1
        return f'<img {" ".join(attrs)} />'

    content = anchor_pattern.sub(replace_anchor, content)
    return content, stats


def insert_phase(config):
    """Phase 2: Insert images from image_map.json back into XHTML files."""
    start_time = time.time()

    input_dir = config['paths']['xhtml_dir']
    temp_dir = config['paths']['temp_dir']

    map_path = os.path.join(temp_dir, 'image_map.json')
    map_data = load_json(map_path)
    if map_data is None:
        print(f'Error: image_map.json not found at {map_path}')
        print('Run the extract phase first: python process_images.py extract')
        return False

    all_images = map_data.get('images', [])
    approved = [img for img in all_images if img.get('approved', True)]
    rejected = len(all_images) - len(approved)

    if not approved:
        print('No approved images to insert.')
        return True

    print(f'{"=" * 60}')
    print(f'  IMAGE INSERTION')
    print(f'  Images: {len(approved)} approved'
          + (f', {rejected} rejected' if rejected else ''))
    print(f'{"=" * 60}\n')

    total_stats = {'replaced': 0, 'skipped': 0, 'not_found': 0}

    xhtml_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.xhtml')])
    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Get images for this file
        file_images = [img for img in approved if img.get('source_file') == filename]
        if not file_images:
            file_images = approved

        modified_content, file_stats = insert_images_into_content(
            content, file_images, filename
        )

        for key in total_stats:
            total_stats[key] += file_stats[key]

        if file_stats['replaced']:
            print(f'  {filename}: {file_stats["replaced"]} inserted')

        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

    duration = time.time() - start_time

    print(f'\n{"=" * 60}')
    print(f'  INSERTION RESULTS')
    print(f'{"=" * 60}')
    print(f'  Inserted: {total_stats["replaced"]}')
    if total_stats['skipped']:
        print(f'  Skipped (rejected): {total_stats["skipped"]}')
    if total_stats['not_found']:
        print(f'  Not found: {total_stats["not_found"]}')
    print(f'  Duration: {duration:.1f}s')

    return True


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    """Main entry point with extract/insert/auto modes."""
    config = load_config()

    if len(sys.argv) < 2:
        print('Image Processor — Extract/Insert Tool')
        print()
        print('Usage: python process_images.py <command>')
        print()
        print('Commands:')
        print('  extract   Extract images from XHTML into image_map.json')
        print('            Replaces <img> tags with {{img_N}} anchors')
        print()
        print('  insert    Insert images from image_map.json back into XHTML')
        print('            Supports path remapping via "new_src" field')
        print()
        print('  auto      Run both phases automatically (no manual review)')
        print()
        print('Workflow:')
        print('  1. python process_images.py extract')
        print('  2. Review/edit data/temp/image_map.json')
        print('     - Set "approved": false to remove specific images')
        print('     - Edit "alt" fields to add/fix alt text')
        print('     - Set "new_src" to use processed/optimized versions')
        print('  3. python process_images.py insert')
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'extract':
        success = extract_phase(config)
    elif command == 'insert':
        success = insert_phase(config)
    elif command == 'auto':
        print('=== Phase 1: Extract ===\n')
        success = extract_phase(config)
        if success:
            print('\n=== Phase 2: Insert ===\n')
            success = insert_phase(config)
    else:
        print(f'Unknown command: {command}')
        print('Use: extract, insert, or auto')
        sys.exit(1)

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
