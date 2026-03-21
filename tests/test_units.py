"""
Unit Tests

Tests for individual functions in the book conversion pipeline.
Covers path handling, heading merging, tag cleaning, footnote processing,
image extraction, annotation truncation, ISBN normalization, and
negative/edge cases.

Usage:
    python -m pytest tests/test_units.py -v
    python tests/test_units.py
"""

import os
import sys
import json
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.xhtml_to_docx import (
    clean_tags,
    replace_tags,
    merge_headings,
    process_footnotes,
    fix_image_path,
    replace_html_links,
)
from scripts.process_images import extract_images_from_content, insert_images_into_content
from scripts.process_footnotes import (
    extract_footnotes_from_content,
    _extract_sentence,
    _find_word_in_content,
)
from scripts.build_structure import parse_xhtml_to_elements
from scripts.utils.file_utils import atomic_json_write, load_json, backup_file

# docx_to_epub imports pandas which may not be available in all environments
try:
    from scripts.docx_to_epub import shorten_annotation, _normalize_isbn
    HAS_PANDAS = True
except (ImportError, ValueError):
    HAS_PANDAS = False


# ═══════════════════════════════════════════════════════════════════════
# xhtml_to_docx: clean_tags
# ═══════════════════════════════════════════════════════════════════════

class TestCleanTags(unittest.TestCase):
    """Tests for InDesign CharOverride tag removal."""

    def test_removes_charoverride_span(self):
        html = '<span class="CharOverride-3">hello</span>'
        self.assertEqual(clean_tags(html), 'hello')

    def test_removes_charoverride_paragraph(self):
        html = '<p class="CharOverride-1"><span>text</span></p>'
        self.assertEqual(clean_tags(html), 'text')

    def test_removes_empty_paragraphs(self):
        html = '<p>   </p>'
        self.assertEqual(clean_tags(html), '')

    def test_preserves_normal_tags(self):
        html = '<p class="Body">Some body text.</p>'
        self.assertEqual(clean_tags(html), '<p class="Body">Some body text.</p>')


# ═══════════════════════════════════════════════════════════════════════
# xhtml_to_docx: replace_tags
# ═══════════════════════════════════════════════════════════════════════

class TestReplaceTags(unittest.TestCase):
    """Tests for InDesign style-to-heading mapping."""

    def test_part_becomes_h2(self):
        html = '<p class="Part">Introduction</p>'
        result = replace_tags(html)
        self.assertIn('<h2>', result)
        self.assertIn('Introduction', result)

    def test_chapter_becomes_h3(self):
        html = '<p class="Chapter">Chapter One</p>'
        result = replace_tags(html)
        self.assertIn('<h3>', result)

    def test_blockquote_mapping(self):
        html = '<p class="Blockquote">A famous quote.</p>'
        result = replace_tags(html)
        self.assertIn('<blockquote>', result)

    def test_unmapped_class_unchanged(self):
        html = '<p class="Body">Regular text</p>'
        result = replace_tags(html)
        self.assertEqual(result, html)


# ═══════════════════════════════════════════════════════════════════════
# xhtml_to_docx: merge_headings
# ═══════════════════════════════════════════════════════════════════════

class TestMergeHeadings(unittest.TestCase):
    """Tests for consecutive heading merger."""

    def test_merges_same_level_headings(self):
        html = '<h2>Part One</h2><h2>Title</h2>'
        result = merge_headings(html)
        self.assertEqual(result.count('<h2>'), 1)
        self.assertIn('Part One', result)
        self.assertIn('Title', result)

    def test_does_not_merge_different_levels(self):
        html = '<h2>Main</h2><h3>Sub</h3>'
        result = merge_headings(html)
        self.assertIn('<h2>', result)
        self.assertIn('<h3>', result)

    def test_merges_with_whitespace_between(self):
        html = '<h3>A</h3>\n  \n<h3>B</h3>'
        result = merge_headings(html)
        self.assertEqual(result.count('<h3>'), 1)
        self.assertIn('A', result)
        self.assertIn('B', result)

    def test_no_headings_passthrough(self):
        html = '<p>Just a paragraph.</p>'
        result = merge_headings(html)
        self.assertEqual(result, html)

    def test_single_heading_unchanged(self):
        html = '<h1>Only One</h1>'
        result = merge_headings(html)
        self.assertIn('<h1>', result)
        self.assertIn('Only One', result)


# ═══════════════════════════════════════════════════════════════════════
# xhtml_to_docx: fix_image_path
# ═══════════════════════════════════════════════════════════════════════

class TestFixImagePath(unittest.TestCase):
    """Tests for image path correction."""

    def test_basic_path_fix(self):
        import re
        content = 'src="images/old/photo.jpg"'
        match = re.search(r'src="(.*?)"', content)
        result = fix_image_path(match, 'chapter1', 'resources')
        self.assertEqual(result, 'src="resources/chapter1-web-resources/image/photo.jpg"')

    def test_windows_backslash_normalization(self):
        import re
        content = 'src="images\\nested\\pic.png"'
        match = re.search(r'src="(.*?)"', content)
        result = fix_image_path(match, 'intro', 'data\\xhtml')
        self.assertIn('data/xhtml', result)
        self.assertNotIn('\\', result)


# ═══════════════════════════════════════════════════════════════════════
# xhtml_to_docx: replace_html_links
# ═══════════════════════════════════════════════════════════════════════

class TestReplaceHtmlLinks(unittest.TestCase):
    """Tests for .html -> .docx link replacement."""

    def test_replaces_html_extension(self):
        html = 'href="chapter1.html"'
        result = replace_html_links(html)
        self.assertIn('chapter1.docx', result)

    def test_preserves_non_html_links(self):
        html = 'href="styles.css"'
        result = replace_html_links(html)
        self.assertEqual(result, html)


# ═══════════════════════════════════════════════════════════════════════
# docx_to_epub: shorten_annotation
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(HAS_PANDAS, 'pandas not available')
class TestShortenAnnotation(unittest.TestCase):
    """Tests for annotation truncation."""

    def test_short_text_unchanged(self):
        text = 'A brief annotation.'
        self.assertEqual(shorten_annotation(text), text)

    def test_long_text_truncated_at_period(self):
        text = 'A' * 100 + '. ' + 'B' * 200 + '. End.'
        result = shorten_annotation(text)
        self.assertLessEqual(len(result), 251)
        self.assertTrue(result.endswith('.'))

    def test_none_input_returns_empty(self):
        self.assertEqual(shorten_annotation(None), '')

    def test_non_string_returns_empty(self):
        self.assertEqual(shorten_annotation(12345), '')

    def test_empty_string_returns_empty(self):
        self.assertEqual(shorten_annotation(''), '')


# ═══════════════════════════════════════════════════════════════════════
# docx_to_epub: _normalize_isbn
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(HAS_PANDAS, 'pandas not available')
class TestNormalizeIsbn(unittest.TestCase):
    """Tests for ISBN normalization (Excel float -> string)."""

    def test_strips_trailing_dot_zero(self):
        self.assertEqual(_normalize_isbn('9781234567890.0'), '9781234567890')

    def test_normal_string_unchanged(self):
        self.assertEqual(_normalize_isbn('978-1-234-5'), '978-1-234-5')

    def test_integer_input(self):
        self.assertEqual(_normalize_isbn(9781234567890), '9781234567890')

    def test_whitespace_stripped(self):
        self.assertEqual(_normalize_isbn('  123.0  '), '123')


# ═══════════════════════════════════════════════════════════════════════
# process_images: extract & insert round-trip
# ═══════════════════════════════════════════════════════════════════════

class TestImageExtractInsert(unittest.TestCase):
    """Tests for image extraction and re-insertion."""

    def test_extract_creates_anchors(self):
        html = '<p>Before</p><img src="pic.png" alt="Photo" /><p>After</p>'
        modified, images = extract_images_from_content(html, 'test.xhtml')
        self.assertEqual(len(images), 1)
        self.assertIn('{{img_1}}', modified)
        self.assertNotIn('<img', modified)
        self.assertEqual(images[0]['src'], 'pic.png')
        self.assertEqual(images[0]['alt'], 'Photo')

    def test_extract_no_images(self):
        html = '<p>No images here.</p>'
        modified, images = extract_images_from_content(html, 'test.xhtml')
        self.assertEqual(len(images), 0)
        self.assertEqual(modified, html)

    def test_insert_restores_images(self):
        images = [{
            'id': 1,
            'src': 'pic.png',
            'alt': 'Photo',
            'width': '',
            'height': '',
            'class': '',
            'approved': True,
        }]
        content = '<p>Before</p>{{img_1}}<p>After</p>'
        result, stats = insert_images_into_content(content, images, 'test.xhtml')
        self.assertIn('src="pic.png"', result)
        self.assertNotIn('{{img_1}}', result)
        self.assertEqual(stats['replaced'], 1)

    def test_insert_skips_rejected_images(self):
        images = [{
            'id': 1,
            'src': 'pic.png',
            'alt': '',
            'width': '',
            'height': '',
            'class': '',
            'approved': False,
        }]
        content = '{{img_1}}'
        result, stats = insert_images_into_content(content, images, 'test.xhtml')
        self.assertNotIn('{{img_1}}', result)
        self.assertNotIn('<img', result)
        self.assertEqual(stats['skipped'], 1)


# ═══════════════════════════════════════════════════════════════════════
# process_footnotes: helper functions
# ═══════════════════════════════════════════════════════════════════════

class TestFootnoteHelpers(unittest.TestCase):
    """Tests for footnote utility functions."""

    def test_extract_sentence_finds_word(self):
        text = 'First sentence. The important word here. Last sentence.'
        result = _extract_sentence(text, 'important')
        self.assertIn('important', result)

    def test_extract_sentence_empty_word(self):
        text = 'Some text here.'
        result = _extract_sentence(text, '')
        self.assertEqual(result, text)

    def test_extract_sentence_empty_text(self):
        result = _extract_sentence('', 'word')
        self.assertEqual(result, '')

    def test_find_word_in_content_case_insensitive(self):
        self.assertTrue(_find_word_in_content('<p>Hello World</p>', 'hello'))
        self.assertTrue(_find_word_in_content('<p>Hello World</p>', 'WORLD'))

    def test_find_word_not_present(self):
        self.assertFalse(_find_word_in_content('<p>Hello</p>', 'goodbye'))

    def test_find_word_empty(self):
        self.assertFalse(_find_word_in_content('<p>text</p>', ''))


# ═══════════════════════════════════════════════════════════════════════
# process_footnotes: extract
# ═══════════════════════════════════════════════════════════════════════

class TestFootnoteExtract(unittest.TestCase):
    """Tests for footnote body extraction."""

    def test_extract_footnote_body(self):
        html = (
            '<p>Some text.</p>'
            '<div id="footnote-1" class="_idFootnote">'
            '<p class="_idFootnoteBody">Footnote text here.</p>'
            '</div>'
        )
        modified, footnotes = extract_footnotes_from_content(html, 'test.xhtml')
        bodies = [fn for fn in footnotes if fn['type'] == 'body']
        self.assertEqual(len(bodies), 1)
        self.assertIn('{{footnote_1}}', modified)
        self.assertNotIn('_idFootnote', modified)

    def test_extract_no_footnotes(self):
        html = '<p>Plain text without footnotes.</p>'
        modified, footnotes = extract_footnotes_from_content(html, 'test.xhtml')
        self.assertEqual(len(footnotes), 0)
        self.assertEqual(modified, html)


# ═══════════════════════════════════════════════════════════════════════
# build_structure: parse_xhtml_to_elements
# ═══════════════════════════════════════════════════════════════════════

class TestParseXhtmlToElements(unittest.TestCase):
    """Tests for XHTML -> structured elements parsing."""

    def test_extracts_headings(self):
        html = '<h1>Title</h1><h2>Chapter</h2>'
        elements = parse_xhtml_to_elements(html, 'test.xhtml')
        headings = [e for e in elements if e['type'] == 'heading']
        self.assertEqual(len(headings), 2)
        self.assertEqual(headings[0]['level'], 1)
        self.assertEqual(headings[1]['level'], 2)

    def test_extracts_paragraphs(self):
        html = '<p>First paragraph.</p><p>Second paragraph.</p>'
        elements = parse_xhtml_to_elements(html, 'test.xhtml')
        paragraphs = [e for e in elements if e['type'] == 'paragraph']
        self.assertEqual(len(paragraphs), 2)

    def test_extracts_images(self):
        html = '<img src="photo.jpg" alt="A photo" />'
        elements = parse_xhtml_to_elements(html, 'test.xhtml')
        images = [e for e in elements if e['type'] == 'image']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['src'], 'photo.jpg')

    def test_skips_empty_paragraphs(self):
        html = '<p>  </p><p>Real text.</p>'
        elements = parse_xhtml_to_elements(html, 'test.xhtml')
        paragraphs = [e for e in elements if e['type'] == 'paragraph']
        self.assertEqual(len(paragraphs), 1)

    def test_extracts_image_anchors(self):
        html = '<p>Before {{img_5}} after.</p>'
        elements = parse_xhtml_to_elements(html, 'test.xhtml')
        anchors = [e for e in elements if e['type'] == 'image_anchor']
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]['anchor_id'], 5)

    def test_empty_input(self):
        elements = parse_xhtml_to_elements('', 'empty.xhtml')
        self.assertEqual(len(elements), 0)


# ═══════════════════════════════════════════════════════════════════════
# file_utils: atomic_json_write, load_json, backup_file
# ═══════════════════════════════════════════════════════════════════════

class TestFileUtils(unittest.TestCase):
    """Tests for file utility functions."""

    def test_atomic_write_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'test.json')
            data = {'key': 'value', 'number': 42}
            ok = atomic_json_write(path, data)
            self.assertTrue(ok)
            loaded = load_json(path)
            self.assertEqual(loaded, data)

    def test_load_json_missing_file(self):
        result = load_json('/nonexistent/path/to/file.json')
        self.assertIsNone(result)

    def test_load_json_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            f.write('this is not json{{{')
            path = f.name
        try:
            result = load_json(path)
            self.assertIsNone(result)
        finally:
            os.remove(path)

    def test_backup_file_creates_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.path.join(tmp, 'original.txt')
            with open(original, 'w') as f:
                f.write('content')
            backup_dir = os.path.join(tmp, 'backups')
            backup_path = backup_file(original, backup_dir=backup_dir)
            self.assertIsNotNone(backup_path)
            self.assertTrue(os.path.exists(backup_path))

    def test_backup_file_nonexistent(self):
        result = backup_file('/nonexistent/file.txt')
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════
# Negative / edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestNegativeCases(unittest.TestCase):
    """Negative and edge case tests."""

    def test_clean_tags_empty_string(self):
        self.assertEqual(clean_tags(''), '')

    def test_replace_tags_empty_string(self):
        self.assertEqual(replace_tags(''), '')

    def test_merge_headings_empty_string(self):
        self.assertEqual(merge_headings(''), '')

    def test_replace_html_links_no_links(self):
        html = '<p>No links at all.</p>'
        self.assertEqual(replace_html_links(html), html)

    def test_process_footnotes_no_footnotes(self):
        html = '<p>Plain paragraph.</p>'
        result = process_footnotes(html)
        self.assertEqual(result, html)

    def test_insert_images_missing_anchor_id(self):
        """Inserting images when content has no matching anchors."""
        images = [{'id': 99, 'src': 'x.png', 'alt': '', 'width': '', 'height': '',
                   'class': '', 'approved': True}]
        content = '<p>No anchors here.</p>'
        result, stats = insert_images_into_content(content, images, 'test.xhtml')
        self.assertEqual(result, content)
        self.assertEqual(stats['replaced'], 0)

    def test_extract_images_malformed_img(self):
        """An img tag with no src should still be extracted."""
        html = '<img alt="no-source" />'
        modified, images = extract_images_from_content(html, 'test.xhtml')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['src'], '')

    def test_parse_elements_malformed_heading(self):
        """Unclosed heading should not crash the parser."""
        html = '<h2>Unclosed heading'
        # Should not raise
        elements = parse_xhtml_to_elements(html, 'test.xhtml')
        self.assertIsInstance(elements, list)


if __name__ == '__main__':
    unittest.main()
