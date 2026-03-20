/**
 * Export to Fixed-Layout HTML (FXL)
 *
 * Exports the active InDesign document to Fixed-Layout HTML format.
 * The output file is saved alongside the original document with
 * an .html extension.
 *
 * Originally based on a script by Keith Gilbert (Gilbert Consulting).
 *
 * Part of the book conversion pipeline: InDesign -> XHTML -> DOCX -> EPUB
 */

Main();

function Main() {
    // Check whether any InDesign documents are open
    if (app.documents.length > 0) {
        var myDoc = app.activeDocument;
        // Build the output filename from the document path
        var myDocName = decodeURI(myDoc.fullName);
        var myDocBaseName = myDocName.substring(0, myDocName.lastIndexOf("."));
        // Configure FXL export preferences
        with (myDoc.htmlFXLExportPreferences) {
            epubPageRangeFormat = PageRangeFormat.EXPORT_ALL_PAGES;
            // To export a specific range, uncomment the following:
            // epubPageRangeFormat = PageRangeFormat.EXPORT_PAGE_RANGE;
            // epubPageRange = "1-2";
        }
        // Export the document to FXL HTML
        myDoc.exportFile(ExportFormat.HTMLFXL, new File(myDocBaseName + ".html"), true);
    }
    else {
        // No documents are open
        alert("No InDesign documents are open. Please open a document and try again.");
    }
}
