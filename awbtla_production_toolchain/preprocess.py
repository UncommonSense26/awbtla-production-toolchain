#!/usr/bin/env python3
"""Convert the archival AWBTLA Markdown master into the intermediate Pandoc Markdown used by the print and EPUB builds.

Only structural markup is converted. Manuscript text is never altered:
- known structural headings become Pandoc headings/divs with attributes;
- note markers [^n] become [n]{.awb-ref};
- endnote entries "n. text" become ::: {.awb-note n=...} divs;
- display math $$...$$ is re-broken into aligned/gathered lines (layout markup only).
The archival master file itself is never written.
"""
import json, re, sys

class StructureError(Exception):
    pass

def _mathlen(s):
    """Approximate the visible width of a math expression, in average text characters."""
    t = s
    rel = r'\\(to|xrightarrow|longrightarrow|Rightarrow|iff|leq|geq|le|ge|wedge|in)(?![a-zA-Z])'
    arrows = len(re.findall(rel, t)) + t.count('=')
    t = re.sub(rel, ' ', t)
    t = re.sub(r'\\begin\{[a-z*]+\}|\\end\{[a-z*]+\}', '', t)
    t = re.sub(r'\\(text|mathrm|operatorname)\{([^{}]*)\}', r'\2', t)
    t = re.sub(r'\\(mathcal|mathbf|mathit|underline|overline|big|Big|bigg|Bigg|left|right|displaystyle)(?![a-zA-Z])', '', t)
    t = re.sub(r'\\qquad', '    ', t)
    t = re.sub(r'\\quad', '  ', t)
    t = re.sub(r'\\[a-zA-Z]+', 'x', t)
    t = re.sub(r'[{}^_&]|\\[,;:! ]|\\\\', '', t)
    return len(t) + 2 * arrows

def _toplevel_split(s, pattern):
    """Split s at top-level (brace depth 0, environment depth 0) occurrences of the regex pattern.
    Returns the list of pieces; the separator is kept at the start of the following piece."""
    pieces, depth, env, last, i = [], 0, 0, 0, 0
    rx = re.compile(pattern)
    while i < len(s):
        c = s[i]
        if c == '\\' and s.startswith('\\begin{', i):
            env += 1; i = s.index('}', i) + 1; continue
        if c == '\\' and s.startswith('\\end{', i):
            env -= 1; i = s.index('}', i) + 1; continue
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        elif depth == 0 and env == 0:
            m = rx.match(s, i)
            if m and i > last:
                pieces.append(s[last:i]); last = i; i = m.end(); continue
        if c == '\\':
            m = re.match(r'\\[a-zA-Z]+|\\.', s[i:])
            i += len(m.group(0)) if m else 1; continue
        i += 1
    pieces.append(s[last:])
    return [p for p in pieces if p.strip()]

BREAK_BEFORE = r'\\(to|xrightarrow|longrightarrow|Rightarrow|iff|leq|geq|le|ge|wedge)(?![a-zA-Z])|=(?!=)'

def break_display(tex, limit=60):
    """Return layout-broken TeX for one display. Text content is unchanged; only line structure is added."""
    body = tex.strip()
    lines = [body]
    m = re.fullmatch(r'\\begin\{aligned\}(.*)\\end\{aligned\}', body, flags=re.S)
    if m:
        lines = [re.sub(r'^\s*&', '', x).strip() for x in re.split(r'\\\\', m.group(1)) if x.strip()]
    out_rel = []
    for line in lines:
        for rel in _toplevel_split(line, r'\\qquad'):
            rel = re.sub(r'^\\qquad', '', rel).strip()
            if _mathlen(rel) <= limit:
                out_rel.append(rel); continue
            segs = _toplevel_split(rel, BREAK_BEFORE)
            rows, cur = [], ''
            for seg in segs:
                if cur and _mathlen(cur + seg) > limit:
                    rows.append(cur); cur = seg
                else:
                    cur += seg
            rows.append(cur)
            if len(rows) == 1:
                out_rel.append(rel)
            else:
                out_rel.append('\\begin{aligned}[t]&' + rows[0].strip() + ''.join('\\\\&\\qquad ' + r.strip() for r in rows[1:]) + '\\end{aligned}')
    if len(out_rel) == 1:
        return out_rel[0]
    return '\\begin{gathered}' + '\\\\'.join(out_rel) + '\\end{gathered}'

def attr(**kw):
    parts = []
    for k, v in kw.items():
        if v is None: continue
        if k == 'id': parts.append('#' + v)
        elif k == 'cls': parts.extend('.' + c for c in v.split())
        else: parts.append('%s="%s"' % (k, str(v).replace('"', '&quot;')))
    return '{' + ' '.join(parts) + '}'

def convert(text, config):
    """Return (intermediate_markdown, structure_dict)."""
    L = text.split('\n')
    st = {'chapters': [], 'parts': [], 'specials': [], 'articles': [], 'notes': [], 'markers': [], 'models': [], 'displays': 0}
    if len(L) < 3 or not L[0].startswith('# ') or not L[2].strip():
        raise StructureError('title block not found in the first three lines')
    st['source_title'] = L[0][2:].strip(); st['source_author'] = L[2].strip()
    heads = config.get('running_heads', {})
    chap_heads = {int(k): v for k, v in heads.get('chapters', {}).items()}
    part_heads = heads.get('parts', {})
    expected_titles = {int(k): v for k, v in config.get('expected_chapter_titles', {}).items()}
    out = []
    i = 3
    region = 'front'
    part_verso = ''
    def nxt(j):
        j += 1
        while j < len(L) and not L[j].strip(): j += 1
        return j
    while i < len(L):
        raw = L[i]; s = raw.strip()
        # ---- structural headings ----
        if s == '# LEGAL NOTICE AND FREEDOM OF EXPRESSION AUTHORITIES':
            region = 'legal'; st['specials'].append('legal')
            out.append('# ' + s[2:] + ' ' + attr(id='legal-notice', cls='awb-special', kind='legal', open='recto', verso='Legal Notice', recto='Legal Notice', bm='Legal Notice')); i += 1; continue
        if s == '### PREFACE':
            region = 'preface'; st['specials'].append('preface')
            out.append('# PREFACE ' + attr(id='preface', cls='awb-special', kind='preface', open='recto', verso='Preface', recto='Preface', bm='Preface')); i += 1; continue
        if s in ('### PROLOGUE', '### INTRODUCTION'):
            j = nxt(i); t = L[j].strip()
            if not t.startswith('### '): raise StructureError('missing title after ' + s)
            kind = s[4:].lower(); region = kind; st['specials'].append(kind)
            rect = heads.get(kind + '_recto', t[4:].title())
            out.append('# ' + t[4:] + ' ' + attr(id=kind, cls='awb-special', kind=kind, label=s[4:], open='recto', verso=s[4:].title(), recto=rect, bm=s[4:].title()))
            i = j + 1; continue
        m = re.fullmatch(r'### (PART ([IVX]+): (.+))', s)
        if m:
            region = 'part'; num = m.group(2)
            part_verso = part_heads.get(num, m.group(1).title())
            st['parts'].append({'num': num, 'title': m.group(1)})
            out.append('# ' + m.group(1) + ' ' + attr(id='part-' + num.lower(), cls='awb-part', verso=part_verso, bm=part_verso))
            i += 1; continue
        m = re.fullmatch(r'### CHAPTER (\d+)', s)
        if m:
            n = int(m.group(1)); j = nxt(i); t = L[j].strip()
            if not t.startswith('### '): raise StructureError('missing title after CHAPTER %d' % n)
            title = t[4:]
            if expected_titles and expected_titles.get(n) not in (None, title):
                raise StructureError('chapter %d title differs from the configured expected title (running-head map may be stale): %r' % (n, title))
            rh = chap_heads.get(n)
            if not rh: raise StructureError('no running head configured for chapter %d' % n)
            st['chapters'].append({'n': n, 'title': title, 'recto': rh})
            region = 'chapter'
            out.append('## ' + title + ' ' + attr(id='chapter-%d' % n, cls='awb-chapter', label='CHAPTER %d' % n, recto=rh, verso=part_verso, bm='Chapter %d: %s' % (n, rh.split(': ', 1)[-1])))
            i = j + 1; continue
        if s == '## CONSTITUTION OF THE WORLD PEOPLES UNION':
            region = 'constitution'; st['specials'].append('constitution')
            out.append('# ' + s[3:] + ' ' + attr(id='constitution', cls='awb-special', kind='constitution', open='recto', verso=heads.get('constitution_verso', 'Constitution'), recto=heads.get('constitution_verso', 'Constitution'), bm='Constitution'))
            i += 1; continue
        if s.startswith("# PEOPLE'S PETITION"):
            region = 'petition'; st['specials'].append('petition')
            out.append('# ' + s[2:] + ' ' + attr(id='petition', cls='awb-special', kind='petition', open='recto', verso="People's Petition", recto="People's Petition", bm="People's Petition"))
            i += 1; continue
        if s == '## INDEX OF FORMAL MODELS':
            region = 'index'; st['specials'].append('index')
            out.append('# ' + s[3:] + ' ' + attr(id='index-of-formal-models', cls='awb-special', kind='index', open='next', verso='Index of Formal Models', recto='Index of Formal Models', bm='Index of Formal Models'))
            out.append(''); out.append('::: {.awb-index}'); i += 1
            while i < len(L) and not L[i].strip().startswith('## '):
                out.append(L[i]); i += 1
            out.append(':::'); continue
        if s == '## ENDNOTES':
            region = 'notes'; st['specials'].append('notes')
            out.append('# ENDNOTES ' + attr(id='endnotes', cls='awb-special', kind='notes', open='recto', verso='Endnotes', recto='Endnotes', bm='Endnotes'))
            i += 1; continue
        if s == '## DEDICATION':
            region = 'dedication'; st['specials'].append('dedication')
            out.append('# DEDICATION ' + attr(id='dedication', cls='awb-special', kind='dedication', open='recto', bm='Dedication'))
            out.append(''); out.append('::: {.awb-dedication}'); i += 1
            while i < len(L):
                out.append(L[i]); i += 1
            out.append(':::'); continue
        # ---- region-specific content ----
        if region == 'notes':
            mm = re.match(r'^(\d+)\. (.*)$', raw)
            if mm:
                st['notes'].append(int(mm.group(1)))
                out.append('::: ' + attr(cls='awb-note', n=mm.group(1)))
                out.append(mm.group(2)); out.append(':::'); i += 1; continue
            if raw.startswith('## '):
                out.append('## ' + raw[3:].strip() + ' ' + attr(cls='awb-notesec unlisted')); i += 1; continue
        if region == 'constitution':
            if s == 'THE CONSTITUTION OF THE WORLD PEOPLES UNION':
                out.append('::: {.awb-const-title}'); out.append(s); out.append(':::'); i += 1; continue
            if s == 'PREAMBLE':
                out.append('## PREAMBLE ' + attr(cls='awb-article unlisted', recto='Constitution: Preamble', bm='Preamble')); i += 1; continue
            mm = re.fullmatch(r'ARTICLE ([IVXL]+)', s)
            if mm:
                j = nxt(i); t = L[j].strip()
                st['articles'].append(mm.group(1))
                out.append('## ' + t + ' ' + attr(cls='awb-article unlisted', label=s, recto='Constitution: Article ' + mm.group(1), bm='Article %s: %s' % (mm.group(1), t.title())))
                i = j + 1; continue
        if region == 'petition':
            if raw.startswith('## '):
                out.append('::: {.awb-petition-subtitle}'); out.append(raw[3:].strip()); out.append(':::'); i += 1; continue
            if raw.startswith('### '):
                out.append('## ' + raw[4:].strip() + ' ' + attr(cls='awb-sub unlisted')); i += 1; continue
            if s.startswith('|') and s.endswith('|'):
                out.append('::: {.awb-signature-table}')
                while i < len(L) and L[i].strip().startswith('|'):
                    out.append(L[i]); i += 1
                out.append(':::'); continue
        if region in ('legal', 'preface', 'prologue', 'introduction', 'chapter', 'part'):
            if raw.startswith('## ') or raw.startswith('### ') or raw.startswith('#### '):
                lvl = min(len(raw) - len(raw.lstrip('#')), 4)
                out.append('#' * max(lvl, 2) + ' ' + raw.lstrip('#').strip() + ' ' + attr(cls='awb-sub unlisted')); i += 1; continue
            if s == '* * *':
                out.append('::: {.awb-scene}'); out.append('\\* \\* \\*'); out.append(':::'); i += 1; continue
        if raw.startswith('#'):
            raise StructureError('unrecognized heading at line %d: %r' % (i + 1, raw[:60]))
        # ---- display math ----
        if s.startswith('$$'):
            buf = raw
            while not (buf.strip().endswith('$$') and len(buf.strip()) > 2):
                i += 1; buf += '\n' + L[i]
            inner = buf.strip()[2:-2]
            st['displays'] += 1
            out.append('$$' + break_display(inner, config.get('formula_break_chars', 60)) + '$$'); i += 1; continue
        mm = re.match(r'^\*\*Formal Model: (TM-\d+)', s)
        if mm: st['models'].append(mm.group(1))
        # ---- note markers ----
        def ref(m):
            st['markers'].append(int(m.group(1))); return '[%s]{.awb-ref}' % m.group(1)
        out.append(re.sub(r'\[\^(\d+)\]', ref, raw)); i += 1
    return '\n'.join(out) + '\n', st

if __name__ == '__main__':
    import yaml
    src, cfg, dst, sj = sys.argv[1:5]
    md, st = convert(open(src, encoding='utf-8').read(), yaml.safe_load(open(cfg, encoding='utf-8')))
    open(dst, 'w', encoding='utf-8').write(md)
    json.dump(st, open(sj, 'w'), indent=1)
    print('chapters', len(st['chapters']), 'notes', len(st['notes']), 'markers', len(st['markers']), 'displays', st['displays'])
