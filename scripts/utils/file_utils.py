"""
File Utility Functions

Provides safe file operations for the book conversion pipeline:
- atomic_json_write: Write JSON with tmp+rename pattern to prevent corruption
- backup_file: Create timestamped backup copies
- load_json / save_json: Convenience wrappers with error handling

Based on Book Studio's file_utils.py atomic write pattern.
"""

import os
import json
import time
import shutil
import tempfile
from datetime import datetime


def atomic_json_write(filepath, data, indent=2, ensure_ascii=False, log_func=None):
    """Write JSON atomically: tmp file -> fsync -> rename.

    This prevents data corruption if the process is interrupted during write.
    On Windows, os.replace is used which is atomic within the same filesystem.

    Args:
        filepath: Target path for the JSON file.
        data: Python object to serialize as JSON.
        indent: JSON indentation level (default: 2).
        ensure_ascii: Whether to escape non-ASCII characters (default: False).
        log_func: Optional logging function for debug output.

    Returns:
        True on success, False on error.
    """
    filepath = str(filepath)
    dir_name = os.path.dirname(filepath) or '.'

    try:
        # Write to a temporary file in the same directory (same filesystem for atomic rename)
        fd, tmp_path = tempfile.mkstemp(
            suffix='.tmp',
            prefix='.json_',
            dir=dir_name
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            os.close(fd)
            raise

        # Atomic rename (os.replace is atomic on same filesystem)
        # Windows retry: sometimes the target is briefly locked
        for attempt in range(3):
            try:
                os.replace(tmp_path, filepath)
                if log_func:
                    log_func(f'  [atomic] Written: {os.path.basename(filepath)}')
                return True
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    raise

    except Exception as e:
        if log_func:
            log_func(f'  [atomic] ERROR writing {filepath}: {e}')
        # Clean up tmp file if it exists
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


def backup_file(filepath, backup_dir=None, log_func=None):
    """Create a timestamped backup copy of a file.

    Args:
        filepath: Path to the file to back up.
        backup_dir: Directory for backups (default: same directory as file).
        log_func: Optional logging function.

    Returns:
        Path to the backup file, or None on error.
    """
    if not os.path.exists(filepath):
        if log_func:
            log_func(f'  [backup] File not found: {filepath}')
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = os.path.basename(filepath)
    name, ext = os.path.splitext(base)
    backup_name = f'{name}_{timestamp}{ext}.bak'

    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, backup_name)
    else:
        backup_path = os.path.join(os.path.dirname(filepath), backup_name)

    try:
        shutil.copy2(filepath, backup_path)
        if log_func:
            log_func(f'  [backup] Created: {backup_name}')
        return backup_path
    except Exception as e:
        if log_func:
            log_func(f'  [backup] ERROR: {e}')
        return None


def load_json(filepath, log_func=None):
    """Load a JSON file with error handling.

    Args:
        filepath: Path to the JSON file.
        log_func: Optional logging function.

    Returns:
        Parsed JSON data, or None on error.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        if log_func:
            log_func(f'  [json] File not found: {filepath}')
        return None
    except json.JSONDecodeError as e:
        if log_func:
            log_func(f'  [json] Parse error in {filepath}: {e}')
        return None


def save_json(filepath, data, **kwargs):
    """Save JSON using atomic write. Convenience wrapper for atomic_json_write."""
    return atomic_json_write(filepath, data, **kwargs)
