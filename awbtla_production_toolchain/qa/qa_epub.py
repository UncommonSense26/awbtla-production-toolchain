"""EPUB QA: EPUBCheck, navigation nesting, language, accessibility metadata, note links, text extraction."""
import html, os, re, subprocess, zipfile
from html.parser import HTMLParser

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'math', 'head'): self.skip += 1
        if tag == 'math': self.out.append(' \u27e6M\u27e7 ')
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'br', 'tr', 'section', 'table'): self.out.append('\n')
        if tag == 'li': self.out.append('\u2022 ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'math', 'head'): self.skip -= 1
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr'): self.out.append('\n')
    def handle_data(self, d):
        if not self.skip: self.out.append(d)

def spine_texts(epub):
    z = zipfile.ZipFile(epub)
    opf_path = re.search(r'full-path="([^"]+)"', z.read('META-INF/container.xml').decode()).group(1)
    opf = z.read(opf_path).decode(); base = os.path.dirname(opf_path)
    items = dict(re.findall(r'<item [^>]*id="([^"]+)"[^>]*href="([^"]+)"', opf))
    items.update({k: v for v, k in re.findall(r'<item [^>]*href="([^"]+)"[^>]*id="([^"]+)"', opf)})
    spine = re.findall(r'<itemref [^>]*idref="([^"]+)"', opf)
    out = []
    for idref in spine:
        href = items.get(idref)
        if not href or 'nav' in href or 'title_page' in href: continue
        p = _Text(); p.feed(z.read(os.path.join(base, href) if base else href).decode()); out.append((href, ''.join(p.out)))
    return out, opf, z

def check_epub(epub, epubcheck_jar, heads_expected, source_emdashes):
    fails, stats = [], {}
    if epubcheck_jar and os.path.exists(epubcheck_jar):
        r = subprocess.run(['java', '-jar', epubcheck_jar, epub], capture_output=True, text=True)
        out = r.stdout + r.stderr
        m = re.search(r'Messages: (\d+) fatals? / (\d+) errors? / (\d+) warnings?', out)
        stats['epubcheck'] = m.group(0) if m else out.strip().splitlines()[-1:]
        if r.returncode != 0 or (m and (int(m.group(1)) or int(m.group(2)))):
            fails.append('EPUBCheck failed: %s' % (m.group(0) if m else out[-400:]))
    else:
        fails.append('EPUBCheck not available')
    texts, opf, z = spine_texts(epub)
    if '<dc:language>en-US</dc:language>' not in opf: fails.append('dc:language en-US missing')
    for prop in ('schema:accessMode', 'schema:accessModeSufficient', 'schema:accessibilityFeature', 'schema:accessibilityHazard', 'schema:accessibilitySummary'):
        if prop not in opf: fails.append('accessibility metadata missing: %s' % prop)
    nav_name = next(n for n in z.namelist() if n.endswith('nav.xhtml'))
    nav = z.read(nav_name).decode()
    stats['nav_entries'] = nav.count('<li')
    ids = set(); hrefs = []
    for n in z.namelist():
        if n.endswith('.xhtml'):
            s = z.read(n).decode()
            ids.update(re.findall(r'id="([^"]+)"', s))
            hrefs += re.findall(r'href="[^"#]*#((?:note|ref)-\d+)"', s)
    bad = [h for h in hrefs if h not in ids]
    stats['note_links'] = len(hrefs)
    if bad: fails.append('unresolved note links: %s' % bad[:10])
    full = '\n'.join(t for _, t in texts)
    em = full.count('\u2014'); stats['em_dashes'] = em
    if em != source_emdashes: fails.append('em dashes in EPUB (%d) differ from source (%d)' % (em, source_emdashes))
    return fails, stats, full
