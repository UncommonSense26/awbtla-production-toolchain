"""Structural QA on the source master (read-only). Counts are read from the source, never assumed."""
import re

def check_source(src_text, st, config, metadata):
    f = []; info = {}
    notes = st['notes']; markers = st['markers']
    info['note_entries'] = len(notes); info['note_markers'] = len(markers)
    if notes != list(range(1, len(notes) + 1)): f.append('endnote entries are not sequential 1..N')
    if len(set(markers)) != len(markers): f.append('a note marker occurs more than once')
    if markers != list(range(1, len(markers) + 1)): f.append('note markers are not in first-appearance order 1..N')
    missing = sorted(set(markers) - set(notes)); orphans = sorted(set(notes) - set(markers))
    if missing: f.append('markers without entries: %s' % missing[:10])
    if orphans: f.append('entries without markers (orphans): %s' % orphans[:10])
    exp = config.get('expected_note_count')
    if exp is not None and exp != len(notes): f.append('note count %d differs from configured expectation %d' % (len(notes), exp))
    # internal cross-references
    xr = 0
    for m in re.finditer(r'[Gg]lobal notes? (\d+)((?:(?:,\s*|\s+and\s+|\s*[\u2013-]\s*)\d+)*)', src_text):
        nums = [int(m.group(1))] + [int(x) for x in re.findall(r'\d+', m.group(2))]
        for n in nums:
            xr += 1
            if n not in notes: f.append('cross-reference to missing note %d' % n)
    info['cross_references'] = xr
    # formal models: every model listed in the Index must have a label in the body
    idx = re.findall(r'(?m)^(TM-\d+):', src_text)
    labels = set(st['models'])
    info['index_models'] = sorted(set(idx)); info['labelled_models'] = sorted(labels)
    for t in set(idx):
        if t not in labels: f.append('model %s is in the Index but has no labelled block' % t)
    for t in config.get('required_models', []):
        if t not in labels: f.append('required model %s missing' % t)
    for region in ('legal', 'constitution', 'petition', 'index', 'notes', 'dedication'):
        if region not in st['specials']: f.append('required region missing: %s' % region)
    if st['source_title'] != metadata['title'].upper(): f.append('source title %r does not match metadata title' % st['source_title'])
    if st['source_author'] != metadata['author']: f.append('source author %r does not match metadata author' % st['source_author'])
    info['chapters'] = len(st['chapters']); info['parts'] = len(st['parts']); info['articles'] = len(st['articles'])
    info['display_equations'] = st['displays']
    return f, info
