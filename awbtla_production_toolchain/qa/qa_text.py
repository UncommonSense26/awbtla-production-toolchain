"""Text-integrity QA: compare the source text (Pandoc plain rendering of the intermediate Markdown)
with text extracted from the PDF or EPUB.

Allowed, documented normalizations only:
  - whitespace and line wrapping;
  - running heads and folios (removed per page by the caller);
  - ligature characters (ff, fi, fl, ffi, ffl) mapped to letters;
  - end-of-line hyphenation (joined when the joined word exists in the source vocabulary);
  - wildcard source tokens for mathematics, fill-in blank rules, and the signature table (checked separately).
Punctuation is never normalized."""
import re

LIGS = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl'}
WILD = ('\u27e6MATH\u27e7', '\u27e6M\u27e7', '\u27e6TABLE\u27e7', '\u27e6BLANK\u27e7')

def norm(s):
    for k, v in LIGS.items(): s = s.replace(k, v)
    return s.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')

def tokens(s):
    return norm(s).split()

def _strip(w):
    return re.sub(r'^[\W_]+|[\W_]+$', '', w)

def dehyphenate(lines, vocab):
    """Join words split across lines by the typesetter: hyphenation breaks, and URL/DOI breaks
    (at "/" or "."), only when the joined form is a token of the source."""
    out = []
    for ln in lines:
        ln = ln.rstrip()
        if out and ln.strip():
            prev = out[-1]; last = prev.split()[-1] if prev.split() else ''; first = ln.split()[0]
            if last.endswith('-') and first[:1].islower():
                joined = _strip(last[:-1] + first); hyph = _strip(last + first)
                if joined in vocab and hyph not in vocab:
                    out[-1] = prev[:-1] + ln.lstrip(); continue
                out[-1] = prev + ln.lstrip(); continue
            if (last.endswith('/') or last.endswith('.')) and _strip(last + first) in vocab and _strip(last) not in vocab:
                out[-1] = prev + ln.lstrip(); continue
        out.append(ln)
    return out

def is_wild(t):
    return any(w in t for w in WILD)

def compare(src_text, ext_text, max_report=40, window=600, k=6):
    a = tokens(src_text); b = tokens(ext_text)
    i = j = 0; diffs = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1; continue
        if is_wild(a[i]):
            # skip extracted tokens until the next k source tokens match
            nxt = []
            for t in a[i+1:]:
                if is_wild(t) or len(nxt) == k: break
                nxt.append(t)
            if i + 1 >= len(a): j = len(b); i += 1; break
            if not nxt: i += 1; continue
            found = None
            for jj in range(j, min(len(b), j + window)):
                if b[jj:jj+len(nxt)] == nxt: found = jj; break
            if found is None:
                diffs.append(('unresolved-wildcard', i, j, ' '.join(a[i:i+8]), ' '.join(b[j:j+8]))); i += 1; continue
            j = found; i += 1; continue
        # resync
        best = None
        for d in range(1, window):
            if a[i:i+k] == b[j+d:j+d+k]: best = ('extra-in-output', 0, d); break
            if b[j:j+k] == a[i+d:i+d+k]: best = ('missing-in-output', d, 0); break
            if i + d < len(a) and a[i+d:i+d+k] == b[j+d:j+d+k] and not is_wild(a[i+d]): best = ('changed', d, d); break
        if best is None:
            diffs.append(('desync', i, j, ' '.join(a[i:i+10]), ' '.join(b[j:j+10]))); break
        kind, di, dj = best
        diffs.append((kind, i, j, ' '.join(a[i:i+max(di, 1)][:12]), ' '.join(b[j:j+max(dj, 1)][:12])))
        i += di; j += dj
        if len(diffs) >= max_report: break
    if i < len(a) and len(diffs) < max_report and not all(is_wild(t) for t in a[i:]):
        diffs.append(('missing-tail', i, j, ' '.join(a[i:i+10]), ''))
    if j < len(b) and len(diffs) < max_report:
        diffs.append(('extra-tail', i, j, '', ' '.join(b[j:j+10])))
    return {'source_tokens': len(a), 'output_tokens': len(b), 'differences': diffs, 'pass': not diffs}
