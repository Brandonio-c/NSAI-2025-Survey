#!/usr/bin/env python3
"""
Generate final_include.json and final_exclude.json files.

This script:
1. Reads the Excel extraction file to identify included papers (84 papers)
2. Matches them with entries in include.json using article_id or title
3. Generates final_include.json with enriched metadata
4. Generates final_exclude.json with all excluded papers
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
from difflib import SequenceMatcher

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
EXCEL_FILE = Path("/Users/coleloughbc/Documents/VSCode-Local/NSAI-Data-crosscheck/data/NSAI-DATA_Extraction.xlsx")
INCLUDE_JSON = PROJECT_ROOT / "docs" / "data" / "include.json"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "data"
FINAL_INCLUDE_JSON = OUTPUT_DIR / "final_include.json"
FINAL_EXCLUDE_JSON = OUTPUT_DIR / "final_exclude.json"


def normalize_paper_id(paper_id) -> Optional[str]:
    """Normalize paper ID for matching."""
    if pd.isna(paper_id):
        return None
    paper_id_str = str(paper_id).strip()
    # Remove 'rayyan-' prefix if present
    if paper_id_str.lower().startswith('rayyan-'):
        paper_id_str = paper_id_str[7:]
    return paper_id_str.lower()


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    if not title:
        return ""
    # Lowercase, remove extra spaces, remove punctuation
    title = str(title).lower().strip()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    if not norm1 or not norm2:
        return 0.0
    return SequenceMatcher(None, norm1, norm2).ratio()


def find_column(df: pd.DataFrame, patterns: List[str]) -> Optional[str]:
    """Find a column by matching patterns."""
    for col in df.columns:
        col_lower = col.lower()
        for pattern in patterns:
            if pattern.lower() in col_lower:
                return col
    return None


def load_excel_data(excel_path: Path) -> pd.DataFrame:
    """Load and process Excel file to find included papers."""
    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Find relevant columns
    paper_id_col = find_column(df, ['paper id', 'paper_id', 'rayyan'])
    decision_col = find_column(df, ['final decision to include / exclude', 'final decision'])
    title_col = find_column(df, ['paper title', 'title'])
    
    if not decision_col:
        raise ValueError("Could not find 'Final Decision to Include / Exclude Study' column")
    if not paper_id_col:
        raise ValueError("Could not find 'Paper ID' column")
    
    print(f"Found columns:")
    print(f"  Paper ID: {paper_id_col}")
    print(f"  Decision: {decision_col}")
    if title_col:
        print(f"  Title: {title_col}")
    
    # Normalize paper IDs
    df['normalized_id'] = df[paper_id_col].apply(normalize_paper_id)
    
    # Identify included papers
    df['is_included'] = df[decision_col].apply(
        lambda x: pd.notna(x) and 'include' in str(x).lower()
    )
    
    included_df = df[df['is_included'] == True].copy()
    excluded_df = df[df['is_included'] == False].copy()
    
    print(f"\nFound {len(included_df)} included papers")
    print(f"Found {len(excluded_df)} excluded papers")
    
    return df, included_df, excluded_df, paper_id_col, title_col


def load_include_json(json_path: Path) -> List[Dict[str, Any]]:
    """Load include.json file."""
    print(f"\nLoading include.json: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data)} entries from include.json")
    return data


def match_papers(
    excel_df: pd.DataFrame,
    include_json: List[Dict[str, Any]],
    paper_id_col: str,
    title_col: Optional[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Match Excel papers with include.json entries.
    Returns a dict mapping normalized_id -> matched_json_entry
    """
    matches = {}
    
    # Create lookup by article_id
    json_by_id = {}
    json_by_title = {}
    
    for entry in include_json:
        article_id = entry.get('article_id', '')
        if article_id:
            # Normalize ID
            norm_id = normalize_paper_id(article_id)
            if norm_id:
                json_by_id[norm_id] = entry
        
        # Also index by normalized title
        title = entry.get('title', '')
        if title:
            norm_title = normalize_title(title)
            if norm_title:
                json_by_title[norm_title] = entry
    
    # Match Excel papers
    matched_by_id = 0
    matched_by_title = 0
    unmatched = []
    
    for idx, row in excel_df.iterrows():
        norm_id = row.get('normalized_id')
        matched_entry = None
        
        # Try matching by ID first
        if norm_id and norm_id in json_by_id:
            matched_entry = json_by_id[norm_id]
            matched_by_id += 1
        elif title_col and pd.notna(row.get(title_col)):
            # Try matching by title
            excel_title = str(row[title_col])
            norm_title = normalize_title(excel_title)
            
            if norm_title in json_by_title:
                matched_entry = json_by_title[norm_title]
                matched_by_title += 1
            else:
                # Try fuzzy matching
                best_match = None
                best_score = 0.0
                for json_title, json_entry in json_by_title.items():
                    score = title_similarity(excel_title, json_title)
                    if score > best_score and score > 0.85:  # 85% similarity threshold
                        best_score = score
                        best_match = json_entry
                
                if best_match:
                    matched_entry = best_match
                    matched_by_title += 1
        
        if matched_entry:
            matches[norm_id if norm_id else f"row_{idx}"] = matched_entry
        else:
            unmatched.append({
                'row_idx': idx,
                'paper_id': row.get(paper_id_col),
                'title': row.get(title_col) if title_col else None
            })
    
    print(f"\nMatching results:")
    print(f"  Matched by ID: {matched_by_id}")
    print(f"  Matched by title: {matched_by_title}")
    print(f"  Unmatched: {len(unmatched)}")
    
    if unmatched and len(unmatched) <= 10:
        print("\nUnmatched papers:")
        for item in unmatched[:10]:
            print(f"  - {item['paper_id']}: {item['title']}")
    
    return matches


def enrich_paper_with_excel_data(
    json_entry: Dict[str, Any],
    excel_row: pd.Series,
    paper_id_col: str,
    title_col: Optional[str]
) -> Dict[str, Any]:
    """Enrich JSON entry with data from Excel row."""
    enriched = json_entry.copy()
    
    # Add Excel data as a new field
    enriched['excel_data'] = {}
    
    # Add all Excel columns (excluding internal ones)
    exclude_cols = ['normalized_id', 'is_included']
    for col in excel_row.index:
        if col not in exclude_cols and pd.notna(excel_row[col]):
            enriched['excel_data'][col] = str(excel_row[col])
    
    return enriched


def generate_final_include(
    included_df: pd.DataFrame,
    matches: Dict[str, Dict[str, Any]],
    paper_id_col: str,
    title_col: Optional[str]
) -> List[Dict[str, Any]]:
    """Generate final_include.json with enriched data."""
    final_included = []
    
    for idx, row in included_df.iterrows():
        norm_id = row.get('normalized_id')
        matched_entry = None
        
        # Find matching JSON entry
        if norm_id and norm_id in matches:
            matched_entry = matches[norm_id]
        else:
            # Try to find by title if ID didn't match
            if title_col and pd.notna(row.get(title_col)):
                excel_title = normalize_title(str(row[title_col]))
                for json_entry in matches.values():
                    json_title = normalize_title(json_entry.get('title', ''))
                    if excel_title == json_title:
                        matched_entry = json_entry
                        break
        
        if matched_entry:
            # Enrich with Excel data
            enriched = enrich_paper_with_excel_data(matched_entry, row, paper_id_col, title_col)
            final_included.append(enriched)
        else:
            # Create entry from Excel data only
            entry = {
                'article_id': str(row[paper_id_col]) if pd.notna(row[paper_id_col]) else f"excel_row_{idx}",
                'title': str(row[title_col]) if title_col and pd.notna(row.get(title_col)) else "Unknown Title",
                'year': str(row.get('publication_year', '')) if pd.notna(row.get('publication_year')) else '',
                'author': '',
                'url': '',
                'abstract': '',
                'note': f"Extracted from Excel only (no match in include.json)",
                'customizations': [],
                'excel_data': {}
            }
            # Add all Excel columns
            exclude_cols = ['normalized_id', 'is_included']
            for col in row.index:
                if col not in exclude_cols and pd.notna(row[col]):
                    entry['excel_data'][col] = str(row[col])
            final_included.append(entry)
    
    print(f"\nGenerated {len(final_included)} entries for final_include.json")
    return final_included


def generate_final_exclude(
    excluded_df: pd.DataFrame,
    include_json: List[Dict[str, Any]],
    matches: Dict[str, Dict[str, Any]],
    paper_id_col: str,
    title_col: Optional[str]
) -> List[Dict[str, Any]]:
    """Generate final_exclude.json with all excluded papers."""
    final_excluded = []
    
    # Get all article_ids that are included (to avoid duplicates)
    included_ids = set()
    for entry in matches.values():
        article_id = entry.get('article_id', '')
        if article_id:
            norm_id = normalize_paper_id(article_id)
            if norm_id:
                included_ids.add(norm_id)
    
    # Process excluded Excel rows
    for idx, row in excluded_df.iterrows():
        norm_id = row.get('normalized_id')
        matched_entry = None
        
        # Only match if not already included
        if norm_id and norm_id not in included_ids:
            # Try to find in include.json
            for entry in include_json:
                entry_id = normalize_paper_id(entry.get('article_id', ''))
                if entry_id == norm_id:
                    matched_entry = entry
                    break
            
            # Try by title if ID didn't match
            if not matched_entry and title_col and pd.notna(row.get(title_col)):
                excel_title = normalize_title(str(row[title_col]))
                for entry in include_json:
                    json_title = normalize_title(entry.get('title', ''))
                    if excel_title == json_title:
                        matched_entry = entry
                        break
        
        if matched_entry:
            enriched = enrich_paper_with_excel_data(matched_entry, row, paper_id_col, title_col)
            enriched['exclusion_reason'] = str(row.get('exclusion_reason', 'N/A')) if 'exclusion_reason' in row.index else 'N/A'
            final_excluded.append(enriched)
        else:
            # Create entry from Excel data only
            entry = {
                'article_id': str(row[paper_id_col]) if pd.notna(row[paper_id_col]) else f"excel_row_{idx}",
                'title': str(row[title_col]) if title_col and pd.notna(row.get(title_col)) else "Unknown Title",
                'year': str(row.get('publication_year', '')) if pd.notna(row.get('publication_year')) else '',
                'author': '',
                'url': '',
                'abstract': '',
                'note': f"Extracted from Excel only (no match in include.json)",
                'customizations': [],
                'exclusion_reason': str(row.get('exclusion_reason', 'N/A')) if 'exclusion_reason' in row.index else 'N/A',
                'excel_data': {}
            }
            # Add all Excel columns
            exclude_cols = ['normalized_id', 'is_included']
            for col in row.index:
                if col not in exclude_cols and pd.notna(row[col]):
                    entry['excel_data'][col] = str(row[col])
            final_excluded.append(entry)
    
    # Also add entries from include.json that are not in Excel included list
    # and have exclusion indicators in customizations
    for entry in include_json:
        article_id = entry.get('article_id', '')
        norm_id = normalize_paper_id(article_id) if article_id else None
        
        # Check if this entry is already processed
        already_processed = False
        for excluded_entry in final_excluded:
            excluded_id = normalize_paper_id(excluded_entry.get('article_id', ''))
            if excluded_id == norm_id:
                already_processed = True
                break
        
        if not already_processed and norm_id not in included_ids:
            # Check customizations for exclusion indicators
            customizations = entry.get('customizations', [])
            is_excluded = False
            exclusion_reason = 'N/A'
            
            for cust in customizations:
                key = cust.get('key', '')
                value = cust.get('value', '')
                if key == 'included' and str(value) in ['-1', '0']:
                    is_excluded = True
                elif key.startswith('__EXR__'):
                    is_excluded = True
                    exclusion_reason = key.replace('__EXR__', '').replace('"', '')
            
            if is_excluded:
                entry_copy = entry.copy()
                entry_copy['exclusion_reason'] = exclusion_reason
                final_excluded.append(entry_copy)
    
    print(f"\nGenerated {len(final_excluded)} entries for final_exclude.json")
    return final_excluded


def main():
    """Main function."""
    print("="*80)
    print("Generate Final Include/Exclude Lists")
    print("="*80)
    
    # Load data
    df, included_df, excluded_df, paper_id_col, title_col = load_excel_data(EXCEL_FILE)
    include_json = load_include_json(INCLUDE_JSON)
    
    # Match papers
    matches = match_papers(df, include_json, paper_id_col, title_col)
    
    # Generate final lists
    final_included = generate_final_include(included_df, matches, paper_id_col, title_col)
    final_excluded = generate_final_exclude(excluded_df, include_json, matches, paper_id_col, title_col)
    
    # Write output files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting {FINAL_INCLUDE_JSON}")
    with open(FINAL_INCLUDE_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_included, f, indent=2, ensure_ascii=False)
    
    print(f"Writing {FINAL_EXCLUDE_JSON}")
    with open(FINAL_EXCLUDE_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_excluded, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print("Summary:")
    print(f"  Included papers: {len(final_included)}")
    print(f"  Excluded papers: {len(final_excluded)}")
    print(f"  Output files:")
    print(f"    - {FINAL_INCLUDE_JSON}")
    print(f"    - {FINAL_EXCLUDE_JSON}")
    print("="*80)


if __name__ == "__main__":
    main()

