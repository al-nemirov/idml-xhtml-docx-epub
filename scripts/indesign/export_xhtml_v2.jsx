/**
 * Export InDesign Documents to XHTML (v2 - Recursive)
 *
 * Recursively searches for .indd files in a selected folder and all subfolders.
 * For each file found:
 * 1. Exports to IDML format
 * 2. Replaces missing fonts with a standard fallback
 * 3. Exports to HTML and converts to XHTML
 * 4. Processes paragraph styles into semantic heading tags
 * 5. Converts InDesign footnotes to standard endnote format
 *
 * This is the recursive version of export_xhtml.jsx, useful when
 * InDesign files are organized in subdirectories.
 *
 * Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
 */

// Load shared utility functions
#include "indesign_utils.jsx"

// Prompt user to select input and output folders
var folderPath = Folder.selectDialog("Select the root folder containing .indd files (will search recursively)");
if (!folderPath) { exit(); }

var outputFolderPath = Folder.selectDialog("Select the output folder for XHTML files");
if (!outputFolderPath) { exit(); }
outputFolderPath = outputFolderPath.fsName + "/";

var standardFont = "Arial"; // Fallback font for missing fonts

/**
 * Recursively find all .indd files in a folder and its subfolders.
 */
function findInddFiles(folder) {
  var files = [];
  var subfolders = folder.getFiles();

  for (var i = 0; i < subfolders.length; i++) {
    var subfolder = subfolders[i];
    if (subfolder instanceof File && subfolder.name.match(/\.indd$/i)) {
      files.push(subfolder);
    } else if (subfolder instanceof Folder) {
      files = files.concat(findInddFiles(subfolder));
    }
  }
  return files;
}

var folder = new Folder(folderPath);
var files = findInddFiles(folder);

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
