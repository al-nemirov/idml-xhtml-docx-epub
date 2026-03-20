# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
