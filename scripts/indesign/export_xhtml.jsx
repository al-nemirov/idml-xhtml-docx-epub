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

// Load shared utility functions
#include "indesign_utils.jsx"

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
      exportAndProcess(file, outputFolderPath, standardFont);
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
