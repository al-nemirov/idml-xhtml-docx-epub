-- Footnote Filter for Pandoc
--
-- Extracts footnote numbers and text from InDesign-style spans,
-- then reformats them as clean paragraphs with the footnote number
-- followed by the footnote text content.
--
-- Handles CharOverride-* classes from InDesign export, converting
-- them into simple numbered footnote paragraphs.

function Note(el)
  -- Extract the footnote number and text, build a new paragraph
  local new_content = {}
  for _, child in ipairs(el.content) do
    if child.t == "Para" then
      local footnote_number = ""
      local text_parts = {}
      for _, subchild in ipairs(child.content) do
        if subchild.t == "Span" and subchild.content then
          for _, subsubchild in ipairs(subchild.content) do
            if subsubchild.t == "Link" then
              -- Extract the footnote number from the link text
              footnote_number = pandoc.utils.stringify(subsubchild.content)
            elseif subsubchild.t == "Str" then
              table.insert(text_parts, pandoc.Str(subsubchild.text))
            elseif subsubchild.t == "Space" then
              table.insert(text_parts, pandoc.Space())
            end
          end
        elseif subchild.t == "Str" then
          table.insert(text_parts, pandoc.Str(subchild.text))
        elseif subchild.t == "Space" then
          table.insert(text_parts, pandoc.Space())
        end
      end
      -- Create a new paragraph with the footnote number and text
      local content_inlines = {}
      table.insert(content_inlines, pandoc.Str(footnote_number .. " "))
      for _, part in ipairs(text_parts) do
        table.insert(content_inlines, part)
      end
      table.insert(new_content, pandoc.Para(content_inlines))
    else
      table.insert(new_content, child)
    end
  end
  el.content = new_content
  return el
end
