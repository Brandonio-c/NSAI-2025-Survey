#!/usr/bin/env python3
"""
pubtrend.py  ─  create year × cluster count table, comma-separated.

Input files (under data/csv/):
    - paper_clusters.csv
    - papers_full_information.xlsx

Output file:
    - pubtrend_counts.csv
        columns: year,c0,c1,c2,c3,c4,c5   (comma-separated)
"""

from pathlib import Path
import pandas as pd
import csv


def col_like(df: pd.DataFrame, needles: list[str], must=True) -> str | None:
    """Return first column containing any of the substrings (case-insensitive)."""
    for col in df.columns:
        name = " ".join(col.lower().split())
        if any(needle.lower() in name for needle in needles):
            return col
    if must:
        raise KeyError(f"None of {needles} found in {list(df.columns)}")
    return None


def main() -> None:
    root    = Path(__file__).resolve().parents[1]
    csv_dir = root / "data" / "csv"

    clusters_fp = csv_dir / "paper_clusters.csv"
    info_fp     = csv_dir / "papers_full_information.xlsx"
    out_fp      = csv_dir / "pubtrend_counts.csv"

    # ---------- load ----------
    clusters = pd.read_csv(clusters_fp)
    info     = pd.read_excel(info_fp, sheet_name=0)

    # ---------- locate key columns ----------
    id_c   = col_like(clusters, ["paper id", "id"])
    clust  = col_like(clusters, ["cluster"])
    id_i   = col_like(info, ["paper id", "id"])
    year   = col_like(info, ["publication year", "year"])

    # ---------- merge ----------
    merged = (
        clusters[[id_c, clust]]
        .merge(info[[id_i, year]], left_on=id_c, right_on=id_i, how="left")
        .rename(columns={clust: "cluster", year: "year"})
        .dropna(subset=["year", "cluster"])
        .astype({"year": int, "cluster": int})
    )

    # ---------- pivot to counts ----------
    pivot = (
        merged.assign(count=1)
        .pivot_table(index="year", columns="cluster",
                     values="count", aggfunc="sum", fill_value=0)
        .reindex(columns=range(6), fill_value=0)   # guarantee c0-c5
        .reset_index()
    )
    pivot.columns = ["year", "c0", "c1", "c2", "c3", "c4", "c5"]

    # ---------- write comma-separated CSV ----------
    pivot.to_csv(out_fp, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"[INFO] wrote {out_fp.relative_to(root)}  ({len(pivot)} rows)")


if __name__ == "__main__":
    main()
