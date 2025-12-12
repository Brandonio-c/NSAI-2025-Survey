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
CLUSTER_LINKS_FILE = Path("/Users/coleloughbc/Documents/VSCode-Local/NSAI-Data-crosscheck/data/cluster_papers_with_links.xlsx")
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
    """Load and process Excel file to find included papers.
    
    Also loads engineered features from run_reproducibility_analysis.py
    to get reproduction status flags.
    """
    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Try to load engineered features from run_reproducibility_analysis.py
    try:
        import sys
        # Add the NSAI-Data-crosscheck/src directory to path
        crosscheck_src = Path("/Users/coleloughbc/Documents/VSCode-Local/NSAI-Data-crosscheck/src")
        if str(crosscheck_src) not in sys.path:
            sys.path.insert(0, str(crosscheck_src))
        
        from run_reproducibility_analysis import load_data, normalize_columns, engineer_features
        
        # Use load_data which handles normalization and engineering
        # But we need to pass the DataFrame, so we'll do it manually
        column_map = normalize_columns(df)
        df = engineer_features(df, column_map)
        
        # Create partially_reproduced_below and partially_reproduced_above columns
        # These are calculated based on gap_percent and partially_reproduced
        # THRESHOLD_GAP is 5.0% (from plot_funnel function, line 3368)
        # IMPORTANT: Create these BEFORE calculating is_included!
        THRESHOLD_GAP = 5.0
        
        if 'partially_reproduced' in df.columns and 'gap_percent' in df.columns:
            # Partially reproduced above threshold: gap <= THRESHOLD_GAP or gap is NaN
            df['partially_reproduced_above'] = (
                (df['partially_reproduced'] == 1) &
                ((df['gap_percent'].notna() & (df['gap_percent'] <= THRESHOLD_GAP)) |
                 (df['gap_percent'].isna()))
            ).astype(int)
            
            # Partially reproduced below threshold: gap > THRESHOLD_GAP
            df['partially_reproduced_below'] = (
                (df['partially_reproduced'] == 1) &
                (df['gap_percent'].notna()) &
                (df['gap_percent'] > THRESHOLD_GAP)
            ).astype(int)
            
            print(f"✓ Created partially_reproduced_above: {df['partially_reproduced_above'].sum()} papers")
            print(f"✓ Created partially_reproduced_below: {df['partially_reproduced_below'].sum()} papers")
        else:
            print("⚠ Could not create partially_reproduced_above/below columns (missing partially_reproduced or gap_percent)")
            df['partially_reproduced_above'] = 0
            df['partially_reproduced_below'] = 0
        
        print("✓ Loaded engineered features from run_reproducibility_analysis.py")
    except Exception as e:
        print(f"⚠ Could not load engineered features: {e}")
        print("  Will infer reproduction category from raw Excel columns")
    
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
    
    # Normalize paper IDs (if not already done)
    if 'normalized_id' not in df.columns:
        df['normalized_id'] = df[paper_id_col].apply(normalize_paper_id)
    
    # Identify included papers: Simple logic - if "Final Decision to Include / Exclude Study" contains "Include", then include it
    if 'is_included' not in df.columns:
        df['is_included'] = df[decision_col].apply(
            lambda x: pd.notna(x) and 'include' in str(x).lower()
        )
        included_count = df['is_included'].sum()
        print(f"  Using 'Final Decision' column: {included_count} included papers")
        if included_count != 84:
            print(f"  WARNING: Expected 84 included papers, found {included_count}")
    
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


def find_repository_url(paper_id: str, title: str, cluster_links_dict: Optional[Dict[str, pd.DataFrame]] = None) -> Optional[str]:
    """Find repository URL from cluster_papers_with_links.xlsx by matching Rayyan ID across all sheets."""
    if cluster_links_dict is None or not cluster_links_dict:
        return None
    
    # Normalize paper ID (Rayyan ID)
    norm_id = normalize_paper_id(paper_id) if paper_id else None
    if not norm_id:
        return None
    
    # Search through all sheets
    for sheet_name, df in cluster_links_dict.items():
        if df.empty:
            continue
        
        # Find Rayyan ID column (could be 'Paper ID', 'Rayyan ID', 'ID', etc.)
        id_cols = [c for c in df.columns if 'rayyan' in c.lower() or ('paper' in c.lower() and 'id' in c.lower()) or c.lower() == 'id']
        
        # Also check for columns that might contain the ID
        if not id_cols:
            id_cols = [c for c in df.columns if 'id' in c.lower()]
        
        for id_col in id_cols:
            for idx, row in df.iterrows():
                if pd.notna(row.get(id_col)):
                    row_id = normalize_paper_id(str(row[id_col]))
                    if row_id == norm_id:
                        # Found match, get any URL/link
                        # Check for various URL/link column names
                        url_cols = []
                        for col in df.columns:
                            col_lower = col.lower()
                            if any(term in col_lower for term in ['url', 'link', 'github', 'repository', 'code', 'repo', 'source']):
                                url_cols.append(col)
                        
                        for url_col in url_cols:
                            url_val = row.get(url_col)
                            if pd.notna(url_val):
                                url_str = str(url_val).strip()
                                if url_str and url_str not in ['', 'N/A', 'nan', 'None', 'null', 'N']:
                                    # Check if it looks like a URL
                                    if url_str.startswith('http://') or url_str.startswith('https://') or url_str.startswith('www.'):
                                        return url_str
                                    elif '.' in url_str and len(url_str) > 5:
                                        # Any URL-like string (not just GitHub)
                                        return url_str if url_str.startswith('http') else f"https://{url_str}"
        
        # Also try matching by title as fallback
        if title:
            norm_title = normalize_title(title)
            title_cols = [c for c in df.columns if 'title' in c.lower()]
            for title_col in title_cols:
                for idx, row in df.iterrows():
                    if pd.notna(row.get(title_col)):
                        row_title = normalize_title(str(row[title_col]))
                        if row_title == norm_title:
                            # Found match by title, get URL
                            url_cols = []
                            for col in df.columns:
                                col_lower = col.lower()
                                if any(term in col_lower for term in ['url', 'link', 'github', 'repository', 'code', 'repo', 'source']):
                                    url_cols.append(col)
                            
                            for url_col in url_cols:
                                url_val = row.get(url_col)
                                if pd.notna(url_val):
                                    url_str = str(url_val).strip()
                                    if url_str and url_str not in ['', 'N/A', 'nan', 'None', 'null', 'N']:
                                        if url_str.startswith('http://') or url_str.startswith('https://') or url_str.startswith('www.'):
                                            return url_str
                                        elif '.' in url_str and len(url_str) > 5:
                                            return url_str if url_str.startswith('http') else f"https://{url_str}"
    
    return None


def enrich_paper_with_excel_data(
    json_entry: Dict[str, Any],
    excel_row: pd.Series,
    paper_id_col: str,
    title_col: Optional[str],
    cluster_links_dict: Optional[Dict[str, pd.DataFrame]] = None
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
    
    # Check for repository URL (for ALL papers - both included and excluded)
    codebase_cols = [c for c in excel_row.index if 'codebase' in c.lower()]
    repo_cols = [c for c in excel_row.index if 'repository' in c.lower()]
    
    repo_url = None
    
    # First check Repository URL column in main Excel
    for repo_col in repo_cols:
        repo_val = excel_row.get(repo_col)
        if pd.notna(repo_val):
            repo_str = str(repo_val).strip()
            if repo_str and repo_str not in ['', 'N/A', 'nan', 'None', 'null', 'N']:
                # Check if it looks like a URL
                if repo_str.startswith('http://') or repo_str.startswith('https://') or repo_str.startswith('www.'):
                    repo_url = repo_str
                    break
                elif '.' in repo_str and len(repo_str) > 5:
                    # Might be a URL without protocol
                    repo_url = repo_str if repo_str.startswith('http') else f"https://{repo_str}"
                    break
    
    # If not found, check cluster_links file
    if not repo_url and cluster_links_dict is not None:
        paper_id = str(excel_row.get(paper_id_col, '')) if paper_id_col in excel_row.index else ''
        title = str(excel_row.get(title_col, '')) if title_col and title_col in excel_row.index else json_entry.get('title', '')
        repo_url = find_repository_url(paper_id, title, cluster_links_dict)
    
    # Store repository URL in a special field for easy access (for all papers)
    if repo_url:
        enriched['repository_url'] = repo_url
    else:
        enriched['repository_url'] = None
    
    return enriched


def generate_final_include(
    included_df: pd.DataFrame,
    matches: Dict[str, Dict[str, Any]],
    paper_id_col: str,
    title_col: Optional[str],
    cluster_links_dict: Optional[Dict[str, pd.DataFrame]] = None
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
            enriched = enrich_paper_with_excel_data(matched_entry, row, paper_id_col, title_col, cluster_links_dict)
            final_included.append(enriched)
        else:
            # Create entry from Excel data only (ALL included papers should be added, even if not in include.json)
            entry = {
                'article_id': str(row[paper_id_col]) if pd.notna(row[paper_id_col]) else f"excel_row_{idx}",
                'title': str(row[title_col]) if title_col and pd.notna(row.get(title_col)) else "Unknown Title",
                'year': str(row.get('publication_year', '')) if pd.notna(row.get('publication_year')) else '',
                'author': '',
                'url': '',
                'abstract': '',
                'note': f"Extracted from Excel only (no match in include.json)",
                'customizations': [],
                'excel_data': {},
                'repository_url': None
            }
            # Add all Excel columns
            exclude_cols = ['normalized_id', 'is_included']
            for col in row.index:
                if col not in exclude_cols and pd.notna(row[col]):
                    entry['excel_data'][col] = str(row[col])
            
            # Check for repository URL if no codebase
            codebase_cols = [c for c in row.index if 'codebase' in c.lower()]
            repo_cols = [c for c in row.index if 'repository' in c.lower()]
            
            has_codebase = False
            for codebase_col in codebase_cols:
                codebase_val = row.get(codebase_col)
                if pd.notna(codebase_val):
                    codebase_str = str(codebase_val).lower()
                    if codebase_str in ['yes', 'true', '1']:
                        has_codebase = True
                        break
            
            if not has_codebase and cluster_links_dict is not None:
                paper_id = str(row.get(paper_id_col, '')) if paper_id_col in row.index else ''
                title = str(row.get(title_col, '')) if title_col and title_col in row.index else entry.get('title', '')
                from generate_final_lists import find_repository_url
                repo_url = find_repository_url(paper_id, title, cluster_links_dict)
                if repo_url:
                    entry['repository_url'] = repo_url
            
            final_included.append(entry)
    
    print(f"\nGenerated {len(final_included)} entries for final_include.json")
    return final_included


def determine_reproduction_category(row: pd.Series, papers_with_exclusion_reasons: set = None) -> str:
    """Determine reproduction category from Excel row data using EXACT logic from run_reproducibility_analysis.py.
    
    This matches the logic in run_reproducibility_analysis.py analyze_reproducibility_funnel() EXACTLY:
    1. Check "If exclude, provide reason" column FIRST (matching exact logic from lines 1379-1400)
    2. If paper has exclusion reason, return appropriate "Not Attempted" category
    3. If paper is in papers_with_exclusion_reasons set, it should have been handled above
    4. For papers NOT in exclusion reasons:
       - Check partially_reproduced_below (from df_for_reproduction, excluding exclusion reasons)
       - Check has_code == 0 (from not_reprod_df_filtered)
       - Check reproducible_all_artifacts == 1 AND not_reproduced_overall == 1 (from not_reprod_df_filtered)
    5. Default to "Missing Some Artifacts" (remainder)
    
    Args:
        row: pandas Series with paper data
        papers_with_exclusion_reasons: set of normalized_paper_ids that have exclusion reasons
    """
    # Get normalized_paper_id to check against exclusion set
    paper_id = row.get('normalized_paper_id', None) or row.get('normalized_id', None)
    
    # FIRST: Check "If exclude, provide reason" column (EXACT logic from run_reproducibility_analysis.py lines 1371-1400)
    # IMPORTANT: Only papers with NON-EMPTY exclusion reasons get categorized here
    # Papers with empty/N/A exclusion reasons will go through normal categorization and default to "Missing some artifacts"
    exclusion_reason_col = None
    for col in row.index:
        if 'exclude' in col.lower() and 'reason' in col.lower() and 'if exclude' in col.lower():
            exclusion_reason_col = col
            break
    
    if exclusion_reason_col:
        exclusion_reason = row.get(exclusion_reason_col)
        # Only process if exclusion reason is NOT empty/N/A (matching pie chart logic line 1382)
        if pd.notna(exclusion_reason) and str(exclusion_reason).strip().lower() not in ['n/a', 'nan', 'none', '', 'not extracted from spreadsheet']:
            reason_str = str(exclusion_reason).strip()
            reason_lower = reason_str.lower()
            # EXACT matching logic from run_reproducibility_analysis.py lines 1385-1400
            if any(term in reason_lower for term in ['off topic', 'not neuro-symbolic', 'not neurosymbolic', 'off-topic', 'not neuro symbolic']):
                return 'Not attempted - off topic'  # Match exact format from pie chart
            elif any(term in reason_lower for term in ['background', 'review', 'survey']):
                return 'Not attempted - background article'  # Match exact format
            elif any(term in reason_lower for term in ['not a research', 'not research', 'not a research article']):
                return 'Not attempted - not a research article'  # Match exact format
            elif any(term in reason_lower for term in ['no fulltext', 'no full text', 'fulltext', 'no full-text', 'no full text available']):
                return 'Not attempted - no fulltext'  # Match exact format
        # If exclusion_reason_col exists but is empty/N/A, continue to normal categorization (will default to "Missing some artifacts")
    
    # If paper has exclusion reason but didn't match above, it's still in exclusion set
    # Skip reproduction categories for these papers
    if papers_with_exclusion_reasons and paper_id and paper_id in papers_with_exclusion_reasons:
        # Should have been caught above, but if not, default to missing artifacts
        return 'Missing Some Artifacts'
    
    # Now check reproduction status (only for papers WITHOUT exclusion reasons)
    # IMPORTANT: Check partially_reproduced_below FIRST (from df_for_reproduction, excluding exclusion reasons)
    # This must come BEFORE checking not_reproduced_overall
    # Make sure this paper is NOT in exclusion reasons set (from df_for_reproduction logic)
    # Check if paper is in exclusion reasons set
    is_in_exclusion_set = papers_with_exclusion_reasons and paper_id and paper_id in papers_with_exclusion_reasons
    
    if is_in_exclusion_set:
        # This paper has an exclusion reason - skip reproduction categories
        # Should have been caught above, but if not, default to missing artifacts
        return 'Missing some artifacts (not code, e.g. data, model, etc.)'
    
    # Paper is NOT in exclusion reasons set - check reproduction status
    # Match EXACT order from pie chart logic (lines 1407-1464):
    # 1. Missing code (from not_reprod_df_filtered where has_code == 0)
    # 2. Has all artifacts but failed (from not_reprod_df_filtered where reproducible_all_artifacts == 1 AND not_reproduced_overall == 1)
    # 3. Partially reproduced below (only if included_final == 0, i.e., excluded)
    # 4. Missing some artifacts (remainder - default)
    
    # IMPORTANT: Check not_reproduced_overall FIRST (matching pie chart logic which uses not_reprod_df_filtered)
    if 'not_reproduced_overall' in row.index and row.get('not_reproduced_overall', 0) == 1:
        # 1. Check "Missing code" FIRST (from not_reprod_df_filtered, has_code == 0) - line 1408
        if 'has_code' in row.index:
            has_code = row.get('has_code', 0)
            if pd.isna(has_code) or has_code == 0:
                return 'Missing code'  # Match exact format from pie chart
        
        # 2. Check "Has all artifacts but failed" (from not_reprod_df_filtered, reproducible_all_artifacts == 1) - line 1413
        if ('reproducible_all_artifacts' in row.index and 
            row.get('reproducible_all_artifacts', 0) == 1):
            return 'Has all artifacts but failed'  # Match exact format from pie chart
    
    # 3. Check partially_reproduced_below (only if excluded, i.e., included_final == 0)
    # This matches pie chart logic: partial_below only counts papers with included_final == 0 (line 1451)
    if 'partially_reproduced_below' in row.index and 'included_final' in row.index:
        partial_below_val = row.get('partially_reproduced_below', 0)
        included_final_val = row.get('included_final', 0)
        # Only categorize as "Partially reproducible (below threshold)" if paper is EXCLUDED
        if pd.notna(partial_below_val) and pd.notna(included_final_val):
            try:
                val_int = int(float(partial_below_val))
                included_int = int(float(included_final_val))
                val_bool = bool(partial_below_val) if isinstance(partial_below_val, bool) else None
                val_str = str(partial_below_val).strip().lower()
            except (ValueError, TypeError):
                val_int = 0
                included_int = 0
                val_bool = None
                val_str = str(partial_below_val).strip().lower()
            
            if ((val_int == 1 or 
                 val_bool is True or 
                 (isinstance(partial_below_val, float) and partial_below_val == 1.0) or
                 val_str in ['1', 'true', '1.0', 'yes']) and
                included_int == 0):  # Only if excluded
                return 'Partially reproducible (below threshold)'  # Match exact format from pie chart
    
    # Check fully_reproduced and partially_reproduced_above
    # IMPORTANT: These categories should only apply to INCLUDED papers
    # If a paper is in excluded_df, it should NOT be categorized as "Fully Reproduced" or "Partially Reproduced (above threshold)"
    # Even if it has those flags, if it's excluded, it should be categorized as "Missing some artifacts"
    # (The pie chart doesn't show these categories in the excluded breakdown)
    # So we skip these checks for excluded papers - they'll default to "Missing some artifacts"
    
    # Default: Missing some artifacts (remainder)
    return 'Missing some artifacts (not code, e.g. data, model, etc.)'  # Match exact format from pie chart
    
    # Fallback: infer from Excel columns
    repro_status_col = None
    for col in row.index:
        if 'were the results reproduced' in col.lower():
            repro_status_col = col
            break
    
    is_reproducible_col = None
    for col in row.index:
        if 'is the study reproducible' in col.lower():
            is_reproducible_col = col
            break
    
    has_codebase_col = None
    for col in row.index:
        if 'has an associated codebase' in col.lower():
            has_codebase_col = col
            break
    
    is_off_topic_col = None
    for col in row.index:
        if 'does the paper discuss neuro-symbolic' in col.lower():
            is_off_topic_col = col
            break
    
    is_background_col = None
    for col in row.index:
        if 'not a review' in col.lower():
            is_background_col = col
            break
    
    is_research_col = None
    for col in row.index:
        if 'does the paper present an original research' in col.lower():
            is_research_col = col
            break
    
    has_fulltext_col = None
    for col in row.index:
        if 'is the full text available' in col.lower():
            has_fulltext_col = col
            break
    
    # Check "Not Attempted" reasons first
    if is_off_topic_col and pd.notna(row.get(is_off_topic_col)):
        if str(row[is_off_topic_col]).lower().strip() == 'no':
            return 'Not Attempted - Off Topic'
    
    if is_background_col and pd.notna(row.get(is_background_col)):
        if str(row[is_background_col]).lower().strip() == 'no':
            return 'Not Attempted - Background Article'
    
    if is_research_col and pd.notna(row.get(is_research_col)):
        if str(row[is_research_col]).lower().strip() == 'no':
            return 'Not Attempted - Not a Research Article'
    
    if has_fulltext_col and pd.notna(row.get(has_fulltext_col)):
        if str(row[has_fulltext_col]).lower().strip() == 'no':
            return 'Not Attempted - No Fulltext'
    
    # Check reproduction status
    if has_codebase_col and pd.notna(row.get(has_codebase_col)):
        has_codebase = str(row[has_codebase_col]).lower().strip() in ['yes', 'true', '1', 'y']
    else:
        has_codebase = False
    
    if not has_codebase:
        return 'Missing Code'
    
    # Fallback logic: only use if engineered features are not available
    # Check if we have engineered features - if so, we shouldn't reach here
    has_engineered_features = (
        'fully_reproduced' in row.index or 
        'partially_reproduced_above' in row.index or 
        'partially_reproduced_below' in row.index or
        'not_reproduced_overall' in row.index or
        'reproducible_all_artifacts' in row.index or
        'has_code' in row.index
    )
    
    if has_engineered_features:
        # If we have engineered features but reached here, something went wrong
        # Default to "Missing Some Artifacts" (the remainder category)
        return 'Missing Some Artifacts'
    
    # Only use fallback if no engineered features are available
    if repro_status_col and pd.notna(row.get(repro_status_col)):
        repro_status = str(row[repro_status_col]).lower().strip()
        if 'partial' in repro_status and 'below' in repro_status:
            return 'Partially Reproduced (Below Threshold)'
        elif 'partial' in repro_status and 'above' in repro_status:
            return 'Partially Reproduced (Above Threshold)'
        elif repro_status in ['yes', 'full', 'match']:
            return 'Fully Reproduced'
        elif repro_status in ['no', 'failed', 'not reproduced']:
            # Only categorize as "Has All Artifacts but Failed" if we can verify all artifacts are available
            # This is a fallback, so we can't be sure - default to "Missing Some Artifacts"
            return 'Missing Some Artifacts'
    
    return 'Missing Some Artifacts'  # Default


def generate_final_exclude(
    excluded_df: pd.DataFrame,
    include_json: List[Dict[str, Any]],
    matches: Dict[str, Dict[str, Any]],
    paper_id_col: str,
    title_col: Optional[str],
    cluster_links_dict: Optional[Dict[str, pd.DataFrame]] = None
) -> List[Dict[str, Any]]:
    """Generate final_exclude.json with all excluded papers using EXACT logic from run_reproducibility_analysis.py."""
    final_excluded = []
    
    # FIRST: Build papers_with_exclusion_reasons set using EXACT logic from run_reproducibility_analysis.py (lines 1371-1400)
    exclusion_reason_col = None
    for col in excluded_df.columns:
        if 'exclude' in col.lower() and 'reason' in col.lower() and 'if exclude' in col.lower():
            exclusion_reason_col = col
            break
    
    papers_with_exclusion_reasons = set()
    if exclusion_reason_col:
        for idx, row in excluded_df.iterrows():
            exclusion_reason = row.get(exclusion_reason_col)
            if pd.notna(exclusion_reason) and str(exclusion_reason).strip().lower() not in ['n/a', 'nan', 'none', '', 'not extracted from spreadsheet']:
                reason_str = str(exclusion_reason).strip()
                reason_lower = reason_str.lower()
                # Check if it matches any exclusion reason pattern
                if any(term in reason_lower for term in ['off topic', 'not neuro-symbolic', 'not neurosymbolic', 'off-topic', 'not neuro symbolic',
                                                          'background', 'review', 'survey',
                                                          'not a research', 'not research', 'not a research article',
                                                          'no fulltext', 'no full text', 'fulltext', 'no full-text', 'no full text available']):
                    if 'normalized_paper_id' in row.index:
                        papers_with_exclusion_reasons.add(row['normalized_paper_id'])
                    elif 'normalized_id' in row.index:
                        papers_with_exclusion_reasons.add(row['normalized_id'])
    
    print(f"  Found {len(papers_with_exclusion_reasons)} papers with exclusion reasons")
    
    # Get all article_ids that are included (to avoid duplicates)
    included_ids = set()
    for entry in matches.values():
        article_id = entry.get('article_id', '')
        if article_id:
            norm_id = normalize_paper_id(article_id)
            if norm_id:
                included_ids.add(norm_id)
    
    # Deduplicate excluded_df by normalized_paper_id (matching pie chart logic)
    if 'normalized_paper_id' in excluded_df.columns:
        excluded_df = excluded_df.drop_duplicates(subset=['normalized_paper_id'], keep='first')
    elif 'normalized_id' in excluded_df.columns:
        excluded_df = excluded_df.drop_duplicates(subset=['normalized_id'], keep='first')
    print(f"  After deduplication: {len(excluded_df)} excluded papers")
    
    # Process excluded Excel rows
    seen_paper_ids = set()  # Track to avoid duplicates in final_excluded
    papers_without_id = 0
    papers_filtered_out = 0
    for idx, row in excluded_df.iterrows():
        norm_id = row.get('normalized_id') or row.get('normalized_paper_id')
        
        # Skip if we've already processed this paper
        if norm_id and norm_id in seen_paper_ids:
            continue
        
        # Track papers without ID (they should still be processed)
        if not norm_id:
            papers_without_id += 1
            # Use row index as temporary ID to avoid duplicates
            norm_id = f"excel_row_{idx}"
        
        if norm_id:
            seen_paper_ids.add(norm_id)
        
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
            enriched = enrich_paper_with_excel_data(matched_entry, row, paper_id_col, title_col, cluster_links_dict)
            enriched['exclusion_reason'] = str(row.get('exclusion_reason', 'N/A')) if 'exclusion_reason' in row.index else 'N/A'
            # Add reproduction category using EXACT logic from run_reproducibility_analysis.py
            reproduction_category = determine_reproduction_category(row, papers_with_exclusion_reasons)
            enriched['reproduction_category'] = reproduction_category
            
            # NOTE: Don't filter out papers based on reproduction category
            # The decision column is the source of truth - if it says "Exclude", the paper is excluded
            # Even if it's "Fully Reproduced" or "Partially Reproduced (above threshold)", if decision says "Exclude", it stays excluded
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
            
            # Check for repository URL if no codebase
            codebase_cols = [c for c in row.index if 'codebase' in c.lower()]
            repo_cols = [c for c in row.index if 'repository' in c.lower()]
            
            has_codebase = False
            for codebase_col in codebase_cols:
                codebase_val = row.get(codebase_col)
                if pd.notna(codebase_val):
                    codebase_str = str(codebase_val).lower()
                    if codebase_str in ['yes', 'true', '1']:
                        has_codebase = True
                        break
            
            if not has_codebase:
                repo_url = None
                # Check Repository URL column
                for repo_col in repo_cols:
                    repo_val = row.get(repo_col)
                    if pd.notna(repo_val):
                        repo_str = str(repo_val).strip()
                        if repo_str and repo_str not in ['', 'N/A', 'nan', 'None', 'null', 'N']:
                            # Check if it looks like a URL
                            if repo_str.startswith('http://') or repo_str.startswith('https://') or repo_str.startswith('www.'):
                                repo_url = repo_str
                                break
                            elif '.' in repo_str and len(repo_str) > 5:
                                # Might be a URL without protocol
                                repo_url = repo_str if repo_str.startswith('http') else f"https://{repo_str}"
                                break
                
                # Check cluster_links if not found
                if not repo_url and cluster_links_dict is not None:
                    paper_id = str(row.get(paper_id_col, '')) if paper_id_col in row.index else ''
                    title = str(row.get(title_col, '')) if title_col and title_col in row.index else entry.get('title', '')
                    repo_url = find_repository_url(paper_id, title, cluster_links_dict)
                
                entry['repository_url'] = repo_url if repo_url else None
            
            # Add reproduction category using EXACT logic from run_reproducibility_analysis.py
            reproduction_category = determine_reproduction_category(row, papers_with_exclusion_reasons)
            entry['reproduction_category'] = reproduction_category
            
            # NOTE: Don't filter out papers based on reproduction category
            # The decision column is the source of truth - if it says "Exclude", the paper is excluded
            # Even if it's "Fully Reproduced" or "Partially Reproduced (above threshold)", if decision says "Exclude", it stays excluded
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
            # Don't add entries from include.json that aren't in Excel
            # These might be old entries that are no longer relevant
            # Only add if they're explicitly marked as excluded in customizations
            # and we can't find them in the Excel file
            pass  # Skip entries from include.json that aren't in Excel excluded list
    
    print(f"\nGenerated {len(final_excluded)} entries for final_exclude.json")
    print(f"  Papers filtered out (Fully/Partially above): {papers_filtered_out}")
    print(f"  Papers without ID: {papers_without_id}")
    print(f"  Expected: {len(excluded_df)} papers in excluded_df")
    print(f"  Actual in final_excluded: {len(final_excluded)}")
    return final_excluded


def main():
    """Main function."""
    print("="*80)
    print("Generate Final Include/Exclude Lists")
    print("="*80)
    
    # Load data
    df, included_df, excluded_df, paper_id_col, title_col = load_excel_data(EXCEL_FILE)
    include_json = load_include_json(INCLUDE_JSON)
    
    # Load cluster links file if it exists (all sheets)
    cluster_links_dict = None
    if CLUSTER_LINKS_FILE.exists():
        try:
            print(f"\nLoading cluster links file: {CLUSTER_LINKS_FILE}")
            xl_file = pd.ExcelFile(CLUSTER_LINKS_FILE)
            cluster_links_dict = {}
            total_entries = 0
            for sheet_name in xl_file.sheet_names:
                df = pd.read_excel(CLUSTER_LINKS_FILE, sheet_name=sheet_name)
                cluster_links_dict[sheet_name] = df
                total_entries += len(df)
                print(f"  Loaded sheet '{sheet_name}': {len(df)} entries")
            print(f"  Total entries across all sheets: {total_entries}")
        except Exception as e:
            print(f"  Warning: Could not load cluster links file: {e}")
            cluster_links_dict = None
    else:
        print(f"\nCluster links file not found: {CLUSTER_LINKS_FILE}")
    
    # Match papers
    matches = match_papers(df, include_json, paper_id_col, title_col)
    
    # Generate final lists
    final_included = generate_final_include(included_df, matches, paper_id_col, title_col, cluster_links_dict)
    final_excluded = generate_final_exclude(excluded_df, include_json, matches, paper_id_col, title_col, cluster_links_dict)
    
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

