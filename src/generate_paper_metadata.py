#!/usr/bin/env python3
"""
generate_paper_metadata.py  –  robust version

Merges:
  data/csv/paper_clusters.csv
  data/csv/papers_full_information.xlsx

→ data/csv/paper_metadata.csv   (columns: paper_id,title,year,cites)
"""

from pathlib import Path
import pandas as pd


def find_column_substring(df: pd.DataFrame, substrings: list[str], mandatory: bool = True) -> str | None:
    """
    Return the first column whose lowercase name contains ANY of the
    provided substrings (also lowercase).  Newlines, spaces and tabs
    inside the header are ignored.
    """
    norm = lambda s: " ".join(s.lower().split())  # collapse whitespace
    for candidate in df.columns:
        cand_norm = norm(candidate)
        for sub in substrings:
            if sub.lower() in cand_norm:
                return candidate
    if mandatory:
        raise KeyError(
            f"None of {substrings} found in columns:\n  {list(df.columns)}"
        )
    return None


def main() -> None:
    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    project_root = Path(__file__).resolve().parents[1]
    csv_dir = project_root / "data" / "csv"

    clusters_fp = csv_dir / "paper_clusters.csv"
    info_fp = csv_dir / "papers_full_information.xlsx"
    out_fp = csv_dir / "paper_metadata.csv"

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    clusters = pd.read_csv(clusters_fp)
    info = pd.read_excel(info_fp, sheet_name=0)

    # ------------------------------------------------------------------
    # Locate key columns by substring
    # ------------------------------------------------------------------
    id_col_clusters = find_column_substring(clusters, ["paper id", "id"])
    title_col = find_column_substring(clusters, ["title"])

    id_col_info = find_column_substring(info, ["paper id", "id"])
    year_col = find_column_substring(info, ["publication year", "year"])
    cites_col = find_column_substring(info, ["citation", "cites"], mandatory=False)

    if cites_col is None:
        info["cites"] = 0
        cites_col = "cites"

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------
    merged = (
        clusters[[id_col_clusters, title_col]]
        .merge(
            info[[id_col_info, year_col, cites_col]],
            left_on=id_col_clusters,
            right_on=id_col_info,
            how="left",
        )
        .rename(
            columns={
                id_col_clusters: "paper_id",
                title_col: "title",
                year_col: "year",
                cites_col: "cites",
            }
        )
        .sort_values("paper_id")
        .reset_index(drop=True)
    )

    # Warn about missing years
    n_missing_year = merged["year"].isna().sum()
    if n_missing_year:
        print(f"[WARN] {n_missing_year} rows have no publication year.")

    merged.to_csv(out_fp, index=False)
    print(f"[INFO] Wrote {len(merged)} rows → {out_fp.relative_to(project_root)}")


if __name__ == "__main__":
    main()
