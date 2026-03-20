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
      if item.t == "Para" and item.content[1].t == "Span" then
        local id = item.content[1].attributes.id
        local unique_id = id .. "_" .. i
        endnotes[unique_id] = el.content[i]
        el.content[i] = pandoc.Null()
      end
    end
  end
  return el
end

function Note(el)
  local id = el.content[1].identifier
  local unique_id = id .. "_" .. el.number
  if endnotes[unique_id] then
    -- Use #footnote- format for the backlink reference
    local backlink = pandoc.Link{t = "Link", content = endnotes[unique_id].content, attributes = {url = "#footnote-" .. id .. "-backlink"}}
    return pandoc.Div({backlink}, {class="endnote"})
  else
    return el
  end
end
