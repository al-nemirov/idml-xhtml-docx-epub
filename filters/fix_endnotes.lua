-- Fix Endnotes Filter for Pandoc
--
-- Adjusts heading levels for footnote sections and converts
-- endnote divs into properly linked footnote references using
-- the #footnote- anchor format for backlinks.

local endnotes = {}

function Header(el)
  if el.level == 1 and el.identifier:match("^fn") then
    el.level = 2
  end
  return el
end

function Div(el)
  if el.classes:includes("endnotes") then
    for i, item in ipairs(el.content) do
      if item.t == "Para" and #item.content > 0 and item.content[1].t == "Span" then
        local id = item.content[1].attributes and item.content[1].attributes.id or ""
        if id ~= "" then
          local unique_id = id .. "_" .. i
          endnotes[unique_id] = el.content[i]
          el.content[i] = pandoc.Null()
        end
      end
    end
  end
  return el
end

function Note(el)
  if #el.content == 0 then return el end

  local first_block = el.content[1]
  local id = first_block.identifier or ""
  local unique_id = id .. "_" .. (el.number or 0)

  if endnotes[unique_id] then
    local backlink_url = "#footnote-" .. id .. "-backlink"
    local link = pandoc.Link(
      endnotes[unique_id].content,
      backlink_url
    )
    return pandoc.Div({pandoc.Para({link})}, {class = "endnote"})
  else
    return el
  end
end
