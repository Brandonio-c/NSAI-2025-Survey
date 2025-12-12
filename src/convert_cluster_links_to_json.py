#!/usr/bin/env python3
"""Convert cluster_papers_with_links.xlsx to JSON format for use in web app."""

import pandas as pd
import json
from pathlib import Path

# Paths
CLUSTER_LINKS_FILE = Path("/Users/coleloughbc/Documents/VSCode-Local/NSAI-Data-crosscheck/data/cluster_papers_with_links.xlsx")
OUTPUT_FILE = Path("/Users/coleloughbc/Documents/VSCode-Local/NSAI-2025-Survey/docs/data/cluster_papers_with_links.json")

def main():
    print("Converting cluster_papers_with_links.xlsx to JSON...")
    
    # Load Excel file
    xl_file = pd.ExcelFile(CLUSTER_LINKS_FILE)
    cluster_data = {}
    
    for sheet_name in xl_file.sheet_names:
        df = pd.read_excel(CLUSTER_LINKS_FILE, sheet_name=sheet_name)
        # Convert DataFrame to list of dictionaries, handling NaN values
        records = []
        for _, row in df.iterrows():
            record = {}
            for col in df.columns:
                val = row[col]
                if pd.notna(val):
                    record[col] = str(val)
            records.append(record)
        cluster_data[sheet_name] = records
    
    # Save to JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(cluster_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Converted to {OUTPUT_FILE}")
    print(f"  Sheets: {list(cluster_data.keys())}")
    print(f"  Total entries: {sum(len(sheet) for sheet in cluster_data.values())}")
    
    # Show sample to verify structure
    if cluster_data:
        first_sheet = list(cluster_data.keys())[0]
        print(f"\nSample from '{first_sheet}':")
        if cluster_data[first_sheet]:
            sample = cluster_data[first_sheet][0]
            print(f"  Keys: {list(sample.keys())[:10]}")
            # Find ID column
            id_cols = [k for k in sample.keys() if 'id' in k.lower() or 'rayyan' in k.lower()]
            print(f"  ID columns: {id_cols}")
            if id_cols:
                print(f"  Sample ID value: {sample.get(id_cols[0], 'N/A')}")

if __name__ == '__main__':
    main()

