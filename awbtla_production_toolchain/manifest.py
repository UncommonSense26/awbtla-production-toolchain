"""Write the production manifest (JSON and Markdown)."""
import json

def write(path_json, path_md, data):
    json.dump(data, open(path_json, 'w', encoding='utf-8'), indent=2, ensure_ascii=False, default=str)
    L = ['# AWBTLA Production Manifest', '']
    for k in ('mode', 'build_timestamp_utc', 'source_file', 'source_sha256', 'expected_sha256', 'config_sha256', 'metadata_sha256', 'toolchain_sha256'):
        L.append('- %s: %s' % (k, data.get(k)))
    L += ['', '## Tools and fonts', '']
    for k, v in data.get('tools', {}).items(): L.append('- %s: %s' % (k, v))
    for k, v in data.get('fonts', {}).items(): L.append('- font %s: %s' % (k, v))
    L += ['', '## Print', '']
    for k, v in data.get('print', {}).items(): L.append('- %s: %s' % (k, v))
    L += ['', '## Metadata', '']
    for k, v in data.get('metadata', {}).items(): L.append('- %s: %s' % (k, v))
    L += ['', '## Outputs', '']
    for o in data.get('outputs', []): L.append('- %s  %s' % (o['sha256'], o['file']))
    L += ['', '## QA', '']
    for k, v in data.get('qa', {}).items(): L.append('- %s: %s' % (k, json.dumps(v, ensure_ascii=False, default=str)[:600]))
    if data.get('cover_parameters'):
        L += ['', '## Cover parameters (estimates; confirm with the platform calculator)', '']
        for k, v in data['cover_parameters'].items(): L.append('- %s: %s' % (k, v))
    open(path_md, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
