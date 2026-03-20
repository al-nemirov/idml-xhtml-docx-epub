/**
 * Shared InDesign utility functions for XHTML export scripts.
 *
 * This file contains common functions used by both export_xhtml.jsx and
 * export_xhtml_v2.jsx to avoid code duplication.
 *
 * Usage: #include "indesign_utils.jsx" at the top of your script.
 */

/**
 * Escape special regex characters in a string to use it as a literal pattern.
 * Without this, paragraph content containing characters like (, ), [, ], etc.
 * would break the regex replacement.
 */
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Replace missing fonts in the document with the specified fallback font.
 * Uses FontStatus.NOT_AVAILABLE instead of comparing to undefined.
 */
function replaceMissingFonts(doc, replacementFont) {
  var allFonts = doc.fonts.everyItem().getElements();
  $.writeln("Total fonts: " + allFonts.length);

  for (var i = 0; i < allFonts.length; i++) {
    try {
      var font = allFonts[i];
      if (font.status === FontStatus.NOT_AVAILABLE || font.status === FontStatus.SUBSTITUTED) {
        $.writeln(
          "Replacing missing font: " +
            font.name +
            " (status: " + font.status + ")" +
            " with " +
            replacementFont
        );
        font.appliedFont = replacementFont;
      }
    } catch (e) {
      // Skip fonts that cannot be replaced
    }
  }
}

/**
 * Replace all fonts in text frames with the standard fallback font.
 */
function replaceAllFonts(doc, standardFont) {
  var textFrames = doc.textFrames;
  $.writeln("Number of text frames: " + textFrames.length);
  for (var j = 0; j < textFrames.length; j++) {
    var textFrame = textFrames[j];
    try {
      var paragraphs = textFrame.paragraphs;
      for (var k = 0; k < paragraphs.length; k++) {
        paragraphs[k].appliedFont = standardFont;
      }
    } catch (e) {
      // Skip frames that cannot be processed
    }
  }
}

/**
 * Map InDesign paragraph styles to semantic HTML heading tags.
 * Uses escapeRegex() to safely handle special characters in paragraph content.
 */
function processParagraphStyles(doc, xhtmlContent) {
  var paragraphs = doc.stories.everyItem().paragraphs.everyItem().getElements();

  for (var i = 0; i < paragraphs.length; i++) {
    var paragraph = paragraphs[i];
    var style = paragraph.appliedParagraphStyle.name;

    var tag;
    switch (style) {
      case "Heading 1":
        tag = "h1";
        break;
      case "Heading 2":
        tag = "h2";
        break;
      case "Heading 3":
        tag = "h3";
        break;
      case "Heading 4":
        tag = "h4";
        break;
      case "Heading 5":
        tag = "h5";
        break;
      case "Heading 6":
        tag = "h6";
        break;
      default:
        tag = "p";
        break;
    }

    // Skip default paragraph style — no replacement needed
    if (tag === "p") continue;

    var content = paragraph.contents;
    if (!content || content.length === 0) continue;

    // Use escaped content for safe regex matching
    var htmlTag = "<" + tag + ">" + content + "</" + tag + ">";
    var regex = new RegExp(escapeRegex(content), "g");
    xhtmlContent = xhtmlContent.replace(regex, htmlTag);
  }

  return xhtmlContent;
}

/**
 * Convert InDesign footnote markup to standard endnote format.
 */
function processFootnotes(xhtmlContent) {
  // Replace footnote href references with standard endnote anchors
  xhtmlContent = xhtmlContent.replace(/href="[^#]*#footnote-(\d+)"/g, 'href="#fn:$1"');

  // Convert footnote body divs to endnote format
  xhtmlContent = xhtmlContent.replace(
    /<div id="footnote-(\d+)" class="_idFootnote">\s*<p[^>]*>(.*?)<\/p>\s*<\/div>/g,
    '<div id="fn:$1" class="footnote">\n<p>$2</p>\n</div>'
  );

  // Convert footnote reference spans to endnote reference links
  xhtmlContent = xhtmlContent.replace(
    /<span[^>]*><a[^>]*href="[^>]*#footnote-(\d+)">(\d+)<\/a><\/span>/g,
    '<a href="#fn:$1" class="footnote-ref">$2</a>'
  );

  // Remove unnecessary file:// URL prefixes (not affecting images)
  xhtmlContent = xhtmlContent.replace(/file:\/\/\/.+?#fn:/g, "#fn:");

  return xhtmlContent;
}

/**
 * Export a document to IDML, open the IDML, replace fonts, export to XHTML.
 * Returns the processed XHTML content string, or null on error.
 */
function exportAndProcess(file, outputFolderPath, standardFont) {
  // 1. Export as IDML (intermediate markup format)
  var idmlFile = new File(file.fsName.replace(".indd", ".idml"));
  var sourceDoc = app.open(file);
  sourceDoc.exportFile(ExportFormat.INDESIGN_MARKUP, idmlFile);
  sourceDoc.close(SaveOptions.NO);

  // 2. Open the IDML file
  var doc = app.open(idmlFile);

  // Replace missing fonts and apply standard font
  replaceMissingFonts(doc, standardFont);
  replaceAllFonts(doc, standardFont);

  // Export to HTML (will be converted to XHTML)
  var fileName = file.name.replace(".indd", ".xhtml");
  var xhtmlExportFile = new File(outputFolderPath + fileName);
  $.writeln("Exporting to: " + xhtmlExportFile.fsName);
  doc.exportFile(ExportFormat.HTML, xhtmlExportFile);
  $.writeln("Export completed to: " + xhtmlExportFile.fsName);

  // Read the exported HTML content
  xhtmlExportFile.open("r");
  var htmlContent = xhtmlExportFile.read();
  xhtmlExportFile.close();

  // Convert to XHTML by adding the XML namespace
  var xhtmlContent = htmlContent.replace(
    /<!DOCTYPE html>/,
    '<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml">'
  );

  // Map paragraph styles to semantic heading tags
  xhtmlContent = processParagraphStyles(doc, xhtmlContent);

  // Process InDesign footnotes into endnote format
  xhtmlContent = processFootnotes(xhtmlContent);

  // Save the processed XHTML
  xhtmlExportFile.open("w");
  xhtmlExportFile.write(xhtmlContent);
  xhtmlExportFile.close();

  // Close the document and remove the temporary IDML file
  doc.close(SaveOptions.NO);
  idmlFile.remove();
  $.writeln("File closed: " + file.name);

  return xhtmlContent;
}
