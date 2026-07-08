-- Link Sphinx/Python-domain roles emitted from Python docstrings.
--
-- Quartodoc preserves roles such as :mod:`aria_nbv.data_handling` in generated
-- qmd. VS Code/Pylance displays those roles well, but Quarto treats them as
-- ordinary text unless a filter rewrites them. This filter resolves the local
-- roles against Quartodoc's generated objects.json inventory.

local role_aliases = {
  ["mod"] = "module",
  ["module"] = "module",
  ["py:mod"] = "module",
  ["py:module"] = "module",
  ["class"] = "class",
  ["py:class"] = "class",
  ["func"] = "function",
  ["function"] = "function",
  ["py:func"] = "function",
  ["py:function"] = "function",
  ["meth"] = "function",
  ["method"] = "function",
  ["py:meth"] = "function",
  ["py:method"] = "function",
  ["attr"] = "attribute",
  ["attribute"] = "attribute",
  ["py:attr"] = "attribute",
  ["py:attribute"] = "attribute",
  ["data"] = "attribute",
  ["py:data"] = "attribute",
  ["const"] = "attribute",
  ["py:const"] = "attribute",
}

local inventory = nil
local by_role_and_name = {}
local by_role_and_short_name = {}
local current_context = nil
local output_dir = nil
local output_file = nil

local function starts_with(value, prefix)
  return value:sub(1, #prefix) == prefix
end

local function split_path(path)
  local parts = {}
  for part in path:gmatch("[^/]+") do
    if part ~= "" and part ~= "." then
      table.insert(parts, part)
    end
  end
  return parts
end

local function dirname(path)
  return path:match("^(.*)/[^/]*$") or ""
end

local function strip_prefix(value, prefix)
  if starts_with(value, prefix) then
    return value:sub(#prefix + 1)
  end
  return value
end

local function relative_href(uri)
  if output_dir == nil or output_file == nil then
    return uri
  end

  local path, anchor = uri:match("^([^#]*)(#?.*)$")
  local page_dir = strip_prefix(dirname(output_file), output_dir .. "/")
  local from_parts = split_path(page_dir)
  local to_parts = split_path(path)

  while #from_parts > 0 and #to_parts > 0 and from_parts[1] == to_parts[1] do
    table.remove(from_parts, 1)
    table.remove(to_parts, 1)
  end

  local rel_parts = {}
  for _ = 1, #from_parts do
    table.insert(rel_parts, "..")
  end
  for _, part in ipairs(to_parts) do
    table.insert(rel_parts, part)
  end

  local rel = table.concat(rel_parts, "/")
  if rel == "" then
    rel = path:match("[^/]+$") or path
  end
  return rel .. (anchor or "")
end

local function short_name(name)
  return name:match("([^%.]+)$") or name
end

local function common_prefix_len(a, b)
  if a == nil or b == nil then
    return 0
  end

  local score = 0
  local a_parts = split_path(a:gsub("%.", "/"))
  local b_parts = split_path(b:gsub("%.", "/"))
  local n = math.min(#a_parts, #b_parts)
  for i = 1, n do
    if a_parts[i] ~= b_parts[i] then
      break
    end
    score = score + 1
  end
  return score
end

local function add_item(item)
  if item.name == nil or item.role == nil or item.uri == nil then
    return
  end

  local key = item.role .. "\0" .. item.name
  by_role_and_name[key] = item

  local short_key = item.role .. "\0" .. short_name(item.name)
  by_role_and_short_name[short_key] = by_role_and_short_name[short_key] or {}
  table.insert(by_role_and_short_name[short_key], item)
end

local function load_inventory()
  if inventory ~= nil then
    return
  end

  inventory = {}
  local project_dir = quarto.project.directory or "."
  local inventory_path = project_dir .. "/objects.json"
  local file = io.open(inventory_path, "r")
  if file == nil then
    io.stderr:write("[aria-python-roles] objects.json not found; Python roles will remain literal.\n")
    return
  end

  local raw = file:read("*a")
  file:close()
  local decoded = pandoc.json.decode(raw)
  inventory = decoded.items or {}

  for _, item in ipairs(inventory) do
    add_item(item)
  end
end

local function context_prefixes()
  local prefixes = {}
  if current_context == nil then
    return prefixes
  end

  local parts = {}
  for part in current_context:gmatch("[^%.]+") do
    table.insert(parts, part)
  end

  while #parts > 0 do
    table.insert(prefixes, table.concat(parts, "."))
    table.remove(parts)
  end

  return prefixes
end

local function parse_target(raw)
  local explicit_text, target = raw:match("^(.+)%s+<([^>]+)>$")
  target = target or raw

  if starts_with(target, "!") then
    return nil
  end

  local shorten = false
  if starts_with(target, "~") then
    shorten = true
    target = target:sub(2)
  end

  if starts_with(target, ".") then
    target = target:sub(2)
  end

  return {
    target = target,
    explicit_text = explicit_text,
    shorten = shorten,
  }
end

local function resolve_exact(role, target)
  return by_role_and_name[role .. "\0" .. target]
end

local function resolve_by_suffix(role, target)
  local matches = {}
  local suffix = "." .. target
  for _, item in ipairs(inventory) do
    if item.role == role and (item.name == target or item.name:sub(-#suffix) == suffix) then
      table.insert(matches, item)
    end
  end

  if #matches == 1 then
    return matches[1]
  end

  local best = nil
  local best_score = -1
  local tied = false
  for _, item in ipairs(matches) do
    local score = common_prefix_len(current_context, item.name)
    if score > best_score then
      best = item
      best_score = score
      tied = false
    elseif score == best_score then
      tied = true
    end
  end

  if best ~= nil and not tied then
    return best
  end
  return nil
end

local function resolve_item(role, target)
  local exact = resolve_exact(role, target)
  if exact ~= nil then
    return exact
  end

  for _, prefix in ipairs(context_prefixes()) do
    local item = resolve_exact(role, prefix .. "." .. target)
    if item ~= nil then
      return item
    end
  end

  local short_matches = by_role_and_short_name[role .. "\0" .. target]
  if short_matches ~= nil and #short_matches == 1 then
    return short_matches[1]
  end

  return resolve_by_suffix(role, target)
end

local function parse_role_token(text)
  local role_token = text:match("^:([A-Za-z0-9_:%+%-]+):$")
  if role_token == nil then
    return nil
  end

  if starts_with(role_token, "external") then
    return nil
  end

  return role_aliases[role_token]
end

local function link_for(role, code)
  local parsed = parse_target(code.text)
  if parsed == nil then
    return nil
  end

  local item = resolve_item(role, parsed.target)
  if item == nil then
    return nil
  end

  local display = parsed.explicit_text or code.text
  if parsed.shorten and parsed.explicit_text == nil then
    display = short_name(parsed.target)
  end

  return pandoc.Link({ pandoc.Code(display) }, relative_href(item.uri))
end

local function rewrite_inlines(inlines)
  load_inventory()
  local rewritten = {}
  local index = 1

  while index <= #inlines do
    local current = inlines[index]
    local next_inline = inlines[index + 1]

    if current.t == "Str" and next_inline ~= nil and next_inline.t == "Code" then
      local role = parse_role_token(current.text)
      if role ~= nil then
        local link = link_for(role, next_inline)
        if link ~= nil then
          table.insert(rewritten, link)
          index = index + 2
        else
          table.insert(rewritten, current)
          index = index + 1
        end
      else
        table.insert(rewritten, current)
        index = index + 1
      end
    else
      table.insert(rewritten, current)
      index = index + 1
    end
  end

  return rewritten
end

local function find_current_context(doc)
  for _, block in ipairs(doc.blocks) do
    if block.t == "Header" and block.identifier ~= nil and starts_with(block.identifier, "aria_nbv.") then
      current_context = block.identifier
      return
    end
  end
end

function Pandoc(doc)
  output_dir = quarto.project.output_directory
  output_file = quarto.doc.output_file
  find_current_context(doc)
  load_inventory()
  return doc:walk({
    Inlines = rewrite_inlines,
  })
end
