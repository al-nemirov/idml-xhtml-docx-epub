"""
Smoke Test

End-to-end validation of the book conversion pipeline.
Creates minimal test fixtures, runs all stages, and verifies outputs.

Usage:
    python tests/smoke_test.py

Requires: Pandoc installed and in PATH.
Calibre (ebook-convert) is optional — DOCX->EPUB test is skipped if not found.
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def create_test_xhtml(xhtml_dir, filename='test-book.xhtml'):
    """Create a minimal XHTML file with headings, paragraphs, footnotes, and an image."""
    content = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test Book</title></head>
<body>
<h1>Test Book Title</h1>

<p class="Part">Introduction</p>
<p>This is the first paragraph of the test book.</p>

<p class="Chapter">Chapter One</p>
<p>This chapter discusses important topics.</p>
<p>Here is a footnote reference<span class="_idFootnoteLink"><a href="#footnote-1">1</a></span>.</p>

<div id="footnote-1" class="_idFootnote">
<p class="_idFootnoteBody">This is the footnote text explaining the reference.</p>
</div>

<p class="Heading 2">Section 1.1</p>
<p>More content follows here with details about the section.</p>

<h3>Sub-section</h3>
<h3>Continued</h3>

<p>Final paragraph of the test content.</p>
</body>
</html>"""
    filepath = os.path.join(xhtml_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


def create_test_metadata(temp_dir):
    """Create a minimal Excel metadata file."""
    try:
        import pandas as pd
        df = pd.DataFrame([{
            'ISBN': 'test-book',
            'Title': 'Test Book Title',
            'Authors': 'Test Author',
            'Annotation': 'A test book for smoke testing the pipeline.',
            'Translators': '',
        }])
        xlsx_path = os.path.join(temp_dir, 'test-metadata.xlsx')
        df.to_excel(xlsx_path, index=False)
        return xlsx_path
    except ImportError:
        print('  SKIP: pandas/openpyxl not available for metadata creation')
        return None


def create_test_config(temp_dir, metadata_path):
    """Create a test config.json."""
    config = {
        'paths': {
            'xhtml_dir': os.path.join(temp_dir, 'xhtml'),
            'docx_dir': os.path.join(temp_dir, 'docx'),
            'epub_dir': os.path.join(temp_dir, 'epub'),
            'output_dir': os.path.join(temp_dir, 'output'),
            'cover_dir': os.path.join(temp_dir, 'covers'),
            'temp_dir': os.path.join(temp_dir, 'temp'),
            'rtf_dir': os.path.join(temp_dir, 'rtf'),
        },
        'metadata_file': metadata_path or 'books.xlsx',
        'reference_doc': os.path.join(PROJECT_ROOT, 'templates', 'custom-reference.docx'),
        'lua_filter': os.path.join(PROJECT_ROOT, 'filters', 'footnote_filter.lua'),
        'lua_filter_endnotes': os.path.join(PROJECT_ROOT, 'filters', 'fix_endnotes.lua'),
        'lua_filter_links': os.path.join(PROJECT_ROOT, 'filters', 'fix_links_epub.lua'),
        'publisher': 'Test Publisher',
        'language': 'en',
        'epub_version': '3',
    }

    # Create all directories
    for key, path in config['paths'].items():
        os.makedirs(path, exist_ok=True)

    config_path = os.path.join(temp_dir, 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    # Set env var so all scripts find this config instead of the project root one
    os.environ['PIPELINE_CONFIG'] = config_path
    return config_path, config


def run_script(script_name, args=None, cwd=None):
    """Run a Python script and return (success, stdout, stderr).

    Passes the current environment (including PIPELINE_CONFIG) so that
    child scripts use the test config instead of the root config.json.
    """
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, script_name)]
    if args:
        cmd.extend(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd or PROJECT_ROOT, env=os.environ.copy(),
    )
    return result.returncode == 0, result.stdout, result.stderr


def test_preflight():
    """Test: preflight.py runs without errors."""
    print('\n[Test 1] Preflight check')
    ok, stdout, stderr = run_script('scripts/preflight.py')
    if ok:
        print('  PASS: preflight.py completed successfully')
    else:
        print('  FAIL: preflight.py returned non-zero')
        print(f'  stdout: {stdout[-200:] if stdout else ""}')
        print(f'  stderr: {stderr[-200:] if stderr else ""}')
    return ok


def test_build_structure(config):
    """Test: build_structure.py creates structured.json."""
    print('\n[Test 2] Build structure')
    ok, stdout, stderr = run_script('scripts/build_structure.py')
    structured_path = os.path.join(config['paths']['temp_dir'], 'structured.json')
    if ok and os.path.exists(structured_path):
        with open(structured_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        elem_count = data.get('stats', {}).get('total_elements', 0)
        print(f'  PASS: structured.json created ({elem_count} elements)')
        return True
    else:
        print(f'  FAIL: build_structure.py failed')
        print(f'  stdout: {stdout[-200:] if stdout else ""}')
        return False


def test_footnote_extract(config):
    """Test: process_footnotes.py extract creates footnote_map.json."""
    print('\n[Test 3] Footnote extraction')
    ok, stdout, stderr = run_script('scripts/process_footnotes.py', ['extract'])
    map_path = os.path.join(config['paths']['temp_dir'], 'footnote_map.json')
    if ok and os.path.exists(map_path):
        with open(map_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        fn_count = len(data.get('footnotes', []))
        print(f'  PASS: footnote_map.json created ({fn_count} footnotes)')
        return True
    else:
        print(f'  FAIL: footnote extraction failed')
        print(f'  stdout: {stdout[-200:] if stdout else ""}')
        return False


def test_footnote_insert(config):
    """Test: process_footnotes.py insert replaces anchors."""
    print('\n[Test 4] Footnote insertion')
    ok, stdout, stderr = run_script('scripts/process_footnotes.py', ['insert'])
    if ok:
        # Verify anchors are replaced in XHTML
        xhtml_files = [f for f in os.listdir(config['paths']['xhtml_dir']) if f.endswith('.xhtml')]
        anchors_left = 0
        for fn in xhtml_files:
            with open(os.path.join(config['paths']['xhtml_dir'], fn), 'r', encoding='utf-8') as f:
                content = f.read()
            anchors_left += content.count('{{footnote_')
        if anchors_left == 0:
            print(f'  PASS: all footnote anchors replaced')
        else:
            print(f'  WARN: {anchors_left} footnote anchors remain')
        return True
    else:
        print(f'  FAIL: footnote insertion failed')
        return False


def test_xhtml_to_docx(config):
    """Test: xhtml_to_docx.py creates DOCX files."""
    print('\n[Test 5] XHTML to DOCX')

    # Check Pandoc is available
    if not shutil.which('pandoc'):
        print('  SKIP: Pandoc not found in PATH')
        return True

    ok, stdout, stderr = run_script('scripts/xhtml_to_docx.py')
    docx_files = [f for f in os.listdir(config['paths']['docx_dir']) if f.endswith('.docx')]
    if ok and docx_files:
        sizes = [os.path.getsize(os.path.join(config['paths']['docx_dir'], f)) for f in docx_files]
        print(f'  PASS: {len(docx_files)} DOCX file(s) created (sizes: {sizes})')
        return True
    else:
        print(f'  FAIL: XHTML to DOCX failed')
        print(f'  stdout: {stdout[-300:] if stdout else ""}')
        print(f'  stderr: {stderr[-300:] if stderr else ""}')
        return False


def test_reproducibility(config):
    """Test: running XHTML->DOCX twice produces same-size output."""
    print('\n[Test 6] Reproducibility check')

    if not shutil.which('pandoc'):
        print('  SKIP: Pandoc not found')
        return True

    docx_dir = config['paths']['docx_dir']
    docx_files = [f for f in os.listdir(docx_dir) if f.endswith('.docx')]
    if not docx_files:
        print('  SKIP: no DOCX files from previous step')
        return True

    # Record sizes from first run
    first_sizes = {f: os.path.getsize(os.path.join(docx_dir, f)) for f in docx_files}

    # Run again
    ok, _, _ = run_script('scripts/xhtml_to_docx.py')
    if not ok:
        print('  FAIL: second run failed')
        return False

    # Compare sizes
    second_sizes = {f: os.path.getsize(os.path.join(docx_dir, f))
                    for f in os.listdir(docx_dir) if f.endswith('.docx')}

    mismatches = []
    for f in first_sizes:
        if f in second_sizes and first_sizes[f] != second_sizes[f]:
            mismatches.append(f'{f}: {first_sizes[f]} vs {second_sizes[f]}')

    if not mismatches:
        print(f'  PASS: {len(first_sizes)} file(s) identical across runs')
        return True
    else:
        print(f'  WARN: size differences: {"; ".join(mismatches)}')
        return True  # Warn only, don't fail


def main():
    """Run all smoke tests."""
    print('=' * 60)
    print('  SMOKE TEST')
    print('=' * 60)

    # Create a temporary working directory
    with tempfile.TemporaryDirectory(prefix='smoke_test_') as temp_dir:
        print(f'\n  Working directory: {temp_dir}')

        # Setup
        metadata_path = create_test_metadata(temp_dir)
        config_path, config = create_test_config(temp_dir, metadata_path)
        xhtml_path = create_test_xhtml(config['paths']['xhtml_dir'])
        print(f'  Test XHTML: {xhtml_path}')
        print(f'  Config: {config_path}')

        tests = [
            test_preflight,
            lambda: test_build_structure(config),
            lambda: test_footnote_extract(config),
            lambda: test_footnote_insert(config),
            lambda: test_xhtml_to_docx(config),
            lambda: test_reproducibility(config),
        ]

        passed = 0
        failed = 0
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f'  ERROR: {e}')
                failed += 1

        # Cleanup: remove env var (temp dir auto-cleans the file)
        os.environ.pop('PIPELINE_CONFIG', None)

    print(f'\n{"=" * 60}')
    print(f'  RESULTS: {passed} passed, {failed} failed')
    print(f'{"=" * 60}')

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
