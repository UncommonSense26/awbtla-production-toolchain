#!/usr/bin/env python3
"""AWBTLA production build: the single entry point.

Fail-closed order of operations:
  1. input must exist and its SHA-256 must equal --expected-sha256 (the hash recorded in Continuity §58);
     on mismatch nothing is created;
  2. configuration and publication metadata are validated;
  3. without --authorize-production the program stops after validation; nothing is created;
  4. production fonts must be present and hash-verified (fallback fonts only in --synthetic-test mode,
     and only with --allow-fallback-fonts, and the outputs are then labelled);
  5. only then is an output directory created and the print interior and EPUB built and QA'd.
"""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import yaml
from pypdf import PdfReader
import preprocess, manifest
from qa import qa_structure, qa_pdf, qa_text, qa_epub

EXIT = dict(ok=0, input=2, hash=3, not_authorized=4, metadata=5, font=6, structure=7, page_limit=8, qa_print=9, qa_epub=10, mode=11, tool=12)
SYNTH_MARK = '<!-- AWBTLA-SYNTHETIC-FIXTURE -->'
PLACEHOLDER = re.compile(r'(TBD|UNKNOWN|PLACEHOLDER|TODO|XXXX|\[[^\]]*\])', re.I)
LEVELS = {0: 'target', 1: 'second configuration', 2: 'third configuration'}

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def die(code, msg):
    print('BUILD STOPPED [%s]: %s' % (code, msg)); sys.exit(EXIT[code])

def isbn13_ok(s):
    d = re.sub(r'[- ]', '', str(s))
    if not re.fullmatch(r'97[89]\d{10}', d): return False
    tot = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d[:12]))
    return (10 - tot % 10) % 10 == int(d[12])

def validate_metadata(md, formats, cfg):
    p = []
    req = ['title', 'author', 'edition', 'copyright_year', 'publication_date', 'publisher_display', 'language']
    if 'paperback' in formats: req.append('paperback_isbn')
    if 'hardcover' in formats: req.append('hardcover_isbn')
    for k in req:
        v = md.get(k)
        if v is None or str(v).strip() == '' or PLACEHOLDER.search(str(v)): p.append('%s is missing or a placeholder (%r)' % (k, v))
    for k in ('paperback_price', 'hardcover_price', 'ebook_price', 'cover_source_filename', 'cover_credit', 'ebook_isbn'):
        v = md.get(k)
        if v not in (None, '') and PLACEHOLDER.search(str(v)): p.append('%s is a placeholder (%r)' % (k, v))
    if md.get('title') != cfg['title']: p.append('title must be exactly %r' % cfg['title'])
    if md.get('author') != cfg['author']: p.append('author must be exactly %r' % cfg['author'])
    if md.get('edition') != cfg['edition']: p.append('edition must be %r' % cfg['edition'])
    if md.get('language') != 'en-US': p.append('language must be en-US')
    try:
        d = datetime.date.fromisoformat(str(md.get('publication_date')))
        if str(md.get('copyright_year')) != str(d.year): p.append('copyright_year must equal the year of first publication (%d)' % d.year)
    except ValueError:
        p.append('publication_date must be an ISO date (YYYY-MM-DD)')
    for k in ('paperback_isbn', 'hardcover_isbn', 'ebook_isbn'):
        v = md.get(k)
        if v not in (None, '') and not PLACEHOLDER.search(str(v)) and not isbn13_ok(v): p.append('%s is not a valid ISBN-13 (%r)' % (k, v))
    isbns = [re.sub(r'[- ]', '', str(md[k])) for k in ('paperback_isbn', 'hardcover_isbn', 'ebook_isbn') if md.get(k)]
    if len(isbns) != len(set(isbns)): p.append('each format needs its own ISBN')
    return p

def verify_fonts(fontdir):
    lock = json.load(open(os.path.join(HERE, 'deps.lock.json')))
    bad, found = [], {}
    for grp in ('source_serif_4', 'stix_two_math'):
        for f, h in lock[grp]['files'].items():
            p = os.path.join(fontdir, f)
            if not os.path.exists(p) or sha256_file(p) != h: bad.append(f)
            else: found[f] = '%s %s' % (grp, lock[grp]['version'])
    return bad, found

TOOLCHAIN_FILES = ['build.py', 'preprocess.py', 'manifest.py', 'install_dependencies.py', 'deps.lock.json', 'production_config.yaml',
                   'publication_metadata.template.yaml', 'README.md', 'filters/awbtla.lua', 'templates/awbtla-template.tex', 'epub/awbtla-epub.css',
                   'qa/__init__.py', 'qa/qa_structure.py', 'qa/qa_pdf.py', 'qa/qa_text.py', 'qa/qa_epub.py', 'tests/run_tests.py',
                   'tests/fixture/synthetic_master.md', 'tests/fixture/synthetic_config.yaml', 'tests/fixture/synthetic_metadata.yaml']

def toolchain_hash():
    """SHA-256 over an explicit list of toolchain source files (path + file hash), so that output
    directories, caches, and a local publication_metadata.yaml never change the recorded value."""
    h = hashlib.sha256()
    for f in TOOLCHAIN_FILES:
        p = os.path.join(HERE, f)
        h.update(f.encode()); h.update((sha256_file(p) if os.path.exists(p) else 'MISSING').encode())
    return h.hexdigest(), len(TOOLCHAIN_FILES)

def run(cmd, cwd, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError('command failed (%d): %s\n%s' % (r.returncode, ' '.join(cmd[:4]), (r.stdout + r.stderr)[-3000:]))
    return r

PANDOC_FROM = 'markdown+smart+tex_math_dollars+fenced_divs+bracketed_spans+header_attributes+pipe_tables'

def build_print(work, inter, cfg, md, level, fontdir, fallback, synthetic, env):
    L = cfg['print']['levels'][level]
    geo = dict(cfg['print']['geometry']); geo.update(L.get('geometry', {}))
    meta = {'isbnlines': [{'isbn': md[k], 'format': f} for k, f in (('paperback_isbn', 'paperback'), ('hardcover_isbn', 'hardcover')) if md.get(k)]}
    json.dump(meta, open(os.path.join(work, 'isbn_meta.json'), 'w'))
    V = dict(trimwidth='%sin' % geo['trim_w'], trimheight='%sin' % geo['trim_h'], inner='%sin' % geo['inner'], outer='%sin' % geo['outer'],
             top='%sin' % geo['top'], bottom='%sin' % geo['bottom'], bodysize=L['body'][0], bodylead=L['body'][1],
             notesize=L['notes'][0], notelead=L['notes'][1], modelsize=cfg['print']['model_text'][0], modellead=cfg['print']['model_text'][1],
             fontdir=fontdir, lang=md['language'])
    cmd = ['pandoc', inter, '-f', PANDOC_FROM, '-t', 'latex', '--lua-filter', os.path.join(HERE, 'filters', 'awbtla.lua'),
           '--template', os.path.join(HERE, 'templates', 'awbtla-template.tex'), '--metadata-file', os.path.join(work, 'isbn_meta.json'), '-o', 'book.tex']
    for k, v in V.items(): cmd += ['-V', '%s=%s' % (k, v)]
    for k in ('title', 'author', 'edition', 'publisher_display'):
        cmd += ['-M', '%s=%s' % ({'publisher_display': 'publisherline'}.get(k, k), md[k])]
    cmd += ['-M', 'copyrightyear=%s' % md['copyright_year']]
    if fallback: cmd += ['-V', 'fallbackfonts=true']
    if synthetic: cmd += ['-V', 'synthetic=true']
    run(cmd, work)
    for f in ('book.pdf', 'book.log', 'book.aux', 'book.toc', 'book.out'):
        if os.path.exists(os.path.join(work, f)) and f != 'book.toc' and f != 'book.aux': os.remove(os.path.join(work, f))
    for p in range(3):
        r = run(['lualatex', '-interaction=nonstopmode', '-halt-on-error', 'book.tex'], work, env=env, check=False)
        if r.returncode != 0:
            raise RuntimeError('LuaLaTeX failed on pass %d:\n%s' % (p + 1, open(os.path.join(work, 'book.log'), errors='replace').read()[-3000:]))
    log = open(os.path.join(work, 'book.log'), errors='replace').read()
    pages = len(PdfReader(os.path.join(work, 'book.pdf')).pages)
    return pages, log, geo, L

def epub_postprocess(path, summary, epoch):
    """Add accessibility metadata to the package document and re-zip deterministically."""
    zin = zipfile.ZipFile(path); names = zin.namelist(); data = {n: zin.read(n) for n in names}; zin.close()
    opf_name = next(n for n in names if n.endswith('.opf'))
    opf = data[opf_name].decode()
    metas = ['<meta property="schema:accessMode">textual</meta>', '<meta property="schema:accessModeSufficient">textual</meta>',
             '<meta property="schema:accessibilityFeature">structuralNavigation</meta>', '<meta property="schema:accessibilityFeature">tableOfContents</meta>',
             '<meta property="schema:accessibilityFeature">readingOrder</meta>', '<meta property="schema:accessibilityFeature">MathML</meta>',
             '<meta property="schema:accessibilityHazard">none</meta>',
             '<meta property="schema:accessibilitySummary">%s</meta>' % summary]
    new = [m for m in metas if m not in opf]
    opf = opf.replace('</metadata>', '\n    '.join([''] + new) + '\n  </metadata>', 1)
    data[opf_name] = opf.encode()
    tmp = path + '.tmp'
    ts = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(tmp, 'w') as z:
        zi = zipfile.ZipInfo('mimetype', ts); zi.compress_type = zipfile.ZIP_STORED; z.writestr(zi, data['mimetype'])
        for n in sorted(x for x in names if x != 'mimetype'):
            zi = zipfile.ZipInfo(n, ts); zi.compress_type = zipfile.ZIP_DEFLATED; z.writestr(zi, data[n])
    os.replace(tmp, path)

def build_epub(work, inter, md, fontdir, fallback, env, src_sha):
    ident = ('urn:isbn:' + re.sub(r'[- ]', '', str(md['ebook_isbn']))) if md.get('ebook_isbn') else 'urn:uuid:' + str(uuid.uuid5(uuid.NAMESPACE_URL, 'awbtla:' + src_sha))
    meta = {'title': md['title'], 'creator': [{'role': 'author', 'text': md['author']}], 'lang': md['language'], 'identifier': [{'text': ident}],
            'date': str(md['publication_date']), 'publisher': md['publisher_display'], 'rights': 'Copyright \u00a9 %s %s. All rights reserved.' % (md['copyright_year'], md['author'])}
    yaml.safe_dump(meta, open(os.path.join(work, 'epub_meta.yaml'), 'w'), allow_unicode=True)
    cmd = ['pandoc', inter, '-f', PANDOC_FROM, '-t', 'epub3', '--lua-filter', os.path.join(HERE, 'filters', 'awbtla.lua'), '--mathml',
           '--toc', '--toc-depth=2', '--split-level=2', '--css', os.path.join(HERE, 'epub', 'awbtla-epub.css'),
           '--metadata-file', os.path.join(work, 'epub_meta.yaml'), '-o', 'book.epub']
    if not fallback:
        for f in ('SourceSerif4-Regular.otf', 'SourceSerif4-It.otf', 'SourceSerif4-Bold.otf', 'SourceSerif4-BoldIt.otf'):
            cmd += ['--epub-embed-font', os.path.join(fontdir, f)]
    run(cmd, work, env=env)
    epub_postprocess(os.path.join(work, 'book.epub'), 'Reflowable text with semantic headings, navigation nested by Part and chapter, linked endnotes with back-links, and mathematics in MathML.', int(env['SOURCE_DATE_EPOCH']))

def source_plain(work, inter):
    r = run(['pandoc', inter, '-f', PANDOC_FROM, '-t', 'plain', '--wrap=none', '--lua-filter', os.path.join(HERE, 'filters', 'awbtla.lua')], work)
    return r.stdout

def pdf_text_for_qa(pdf, geo, vocab):
    """Extract only the text block (running heads and folios excluded by geometry), from arabic page 1 on."""
    top = geo['top'] * 72 - 2; h = (geo['trim_h'] - geo['top'] - geo['bottom']) * 72 + 4
    texts = qa_pdf.page_texts(pdf, crop=(0, top, geo['trim_w'] * 72, h)); labels = PdfReader(pdf).page_labels
    start = labels.index('1') if '1' in labels else 0
    lines = []
    for t in texts[start:]:
        lines += [l for l in t.split('\n') if l.strip()]
    return '\n'.join(qa_text.dehyphenate(lines, vocab))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', required=True); ap.add_argument('--expected-sha256', required=True)
    ap.add_argument('--metadata', required=True); ap.add_argument('--config', default=os.path.join(HERE, 'production_config.yaml'))
    ap.add_argument('--formats', nargs='+', choices=['paperback', 'hardcover', 'epub'], default=['paperback', 'hardcover', 'epub'])
    ap.add_argument('--authorize-production', action='store_true'); ap.add_argument('--outdir')
    ap.add_argument('--synthetic-test', action='store_true'); ap.add_argument('--allow-fallback-fonts', action='store_true')
    ap.add_argument('--fontdir', default=os.path.join(HERE, 'vendor', 'fonts'))
    a = ap.parse_args()
    # ---- Gate 1: input hash ----
    if not os.path.isfile(a.input): die('input', 'input file not found: %s' % a.input)
    exp = a.expected_sha256.strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', exp): die('hash', 'expected SHA-256 is not a 64-hex-digit value')
    got = sha256_file(a.input)
    if got != exp: die('hash', 'INPUT HASH MISMATCH: file %s has %s, expected %s. No output was created.' % (a.input, got, exp))
    print('INPUT HASH VERIFIED:', got)
    src = open(a.input, encoding='utf-8').read()
    if a.synthetic_test and SYNTH_MARK not in src: die('mode', '--synthetic-test requires the synthetic fixture marker in the input')
    if not a.synthetic_test and SYNTH_MARK in src: die('mode', 'a synthetic fixture cannot be used for a production build')
    if a.allow_fallback_fonts and not a.synthetic_test: die('mode', '--allow-fallback-fonts is permitted only with --synthetic-test')
    cfg = yaml.safe_load(open(a.config, encoding='utf-8')); md = yaml.safe_load(open(a.metadata, encoding='utf-8'))
    problems = validate_metadata(md, a.formats, cfg)
    try:
        inter, st = preprocess.convert(src, cfg)
    except preprocess.StructureError as e:
        die('structure', 'source structure error: %s' % e)
    sfail, sinfo = qa_structure.check_source(src, st, cfg, md)
    print('STRUCTURE:', json.dumps(sinfo))
    # ---- Gate 2: authorization ----
    if not a.authorize_production:
        print('VALIDATION COMPLETE (%d metadata problem(s), %d structure problem(s)). PRODUCTION IS NOT AUTHORIZED: no artifacts were created.' % (len(problems), len(sfail)))
        for x in problems + sfail: print('  -', x)
        sys.exit(EXIT['not_authorized'])
    if problems: die('metadata', 'metadata invalid for authorized production: ' + '; '.join(problems))
    if sfail: die('structure', 'source structure QA failed: ' + '; '.join(sfail))
    # ---- fonts ----
    bad, fonts = verify_fonts(a.fontdir); fallback = False
    if bad:
        if a.synthetic_test and a.allow_fallback_fonts:
            fallback = True; print('WARNING: production fonts unavailable (%s); SYNTHETIC TEST uses FALLBACK FONTS.' % ', '.join(bad))
        else:
            die('font', 'PRODUCTION FONT UNAVAILABLE OR UNVERIFIED: %s. Run install_dependencies.py.' % ', '.join(bad))
    for tool in ('pandoc', 'lualatex', 'pdftotext', 'pdffonts', 'java'):
        if not shutil.which(tool): die('tool', 'required tool not found: ' + tool)
    # ---- output directory (created only after both gates) ----
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = a.outdir or os.path.join(os.getcwd(), 'AWBTLA_PRODUCTION_BUILD_' + stamp)
    if os.path.exists(out) and os.listdir(out): die('mode', 'output directory exists and is not empty: ' + out)
    os.makedirs(out, exist_ok=True); work = os.path.join(out, 'work'); os.makedirs(work)
    open(os.path.join(work, 'intermediate.md'), 'w', encoding='utf-8').write(inter)
    json.dump(st, open(os.path.join(work, 'structure.json'), 'w'), indent=1)
    inter_p = os.path.join(work, 'intermediate.md')
    pub = datetime.date.fromisoformat(str(md['publication_date']))
    epoch = int(datetime.datetime(pub.year, pub.month, pub.day, tzinfo=datetime.timezone.utc).timestamp())
    env = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch), FORCE_SOURCE_DATE='1', TZ='UTC')
    prefix = ('SYNTHETIC_TEST_' if a.synthetic_test else '') + 'AWBTLA_'
    heads = sorted({c['recto'] for c in st['chapters']} | set(cfg['running_heads']['parts'].values()) | set(cfg['running_heads'].get('fixed', []))
                   | {'Constitution: Article ' + x for x in st['articles']} | {'Constitution: Preamble'})
    src_em = src.count('\u2014')
    outputs = []; qa = {'structure': sinfo}
    print_info = {}
    if 'paperback' in a.formats or 'hardcover' in a.formats:
        lim = cfg['print']['page_limits']; level = 0
        while True:
            pages, log, geo, L = build_print(work, inter_p, cfg, md, level, a.fontdir, fallback, a.synthetic_test, env)
            print('PRINT BUILD (%s): %d pages' % (LEVELS[level], pages))
            if level == 0 and pages > lim['first']: level = 1; continue
            if level == 1 and pages > lim['second']: level = 2; continue
            break
        if pages > lim['hard_max']:
            os.remove(os.path.join(work, 'book.pdf'))
            die('page_limit', 'HARDCOVER TRIM SPLIT REQUIRED UNDER PRODUCTION DECISION RECORD: %d pages after the full calibration ladder exceeds %d.' % (pages, lim['hard_max']))
        pdf = os.path.join(work, 'book.pdf')
        geo['baseline'] = L['body'][1]; geo['baseline_size'] = L['body'][0]
        fails, warns, pstats = qa_pdf.check_pdf(pdf, log, cfg, geo, st, src_em, re.findall(r'(?m)^#{2,4} (.+?) \{[^}]*awb-(?:sub|article|notesec)', inter), fallback)
        vocab = set(re.sub(r'^[\W_]+|[\W_]+$', '', w) for w in qa_text.tokens(source_plain(work, inter_p)))
        headings = [h for h in re.findall(r'(?m)^#{2,4} (.+?) \{[^}]*awb-(?:sub|article|notesec)', inter)]
        splain = source_plain(work, inter_p)
        tq = qa_text.compare(splain, pdf_text_for_qa(pdf, geo, vocab))
        if not tq['pass']: fails.append('text integrity: %d difference(s), first: %s' % (len(tq['differences']), tq['differences'][:3]))
        qa['print_layout'] = {'fails': fails, 'stats': pstats}; qa['print_text'] = {'pass': tq['pass'], 'source_tokens': tq['source_tokens'], 'output_tokens': tq['output_tokens'], 'differences': tq['differences'][:10]}
        name = prefix + 'PRINT_INTERIOR_7x10_%s.pdf' % pub.isoformat()
        final = os.path.join(out, name + ('.QA-FAILED' if fails else ''))
        shutil.copy2(pdf, final)
        outputs.append({'file': os.path.basename(final), 'sha256': sha256_file(final), 'formats': [f for f in a.formats if f != 'epub']})
        print_info = {'trim': '%s x %s in' % (geo['trim_w'], geo['trim_h']), 'calibration_level': LEVELS[level], 'body': '%s/%s pt' % tuple(L['body']),
                      'notes': '%s/%s pt' % tuple(L['notes']), 'margins_in': {k: geo[k] for k in ('inner', 'outer', 'top', 'bottom')}, 'pages': pages}
        if fails:
            write_manifest(out, a, got, exp, md, fonts, fallback, print_info, outputs, qa, pages)
            die('qa_print', 'print QA failed: ' + ' | '.join(str(x) for x in fails))
    if 'epub' in a.formats:
        build_epub(work, inter_p, md, a.fontdir, fallback, env, got)
        ep = os.path.join(work, 'book.epub')
        jar = os.path.join(HERE, 'vendor', 'epubcheck', 'epubcheck-5.1.0', 'epubcheck.jar')
        efails, estats, etext = qa_epub.check_epub(ep, jar, heads, src_em)
        vocab = set()
        tq = qa_text.compare(source_plain(work, inter_p), etext)
        if not tq['pass']: efails.append('text integrity: %d difference(s), first: %s' % (len(tq['differences']), tq['differences'][:3]))
        qa['epub'] = {'fails': efails, 'stats': estats, 'text_pass': tq['pass'], 'differences': tq['differences'][:10]}
        name = prefix + 'EBOOK_%s.epub' % pub.isoformat()
        final = os.path.join(out, name + ('.QA-FAILED' if efails else ''))
        shutil.copy2(ep, final)
        outputs.append({'file': os.path.basename(final), 'sha256': sha256_file(final), 'formats': ['epub']})
        if efails:
            write_manifest(out, a, got, exp, md, fonts, fallback, print_info, outputs, qa, print_info.get('pages'))
            die('qa_epub', 'EPUB QA failed: ' + ' | '.join(str(x) for x in efails))
    write_manifest(out, a, got, exp, md, fonts, fallback, print_info, outputs, qa, print_info.get('pages'))
    print('BUILD COMPLETE:', out)

def write_manifest(out, a, got, exp, md, fonts, fallback, print_info, outputs, qa, pages):
    th, nfiles = toolchain_hash()
    tools = {'pandoc': subprocess.run(['pandoc', '--version'], capture_output=True, text=True).stdout.splitlines()[0],
             'lualatex': subprocess.run(['lualatex', '--version'], capture_output=True, text=True).stdout.splitlines()[0]}
    cover = {}
    if pages:
        cover = {'paperback_spine_in_estimate_cream': round(pages * 0.0025, 4), 'basis': 'page count x 0.0025 in (cream); confirm with the platform cover calculator',
                 'hardcover': 'use the platform hardcover cover calculator/template for %d pages' % pages}
    data = {'mode': 'SYNTHETIC TEST' if a.synthetic_test else 'PRODUCTION', 'fallback_fonts': fallback,
            'build_timestamp_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'source_file': os.path.basename(a.input), 'source_sha256': got, 'expected_sha256': exp,
            'config_sha256': sha256_file(a.config), 'metadata_sha256': sha256_file(a.metadata), 'toolchain_sha256': th, 'toolchain_files_hashed': nfiles,
            'tools': tools, 'fonts': {k: v for k, v in fonts.items()} if not fallback else {'fallback': 'TeX Gyre Pagella / Latin Modern Math'},
            'print': print_info, 'metadata': {k: md.get(k) for k in ('title', 'author', 'edition', 'copyright_year', 'publication_date', 'publisher_display', 'paperback_isbn', 'hardcover_isbn', 'ebook_isbn', 'paperback_price', 'hardcover_price', 'ebook_price', 'cover_source_filename', 'cover_credit')},
            'outputs': outputs, 'qa': qa, 'cover_parameters': cover}
    manifest.write(os.path.join(out, 'AWBTLA_PRODUCTION_MANIFEST.json'), os.path.join(out, 'AWBTLA_PRODUCTION_MANIFEST.md'), data)

if __name__ == '__main__':
    try:
        main()
    except RuntimeError as e:
        print('BUILD STOPPED [tool]:', str(e)[-4000:]); sys.exit(EXIT['tool'])
