"""
XHTML to DOCX Converter

Converts XHTML files exported from InDesign into DOCX format using Pandoc.
Performs cleanup of InDesign-specific tags, maps CSS classes to semantic HTML
heading elements, processes footnotes, and fixes image paths before conversion.

Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
"""

import os
import re
import json
import logging
import subprocess
import tempfile
import time
import sys
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.json in the project root.

    Honors the PIPELINE_CONFIG environment variable to override the default
    config path (useful for testing without touching the root config.json).
    """
    config_path = os.environ.get(
        'PIPELINE_CONFIG',
        os.path.join(os.path.dirname(__file__), '..', 'config.json'),
    )
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error('config.json not found at %s', os.path.abspath(config_path))
        logger.error('Copy config.example.json to config.json and edit it.')
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error('invalid JSON in config.json: %s', e)
        sys.exit(1)


def clean_tags(content):
    """Remove unnecessary InDesign-generated CharOverride tags and empty paragraphs."""
    content = re.sub(
        r'<p class="CharOverride-\d+"[^>]*>(<span[^>]*>)?(.*?)(</span>)?</p>',
        r'\2', content, flags=re.DOTALL
    )
    content = re.sub(
        r'<span class="CharOverride-\d+"[^>]*>(.*?)</span>',
        r'\1', content, flags=re.DOTALL
    )
    content = re.sub(r'<p>\s*</p>', '', content)
    return content


def replace_tags(content):
    """Map InDesign CSS paragraph style classes to semantic HTML heading elements.

    The keys must match the actual InDesign paragraph style names.
    Rename your InDesign styles to these English names before export.
    """
    replacements = {
        "Part": "h2",
        "Chapter": "h3",
        "Heading 2": "h2",
        "Subheading": "h2",
        "Subtitle": "h2",
        "Heading 3": "h3",
        "Heading 4": "h4",
        "Heading 5": "h5",
        "Heading 6": "h6",
        "Blockquote": "blockquote",
        "footnote-text": "footnote",
        "Footnote-ref": "footnote-ref",
        "Footnote-back": "footnote-back",
    }

    for style, tag in replacements.items():
        pattern = re.compile(
            r'<p class="{}"[^>]*>(.*?)</p>'.format(re.escape(style)),
            re.DOTALL
        )
        content = pattern.sub(r'<{tag}>\1</{tag}>'.format(tag=tag), content)

    return content


class _HeadingMerger(HTMLParser):
    """DOM-safe heading merger using Python's HTMLParser.

    Merges consecutive headings of the same level (e.g., two <h2> tags in a row)
    into a single heading, preserving all attributes and nested HTML safely.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self._pending_tag = None    # Tag name of the pending heading (e.g., 'h2')
        self._pending_attrs = None  # Attributes of the pending heading
        self._pending_parts = []    # Inner HTML parts of the pending heading
        self._depth = 0             # Nesting depth inside the pending heading

    def _flush_pending(self):
        """Write the pending heading to output."""
        if self._pending_tag:
            attr_str = ''
            if self._pending_attrs:
                attr_str = ' ' + ' '.join(
                    f'{k}="{v}"' if v is not None else k
                    for k, v in self._pending_attrs
                )
            inner = ''.join(self._pending_parts)
            self.output.append(f'<{self._pending_tag}{attr_str}>{inner}</{self._pending_tag}>')
            self._pending_tag = None
            self._pending_attrs = None
            self._pending_parts = []
            self._depth = 0

    def _is_heading(self, tag):
        return tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text() or ''
        if self._pending_tag:
            if tag == self._pending_tag and self._depth == 0:
                # Same-level heading right after: merge (append space separator)
                self._pending_parts.append(' ')
                return
            self._pending_parts.append(raw)
            if self._is_heading(tag):
                self._depth += 1
        elif self._is_heading(tag):
            self._pending_tag = tag
            self._pending_attrs = attrs
            self._pending_parts = []
            self._depth = 0
        else:
            self.output.append(raw)

    def handle_endtag(self, tag):
        if self._pending_tag:
            if tag == self._pending_tag and self._depth == 0:
                # Don't flush yet; wait to see if the next tag is the same heading
                return
            if self._is_heading(tag) and self._depth > 0:
                self._depth -= 1
            self._pending_parts.append(f'</{tag}>')
        else:
            self.output.append(f'</{tag}>')

    def handle_data(self, data):
        if self._pending_tag:
            # If only whitespace between headings, absorb it
            if self._depth == 0 and not data.strip():
                return
            self._pending_parts.append(data)
        else:
            # Whitespace between potential headings: buffer it
            self.output.append(data)

    def handle_entityref(self, name):
        text = f'&{name};'
        if self._pending_tag:
            self._pending_parts.append(text)
        else:
            self.output.append(text)

    def handle_charref(self, name):
        text = f'&#{name};'
        if self._pending_tag:
            self._pending_parts.append(text)
        else:
            self.output.append(text)

    def handle_comment(self, data):
        text = f'<!--{data}-->'
        if self._pending_tag:
            self._pending_parts.append(text)
        else:
            self.output.append(text)

    def handle_decl(self, decl):
        self._flush_pending()
        self.output.append(f'<!{decl}>')

    def handle_pi(self, data):
        self._flush_pending()
        self.output.append(f'<?{data}>')

    def close(self):
        super().close()
        self._flush_pending()

    def get_result(self):
        self._flush_pending()
        return ''.join(self.output)


def merge_headings(content):
    """Merge consecutive headings of the same level into a single heading.

    Uses a DOM-safe HTML parser instead of regex to correctly handle
    headings with attributes, nested elements, and special characters.
    """
    parser = _HeadingMerger()
    parser.feed(content)
    return parser.get_result()


def process_footnotes(content):
    """Process InDesign footnotes: reformat references and footnote blocks."""
    # Replace footnote references while preserving backlinks
    content = re.sub(
        r'<a[^>]*href="([^"]*\.html)#footnote-(\d+)-backlink">(\d+)</a>',
        lambda m: (
            f'<a href="{m.group(1).replace(".html", ".docx")}'
            f'#footnote-{m.group(2)}-backlink">[{m.group(3)}]</a>'
        ),
        content
    )

    # Handle footnotes inside span elements
    content = re.sub(
        r'<span[^>]*><span id="footnote-(\d+)-backlink">'
        r'<a[^>]*href="#fn:(\d+)"[^>]*>(\d+)</a></span></span>',
        lambda m: (
            f'<span><span id="footnote-{m.group(1)}-backlink">'
            f'<a href="#fn:{m.group(2)}">[{m.group(3)}]</a></span></span>'
        ),
        content
    )

    # Replace footnote blocks while preserving backlinks
    content = re.sub(
        r'<div id="footnote-(\d+)" class="_idFootnote">\s*<p[^>]*>(.*?)</p>\s*</div>',
        lambda m: (
            f'<div id="footnote-{m.group(1)}" class="_idFootnote">'
            f'<p>[{m.group(1)}] {m.group(2)}</p></div>'
        ),
        content,
        flags=re.DOTALL
    )

    # Only add footnotes-list container if there are actual footnotes
    has_footnotes = bool(re.search(
        r'<li id="fn:\d+">', content
    ))
    if has_footnotes and '<ol class="footnotes-list">' not in content:
        content += '<ol class="footnotes-list">{footnotes}</ol>'

    return content


def fix_image_path(match, filename, resource_dir):
    """Fix image paths to point to the correct resource directory.

    Uses the original basename from the src attribute without modifying it,
    so the path matches the actual file on disk. Always uses POSIX forward
    slashes for XHTML/HTML compatibility (even on Windows).
    """
    old_path = match.group(1)
    basename = os.path.basename(old_path)
    # Use POSIX forward slashes for URLs in XHTML (os.path.join uses \ on Windows)
    new_path = '/'.join([
        resource_dir.replace('\\', '/'),
        f"{filename}-web-resources",
        'image',
        basename,
    ])
    return f'src="{new_path}"'


def replace_html_links(content):
    """Replace all .html link references with .docx extensions."""
    content = re.sub(
        r'href="([^"]*\.html)"',
        lambda m: f'href="{m.group(1).replace(".html", ".docx")}"',
        content
    )
    return content


def process_file(input_path, output_path, resource_dir, reference_doc,
                 lua_filters, extra_resource_paths=None):
    """Process a single XHTML file: clean, transform, and convert to DOCX via Pandoc.

    Args:
        input_path: Path to the source XHTML file.
        output_path: Path for the output DOCX file.
        resource_dir: Base directory for image resources.
        reference_doc: Path to the Pandoc reference DOCX template.
        lua_filters: List of Lua filter paths to apply during conversion.
        extra_resource_paths: Additional directories for Pandoc --resource-path.
    """
    with open(input_path, 'r', encoding='utf-8') as file:
        content = file.read()

    filename = os.path.splitext(os.path.basename(input_path))[0]

    # Pipeline: clean -> replace styles -> merge headings -> footnotes -> fix links
    content = clean_tags(content)
    content = replace_tags(content)
    content = merge_headings(content)
    content = process_footnotes(content)
    content = replace_html_links(content)

    # Fix image paths
    content = re.sub(
        r'src="(.*?)"',
        lambda m: fix_image_path(m, filename, resource_dir),
        content
    )

    # Collect and insert footnotes
    footnotes = re.findall(
        r'<li id="fn:(\d+)">(.*?)<a href="#fnref:\1" class="footnote-back">↩</a></li>',
        content, re.DOTALL
    )
    footnotes_content = "\n".join([
        f'<li id="fn:{num}">{text} <a href="#fnref:{num}" class="footnote-back">↩</a></li>'
        for num, text in footnotes
    ])
    content = content.replace('{footnotes}', footnotes_content)

    # Write to a temporary file and convert via Pandoc
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.html', encoding='utf-8', delete=False
    ) as tmp:
        tmp.write(content)
        temp_path = tmp.name

    try:
        command = [
            'pandoc', temp_path, '-o', output_path,
            '--reference-doc', reference_doc,
        ]

        # Add all Lua filters
        for lua_filter in lua_filters:
            if os.path.exists(lua_filter):
                command.append(f'--lua-filter={lua_filter}')

        # Build resource path: include resource_dir, image subdirectory, and extras
        resource_paths = [resource_dir]
        image_subdir = os.path.join(resource_dir, f"{filename}-web-resources", 'image')
        if os.path.isdir(image_subdir):
            resource_paths.append(image_subdir)
        if extra_resource_paths:
            resource_paths.extend(extra_resource_paths)
        command.extend(['--resource-path', os.pathsep.join(resource_paths)])

        max_retries = 2
        timeout_seconds = 300
        for attempt in range(1, max_retries + 1):
            try:
                start_t = time.time()
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=timeout_seconds,
                )
                elapsed = time.time() - start_t
                if result.returncode != 0:
                    logger.error(
                        'Pandoc error for %s (exit code %d, %.1fs):',
                        os.path.basename(input_path), result.returncode, elapsed,
                    )
                    if result.stderr:
                        logger.error('  %s', result.stderr.strip())
                    if attempt < max_retries:
                        logger.warning('  Retrying (%d/%d)...', attempt, max_retries)
                        time.sleep(1)
                        continue
                    return False

                logger.info(
                    '  Converted: %s -> %s (exit code 0, %.1fs)',
                    os.path.basename(input_path), os.path.basename(output_path), elapsed,
                )
                return True

            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_t
                logger.error(
                    'Pandoc timed out after %ds for %s',
                    timeout_seconds, os.path.basename(input_path),
                )
                if attempt < max_retries:
                    logger.warning('  Retrying (%d/%d)...', attempt, max_retries)
                    time.sleep(1)
                    continue
                return False

        return False

    finally:
        # Always clean up the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    """Main entry point: process all XHTML files in the configured directory."""
    config = load_config()

    input_dir = config['paths']['xhtml_dir']
    output_dir = config['paths']['docx_dir']
    resource_dir = config['paths']['xhtml_dir']
    reference_doc = config['reference_doc']

    # Collect all configured Lua filters
    lua_filters = []
    for key in ('lua_filter', 'lua_filter_endnotes', 'lua_filter_links'):
        path = config.get(key, '')
        if path:
            lua_filters.append(path)

    if not os.path.exists(input_dir):
        logger.error('input directory not found: %s', input_dir)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    xhtml_files = [f for f in os.listdir(input_dir) if f.endswith('.xhtml')]
    if not xhtml_files:
        logger.warning('No .xhtml files found in %s', input_dir)
        return

    logger.info('Processing %d XHTML file(s)...', len(xhtml_files))

    success = 0
    errors = 0

    for filename in xhtml_files:
        input_path = os.path.join(input_dir, filename)
        output_filename = os.path.splitext(filename)[0] + '.docx'
        output_path = os.path.join(output_dir, output_filename)

        if process_file(input_path, output_path, resource_dir, reference_doc, lua_filters):
            success += 1
        else:
            errors += 1

    logger.info('Conversion completed: %d successful, %d errors', success, errors)

    if errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
