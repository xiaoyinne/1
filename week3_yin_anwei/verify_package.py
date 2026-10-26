"""Verify archived and published bytes plus fixed-query result bookkeeping; no ICP rerun."""
from pathlib import Path
import json,hashlib,csv,sys

root=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
manifest=json.loads((root/'FILE_SHA256.json').read_text(encoding='utf8'))
for name,expected in manifest.items():
    path=root/name
    assert path.is_file(),f'Missing: {name}'
    assert sha(path)==expected,f'Changed: {name}'
archive=root/'experiment_20261020'
original=json.loads((archive/'FILE_SHA256.json').read_text(encoding='utf8'))
for name,expected in original.items():assert sha(archive/name)==expected,name
validation=json.loads((archive/'validation.json').read_text(encoding='utf8'))
assert validation['passed'] and validation['fixed_query_runs']==28
queries=json.loads((archive/'fixed_query_v1/schedule.json').read_text(encoding='utf8'))
selected=queries['selected_stamp_ns']
assert len(selected)==53 and len(set(selected))==53
assert len(list((archive/'fixed_query_v1/scans').glob('scan_*.npy')))==53
checked=0
for category in ['fixed_runs','delete_runs']:
    for attempt in sorted((archive/category).glob('*/attempts.csv')):
        records=list(csv.DictReader(attempt.open(encoding='utf8')))
        assert len(records)==53,attempt
        assert [int(r['stamp_ns'])for r in records]==selected,attempt
        assert all(r['accepted']in ['0','1']for r in records),attempt
        assert all(0<=float(r['fitness'])<=1 for r in records),attempt
        checked+=1
assert checked==28,checked
print(f'PASS: {len(manifest)} published file hashes; {len(original)} original archive hashes; 28 runs x 53 attempts; 53 query scans.')
