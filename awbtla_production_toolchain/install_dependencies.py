#!/usr/bin/env python3
"""Install the pinned production dependencies and verify every file against deps.lock.json.
Fonts go to vendor/fonts (the SIL Open Font License permits redistribution); EPUBCheck goes to vendor/epubcheck.
Exits non-zero on any hash mismatch. Safe to re-run."""
import hashlib, io, json, os, sys, urllib.request, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = json.load(open(os.path.join(HERE, 'deps.lock.json')))
FONTS = os.path.join(HERE, 'vendor', 'fonts'); EPC = os.path.join(HERE, 'vendor', 'epubcheck')

def sha(b): return hashlib.sha256(b).hexdigest()
def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r: return r.read()
def bad_fonts():
    out = []
    for grp in ('source_serif_4', 'stix_two_math'):
        for f, h in LOCK[grp]['files'].items():
            p = os.path.join(FONTS, f)
            if not os.path.exists(p) or sha(open(p, 'rb').read()) != h: out.append(f)
    return out

def main():
    os.makedirs(FONTS, exist_ok=True); os.makedirs(EPC, exist_ok=True)
    if bad_fonts():
        z = fetch(LOCK['source_serif_4']['url'])
        if sha(z) != LOCK['source_serif_4']['sha256']: sys.exit('Source Serif 4 archive hash mismatch')
        zf = zipfile.ZipFile(io.BytesIO(z))
        for f in LOCK['source_serif_4']['files']:
            name = next(n for n in zf.namelist() if n.endswith('/OTF/' + f))
            open(os.path.join(FONTS, f), 'wb').write(zf.read(name))
        lic = next(n for n in zf.namelist() if n.endswith('LICENSE.md'))
        open(os.path.join(FONTS, 'SourceSerif4-LICENSE.md'), 'wb').write(zf.read(lic))
        open(os.path.join(FONTS, 'STIXTwoMath-Regular.otf'), 'wb').write(fetch(LOCK['stix_two_math']['url']))
    bad = bad_fonts()
    if bad: sys.exit('Font verification failed: ' + ', '.join(bad))
    jar = os.path.join(EPC, 'epubcheck-%s' % LOCK['epubcheck']['version'], 'epubcheck.jar')
    if not os.path.exists(jar):
        z = fetch(LOCK['epubcheck']['url'])
        if sha(z) != LOCK['epubcheck']['sha256']: sys.exit('EPUBCheck archive hash mismatch')
        zipfile.ZipFile(io.BytesIO(z)).extractall(EPC)
    print('Dependencies installed and verified.\n  fonts:', FONTS, '\n  epubcheck:', jar)

if __name__ == '__main__':
    main()
