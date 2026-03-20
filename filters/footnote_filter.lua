-- Footnote Filter for Pandoc
--
-- Extracts footnote numbers and text from InDesign-style spans,
-- then reformats them as clean paragraphs with the footnote number
-- followed by the footnote text content.

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
              footnote_number = subsubchild.content[1].text
            elseif subsubchild.t == "Str" then
              table.insert(text_parts, subsubchild.text)
            end
          end
        elseif subchild.t == "Str" then
          table.insert(text_parts, subchild.text)
        end
      end
      -- Create a new paragraph with the footnote number and text
      table.insert(new_content, pandoc.Para({
        pandoc.Str(footnote_number .. " "),
        pandoc.Span(text_parts, {class = "CharOverride-15"})
      }))
    else
      table.insert(new_content, child)
    end
  end
  el.content = new_content
  return el
end
