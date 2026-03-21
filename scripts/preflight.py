"""
Preflight Check

Validates the environment before running the book conversion pipeline.
Checks for required configuration, external tools (Pandoc, Calibre),
Python dependencies, template files, and directory structure.

Usage:
    python scripts/preflight.py

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import sys
import json
import shutil
import importlib


def load_config():
    """Load configuration from config.json in the project root."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(f'  config.json has invalid JSON: {e}')
        return None


def check_config():
    """Check that config.json exists and is valid."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if not os.path.exists(config_path):
        print('  FAIL: config.json not found')
        print('        Run: cp config.example.json config.json')
        return False

    config = load_config()
    if config is None:
        return False

    # Check required keys
    required_keys = ['paths', 'metadata_file', 'reference_doc', 'lua_filter']
    missing = [k for k in required_keys if k not in config]
    if missing:
        print(f'  FAIL: Missing config keys: {", ".join(missing)}')
        return False

    required_paths = ['xhtml_dir', 'docx_dir', 'epub_dir', 'output_dir', 'temp_dir']
    missing_paths = [p for p in required_paths if p not in config.get('paths', {})]
    if missing_paths:
        print(f'  FAIL: Missing path keys: {", ".join(missing_paths)}')
        return False

    print('  OK: config.json is valid')
    return True


def check_external_tools():
    """Check that Pandoc and Calibre are installed and in PATH."""
    ok = True

    pandoc = shutil.which('pandoc')
    if pandoc:
        print(f'  OK: Pandoc found at {pandoc}')
    else:
        print('  FAIL: Pandoc not found in PATH')
        print('        Install from: https://pandoc.org/')
        ok = False

    calibre = shutil.which('ebook-convert')
    if calibre:
        print(f'  OK: Calibre (ebook-convert) found at {calibre}')
    else:
        print('  WARN: Calibre (ebook-convert) not found in PATH')
        print('        Install from: https://calibre-ebook.com/')
        print('        (Only needed for Stage 4: DOCX -> EPUB)')

    return ok


def check_python_deps():
    """Check that all required Python packages are installed."""
    deps = {
        'lxml': 'lxml',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'bs4': 'beautifulsoup4',
        'pypandoc': 'pypandoc',
    }

    ok = True
    for module_name, pip_name in deps.items():
        try:
            importlib.import_module(module_name)
            print(f'  OK: {pip_name}')
        except ImportError:
            print(f'  FAIL: {pip_name} not installed')
            print(f'        Run: pip install {pip_name}')
            ok = False

    return ok


def check_templates():
    """Check that required template files exist."""
    config = load_config()
    if not config:
        print('  SKIP: Cannot check templates without valid config')
        return False

    ok = True
    project_root = os.path.join(os.path.dirname(__file__), '..')

    # Reference document
    ref_doc = os.path.join(project_root, config.get('reference_doc', ''))
    if os.path.exists(ref_doc):
        size_kb = os.path.getsize(ref_doc) / 1024
        print(f'  OK: Reference document ({size_kb:.0f} KB)')
    else:
        print(f'  FAIL: Reference document not found: {config.get("reference_doc")}')
        ok = False

    # Lua filters
    for key in ('lua_filter', 'lua_filter_endnotes', 'lua_filter_links'):
        filter_path = config.get(key, '')
        if filter_path:
            full_path = os.path.join(project_root, filter_path)
            if os.path.exists(full_path):
                print(f'  OK: {key} -> {filter_path}')
            else:
                print(f'  FAIL: {key} not found: {filter_path}')
                ok = False

    return ok


def check_directories():
    """Check/create required working directories."""
    config = load_config()
    if not config:
        print('  SKIP: Cannot check directories without valid config')
        return False

    for key, path in config.get('paths', {}).items():
        if os.path.isabs(path):
            full_path = path
        else:
            full_path = os.path.join(os.path.dirname(__file__), '..', path)

        if os.path.isdir(full_path):
            print(f'  OK: {key} -> {path}')
        else:
            try:
                os.makedirs(full_path, exist_ok=True)
                print(f'  CREATED: {key} -> {path}')
            except OSError as e:
                print(f'  FAIL: Cannot create {key}: {e}')

    return True


def main():
    """Run all preflight checks."""
    print('=' * 60)
    print('  PREFLIGHT CHECK')
    print('=' * 60)

    sections = [
        ('Configuration', check_config),
        ('External Tools', check_external_tools),
        ('Python Dependencies', check_python_deps),
        ('Template Files', check_templates),
        ('Working Directories', check_directories),
    ]

    all_ok = True
    for name, check_func in sections:
        print(f'\n[{name}]')
        if not check_func():
            all_ok = False

    print(f'\n{"=" * 60}')
    if all_ok:
        print('  All checks passed. Pipeline is ready to run.')
    else:
        print('  Some checks failed. Fix the issues above before running the pipeline.')
    print('=' * 60)

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
