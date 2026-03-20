"""
Footnote Processor (Extract / Insert)

Processes XHTML files to handle InDesign-style footnotes using a two-phase
approach based on the Book Studio extraction/injection technology:

  Phase 1 — EXTRACT:
    - Finds all InDesign footnote bodies (div.id="footnote-N") and references
    - Extracts each footnote with metadata: id, word, text, paragraph context
    - Saves to footnote_map.json (editable by user)
    - Replaces footnote bodies with {{footnote_N}} anchors in the XHTML
    - Rewrites reference spans to {{footnote_ref_N}} for tracking

  Phase 2 — INSERT:
    - Reads the footnote map (possibly edited by the user)
    - Filters only approved footnotes (approved=true by default)
    - Matches footnotes by anchor or by word search (fuzzy fallback)
    - Inserts footnotes back as properly formatted endnotes
    - Rewrites cross-file footnote links to standard #fn:N format

Usage:
    python process_footnotes.py extract   # Phase 1: extract footnotes
    python process_footnotes.py insert    # Phase 2: insert footnotes back
    python process_footnotes.py auto      # Both phases (no manual review)

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import re
import json
import sys
import shutil
import time


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


def _extract_sentence(text, word):
    """Extract the sentence containing the given word from text."""
    if not word or not text:
        return text[:200] if text else ""

    sentences = re.split(r'(?<=[.!?])\s+', text)
    word_lower = word.lower()

    for sent in sentences:
        if word_lower in sent.lower():
            return sent.strip()

    return sentences[0].strip() if sentences else text[:200]


def _find_word_in_content(content, word):
    """Check if a word/phrase exists in the XHTML content (case-insensitive)."""
    if not word:
        return False
    return word.lower() in content.lower()


def _get_paragraph_context(content, position, context_chars=200):
    """Extract surrounding text context around a position in content."""
    # Remove HTML tags for clean context
    clean = re.sub(r'<[^>]+>', ' ', content)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Find approximate position in cleaned text
    start = max(0, position - context_chars)
    end = min(len(clean), position + context_chars)
    return clean[start:end].strip()


# ═══════════════════════════════════════════════════════════════════════
# PHASE 1: EXTRACT FOOTNOTES
# ═══════════════════════════════════════════════════════════════════════

def extract_footnotes_from_content(content, filename):
    """Extract InDesign footnotes from XHTML content.

    Finds footnote bodies (div.id="footnote-N") and their reference spans,
    extracts text, context, and metadata into a structured map.
    Replaces footnote bodies with {{footnote_N}} anchors.

    Returns:
        tuple: (modified_content, list_of_footnote_entries)
    """
    footnotes = []

    # --- Extract footnote BODIES ---
    footnote_body_pattern = re.compile(
        r'<div id="footnote-(\d+)" class="_idFootnote">\s*<p[^>]*>(.*?)</p>\s*</div>',
        re.DOTALL
    )

    def replace_body(match):
        fn_id = match.group(1)
        fn_text = match.group(2).strip()
        # Clean HTML tags from footnote text
        fn_text_clean = re.sub(r'<[^>]+>', '', fn_text).strip()
        anchor = f'{{{{footnote_{fn_id}}}}}'

        # Get surrounding context
        context = _get_paragraph_context(content, match.start())

        footnotes.append({
            'id': int(fn_id),
            'anchor': anchor,
            'text': fn_text,
            'text_clean': fn_text_clean,
            'source_file': filename,
            'type': 'body',
            'context': context,
            'approved': True,  # Approved by default (user can change)
        })

        return anchor

    content = footnote_body_pattern.sub(replace_body, content)

    # --- Extract footnote REFERENCES (for cross-referencing) ---
    ref_pattern = re.compile(
        r'<span[^>]*><a[^>]*href="([^"]*?)#footnote-(\d+)"[^>]*>(\d+)</a></span>'
    )

    for match in ref_pattern.finditer(content):
        target_file = match.group(1)
        fn_id = match.group(2)
        ref_text = match.group(3)

        # Get the word/phrase near the reference for matching
        # Look backwards from the match position for the nearest text
        pre_text = content[:match.start()]
        pre_clean = re.sub(r'<[^>]+>', '', pre_text)
        # Take last few words before the reference number
        words_before = pre_clean.strip().split()[-5:] if pre_clean.strip() else []
        word_context = ' '.join(words_before)

        footnotes.append({
            'id': int(fn_id),
            'anchor': f'{{{{footnote_ref_{fn_id}}}}}',
            'text': ref_text,
            'word': word_context,
            'source_file': filename,
            'target_file': target_file,
            'type': 'reference',
            'approved': True,
        })

    return content, footnotes


def extract_phase(config):
    """Phase 1: Extract footnotes from all XHTML files into footnote_map.json."""
    start_time = time.time()

    input_dir = config['paths']['xhtml_dir']
    temp_dir = config['paths']['temp_dir']

    os.makedirs(temp_dir, exist_ok=True)

    if not os.path.exists(input_dir):
        print(f'Error: input directory not found: {input_dir}')
        return False

    all_footnotes = []
    processed_files = []
    stats = {'bodies': 0, 'references': 0, 'files': 0}

    xhtml_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.xhtml')])
    if not xhtml_files:
        print(f'No .xhtml files found in {input_dir}')
        return False

    print(f'{"=" * 60}')
    print(f'  FOOTNOTE EXTRACTION')
    print(f'  Files: {len(xhtml_files)} | Source: {input_dir}')
    print(f'{"=" * 60}\n')

    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        modified_content, file_footnotes = extract_footnotes_from_content(content, filename)

        if file_footnotes:
            all_footnotes.extend(file_footnotes)
            body_count = sum(1 for v in file_footnotes if v['type'] == 'body')
            ref_count = sum(1 for v in file_footnotes if v['type'] == 'reference')
            stats['bodies'] += body_count
            stats['references'] += ref_count
            stats['files'] += 1
            print(f'  {filename}: {body_count} footnotes, {ref_count} references')

            # Save modified XHTML with anchors
            with open(input_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)

            processed_files.append(filename)
        else:
            print(f'  {filename}: no footnotes')

    # Build the footnote map with metadata
    map_data = {
        'version': '2.0',
        'description': 'Extracted InDesign footnotes. Edit "approved" and "text" fields as needed.',
        'stats': {
            'total_bodies': stats['bodies'],
            'total_references': stats['references'],
            'files_processed': stats['files'],
        },
        'processed_files': processed_files,
        'footnotes': all_footnotes,
    }

    # Save the footnote map
    map_path = os.path.join(temp_dir, 'footnote_map.json')
    with open(map_path, 'w', encoding='utf-8') as f:
        json.dump(map_data, f, ensure_ascii=False, indent=2)

    duration = time.time() - start_time

    print(f'\n{"=" * 60}')
    print(f'  EXTRACTION RESULTS')
    print(f'{"=" * 60}')
    print(f'  Footnote bodies: {stats["bodies"]}')
    print(f'  Footnote references: {stats["references"]}')
    print(f'  Files processed: {stats["files"]}')
    print(f'  Map saved: {map_path}')
    print(f'  Duration: {duration:.1f}s')
    print(f'\n  You can now review/edit {map_path}')
    print(f'  Set "approved": false to skip specific footnotes.')
    print(f'  Then run: python process_footnotes.py insert')

    return True


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2: INSERT FOOTNOTES
# ═══════════════════════════════════════════════════════════════════════

def insert_footnotes_into_content(content, footnote_bodies, filename):
    """Insert footnotes back into XHTML content from the map.

    Replaces {{footnote_N}} anchors with properly formatted endnote blocks.
    Rewrites footnote reference spans to use standard #fn:N format.
    Uses fuzzy word matching as fallback when anchors are not found.

    Returns:
        tuple: (modified_content, stats_dict)
    """
    stats = {'replaced': 0, 'skipped': 0, 'fuzzy_matched': 0, 'not_found': 0}

    # --- Build lookup by ID ---
    fn_by_id = {}
    for fn in footnote_bodies:
        fn_id = fn.get('id')
        if fn_id is not None:
            fn_by_id[fn_id] = fn

    # --- Replace {{footnote_N}} anchors ---
    anchor_pattern = re.compile(r'\{\{footnote_(\d+)\}\}')

    def replace_anchor(match):
        fn_id = int(match.group(1))

        if fn_id not in fn_by_id:
            stats['not_found'] += 1
            return match.group(0)  # Keep anchor

        fn = fn_by_id[fn_id]
        if not fn.get('approved', True):
            stats['skipped'] += 1
            return ''  # Remove anchor for rejected footnotes

        fn_text = fn.get('text', '')
        stats['replaced'] += 1

        return (
            f'<div id="fn:{fn_id}" class="footnote">\n'
            f'  <p><a href="#fnref:{fn_id}" class="footnote-back">[{fn_id}]</a> '
            f'{fn_text}</p>\n'
            f'</div>'
        )

    content = anchor_pattern.sub(replace_anchor, content)

    # --- Fuzzy fallback: find unreplaced footnotes by word match ---
    for fn in footnote_bodies:
        fn_id = fn.get('id')
        anchor = f'{{{{footnote_{fn_id}}}}}'

        # Skip if already replaced via anchor
        if anchor not in content:
            continue

        # Skip if the anchor wasn't in the original (shouldn't happen, but safety check)
        if not fn.get('approved', True):
            content = content.replace(anchor, '')
            stats['skipped'] += 1
            continue

        # Try to find by word context
        word = fn.get('word', '')
        if word and _find_word_in_content(content, word):
            fn_text = fn.get('text', '')
            # Insert footnote at the end of the file before </body>
            footnote_html = (
                f'\n<div id="fn:{fn_id}" class="footnote">\n'
                f'  <p><a href="#fnref:{fn_id}" class="footnote-back">[{fn_id}]</a> '
                f'{fn_text}</p>\n'
                f'</div>'
            )
            content = content.replace(anchor, '')
            # Insert before </body> or at the end
            if '</body>' in content:
                content = content.replace('</body>', footnote_html + '\n</body>')
            else:
                content += footnote_html
            stats['fuzzy_matched'] += 1
        else:
            stats['not_found'] += 1

    # --- Rewrite footnote reference links to standard format ---
    content = re.sub(
        r'<span[^>]*><a[^>]*href="[^"]*#footnote-(\d+)"[^>]*>(\d+)</a></span>',
        lambda m: (
            f'<a id="fnref:{m.group(1)}" href="#fn:{m.group(1)}" '
            f'class="footnote-ref"><sup>{m.group(2)}</sup></a>'
        ),
        content
    )

    # Clean up leftover file:// URLs
    content = re.sub(r'file:\/\/\/.+?#fn:', '#fn:', content)

    return content, stats


def insert_phase(config):
    """Phase 2: Insert footnotes from footnote_map.json back into XHTML files."""
    start_time = time.time()

    input_dir = config['paths']['xhtml_dir']
    # Insert back into xhtml_dir (same directory as extract) so Stage 3 can find them
    output_dir = config['paths']['xhtml_dir']
    resource_dir = config['paths']['xhtml_dir']
    temp_dir = config['paths']['temp_dir']

    map_path = os.path.join(temp_dir, 'footnote_map.json')
    if not os.path.exists(map_path):
        print(f'Error: footnote_map.json not found at {map_path}')
        print('Run the extract phase first: python process_footnotes.py extract')
        return False

    # Load the footnote map
    with open(map_path, 'r', encoding='utf-8') as f:
        map_data = json.load(f)

    all_footnotes = map_data.get('footnotes', [])

    # Filter only body-type footnotes (not references)
    footnote_bodies = [fn for fn in all_footnotes if fn.get('type') == 'body']

    # Filter only approved
    approved = [fn for fn in footnote_bodies if fn.get('approved', True)]
    rejected = len(footnote_bodies) - len(approved)

    if not approved:
        print('No approved footnotes to insert.')
        return True

    os.makedirs(output_dir, exist_ok=True)

    print(f'{"=" * 60}')
    print(f'  FOOTNOTE INSERTION')
    print(f'  Footnotes: {len(approved)} approved'
          + (f', {rejected} rejected' if rejected else ''))
    print(f'{"=" * 60}\n')

    total_stats = {'replaced': 0, 'skipped': 0, 'fuzzy_matched': 0, 'not_found': 0}

    xhtml_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.xhtml')])
    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Get footnotes for this file
        file_footnotes = [fn for fn in approved if fn.get('source_file') == filename]
        if not file_footnotes:
            # Also try footnotes without source_file (universal)
            file_footnotes = approved

        modified_content, file_stats = insert_footnotes_into_content(
            content, file_footnotes, filename
        )

        for key in total_stats:
            total_stats[key] += file_stats[key]

        if file_stats['replaced'] or file_stats['fuzzy_matched']:
            print(f'  {filename}: {file_stats["replaced"]} inserted'
                  + (f', {file_stats["fuzzy_matched"]} fuzzy' if file_stats['fuzzy_matched'] else ''))

        # Write the processed file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        # Copy associated image resource directories
        if output_dir != input_dir:
            image_dir = os.path.join(resource_dir, filename.replace('.xhtml', '-web-resources'))
            new_image_dir = os.path.join(output_dir, filename.replace('.xhtml', '-web-resources'))

            if os.path.exists(image_dir):
                if os.path.exists(new_image_dir):
                    shutil.rmtree(new_image_dir)
                shutil.copytree(image_dir, new_image_dir)

    duration = time.time() - start_time

    print(f'\n{"=" * 60}')
    print(f'  INSERTION RESULTS')
    print(f'{"=" * 60}')
    print(f'  Inserted (exact): {total_stats["replaced"]}')
    if total_stats['fuzzy_matched']:
        print(f'  Inserted (fuzzy): {total_stats["fuzzy_matched"]}')
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
        print('Footnote Processor — Extract/Insert Tool')
        print()
        print('Usage: python process_footnotes.py <command>')
        print()
        print('Commands:')
        print('  extract   Extract footnotes from XHTML into footnote_map.json')
        print('            Replaces footnote bodies with {{footnote_N}} anchors')
        print()
        print('  insert    Insert footnotes from footnote_map.json back into XHTML')
        print('            Supports fuzzy word matching as fallback')
        print()
        print('  auto      Run both phases automatically (no manual review)')
        print()
        print('Workflow:')
        print('  1. python process_footnotes.py extract')
        print('  2. Review/edit data/temp/footnote_map.json')
        print('     - Set "approved": false to skip specific footnotes')
        print('     - Edit "text" fields to fix footnote content')
        print('  3. python process_footnotes.py insert')
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
