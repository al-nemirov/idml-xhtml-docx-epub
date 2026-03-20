# Book Conversion Pipeline

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Pandoc](https://img.shields.io/badge/Pandoc-required-green.svg)](https://pandoc.org/)
[![Calibre](https://img.shields.io/badge/Calibre-required-orange.svg)](https://calibre-ebook.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Multi-format book conversion pipeline: InDesign &rarr; XHTML &rarr; DOCX &rarr; EPUB**

Automates the end-to-end process of converting books from Adobe InDesign source files into production-ready EPUB ebooks, with intermediate XHTML and DOCX stages for maximum control over formatting, footnotes, metadata, and accessibility.

## Pipeline

```
 InDesign (.indd)
       |
       v
 [export_xhtml.jsx]     JSX script (runs inside InDesign)
       |
       v
   XHTML files
       |
       v
 [process_footnotes.py]  Convert InDesign footnotes to endnotes
       |
       v
 [xhtml_to_docx.py]      Clean tags, map styles, convert via Pandoc
       |
       v
   DOCX files
       |
       v
 [docx_to_epub.py]       Convert via Calibre with metadata from Excel
       |
       v
   EPUB files
       |
       v
 [enrich_epub.py]        Add accessibility metadata, styles, title page
       |
       v
   Final EPUB
```

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| [Python](https://www.python.org/) | 3.8+ | Script runtime |
| [Pandoc](https://pandoc.org/) | 2.x+ | XHTML to DOCX conversion |
| [Calibre](https://calibre-ebook.com/) | 5.x+ | DOCX to EPUB conversion |
| [Adobe InDesign](https://www.adobe.com/products/indesign.html) | CS6+ | Required only for JSX export scripts |

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/al-nemirov/idml-xhtml-docx-epub.git
   cd idml-xhtml-docx-epub
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create your configuration file:**
   ```bash
   cp config.example.json config.json
   ```

4. **Edit `config.json`** with your actual paths and publisher details.

5. **Ensure Pandoc and Calibre are installed** and available in your system PATH.

## Quick Start

```bash
# 1. Export from InDesign (run inside InDesign Scripts panel)
#    Use scripts/indesign/export_xhtml.jsx

# 2. Process footnotes
python scripts/process_footnotes.py

# 3. Convert XHTML to DOCX
python scripts/xhtml_to_docx.py

# 4. Convert DOCX to EPUB
python scripts/docx_to_epub.py

# 5. Enrich EPUB with metadata and accessibility
python scripts/enrich_epub.py
```

## Configuration

All paths and settings are managed via `config.json`. See `config.example.json` for the template.

| Key | Description | Default |
|---|---|---|
| `paths.xhtml_dir` | Directory containing source XHTML files | `./data/xhtml` |
| `paths.docx_dir` | Output directory for DOCX files | `./data/docx` |
| `paths.epub_dir` | Output directory for EPUB files | `./data/epub` |
| `paths.output_dir` | Final output directory for enriched EPUBs | `./data/output` |
| `paths.cover_dir` | Directory containing cover images (ISBN.jpg) | `./data/covers` |
| `paths.temp_dir` | Temporary working directory | `./data/temp` |
| `metadata_file` | Excel file with book metadata | `books.xlsx` |
| `reference_doc` | Pandoc reference DOCX for styling | `templates/custom-reference.docx` |
| `lua_filter` | Pandoc Lua filter for footnotes | `filters/footnote_filter.lua` |
| `publisher` | Publisher name for EPUB metadata | `Your Publisher Name` |
| `language` | Book language code | `en` |
| `epub_version` | EPUB specification version | `3` |

## Pipeline Stages

### Stage 1: InDesign Export (JSX)

The `scripts/indesign/` folder contains ExtendScript (JSX) files that run inside Adobe InDesign:

- **`export_xhtml.jsx`** &mdash; Batch export .indd files to XHTML with font normalization and footnote processing.
- **`export_xhtml_v2.jsx`** &mdash; Same as above but with recursive subdirectory search.
- **`export_fxl.jsx`** &mdash; Export to Fixed-Layout HTML format.

### Stage 2: Footnote Processing

**`process_footnotes.py`** converts InDesign-style inline footnotes into standard endnote format, rewrites cross-file footnote links, and copies associated image resources.

### Stage 3: XHTML to DOCX

**`xhtml_to_docx.py`** cleans InDesign-specific tags, maps CSS classes to semantic HTML headings, merges consecutive headings, processes footnotes, fixes image paths, and converts to DOCX via Pandoc with custom Lua filters.

### Stage 4: DOCX to EPUB

**`docx_to_epub.py`** reads book metadata (title, author, ISBN, annotation, translators) from an Excel spreadsheet, applies cover images, and converts to EPUB 3 using Calibre.

### Stage 5: EPUB Enrichment

**`enrich_epub.py`** unpacks each EPUB to add accessibility metadata (ARIA roles, schema.org attributes), updates the title page with book information, enhances stylesheets, and removes InDesign class artifacts from headings.

### Pandoc Lua Filters

- **`filters/footnote_filter.lua`** &mdash; Reformats InDesign footnote spans into clean numbered paragraphs.
- **`filters/fix_endnotes.lua`** &mdash; Adjusts heading levels for footnote sections and links endnotes with backlinks.
- **`filters/fix_links_epub.lua`** &mdash; Replaces .docx link extensions with .epub for cross-references.

## File Structure

```
idml-xhtml-docx-epub/
├── config.example.json          # Configuration template
├── requirements.txt             # Python dependencies
├── LICENSE                      # MIT License
├── CHANGELOG.md                 # Version history
├── scripts/
│   ├── xhtml_to_docx.py        # Stage 3: XHTML -> DOCX
│   ├── docx_to_epub.py         # Stage 4: DOCX -> EPUB
│   ├── enrich_epub.py          # Stage 5: EPUB enrichment
│   ├── epub_to_html.py         # Utility: RTF -> XHTML
│   ├── process_footnotes.py    # Stage 2: Footnote processing
│   └── indesign/
│       ├── export_xhtml.jsx    # Stage 1: InDesign -> XHTML
│       ├── export_xhtml_v2.jsx # Stage 1: Recursive variant
│       └── export_fxl.jsx      # Fixed-layout HTML export
├── filters/
│   ├── footnote_filter.lua     # Pandoc footnote filter
│   ├── fix_endnotes.lua        # Pandoc endnote fixer
│   └── fix_links_epub.lua      # Pandoc link extension fixer
├── templates/
│   ├── custom-reference.docx   # Pandoc reference document
│   ├── styles.css              # Footnote styles
│   └── template.opf            # OPF package template
└── data/                        # Working directories (gitignored)
    ├── xhtml/
    ├── docx/
    ├── epub/
    ├── output/
    ├── covers/
    └── temp/
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
