"""Layout QA on the typeset print PDF."""
import re, subprocess
from pypdf import PdfReader

PT = 72.0

def page_words(pdf):
    html = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True, check=True).stdout
    pages = []
    for pg in re.split(r'<page ', html)[1:]:
        w = [(float(a), float(b), float(c), float(d), t) for a, b, c, d, t in
             re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', pg)]
        pages.append(w)
    return pages

def page_texts(pdf, crop=None):
    cmd = ['pdftotext']
    if crop:
        x, y, w, h = crop; cmd += ['-raw', '-x', str(int(x)), '-y', str(int(y)), '-W', str(int(w)), '-H', str(int(h))]
    t = subprocess.run(cmd + [pdf, '-'], capture_output=True, text=True, check=True).stdout
    pg = t.split('\f')
    return pg[:-1] if pg and not pg[-1].strip() else pg

def check_pdf(pdf, log_text, cfg, geo, st, source_emdashes, heads, fallback):
    fails, warns, stats = [], [], {}
    r = PdfReader(pdf); n = len(r.pages); stats['pages'] = n
    W, H = geo['trim_w'] * PT, geo['trim_h'] * PT
    for i, p in enumerate(r.pages):
        mb = p.mediabox
        if abs(float(mb.width) - W) > 0.5 or abs(float(mb.height) - H) > 0.5:
            fails.append('page %d is %.1f x %.1f pt, expected %.1f x %.1f' % (i + 1, float(mb.width), float(mb.height), W, H)); break
    words = page_words(pdf)
    inner, outer = geo['inner'] * PT, geo['outer'] * PT
    safe = 0.25 * PT
    over = []; clipped = []; headover = []
    for i, ws in enumerate(words):
        recto = (i % 2 == 0)
        left = inner if recto else outer
        right = W - (outer if recto else inner)
        for x0, y0, x1, y1, t in ws:
            if x0 < 0 or x1 > W or y0 < 0 or y1 > H: clipped.append((i + 1, t))
            elif x0 < left - 3.0 or x1 > right + 3.0:   # 3pt allows microtype margin protrusion
                (headover if y0 < geo['top'] * PT - 4 else over).append((i + 1, round(x0, 1), round(x1, 1), t))
            if y0 < safe or y1 > H - safe: clipped.append((i + 1, 'outside KDP safe zone: ' + t))
    if clipped: fails.append('clipped or unsafe text: %s' % clipped[:5])
    if over: fails.append('content outside the text measure on %d words, e.g. %s' % (len(over), over[:5]))
    if headover: fails.append('running-head overflow: %s' % headover[:5])
    for tag in ('AWB-FORMULA-OVERFLOW', 'AWB-HEAD-OVERFLOW'):
        c = log_text.count(tag)
        if c: fails.append('%s reported %d time(s) by the typesetter' % (tag, c))
    stats['formulas_scaled'] = log_text.count('AWB-FORMULA-SCALED')
    ofull = re.findall(r'Overfull \\hbox \(([\d.]+)pt too wide\)', log_text)
    big = [x for x in ofull if float(x) > 1.0]
    stats['overfull_hboxes_over_1pt'] = len(big)
    if big: fails.append('%d overfull line(s) wider than 1pt' % len(big))
    if 'Missing character' in log_text: fails.append('missing glyph(s) reported in the log: %d' % log_text.count('Missing character'))
    texts = page_texts(pdf)
    full = '\n'.join(texts)
    if '\ufffd' in full: fails.append('replacement characters in extracted text')
    ligs = sum(full.count(c) for c in '\ufb00\ufb01\ufb02\ufb03\ufb04')
    stats['ligature_codepoints_in_extraction'] = ligs
    if ligs: fails.append('ligatures extract as ligature code points (%d); extraction is not ligature-safe' % ligs)
    em = full.count('\u2014'); stats['em_dashes'] = em
    if em != source_emdashes: fails.append('em dashes in PDF (%d) differ from source (%d)' % (em, source_emdashes))
    # blank pages and folios
    labels = r.page_labels
    blank = [i + 1 for i, t in enumerate(texts) if not t.strip()]
    folio_only = [i + 1 for i, t in enumerate(texts) if t.strip() and re.fullmatch(r'\s*([0-9]+|[ivxlcdm]+)\s*', t)]
    stats['blank_pages'] = len(blank)
    if folio_only: fails.append('folio printed on an otherwise blank page: %s' % folio_only[:10])
    seen = {}; missing = []
    for i, t in enumerate(texts):
        lines = [l.strip() for l in t.split('\n') if l.strip()]
        if not lines: continue
        cand = [l for l in (lines[-1:] + lines[:1]) if re.fullmatch(r'[0-9]+|[ivxlcdm]+', l)]
        if cand:
            if cand[0] != labels[i]: fails.append('page %d prints folio %s but its page label is %s' % (i + 1, cand[0], labels[i]))
            if cand[0] in seen: fails.append('duplicate folio %s on pages %d and %d' % (cand[0], seen[cand[0]], i + 1))
            seen[cand[0]] = i + 1
        else:
            missing.append(i + 1)
    stats['pages_without_printed_folio'] = len(missing)
    # headings at page bottoms: a heading may not sit in the last two lines of a full page
    hs = set(h.strip() for h in heads if h.strip())
    bottoms = []
    lim = H - geo['bottom'] * PT - 2 * geo.get('baseline', 14)
    for i, t in enumerate(texts):
        lines = [l.strip() for l in t.split('\n') if l.strip()]
        body = [l for l in lines if not re.fullmatch(r'[0-9]+|[ivxlcdm]+', l)]
        bw = [w for w in words[i] if geo['top'] * PT - 2 < w[1] < H - geo['bottom'] * PT + 2] if i < len(words) else []
        full_page = bool(bw) and max(w[3] for w in bw) > lim
        for l in body[-2:]:
            if l in hs and full_page: bottoms.append((i + 1, l))
    if bottoms: fails.append('heading in the last two lines of a page: %s' % bottoms[:5])
    splits = []
    for i, t in enumerate(texts):
        for m in re.finditer(r'Formal Model: (TM-\d+)', t):
            after = t[m.end():]
            if 'Common Sense Prompt:' not in after: splits.append((i + 1, m.group(1)))
    if splits: fails.append('formal-model block split across pages: %s' % splits[:5])
    stats['formal_model_labels'] = len(re.findall(r'Formal Model: TM-\d+', full))
    # fonts
    pf = subprocess.run(['pdffonts', pdf], capture_output=True, text=True).stdout.splitlines()[2:]
    notemb = [l.split()[0] for l in pf if len(l.split()) > 5 and l.split()[-5] != 'yes']
    names = ' '.join(l.split()[0] for l in pf)
    stats['fonts'] = sorted(set(re.sub(r'^[A-Z]{6}\+', '', l.split()[0]) for l in pf if l.split()))
    if notemb: fails.append('fonts not embedded: %s' % notemb)
    if not fallback:
        if 'SourceSerif4' not in names: fails.append('Source Serif 4 not found in the PDF')
        if 'STIXTwoMath' not in names and st['displays']: fails.append('STIX Two Math not found in the PDF')
    # line geometry for hyphenation and widow/orphan checks (the engine enforces penalties of 10000; these checks audit the result)
    top_y, bot_y = geo['top'] * PT - 2, H - geo['bottom'] * PT + 2
    def lines_of(ws):
        body = sorted((w for w in ws if w[1] > top_y and w[3] < bot_y), key=lambda w: (w[3], w[0]))
        rows = []
        for w in body:
            if rows and abs(w[3] - rows[-1]['y']) <= 6: rows[-1]['w'].append(w)
            else: rows.append({'y': w[3], 'w': [w]})
        return [(min(x[0] for x in r['w']), max(x[2] for x in r['w']), r['y'], ' '.join(x[4] for x in sorted(r['w'], key=lambda x: x[0]))) for r in rows]
    PL = [lines_of(ws) for ws in words]
    triple, turn, widows, orphans = [], [], [], []
    ind = 1.5 * geo.get('baseline_size', 10.75)
    for i, ls in enumerate(PL):
        run = 0
        for x0, x1, y, t in ls:
            run = run + 1 if (t.endswith('-') and not t.endswith('--')) else 0
            if run >= 3: triple.append(i + 1); break
        recto = (i % 2 == 0); left = inner if recto else outer; right = W - (outer if recto else inner)
        if ls and i + 1 < len(PL) and PL[i + 1]:
            x0, x1, y, t = ls[-1]
            if t.endswith('-') and ls[-1][2] > lim: turn.append(i + 1)
            nx = PL[i + 1][0]; nleft = inner if (i + 1) % 2 == 0 else outer
            if y > lim and left + 10 <= x0 <= left + ind + 6 and nx[0] < nleft + 5 and len(ls) > 3: orphans.append(i + 1)
        if i > 0 and len(ls) >= 2 and PL[i - 1]:
            p0, p1, py, pt = PL[i - 1][-1]; pright = W - (outer if (i - 1) % 2 == 0 else inner)
            x0, x1, y, t = ls[0]
            if p1 >= pright - 3 and py > lim and x1 < right - 20 and left + 10 <= ls[1][0] <= left + ind + 6 and t not in hs: widows.append(i + 1)
    stats['consecutive_hyphen_runs_3plus'] = len(triple); stats['hyphen_at_page_turn'] = len(turn)
    stats['widow_candidates'] = len(widows); stats['orphan_candidates'] = len(orphans)
    if triple: fails.append('three or more consecutive hyphenated lines on pages %s' % triple[:10])
    if turn: fails.append('hyphenated word across a page turn on pages %s' % turn[:10])
    if widows: fails.append('widow line at top of pages %s' % widows[:10])
    if orphans: fails.append('orphan line at bottom of pages %s' % orphans[:10])
    return fails, warns, stats
