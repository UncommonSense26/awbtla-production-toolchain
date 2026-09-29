#!/usr/bin/env python3
"""Synthetic positive build, reproducibility check, and negative tests for the AWBTLA production toolchain.
Uses only tests/fixture/* (synthetic). Never touches a manuscript. Results: tests/test_runs/results.json.
Run everything:  python3 tests/run_tests.py
Run in phases:   --phase=positive, --phase=negative_fast, --phase=negative_pages, --phase=negative_layout, --phase=finalize
Build outputs are deleted at finalize after their results are recorded (add --keep to retain them)."""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); TC = os.path.dirname(HERE)
sys.path.insert(0, TC)
import yaml
from pypdf import PdfReader
FX = os.path.join(HERE, 'fixture'); RUNS = os.path.join(HERE, 'test_runs')
SRC = os.path.join(FX, 'synthetic_master.md'); META = os.path.join(FX, 'synthetic_metadata.yaml'); CFG = os.path.join(FX, 'synthetic_config.yaml')
BUILD = os.path.join(TC, 'build.py')
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def build(outdir, src=SRC, meta=META, cfg=CFG, expected=None, auth=True, extra=()):
    cmd = [sys.executable, BUILD, '--input', src, '--expected-sha256', expected or sha(src), '--metadata', meta, '--config', cfg,
           '--formats', 'paperback', 'hardcover', 'epub', '--synthetic-test', '--outdir', outdir] + list(extra)
    if auth: cmd.append('--authorize-production')
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

def variant(name, text):
    p = os.path.join(RUNS, 'inputs', name); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(text); return p

def verify_positive(out):
    v = {}
    pdf = next(os.path.join(out, f) for f in os.listdir(out) if f.endswith('.pdf'))
    epub = next(os.path.join(out, f) for f in os.listdir(out) if f.endswith('.epub'))
    r = PdfReader(pdf); labels = r.page_labels
    txt = subprocess.run(['pdftotext', pdf, '-'], capture_output=True, text=True).stdout.split('\f')
    def side(prefix):
        for i, t in enumerate(txt):
            if t.strip().startswith(prefix): return 'recto' if i % 2 == 0 else 'verso'
    v['recto_openings'] = {k: side(k) for k in ('LEGAL NOTICE', 'PREFACE', 'PROLOGUE', 'INTRODUCTION', 'PART I:', 'PART II:', 'CONSTITUTION OF', 'PEOPLE\u2019S PETITION', 'ENDNOTES', 'DEDICATION')}
    v['arabic_1_at_legal_notice'] = txt[labels.index('1')].strip().startswith('LEGAL NOTICE')
    def outline(o, d=0, acc=None):
        acc = [] if acc is None else acc
        for x in o:
            if isinstance(x, list): outline(x, d + 1, acc)
            else: acc.append((d, x.title))
        return acc
    ol = outline(r.outline); v['bookmarks'] = ol
    v['bookmarks_nested'] = any(d == 1 and t.startswith('Chapter 1') for d, t in ol) and any(d == 1 and t.startswith('Article I') for d, t in ol)
    dests = set(r.named_destinations.keys())
    v['note_link_targets'] = all(('note-%d' % n in dests and 'ref-%d' % n in dests) for n in range(1, 5))
    links = [a.get_object() for pg in r.pages for a in (pg.get('/Annots') or [])]
    v['internal_link_annotations'] = sum(1 for a in links if a.get('/Subtype') == '/Link')
    cat = r.trailer['/Root']; info = r.metadata
    v['pdf_lang'] = str(cat.get('/Lang')); v['pdf_title'] = info.get('/Title'); v['pdf_author'] = info.get('/Author')
    words = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True).stdout
    heads = set()
    for pg in re.split(r'<page ', words)[1:]:
        hw = [w for w in re.findall(r'yMin="([\d.]+)"[^>]*>(.*?)</word>', pg) if float(w[0]) < 50]
        if hw: heads.add(' '.join(x[1] for x in hw))
    v['running_heads_seen'] = sorted(heads)
    log = open(os.path.join(out, 'work', 'book.log'), errors='replace').read()
    v['formula_overflow_markers'] = log.count('AWB-FORMULA-OVERFLOW'); v['head_overflow_markers'] = log.count('AWB-HEAD-OVERFLOW')
    tex = open(os.path.join(out, 'work', 'book.tex'), encoding='utf-8').read()
    v['formula_broken_lines'] = tex.count('\\awbdisplay{') and tex[tex.index('\\awbdisplay{'):].split('\n')[0].count('\\\\')
    v['signature_table_rows'] = len(re.findall(r'\\awbrowstrut', tex))
    v['signature_table_headers_verbatim'] = 'Residence, Locality, or Other Qualification Required by Applicable Law' in tex
    import zipfile
    z = zipfile.ZipFile(epub); nav = z.read(next(n for n in z.namelist() if n.endswith('nav.xhtml'))).decode()
    v['epub_nav_parts_nest_chapters'] = bool(re.search(r'PART I: SYNTHETIC PART ONE</a>\s*<ol[^>]*>\s*<li[^>]*>\s*<a[^>]*>CHAPTER 1', nav))
    v['epub_mathml'] = any(b'<math' in z.read(n) for n in z.namelist() if n.endswith('.xhtml'))
    man = json.load(open(os.path.join(out, 'AWBTLA_PRODUCTION_MANIFEST.json')))
    v['manifest_qa'] = {'print_layout_fails': man['qa']['print_layout']['fails'], 'print_text_pass': man['qa']['print_text']['pass'],
                        'epub_fails': man['qa']['epub']['fails'], 'epubcheck': man['qa']['epub']['stats'].get('epubcheck'), 'pages': man['print']['pages']}
    return v, pdf, epub

def load():
    p = os.path.join(RUNS, 'results.json')
    return json.load(open(p)) if os.path.exists(p) else {}

def save(res):
    json.dump(res, open(os.path.join(RUNS, 'results.json'), 'w'), indent=1, default=str)

def phase_positive(res):
    a, b = os.path.join(RUNS, 'positive_a'), os.path.join(RUNS, 'positive_b')
    rc, out = build(a); res['positive'] = {'exit': rc, 'tail': out.strip().splitlines()[-2:]}
    if rc != 0: return
    v, pdfa, epuba = verify_positive(a); res['positive']['verification'] = v
    rc2, _ = build(b); res['reproducibility'] = {'second_build_exit': rc2}
    if rc2 == 0:
        pdfb = next(os.path.join(b, f) for f in os.listdir(b) if f.endswith('.pdf')); epubb = next(os.path.join(b, f) for f in os.listdir(b) if f.endswith('.epub'))
        res['reproducibility'].update({'pdf_byte_identical': sha(pdfa) == sha(pdfb), 'epub_byte_identical': sha(epuba) == sha(epubb),
                                       'pdf_sha256': [sha(pdfa), sha(pdfb)], 'epub_sha256': [sha(epuba), sha(epubb)],
                                       'pdf_text_identical': subprocess.run(['pdftotext', pdfa, '-'], capture_output=True).stdout == subprocess.run(['pdftotext', pdfb, '-'], capture_output=True).stdout})
    # text mismatch: a tampered source rendering must fail against the good PDF; the true source must pass
    import build as B
    from qa import qa_text
    work = os.path.join(a, 'work'); inter = open(os.path.join(work, 'intermediate.md'), encoding='utf-8').read()
    tp = os.path.join(RUNS, 'inputs', 'tampered_intermediate.md'); os.makedirs(os.path.dirname(tp), exist_ok=True)
    open(tp, 'w', encoding='utf-8').write(inter.replace('This synthetic paragraph follows a scene break', 'This synthetic paragraph precedes a scene break', 1))
    good = B.source_plain(work, os.path.join(work, 'intermediate.md')); bad = B.source_plain(work, tp)
    geo = dict(yaml.safe_load(open(CFG))['print']['geometry'])
    vocab = set(re.sub(r'^[\W_]+|[\W_]+$', '', w) for w in qa_text.tokens(good))
    ext = B.pdf_text_for_qa(pdfa, geo, vocab)
    g = qa_text.compare(good, ext); t = qa_text.compare(bad, ext)
    res.setdefault('negative', {})['text_mismatch'] = {'expected': 'QA failure on tampered text', 'good_source_pass': g['pass'], 'tampered_source_pass': t['pass'],
                                                       'differences': t['differences'][:2], 'pass': g['pass'] and not t['pass']}

def expect(neg, name, rc, out, code, outdir, must_not_exist=True, contains=None):
    ok = (rc == code) and (not must_not_exist or not os.path.exists(outdir)) and (contains is None or contains in out)
    neg[name] = {'expected_exit': code, 'exit': rc, 'output_dir_created': os.path.exists(outdir), 'pass': ok,
                 'message': [l[:300] for l in out.splitlines() if 'BUILD STOPPED' in l or 'NOT AUTHORIZED' in l][:1]}

def phase_negative_fast(res):
    neg = res.setdefault('negative', {}); os.makedirs(os.path.join(RUNS, 'inputs'), exist_ok=True)
    o = os.path.join(RUNS, 'neg_hash'); rc, out = build(o, expected='0' * 64); expect(neg, 'wrong_source_hash', rc, out, 3, o)
    o = os.path.join(RUNS, 'neg_auth'); rc, out = build(o, auth=False); expect(neg, 'missing_authorization', rc, out, 4, o)
    m = yaml.safe_load(open(META)); m['paperback_isbn'] = '[PAPERBACK ISBN]'
    mp = os.path.join(RUNS, 'inputs', 'placeholder_meta.yaml'); yaml.safe_dump(m, open(mp, 'w'))
    o = os.path.join(RUNS, 'neg_isbn'); rc, out = build(o, meta=mp); expect(neg, 'placeholder_isbn', rc, out, 5, o)
    empty = os.path.join(RUNS, 'inputs', 'empty_fontdir'); os.makedirs(empty, exist_ok=True)
    o = os.path.join(RUNS, 'neg_font'); rc, out = build(o, extra=['--fontdir', empty]); expect(neg, 'missing_production_font', rc, out, 6, o)
    src = open(SRC, encoding='utf-8').read()
    mv = variant('missing_note.md', src.replace('4. Synthetic note four.\n', '', 1))
    o = os.path.join(RUNS, 'neg_note'); rc, out = build(o, src=mv); expect(neg, 'missing_note', rc, out, 7, o)

def phase_negative_pages(res):
    neg = res.setdefault('negative', {}); os.makedirs(os.path.join(RUNS, 'inputs'), exist_ok=True)
    c = yaml.safe_load(open(CFG)); c['print']['page_limits'] = {'first': 5, 'second': 6, 'hard_max': 7}
    cp = os.path.join(RUNS, 'inputs', 'small_limits.yaml'); yaml.safe_dump(c, open(cp, 'w'), allow_unicode=True)
    o = os.path.join(RUNS, 'neg_pages'); rc, out = build(o, cfg=cp)
    expect(neg, 'oversized_page_count', rc, out, 8, o, must_not_exist=False, contains='HARDCOVER TRIM SPLIT REQUIRED UNDER PRODUCTION DECISION RECORD')
    neg['oversized_page_count']['ladder'] = [l for l in out.splitlines() if l.startswith('PRINT BUILD')]
    neg['oversized_page_count']['final_pdf_created'] = any(f.endswith('.pdf') for f in os.listdir(o)) if os.path.exists(o) else False
    neg['oversized_page_count']['pass'] = neg['oversized_page_count']['pass'] and len(neg['oversized_page_count']['ladder']) == 3 and not neg['oversized_page_count']['final_pdf_created']

def phase_negative_layout(res):
    neg = res.setdefault('negative', {}); os.makedirs(os.path.join(RUNS, 'inputs'), exist_ok=True)
    src = open(SRC, encoding='utf-8').read()
    fv = variant('formula_overflow.md', src.replace('**Common Sense Prompt:** What synthetic', '$$\\text{SyntheticUnbreakableTokenWithoutAnyPermissibleBreakPointsThatCannotFitTheMeasureEvenAtNinetyPercent}$$\n\n**Common Sense Prompt:** What synthetic', 1))
    o = os.path.join(RUNS, 'neg_formula'); rc, out = build(o, src=fv); expect(neg, 'formula_overflow', rc, out, 9, o, must_not_exist=False, contains='AWB-FORMULA-OVERFLOW')
    c = yaml.safe_load(open(CFG)); c['running_heads']['chapters'][2] = 'Chapter 2: ' + 'An Unacceptably Long Running Head ' * 4
    hp = os.path.join(RUNS, 'inputs', 'long_head.yaml'); yaml.safe_dump(c, open(hp, 'w'), allow_unicode=True)
    o = os.path.join(RUNS, 'neg_head'); rc, out = build(o, cfg=hp); expect(neg, 'running_head_overflow', rc, out, 9, o, must_not_exist=False, contains='AWB-HEAD-OVERFLOW')

def phase_finalize(res, keep):
    neg = res.get('negative', {})
    res['all_negative_pass'] = bool(neg) and all(x['pass'] for x in neg.values())
    if not keep:
        for d in os.listdir(RUNS):
            if d != 'results.json': shutil.rmtree(os.path.join(RUNS, d), ignore_errors=True)
        res['build_outputs_deleted_after_recording'] = True

def main():
    keep = '--keep' in sys.argv
    phases = [x.split('=', 1)[1] for x in sys.argv if x.startswith('--phase=')] or ['all']
    if 'all' in phases: phases = ['positive', 'negative_fast', 'negative_pages', 'negative_layout', 'finalize']
    if 'positive' in phases and os.path.exists(RUNS): shutil.rmtree(RUNS)
    os.makedirs(RUNS, exist_ok=True); res = load(); res['fixture_sha256'] = sha(SRC)
    for ph in phases:
        if ph == 'finalize': phase_finalize(res, keep)
        else: globals()['phase_' + ph](res)
        save(res)
    print(json.dumps({'phases': phases, 'positive_exit': res.get('positive', {}).get('exit'),
                      'reproducibility': {k: v for k, v in res.get('reproducibility', {}).items() if 'identical' in k},
                      'negative': {k: v['pass'] for k, v in res.get('negative', {}).items()}, 'all_negative_pass': res.get('all_negative_pass')}, indent=1))

if __name__ == '__main__':
    main()
