"""
Run one NCBI RQ regression at scale on OSPool. Loads the pre-pulled parquet
files from ./data (from pull_data.submit), fits the FE model, bootstraps
SEs by resampling the entity dimension.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from src.ncbi_client import pubmed_query_to_dataframe
from src.regression import fixed_effects_panel


def load_pubmed_cache(prefix: str) -> pd.DataFrame:
    files = sorted(Path("data").glob(f"{prefix}*.parquet"))
    if not files:
        raise FileNotFoundError(f"no cached parquet matching {prefix}*")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def build(rq: int):
    lit = load_pubmed_cache("pubmed__")   # unified prefix from the client cache
    if rq in (1, 2):
        # We may have multiple queries in cache; keep only the non-retraction one.
        lit = lit[~lit.get("is_retraction", False)]

    if rq == 1:
        panel = (
            lit.dropna(subset=["year","country"])
            .groupby(["country","year"]).size().reset_index(name="n_articles")
        )
        panel["log1p_n"] = np.log1p(panel["n_articles"])
        panel = panel.sort_values(["country","year"])
        panel["lag1_log1p_n"] = panel.groupby("country")["log1p_n"].shift(1)
        panel = panel.dropna(subset=["lag1_log1p_n"])
        return panel, "log1p_n", ["lag1_log1p_n"], "country"

    if rq == 2:
        def uniq(mesh_series):
            all_ = set()
            for s in mesh_series.dropna():
                for t in s.split(";"):
                    if t: all_.add(t)
            return len(all_)
        jy = (
            lit.dropna(subset=["year","journal"])
            .groupby(["journal","year"])
            .agg(n_articles=("pmid","count"),
                 mesh_breadth=("mesh_terms", uniq),
                 mean_n_authors=("n_authors","mean"))
            .reset_index()
        )
        jy = jy[jy["n_articles"] >= 5]
        jy["log_articles"] = np.log(jy["n_articles"])
        return jy, "log_articles", ["mesh_breadth"], "journal"

    if rq == 3:
        ret = lit[lit["is_retraction"] == True]
        cy = ret.dropna(subset=["year","country"]).groupby(["country","year"]).size().reset_index(name="n_retracted")
        cy["log_n_retracted"] = np.log1p(cy["n_retracted"])
        return cy, "log_n_retracted", ["year"], "country"

    raise SystemExit(f"unknown rq: {rq}")


def bootstrap(df, dep, regs, entity, n_boot):
    ents = df[entity].unique()
    rng = np.random.default_rng(0)
    coefs = []
    for _ in range(n_boot):
        draw = rng.choice(ents, size=len(ents), replace=True)
        sub = df[df[entity].isin(draw)]
        try:
            r = fixed_effects_panel(sub, dep, regs,
                                    entity=entity, entity_effects=True,
                                    time_effects=(entity != "country"),
                                    name="boot")
            coefs.append(r.coef_table["coef"])
        except Exception:
            continue
    return pd.DataFrame(coefs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rq", type=int, required=True, choices=[1,2,3])
    ap.add_argument("--bootstrap", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)

    df, dep, regs, entity = build(args.rq)
    res = fixed_effects_panel(df, dep, regs,
                              entity=entity, entity_effects=True,
                              time_effects=(entity != "country"),
                              name=f"RQ{args.rq}")
    res.coef_table.to_csv(args.out / f"rq{args.rq}_main.csv")
    print(res.as_markdown())

    if args.bootstrap > 0:
        b = bootstrap(df, dep, regs, entity, args.bootstrap)
        summary = pd.DataFrame({
            "boot_mean": b.mean(), "boot_sd": b.std(),
            "boot_p025": b.quantile(0.025), "boot_p975": b.quantile(0.975),
        })
        summary.to_csv(args.out / f"rq{args.rq}_bootstrap.csv")
        print(summary)


if __name__ == "__main__":
    main()
