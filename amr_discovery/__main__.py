import argparse
import json
import sys
from pathlib import Path
import pandas as pd
from .data import build_cohort, IntegrityError
from .ncbi import fetch_biosamples
from .demo import generate_demo
from .modeling import fit_and_evaluate
from .reporting import write_report


def run(args, audit_only=False):
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=False)
    try:
        cohort,audit,exclusions,features=build_cohort(args.data,cfg,args.breakpoints)
        cohort.to_csv(out / "cohort.csv",index=False)
        exclusions.to_csv(out / "exclusions.csv",index=False)
        (out / "audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
        (out / "configuration.json").write_text(json.dumps(cfg,indent=2),encoding="utf-8")
        if audit_only:
            write_report(out,audit)
            print(json.dumps(audit,indent=2));return 0
        if args.command == "validate":
            from .validation import validation_suite
            summary = validation_suite(cohort,features,cfg,audit,out)
            print(json.dumps(summary,indent=2));return 0
        try:
            result,_=fit_and_evaluate(cohort,features,cfg,audit,out)
        except IntegrityError as e:
            (out / "blocked.json").write_text(json.dumps({"status":"TRAINING_BLOCKED","reason":str(e)},indent=2))
            write_report(out,audit,blocked=str(e))
            print(f"Training blocked: {e}. Audit saved in {out}",file=sys.stderr);return 2
        write_report(out,audit,result)
        print(json.dumps({"report":str(out / "report.html"),"status":result["evidence_status"],
                          "n":result["n"],"selected_model":result["selected_model"]},indent=2));return 0
    except IntegrityError as e:
        (out / "blocked.json").write_text(json.dumps({"status":"INPUT_REJECTED","reason":str(e)},indent=2))
        print(str(e),file=sys.stderr);return 2


def main():
    parser=argparse.ArgumentParser(description="Free local phenotype-only AMR research pipeline")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser('freeze-external', help='Freeze trusted local model artifacts before acquiring external results')
    p.add_argument('--run', required=True);p.add_argument('--out', required=True)
    p=sub.add_parser('external', help='Evaluate every eligible external isolate without refitting')
    p.add_argument('--protocol', required=True);p.add_argument('--data', required=True)
    p.add_argument('--out', required=True);p.add_argument('--breakpoints')
    for name in ["audit","run","validate"]:
        p=sub.add_parser(name);p.add_argument("--data",required=True);p.add_argument("--config",required=True)
        p.add_argument("--out",required=True);p.add_argument("--breakpoints")
    p=sub.add_parser("import-wide",help="Chunked full-file import using an explicitly reviewed column mapping")
    p.add_argument("--data",required=True);p.add_argument("--mapping",required=True);p.add_argument("--out",required=True)
    p=sub.add_parser("fetch-ncbi");p.add_argument("--query",required=True);p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=200);p.add_argument("--email",default="");p.add_argument("--resume",action="store_true")
    p=sub.add_parser("demo");p.add_argument("--out",required=True);p.add_argument("--n",type=int,default=800)
    p=sub.add_parser("topology",help="Exploratory networks using an existing run's training partition only")
    p.add_argument("--run",required=True);p.add_argument("--genes");p.add_argument("--geography");p.add_argument("--out",required=True)
    args=parser.parse_args()
    if args.command=='freeze-external':
        from .external import freeze_external
        print(json.dumps(freeze_external(args.run,args.out),indent=2));return 0
    if args.command=='external':
        from .external import evaluate_external
        result=evaluate_external(args.protocol,args.data,args.out,args.breakpoints)
        print(json.dumps(result,indent=2));return 2 if result['status']=='BLOCKED' else 0
    if args.command=="import-wide":
        from .importer import import_wide
        print(json.dumps(import_wide(args.data,args.mapping,args.out),indent=2));return 0
    if args.command=="fetch-ncbi":
        print(json.dumps(fetch_biosamples(args.out,args.query,args.limit,args.email,args.resume),indent=2));return 0
    if args.command=="demo":
        print(generate_demo(args.out,args.n));return 0
    if args.command=="topology":
        from .topology import gene_network, spatial_edges
        if not args.genes and not args.geography:
            parser.error("topology requires --genes or --geography")
        split=pd.read_csv(Path(args.run)/"cohort_with_splits.csv",dtype=str)
        ids=set(split.loc[split.partition.eq("train"),"isolate_id"])
        out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
        for kind,path,func in [("genes",args.genes,gene_network),("geography",args.geography,spatial_edges)]:
            if path:
                func(pd.read_csv(path,dtype=str).fillna(""),ids).to_csv(out/f"{kind}_edges.csv",index=False)
        (out/"interpretation.txt").write_text("Exploratory training-only observations. No causal interaction, transmission, or clinical claim.\n")
        print(str(out));return 0
    return run(args,args.command=="audit")


if __name__=="__main__":
    raise SystemExit(main())
