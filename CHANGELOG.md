# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-03-20

### Changed

- **Footnote system**: Rewritten with two-phase extract/insert approach (inspired by docx-image-swap technology). Users can now review and edit footnotes between extraction and reinsertion
- All Python scripts now use proper `main()` entry points with `if __name__ == '__main__'`
- All scripts now use `load_config()` with proper error handling instead of top-level config loading
- Temporary files now use `tempfile` module instead of hardcoded paths
- EPUB enrichment uses `tempfile.TemporaryDirectory` for automatic cleanup
- Subprocess calls now use `capture_output=True` and proper error reporting

### Fixed

- `export_xhtml.jsx`: Fixed IDML export using `exportFile()` instead of incorrect `save()` call
- `xhtml_to_docx.py`: Removed unused `unidecode` import, fixed temp file cleanup
- `enrich_epub.py`: Fixed XML namespace string formatting, replaced manual cleanup with `shutil.rmtree`
- `epub_to_html.py`: Fixed deprecated `findAll` -> `find_all` and `text=` -> `string=` (BS4 4.12+)
- `footnote_filter.lua`: Fixed `text_parts` to use proper Pandoc inline elements instead of raw strings
- `fix_endnotes.lua`: Fixed malformed `pandoc.Link` constructor, added safety checks
- `docx_to_epub.py`: Added error handling for missing cover images and Calibre not found

### Added

- `pypandoc` to requirements.txt (was missing, used by `epub_to_html.py`)
- `rtf_dir` path option in configuration
- Lua filter paths (`lua_filter_endnotes`, `lua_filter_links`) in configuration
- Success/error counters for batch processing
- Proper CLI usage messages for `process_footnotes.py`

### Removed

- `unidecode` dependency (was imported but never used)

## [1.0.0] - 2026-03-20

### Added

- XHTML to DOCX conversion with Pandoc (`xhtml_to_docx.py`)
- DOCX to EPUB conversion with Calibre (`docx_to_epub.py`)
- EPUB metadata enrichment and accessibility support (`enrich_epub.py`)
- Footnote processing from InDesign format to endnotes (`process_footnotes.py`)
- RTF/EPUB to XHTML utility converter (`epub_to_html.py`)
- InDesign JSX export scripts (XHTML, XHTML recursive, Fixed-Layout HTML)
- Pandoc Lua filters for footnotes, endnotes, and link fixes
- Configuration-based path management via `config.json`
- Excel-based book metadata support (title, author, ISBN, annotation, translators)
- EPUB 3 accessibility metadata (schema.org, ARIA roles)
- Custom reference document and CSS templates
