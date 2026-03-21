-- Fix Links for EPUB Filter
--
-- Replaces .docx file extensions in link targets with .epub
-- to ensure cross-references work correctly in the final EPUB output.

function Link(el)
  el.target = string.gsub(el.target, "%.docx$", ".epub")
  return el
end
