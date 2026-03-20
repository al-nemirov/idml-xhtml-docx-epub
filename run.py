"""
Pipeline Runner

Executes the book conversion pipeline steps in sequence.
Based on Book Studio's pipeline runner approach.

Usage:
    python run.py                # Run all steps
    python run.py --from 3       # Start from step 3
    python run.py --only 2       # Run only step 2
    python run.py --list         # List available steps
    python run.py --preflight    # Run preflight check only

Steps:
    1. Build structured.json from XHTML
    2. Extract footnotes (footnote_map.json)
    3. Extract images (image_map.json)
    4. Insert footnotes back into XHTML
    5. Insert images back into XHTML
    6. Convert XHTML to DOCX (Pandoc)
    7. Convert DOCX to EPUB (Calibre)
    8. Enrich EPUB (metadata, accessibility)

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import sys
import time
import argparse
import importlib
import json


def load_config():
    """Load configuration from config.json in the project root."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
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


# Pipeline step definitions
STEPS = [
    {
        'num': 1,
        'name': 'Build Structure',
        'description': 'Parse XHTML files into structured.json',
        'module': 'scripts.build_structure',
        'func': 'build_structure',
        'args': 'config',
    },
    {
        'num': 2,
        'name': 'Extract Footnotes',
        'description': 'Extract footnotes from XHTML into footnote_map.json',
        'module': 'scripts.process_footnotes',
        'func': 'extract_phase',
        'args': 'config',
    },
    {
        'num': 3,
        'name': 'Extract Images',
        'description': 'Extract images from XHTML into image_map.json',
        'module': 'scripts.process_images',
        'func': 'extract_phase',
        'args': 'config',
    },
    {
        'num': 4,
        'name': 'Insert Footnotes',
        'description': 'Insert approved footnotes back into XHTML',
        'module': 'scripts.process_footnotes',
        'func': 'insert_phase',
        'args': 'config',
    },
    {
        'num': 5,
        'name': 'Insert Images',
        'description': 'Insert approved images back into XHTML',
        'module': 'scripts.process_images',
        'func': 'insert_phase',
        'args': 'config',
    },
    {
        'num': 6,
        'name': 'XHTML to DOCX',
        'description': 'Convert XHTML to DOCX via Pandoc',
        'module': 'scripts.xhtml_to_docx',
        'func': 'main',
        'args': 'none',
    },
    {
        'num': 7,
        'name': 'DOCX to EPUB',
        'description': 'Convert DOCX to EPUB via Calibre',
        'module': 'scripts.docx_to_epub',
        'func': 'main',
        'args': 'none',
    },
    {
        'num': 8,
        'name': 'Enrich EPUB',
        'description': 'Add metadata, accessibility, styles to EPUB',
        'module': 'scripts.enrich_epub',
        'func': 'main',
        'args': 'none',
    },
]


def list_steps():
    """Print available pipeline steps."""
    print(f'{"=" * 60}')
    print(f'  PIPELINE STEPS')
    print(f'{"=" * 60}\n')
    for step in STEPS:
        print(f'  {step["num"]}. {step["name"]}')
        print(f'     {step["description"]}')
        print()


def run_step(step, config):
    """Execute a single pipeline step.

    Returns:
        bool: True on success, False on error.
    """
    step_num = step['num']
    step_name = step['name']

    print(f'\n{"═" * 60}')
    print(f'  STEP {step_num}: {step_name.upper()}')
    print(f'{"═" * 60}\n')

    start_time = time.time()

    try:
        # Import the module
        module = importlib.import_module(step['module'])
        func = getattr(module, step['func'])

        # Call the function
        if step['args'] == 'config':
            result = func(config)
        else:
            # Functions like main() that load config themselves
            result = func()

        duration = time.time() - start_time

        # Interpret result
        if result is False:
            print(f'\n  ✗ Step {step_num} ({step_name}) FAILED [{duration:.1f}s]')
            return False

        print(f'\n  ✓ Step {step_num} ({step_name}) completed [{duration:.1f}s]')
        return True

    except SystemExit:
        # Some main() functions call sys.exit on error
        duration = time.time() - start_time
        print(f'\n  ✗ Step {step_num} ({step_name}) exited [{duration:.1f}s]')
        return False

    except Exception as e:
        duration = time.time() - start_time
        print(f'\n  ✗ Step {step_num} ({step_name}) ERROR [{duration:.1f}s]: {e}')
        import traceback
        traceback.print_exc()
        return False


def run_preflight():
    """Run the preflight check."""
    try:
        module = importlib.import_module('scripts.preflight')
        return module.main() == 0
    except Exception as e:
        print(f'Preflight error: {e}')
        return False


def main():
    """Main entry point for the pipeline runner."""
    # Ensure we're in the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # Add project root to path for module imports
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    parser = argparse.ArgumentParser(
        description='Book Conversion Pipeline Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Steps:
  1. Build Structure    - Parse XHTML into structured.json
  2. Extract Footnotes  - Footnotes -> footnote_map.json
  3. Extract Images     - Images -> image_map.json
  4. Insert Footnotes   - Footnotes back into XHTML
  5. Insert Images      - Images back into XHTML
  6. XHTML to DOCX      - Convert via Pandoc
  7. DOCX to EPUB       - Convert via Calibre
  8. Enrich EPUB        - Metadata & accessibility

Examples:
  python run.py              Run all steps
  python run.py --from 4     Start from step 4 (insert footnotes)
  python run.py --only 6     Run only step 6 (XHTML to DOCX)
  python run.py --list       List available steps
  python run.py --preflight  Environment check
'''
    )
    parser.add_argument('--list', action='store_true', help='List available steps')
    parser.add_argument('--preflight', action='store_true', help='Run preflight check only')
    parser.add_argument('--from', type=int, dest='from_step', metavar='N',
                        help='Start from step N')
    parser.add_argument('--to', type=int, dest='to_step', metavar='N',
                        help='Stop after step N')
    parser.add_argument('--only', type=int, metavar='N',
                        help='Run only step N')
    parser.add_argument('--skip-preflight', action='store_true',
                        help='Skip preflight check')

    args = parser.parse_args()

    if args.list:
        list_steps()
        return

    if args.preflight:
        success = run_preflight()
        sys.exit(0 if success else 1)

    # Load config
    config = load_config()

    # Run preflight unless skipped
    if not args.skip_preflight:
        print('Running preflight check...\n')
        if not run_preflight():
            print('\nPreflight check failed. Fix issues above or use --skip-preflight.')
            sys.exit(1)
        print()

    # Determine which steps to run
    if args.only:
        steps_to_run = [s for s in STEPS if s['num'] == args.only]
        if not steps_to_run:
            print(f'Error: step {args.only} not found. Use --list to see available steps.')
            sys.exit(1)
    else:
        from_step = args.from_step or 1
        to_step = args.to_step or len(STEPS)
        steps_to_run = [s for s in STEPS if from_step <= s['num'] <= to_step]

    if not steps_to_run:
        print('No steps to run.')
        return

    # Execute pipeline
    total_start = time.time()
    print(f'{"═" * 60}')
    print(f'  PIPELINE: Running steps {steps_to_run[0]["num"]}-{steps_to_run[-1]["num"]}')
    print(f'{"═" * 60}')

    completed = 0
    failed = 0

    for step in steps_to_run:
        success = run_step(step, config)
        if success:
            completed += 1
        else:
            failed += 1
            print(f'\nPipeline stopped at step {step["num"]}.')
            break

    total_duration = time.time() - total_start

    print(f'\n{"═" * 60}')
    print(f'  PIPELINE COMPLETE')
    print(f'{"═" * 60}')
    print(f'  Completed: {completed}/{len(steps_to_run)} steps')
    if failed:
        print(f'  Failed: {failed}')
    print(f'  Total time: {total_duration:.1f}s')
    print(f'{"═" * 60}')

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
