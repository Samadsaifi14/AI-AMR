"""Public NCBI BioSample antibiogram acquisition. No key or billing required."""
from __future__ import annotations
import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["isolate_id", "source_id", "patient_id", "duplicate_group", "species",
          "country", "collection_date", "host", "specimen", "drug", "measurement",
          "operator", "units", "method", "platform", "standard", "standard_version",
          "reported_sir", "ndm", "oxa48", "mechanism_evidence", "evidence_class",
          "accession", "source_row"]


def parse_biosamples(raw: bytes, source_file: str = "") -> list[dict]:
    root = ET.fromstring(raw)
    rows = []
    for sample in root.iter("BioSample"):
        accession = sample.get("accession", "")
        attrs = {(a.get("harmonized_name") or a.get("attribute_name", "")).lower():
                 (a.text or "").strip() for a in sample.findall("./Attributes/Attribute")}
        org = sample.find("./Description/Organism")
        species = org.get("taxonomy_name", "") if org is not None else ""
        projects = [x.get("label", "") for x in sample.findall(".//Link")
                    if x.get("target") == "bioproject" and x.get("label", "").startswith("PRJ")]
        projects += [x.text.strip() for x in sample.findall(".//Link")
                     if x.text and x.text.strip().startswith("PRJ")]
        projects += [v for k, v in attrs.items() if "bioproject" in k and v.startswith("PRJ")]
        source = "|".join(sorted(set(projects))) or "NCBI_SOURCE_UNKNOWN"
        base = dict(isolate_id=accession, accession=accession, source_id=source,
                    patient_id="", duplicate_group="", species=species,
                    country=attrs.get("geo_loc_name", attrs.get("country", "")).split(":")[0],
                    collection_date=attrs.get("collection_date", ""),
                    host=attrs.get("host", ""), specimen=attrs.get("isolation_source", ""),
                    ndm="unknown", oxa48="unknown", mechanism_evidence="not_curated",
                    evidence_class="measured_public", standard_version="")
        for table in sample.findall(".//Table"):
            if "antibiogram" not in table.get("class", "").lower():
                continue
            headers = ["".join(c.itertext()).strip().lower() for c in table.findall("./Header/Cell")]
            for n, row in enumerate(table.findall("./Body/Row"), 1):
                values = ["".join(c.itertext()).strip() for c in row.findall("Cell")]
                if len(values) != len(headers):
                    raise ValueError(f"Malformed antibiogram {accession}, row {n}")
                d = dict(zip(headers, values))
                rows.append({**base, "drug": d.get("antibiotic", ""),
                             "measurement": d.get("measurement", ""),
                             "operator": d.get("measurement sign", ""),
                             "units": d.get("measurement units", d.get("measurement unit", "")),
                             "method": d.get("laboratory typing method", ""),
                             "platform": d.get("laboratory typing platform", ""),
                             "standard": d.get("testing standard", ""),
                             "reported_sir": d.get("resistance phenotype", ""),
                             "source_row": f"{source_file}:{accession}:{n}"})
    return rows


def fetch_biosamples(out: str, query: str, limit: int = 200, email: str = "", resume: bool = False) -> dict:
    if not 1 <= limit <= 5000:
        raise ValueError("Set limit between 1 and 5000; use an explicit planned acquisition scope.")
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=resume)
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    last = [0.0]

    def request(endpoint, params):
        for attempt in range(3):
            time.sleep(max(0, .4 - (time.monotonic() - last[0])))
            args = {"db": "biosample", "tool": "amr_discovery_local", **params}
            if email:
                args["email"] = email
            url = base + endpoint + "?" + urllib.parse.urlencode(args)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "amr-discovery-research/0.1"})
                with urllib.request.urlopen(req, timeout=45) as response:
                    content = response.read()
                last[0] = time.monotonic()
                return content
            except Exception:
                last[0] = time.monotonic()
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    if resume and (folder / "search.json").exists():
        search_raw = (folder / "search.json").read_bytes()
        previous = folder / "request.json"
        if previous.exists() and json.loads(previous.read_text()) != {"query": query, "limit": limit}:
            raise ValueError("Resume parameters must match the original acquisition.")
        if not previous.exists():
            raise ValueError("Legacy partial download: create request.json with its exact query and limit before resuming.")
    else:
        search_raw = request("esearch.fcgi", {"term": query, "retmode": "json", "retmax": limit})
        (folder / "search.json").write_bytes(search_raw)
        (folder / "request.json").write_text(json.dumps({"query": query, "limit": limit}), encoding="utf-8")
    search = json.loads(search_raw)["esearchresult"]
    if "errorlist" in search:
        raise ValueError(f"NCBI query error: {search['errorlist']}")
    ids = search["idlist"]
    rows, files = [], []
    for start in range(0, len(ids), 100):
        name = f"biosamples_{start:05d}.xml"
        if resume and (folder / name).exists():
            raw = (folder / name).read_bytes()
        else:
            raw = request("efetch.fcgi", {"id": ",".join(ids[start:start+100]), "retmode": "xml"})
            ET.fromstring(raw)  # Never cache an error body as a successful batch.
            (folder / name).write_bytes(raw)
        rows.extend(parse_biosamples(raw, name))
        files.append({"file": name, "sha256": hashlib.sha256(raw).hexdigest()})
        print(f"Retrieved {min(start+100, len(ids))}/{len(ids)} BioSamples", flush=True)
    with (folder / "observations.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "query": query,
                "available_biosamples": int(search["count"]), "requested_limit": limit,
                "retrieved_biosamples": len(ids), "ast_rows": len(rows), "files": files,
                "cost_usd": 0, "access": "public NCBI E-utilities; no paid API",
                "selection": "NCBI default order; convenience pilot, not representative sampling",
                "mechanisms": "unknown until independent annotation is curated",
                "patient_identity": "unavailable; patient independence not established"}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
