-- AWBTLA structural filter. Modes: latex (print), epub3 (ebook), plain (text-integrity QA).
-- Converts structural markup only; manuscript text is passed through unchanged.
local MODE = FORMAT:match('latex') and 'latex' or (FORMAT:match('epub') and 'epub' or 'plain')

local function tex_inlines(inl)
  local s = pandoc.write(pandoc.Pandoc({pandoc.Plain(inl)}), 'latex'):gsub('\n', ' ')
  return s
end
local function tex_str(s)
  if s == nil or s == '' then return '' end
  local doc = pandoc.read(s, 'markdown+smart')
  if #doc.blocks == 0 then return '' end
  return tex_inlines(doc.blocks[1].content)
end
local function stringify(x) return pandoc.utils.stringify(x) end
local function raw(s) return pandoc.RawBlock('latex', s) end
local function rawi(s) return pandoc.RawInline('latex', s) end

-- ---------- inline protection (latex only) ----------
local function protect_str(el)
  local t = el.text
  if t:match('^_+[%p]*$') and #t:match('^_+') >= 6 then
    local n = #t:match('^_+'); local rest = t:sub(n + 1)
    local out = {rawi(string.format('\\awbblank{%d}', n))}
    if rest ~= '' then table.insert(out, pandoc.Str(rest)) end
    return out
  end
  local core, trail = t:match('^(.-)([%.,;:%)%]]*)$')
  if core:match('^https?://') or core:match('^10%.%d%d%d%d+/') then
    local url = core:gsub('([#%%{}\\])', '\\%1')
    local out = {rawi('\\url{' .. url .. '}')}
    if trail ~= '' then table.insert(out, pandoc.Str(trail)) end
    return out
  end
  if core:match('%d') and core:match('%-') and not core:match('^%-') then
    local lead, body = core:match('^([%(%[]*)(.*)$')
    local out = {}
    if lead ~= '' then table.insert(out, pandoc.Str(lead)) end
    table.insert(out, rawi('\\mbox{' .. tex_inlines({pandoc.Str(body)}) .. '}'))
    if trail ~= '' then table.insert(out, pandoc.Str(trail)) end
    return out
  end
  return nil
end

local TIE_AFTER = {['§']=true, ['§§']=true, ['No.']=true, ['art.']=true, ['arts.']=true, ['amend.']=true, ['Fed.']=true, ['Reg.']=true, ['DIN']=true, ['DINs']=true, ['Case']=true}
local REPORTERS = {['U.S.']=true, ['U.S.C.']=true, ['S.']=true, ['Ct.']=true, ['F.']=true, ['F.2d']=true, ['F.3d']=true, ['F.4th']=true, ['So.']=true, ['So.2d']=true, ['So.3d']=true, ['Stat.']=true, ['FCC']=true, ['Rcd']=true, ['L.']=true, ['Ed.']=true}
local function tie_inlines(inl)
  local out = pandoc.List()
  for i = 1, #inl do
    local el = inl[i]
    if el.t == 'Space' and i > 1 and i < #inl then
      local p, n = inl[i-1], inl[i+1]
      local ps = p.t == 'Str' and p.text or ''
      local ns = n.t == 'Str' and n.text or ''
      if TIE_AFTER[ps] or (REPORTERS[ns] and ps:match('^%d')) or (REPORTERS[ps] and ns:match('^%d')) then
        out:insert(rawi('~'))
      else out:insert(el) end
    else out:insert(el) end
  end
  return out
end

-- ---------- helpers for blocks ----------
local function starts_strong(blk, prefix)
  if blk.t ~= 'Para' or #blk.content == 0 or blk.content[1].t ~= 'Strong' then return false end
  return stringify(blk.content[1]):sub(1, #prefix) == prefix
end

local function header_latex(h)
  local a = h.attributes; local c = h.classes
  local title = tex_inlines(h.content)
  if c:includes('awb-special') then
    return raw(string.format('\\awbSpecial{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}', a.open or 'recto', a.kind or '', tex_str(a.label), title, tex_str(a.verso), tex_str(a.recto), stringify(pandoc.read(a.bm or '', 'markdown+smart').blocks), h.identifier))
  elseif c:includes('awb-part') then
    return raw(string.format('\\awbPart{%s}{%s}{%s}{%s}', title, tex_str(a.verso), stringify(pandoc.read(a.bm or '', 'markdown+smart').blocks), h.identifier))
  elseif c:includes('awb-chapter') then
    return raw(string.format('\\awbChapter{%s}{%s}{%s}{%s}{%s}{%s}', tex_str(a.label), title, tex_str(a.verso), tex_str(a.recto), stringify(pandoc.read(a.bm or '', 'markdown+smart').blocks), h.identifier))
  elseif c:includes('awb-article') then
    return raw(string.format('\\awbArticle{%s}{%s}{%s}{%s}', tex_str(a.label), title, tex_str(a.recto), stringify(pandoc.read(a.bm or '', 'markdown+smart').blocks)))
  elseif c:includes('awb-notesec') then
    return raw(string.format('\\awbNoteSection{%s}', title))
  else
    return raw(string.format('\\awbSubhead{%d}{%s}', h.level, title))
  end
end

local function signature_table_latex(tbl)
  local heads = {}
  for _, cell in ipairs(tbl.head.rows[1].cells) do table.insert(heads, tex_inlines(pandoc.utils.blocks_to_inlines(cell.contents))) end
  local nrows = 0
  local nums = {}
  for _, body in ipairs(tbl.bodies) do for _, row in ipairs(body.body) do nrows = nrows + 1; table.insert(nums, stringify(row.cells[1].contents)) end end
  local s = {'\\awbSigBegin\\begin{tabularx}{\\linewidth}{|N|W|W|D|Q|Q|}\\hline'}
  table.insert(s, table.concat(heads, ' & ') .. ' \\\\ \\hline')
  for _, n in ipairs(nums) do table.insert(s, n .. ' & & & & & \\awbrowstrut \\\\ \\hline') end
  table.insert(s, '\\end{tabularx}\\awbSigEnd')
  return raw(table.concat(s, '\n'))
end

-- ---------- per-mode block processing ----------
local function process_latex(blocks)
  local out = pandoc.List(); local in_model = false; local noindent_next = false
  for i, b in ipairs(blocks) do
    if b.t == 'Header' then
      out:insert(header_latex(b)); noindent_next = false
    elseif b.t == 'Div' and b.classes:includes('awb-note') then
      local inl = pandoc.utils.blocks_to_inlines(b.content)
      out:insert(raw(string.format('\\awbnote{%s}{%s}', b.attributes.n, tex_inlines(tie_inlines(inl)))))
    elseif b.t == 'Div' and b.classes:includes('awb-scene') then
      out:insert(raw('\\awbscene')); noindent_next = true
    elseif b.t == 'Div' and b.classes:includes('awb-signature-table') then
      for _, x in ipairs(b.content) do if x.t == 'Table' then out:insert(signature_table_latex(x)) end end
    elseif b.t == 'Div' and b.classes:includes('awb-const-title') then
      out:insert(raw('\\awbConstTitle{' .. tex_inlines(pandoc.utils.blocks_to_inlines(b.content)) .. '}'))
    elseif b.t == 'Div' and b.classes:includes('awb-petition-subtitle') then
      out:insert(raw('\\awbPetitionSubtitle{' .. tex_inlines(pandoc.utils.blocks_to_inlines(b.content)) .. '}'))
    elseif b.t == 'Div' and (b.classes:includes('awb-index') or b.classes:includes('awb-dedication')) then
      local env = b.classes:includes('awb-index') and 'awbindex' or 'awbdedication'
      out:insert(raw('\\begin{' .. env .. '}')); for _, x in ipairs(b.content) do out:insert(x) end; out:insert(raw('\\end{' .. env .. '}'))
    elseif b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Math' and b.content[1].mathtype == 'DisplayMath' then
      out:insert(raw('\\awbdisplay{' .. b.content[1].text .. '}')); noindent_next = true
    else
      local is_label, is_where, is_prompt = starts_strong(b, 'Formal Model: '), starts_strong(b, 'Where:'), starts_strong(b, 'Common Sense Prompt:')
      if is_label then out:insert(raw('\\begin{awbmodel}')); in_model = true end
      if in_model and is_where then out:insert(raw('\\awbmodelkey')) end
      if noindent_next and b.t == 'Para' then b.content:insert(1, rawi('\\noindent ')) end
      noindent_next = (b.t == 'BulletList' or b.t == 'OrderedList')
      out:insert(b)
      if in_model and is_prompt then out:insert(raw('\\end{awbmodel}')); in_model = false; noindent_next = true end
    end
  end
  if in_model then error('AWB-STRUCTURE: formal model block without a Common Sense Prompt') end
  return out
end

local function label_prefix(h)
  if h.attributes.label and h.attributes.label ~= '' then
    local lab = pandoc.read(h.attributes.label, 'markdown+smart').blocks[1].content
    local c = pandoc.List(lab); c:insert(pandoc.LineBreak()); c:extend(h.content); h.content = c
  end
  return h
end

local function process_epub(blocks)
  local out = pandoc.List(); local model = nil
  for _, b in ipairs(blocks) do
    if b.t == 'Header' then
      b = label_prefix(b)
      local keep = {}
      for k, v in pairs(b.attributes) do if k == 'kind' then keep['data-kind'] = v end end
      b.attributes = keep
      if b.classes:includes('awb-special') or b.classes:includes('awb-part') then b.level = 1
      elseif b.classes:includes('awb-chapter') then b.level = 2 end
      out:insert(b)
    elseif b.t == 'Div' and b.classes:includes('awb-note') then
      local n = b.attributes.n
      local para = b.content[1]
      local back = pandoc.Link({pandoc.Str(n .. '.')}, '#ref-' .. n, '', {role = 'doc-backlink'})
      local inl = pandoc.List({back, pandoc.Space()}); inl:extend(para.content)
      out:insert(pandoc.Div({pandoc.Para(inl)}, {id = 'note-' .. n, class = 'awb-note'}))
    else
      if starts_strong(b, 'Formal Model: ') then model = pandoc.List() end
      if model then model:insert(b) else out:insert(b) end
      if model and starts_strong(b, 'Common Sense Prompt:') then out:insert(pandoc.Div(model, {class = 'awb-model'})); model = nil end
    end
  end
  return out
end

local function process_plain(blocks)
  local out = pandoc.List()
  for _, b in ipairs(blocks) do
    if b.t == 'Header' then
      b = label_prefix(b); out:insert(pandoc.Para(b.content))
    elseif b.t == 'Div' and b.classes:includes('awb-note') then
      local inl = pandoc.List({pandoc.Str(b.attributes.n .. '.'), pandoc.Space()}); inl:extend(pandoc.utils.blocks_to_inlines(b.content))
      out:insert(pandoc.Para(inl))
    elseif b.t == 'Div' and b.classes:includes('awb-signature-table') then
      out:insert(pandoc.Para({pandoc.Str('⟦TABLE⟧')}))
    elseif b.t == 'BulletList' then
      for _, item in ipairs(b.content) do
        local inl = pandoc.List({pandoc.Str('•'), pandoc.Space()}); inl:extend(pandoc.utils.blocks_to_inlines(item)); out:insert(pandoc.Para(inl))
      end
    else out:insert(b) end
  end
  return out
end

function Pandoc(doc)
  -- inline passes first
  if MODE == 'latex' then
    doc = doc:walk({Inlines = function(inl) return tie_inlines(inl) end})
    doc = doc:walk({Str = protect_str})
    doc = doc:walk({Span = function(sp)
      if sp.classes:includes('awb-ref') then return rawi('\\awbref{' .. stringify(sp) .. '}') end end})
  elseif MODE == 'epub' then
    doc = doc:walk({Span = function(sp)
      if sp.classes:includes('awb-ref') then local n = stringify(sp)
        return pandoc.Link({pandoc.Superscript({pandoc.Str(n)})}, '#note-' .. n, '', {id = 'ref-' .. n, role = 'doc-noteref'}) end end})
  else
    doc = doc:walk({Str = function(s) local u = s.text:match('^(_+)') if u and #u >= 6 then return pandoc.Str('⟦BLANK⟧' .. s.text:sub(#u + 1)) end end})
    doc = doc:walk({Span = function(sp) if sp.classes:includes('awb-ref') then return pandoc.Str(stringify(sp)) end end,
                    Math = function(m) return pandoc.Str(m.mathtype == 'DisplayMath' and ' ⟦MATH⟧ ' or '⟦M⟧') end})
  end
  if MODE == 'latex' then doc.blocks = process_latex(doc.blocks)
  elseif MODE == 'epub' then doc.blocks = process_epub(doc.blocks)
  else doc.blocks = process_plain(doc.blocks) end
  return doc
end
