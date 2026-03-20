/**
 * Export InDesign Documents to XHTML
 *
 * Batch-processes all .indd files in a selected folder:
 * 1. Exports each document to IDML (intermediate format)
 * 2. Replaces missing fonts with a standard fallback font
 * 3. Exports to HTML and converts to XHTML format
 * 4. Processes paragraph styles into semantic heading tags
 * 5. Converts InDesign footnotes to standard endnote format
 *
 * Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
 */

// Prompt user to select input and output folders
var folderPath = Folder.selectDialog("Select the folder containing .indd files");
if (!folderPath) { exit(); }

var outputFolderPath = Folder.selectDialog("Select the output folder for XHTML files");
if (!outputFolderPath) { exit(); }
outputFolderPath = outputFolderPath.fsName + "/";

var standardFont = "Arial"; // Fallback font for missing fonts

var folder = new Folder(folderPath);
var files = folder.getFiles("*.indd");

app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;

try {
  $.writeln("Number of files found: " + files.length);

  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    $.writeln("Processing file: " + file.name);

    try {
      // 1. Export as IDML (intermediate markup format)
      var idmlFile = new File(file.fsName.replace(".indd", ".idml"));
      var sourceDoc = app.open(file);
      sourceDoc.save(idmlFile, false, "", true);

      // 2. Open the IDML file
      var doc = app.open(idmlFile);

      // Replace missing fonts with the standard fallback
      replaceMissingFonts(doc, standardFont);

      // Replace all fonts with the standard font at the paragraph level
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
    } catch (e) {
      $.writeln("Error processing file: " + file.name + " - " + e);
    }
  }
} catch (e) {
  $.writeln("Error: " + e);
} finally {
  app.scriptPreferences.userInteractionLevel = UserInteractionLevels.INTERACT_WITH_ALL;
  $.writeln("Script completed.");
}

/**
 * Replace missing fonts in the document with the specified fallback font.
 */
function replaceMissingFonts(doc, replacementFont) {
  var allFonts = doc.fonts.everyItem().getElements();
  $.writeln("Total fonts: " + allFonts.length);

  for (var i = 0; i < allFonts.length; i++) {
    try {
      var font = allFonts[i];
      if (font.status == undefined) {
        $.writeln(
          "Replacing missing font: " +
            font.name +
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
 * Map InDesign paragraph styles to semantic HTML heading tags.
 */
function processParagraphStyles(doc, xhtmlContent) {
  var paragraphStyles = doc.paragraphStyles;
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

    var content = paragraph.contents;
    var htmlTag = '<' + tag + '>' + content + '</' + tag + '>';
    var regex = new RegExp(content, "g");
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
  xhtmlContent = xhtmlContent.replace(/file:\/\/\/.+?#fn:/g, '#fn:');

  return xhtmlContent;
}
