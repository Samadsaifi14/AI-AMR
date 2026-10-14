"""Synthetic software fixtures. Never evidence for biological performance."""
import csv
from pathlib import Path
import numpy as np
from .ncbi import FIELDS


def generate_demo(out, n=800, seed=42):
    folder = Path(out)
    folder.mkdir(parents=True,exist_ok=False)
    rng = np.random.default_rng(seed)
    rows = []
    drugs = ["cefepime", "ceftazidime", "ciprofloxacin", "gentamicin", "amikacin"]
    for i in range(n):
        source = "DEMO_A" if i < int(.7*n) else "DEMO_B"
        latent = rng.normal()
        y = int(latent + rng.normal(scale=.7) > .15)
        base = dict(isolate_id=f"SYNTH_{i:05d}", source_id=source, patient_id=f"P{i//2}",
                    duplicate_group="",species="Klebsiella pneumoniae" if i%2 else "Escherichia coli",
                    country="FICTIONAL_A" if source=="DEMO_A" else "FICTIONAL_B",
                    collection_date=f"2024-{1+i%12:02d}-01",host="Homo sapiens",specimen="synthetic",
                    units="mg/L",method="MIC",platform="synthetic",standard="EUCAST",
                    standard_version="SYNTHETIC_ONLY",ndm="positive" if i%3==0 else "unknown",
                    oxa48="positive" if i%5==0 else "unknown",mechanism_evidence="synthetic_fixture",
                    evidence_class="synthetic",accession="",source_row=f"generated:{i}")
        rows.append({**base,"drug":"meropenem","measurement":"8" if y else "0.5","operator":"=",
                     "reported_sir":"R" if y else "S"})
        for j,drug in enumerate(drugs):
            if rng.random()<.1:
                continue
            logvalue=np.clip(np.round((1-j*.1)*latent+rng.normal(scale=1)+j*.5),-5,7)
            operator = ">" if logvalue==7 else "<=" if logvalue==-5 else "="
            rows.append({**base,"drug":drug,"measurement":str(2.**logvalue),"operator":operator,
                         "reported_sir":"unknown"})
    with (folder / "observations.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    return folder / "observations.csv"

