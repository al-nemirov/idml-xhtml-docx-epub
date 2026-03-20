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
 [process_footnotes.py extract]   Extract footnotes -> footnote_map.json
       |
       v
 (optional: review/edit footnotes in footnote_map.json)
       |
       v
 [process_footnotes.py insert]    Insert footnotes back as endnotes
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
# 0. Validate your environment
python scripts/preflight.py

# 1. Export from InDesign (run inside InDesign Scripts panel)
#    Use scripts/indesign/export_xhtml.jsx

# 2. Process footnotes (two-phase: extract -> review -> insert)
python scripts/process_footnotes.py extract
# Review/edit data/temp/footnote_map.json if needed
python scripts/process_footnotes.py insert

# Or run both phases automatically:
python scripts/process_footnotes.py auto

# 3. Convert XHTML to DOCX
python scripts/xhtml_to_docx.py

# 4. Convert DOCX to EPUB
python scripts/docx_to_epub.py

# 5. Enrich EPUB with metadata and accessibility
python scripts/enrich_epub.py
```

## Footnote Processing

The footnote system uses a two-phase extraction/insertion approach:

### Phase 1: Extract

```bash
python scripts/process_footnotes.py extract
```

- Scans all XHTML files for InDesign footnotes (`div.id="footnote-N"`)
- Saves footnote text and metadata to `data/temp/footnote_map.json`
- Replaces footnote bodies in XHTML with `{{footnote_N}}` anchors

### Manual Review (Optional)

Open `data/temp/footnote_map.json` and review/edit extracted footnotes:
- Fix OCR errors in footnote text
- Adjust formatting
- Remove unwanted footnotes

### Phase 2: Insert

```bash
python scripts/process_footnotes.py insert
```

- Reads the (optionally edited) footnote map
- Replaces `{{footnote_N}}` anchors with properly formatted endnotes
- Rewrites footnote reference links to standard `#fn:N` format

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
| `paths.rtf_dir` | Directory for RTF source files | `./data/rtf` |
| `metadata_file` | Excel file with book metadata | `books.xlsx` |
| `reference_doc` | Pandoc reference DOCX for styling | `templates/custom-reference.docx` |
| `lua_filter` | Pandoc Lua filter for footnotes | `filters/footnote_filter.lua` |
| `lua_filter_endnotes` | Pandoc Lua filter for endnotes | `filters/fix_endnotes.lua` |
| `lua_filter_links` | Pandoc Lua filter for link extensions | `filters/fix_links_epub.lua` |
| `publisher` | Publisher name for EPUB metadata | `Your Publisher Name` |
| `language` | Book language code | `en` |
| `epub_version` | EPUB specification version | `3` |

## InDesign Document Preparation

Before running the pipeline, prepare your InDesign documents for optimal export:

### Paragraph Styles (Critical)

The pipeline maps InDesign paragraph style names to HTML headings. For best results, rename your InDesign paragraph styles to match the expected names:

| InDesign Style | HTML Output | Notes |
|---|---|---|
| `Heading 1` | `<h1>` | Used by JSX scripts for heading detection |
| `Heading 2` | `<h2>` | |
| `Heading 3` &ndash; `Heading 6` | `<h3>` &ndash; `<h6>` | |
| `Часть` (Part) | `<h2>` | Russian style names in XHTML stage |
| `Глава` (Chapter) | `<h3>` | Russian style names in XHTML stage |
| `Заголовок 2`&ndash;`6` | `<h2>`&ndash;`<h6>` | Russian style names in XHTML stage |
| `Цитата` (Quote) | `<blockquote>` | |

> **Tip**: Renaming InDesign styles to `Heading 1`, `Heading 2`, etc. before export ensures the JSX scripts correctly identify heading levels. The Python XHTML stage also supports Russian-named styles for localized InDesign templates.

### Images (Important)

Images are only exported correctly if they are **anchored within text frames** (inline images). Floating images placed independently on the page will **not** be included in the XHTML export.

To ensure images are exported:
1. **Anchor images to text** &mdash; Right-click the image frame in InDesign, choose Object &rarr; Anchored Object &rarr; Insert, or paste the image directly into a text frame at the desired position
2. **Use inline or above-line anchoring** &mdash; Custom-positioned anchored objects may not export correctly
3. **Keep image files linked** &mdash; Embedded images work, but linked files produce better quality
4. **Check the Links panel** &mdash; Ensure all images show "OK" status (no missing or modified links)

After export, images are saved in `*-web-resources/image/` subdirectories alongside each XHTML file.

### Footnotes

InDesign footnotes are automatically detected and processed by the pipeline. The JSX scripts convert them to `div.id="footnote-N"` format, which the Python footnote processor then handles using the extract/insert approach.

## Pipeline Stages

### Stage 1: InDesign Export (JSX)

The `scripts/indesign/` folder contains ExtendScript (JSX) files that run inside Adobe InDesign:

- **`export_xhtml.jsx`** &mdash; Batch export .indd files to XHTML with font normalization and footnote processing.
- **`export_xhtml_v2.jsx`** &mdash; Same as above but with recursive subdirectory search.
- **`export_fxl.jsx`** &mdash; Export to Fixed-Layout HTML format.

### Stage 2: Footnote Processing

**`process_footnotes.py`** uses a two-phase extract/insert approach:
1. **Extract**: Pulls footnotes from XHTML into `footnote_map.json` with `{{footnote_N}}` anchors
2. **Review**: User can edit the JSON map to fix or adjust footnotes
3. **Insert**: Replaces anchors with properly formatted endnotes

### Stage 3: XHTML to DOCX

**`xhtml_to_docx.py`** cleans InDesign-specific tags, maps CSS classes to semantic HTML headings (Russian style names match InDesign source), merges consecutive headings, fixes image paths, and converts to DOCX via Pandoc with custom Lua filters.

Image paths are automatically resolved to the `*-web-resources/image/` directories created during InDesign export. Spaces in filenames are replaced with underscores for compatibility.

### Stage 4: DOCX to EPUB

**`docx_to_epub.py`** reads book metadata (title, author, ISBN, annotation, translators) from an Excel spreadsheet, applies cover images, and converts to EPUB 3 using Calibre.

### Stage 5: EPUB Enrichment

**`enrich_epub.py`** unpacks each EPUB to add accessibility metadata (ARIA roles, schema.org attributes), updates the title page with book information, enhances stylesheets, and removes InDesign class artifacts from headings.

### Utility: RTF to XHTML

**`rtf_to_xhtml.py`** converts RTF files to XHTML format using pypandoc, extracting embedded images and separating CSS styles. Useful when source documents arrive in RTF format.

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
│   ├── rtf_to_xhtml.py         # Utility: RTF -> XHTML
│   ├── preflight.py            # Pre-flight environment check
│   ├── process_footnotes.py    # Stage 2: Footnote extract/insert
│   └── indesign/
│       ├── export_xhtml.jsx    # Stage 1: InDesign -> XHTML
│       ├── export_xhtml_v2.jsx # Stage 1: Recursive variant
│       ├── indesign_utils.jsx  # Shared JSX utility functions
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
    ├── rtf/
    └── temp/
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
