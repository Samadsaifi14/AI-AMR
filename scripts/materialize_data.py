"""Expand the committed public AST table and verify its original input hash."""
import gzip
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = root / 'data/raw/ncbi_kp_human/observations.csv.gz'
data = gzip.decompress(source.read_bytes())
expected = json.loads((root / 'results/public_pilot/audit.json').read_text())['input_sha256']
if hashlib.sha256(data).hexdigest() != expected:
    raise ValueError('Public AST data differs from the recorded source hash.')
target = source.with_suffix('')
target.write_bytes(data)
print(f'Verified and expanded {target.relative_to(root)}')
