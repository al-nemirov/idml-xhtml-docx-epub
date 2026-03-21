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
import logging
import shutil
import importlib

logger = logging.getLogger(__name__)


def _config_path():
    """Return the effective config path, honoring PIPELINE_CONFIG env var."""
    return os.environ.get(
        'PIPELINE_CONFIG',
        os.path.join(os.path.dirname(__file__), '..', 'config.json'),
    )


def load_config():
    """Load configuration from config.json in the project root.

    Honors the PIPELINE_CONFIG environment variable to override the default
    config path (useful for testing without touching the root config.json).
    """
    config_path = _config_path()
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        logger.error('  config.json has invalid JSON: %s', e)
        return None


def check_config():
    """Check that config.json exists and is valid."""
    config_path = _config_path()
    if not os.path.exists(config_path):
        logger.error('  FAIL: config.json not found')
        logger.error('        Run: cp config.example.json config.json')
        return False

    config = load_config()
    if config is None:
        return False

    # Check required keys
    required_keys = ['paths', 'metadata_file', 'reference_doc', 'lua_filter']
    missing = [k for k in required_keys if k not in config]
    if missing:
        logger.error('  FAIL: Missing config keys: %s', ', '.join(missing))
        return False

    required_paths = ['xhtml_dir', 'docx_dir', 'epub_dir', 'output_dir', 'temp_dir']
    missing_paths = [p for p in required_paths if p not in config.get('paths', {})]
    if missing_paths:
        logger.error('  FAIL: Missing path keys: %s', ', '.join(missing_paths))
        return False

    logger.info('  OK: config.json is valid')
    return True


def check_external_tools():
    """Check that Pandoc and Calibre are installed and in PATH."""
    ok = True

    pandoc = shutil.which('pandoc')
    if pandoc:
        logger.info('  OK: Pandoc found at %s', pandoc)
    else:
        logger.error('  FAIL: Pandoc not found in PATH')
        logger.error('        Install from: https://pandoc.org/')
        ok = False

    calibre = shutil.which('ebook-convert')
    if calibre:
        logger.info('  OK: Calibre (ebook-convert) found at %s', calibre)
    else:
        logger.warning('  WARN: Calibre (ebook-convert) not found in PATH')
        logger.warning('        Install from: https://calibre-ebook.com/')
        logger.warning('        (Only needed for Stage 4: DOCX -> EPUB)')

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
            logger.info('  OK: %s', pip_name)
        except ImportError:
            logger.error('  FAIL: %s not installed', pip_name)
            logger.error('        Run: pip install %s', pip_name)
            ok = False

    return ok


def check_templates():
    """Check that required template files exist."""
    config = load_config()
    if not config:
        logger.warning('  SKIP: Cannot check templates without valid config')
        return False

    ok = True
    project_root = os.path.join(os.path.dirname(__file__), '..')

    # Reference document
    ref_doc = os.path.join(project_root, config.get('reference_doc', ''))
    if os.path.exists(ref_doc):
        size_kb = os.path.getsize(ref_doc) / 1024
        logger.info('  OK: Reference document (%d KB)', size_kb)
    else:
        logger.error('  FAIL: Reference document not found: %s', config.get('reference_doc'))
        ok = False

    # Lua filters
    for key in ('lua_filter', 'lua_filter_endnotes', 'lua_filter_links'):
        filter_path = config.get(key, '')
        if filter_path:
            full_path = os.path.join(project_root, filter_path)
            if os.path.exists(full_path):
                logger.info('  OK: %s -> %s', key, filter_path)
            else:
                logger.error('  FAIL: %s not found: %s', key, filter_path)
                ok = False

    return ok


def check_directories():
    """Check/create required working directories."""
    config = load_config()
    if not config:
        logger.warning('  SKIP: Cannot check directories without valid config')
        return False

    for key, path in config.get('paths', {}).items():
        if os.path.isabs(path):
            full_path = path
        else:
            full_path = os.path.join(os.path.dirname(__file__), '..', path)

        if os.path.isdir(full_path):
            logger.info('  OK: %s -> %s', key, path)
        else:
            try:
                os.makedirs(full_path, exist_ok=True)
                logger.info('  CREATED: %s -> %s', key, path)
            except OSError as e:
                logger.error('  FAIL: Cannot create %s: %s', key, e)

    return True


def main():
    """Run all preflight checks."""
    logger.info('%s', '=' * 60)
    logger.info('  PREFLIGHT CHECK')
    logger.info('%s', '=' * 60)

    sections = [
        ('Configuration', check_config),
        ('External Tools', check_external_tools),
        ('Python Dependencies', check_python_deps),
        ('Template Files', check_templates),
        ('Working Directories', check_directories),
    ]

    all_ok = True
    for name, check_func in sections:
        logger.info('\n[%s]', name)
        if not check_func():
            all_ok = False

    logger.info('')
    logger.info('%s', '=' * 60)
    if all_ok:
        logger.info('  All checks passed. Pipeline is ready to run.')
    else:
        logger.error('  Some checks failed. Fix the issues above before running the pipeline.')
    logger.info('%s', '=' * 60)

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
