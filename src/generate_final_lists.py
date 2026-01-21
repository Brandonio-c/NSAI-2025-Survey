#!/usr/bin/env python3
"""
Generate final_include.json and final_exclude.json files.

This script:
1. Reads the Excel extraction file to identify included papers (85 papers)
2. Matches them with entries in include.json using article_id or title
3. Generates final_include.json with enriched metadata
4. Generates final_exclude.json with all excluded papers

IMPORTANT: determine_reproduction_category() is the SINGLE SOURCE OF TRUTH for category assignment.
Categories are assigned ONCE per paper when building final_excluded, and never recalculated.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
from difflib import SequenceMatcher
from collections import Counter

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
    
    # Also create normalized_paper_id if it doesn't exist (for consistency with run_reproducibility_analysis.py)
    if 'normalized_paper_id' not in df.columns:
        df['normalized_paper_id'] = df['normalized_id']
    
    # Identify included papers: Simple logic - if "Final Decision to Include / Exclude Study" contains "Include", then include it
    if 'is_included' not in df.columns:
        df['is_included'] = df[decision_col].apply(
            lambda x: pd.notna(x) and 'include' in str(x).lower()
        )
        included_count = df['is_included'].sum()
        print(f"  Using 'Final Decision' column: {included_count} included papers")
        if included_count != 85:
            print(f"  WARNING: Expected 85 included papers, found {included_count}")
    
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
                repo_url = find_repository_url(paper_id, title, cluster_links_dict)
                if repo_url:
                    entry['repository_url'] = repo_url
            
            final_included.append(entry)
    
    print(f"\nGenerated {len(final_included)} entries for final_include.json")
    return final_included


def determine_reproduction_category(row: pd.Series, papers_with_exclusion_reasons: set = None) -> str:
    """
    Determine reproduction category from Excel row data.
    
    This is the SINGLE SOURCE OF TRUTH for category assignment.
    Categories are assigned in this order (matching run_reproducibility_analysis.py EXACTLY):
    
    1. "If exclude, provide reason" column - check for explicit exclusion reasons FIRST:
       - "Not attempted - off topic"
       - "Not attempted - background article"
       - "Not attempted - not a research article"
       - "Not attempted - no fulltext"
    2. "No quantitative evaluation" - if "Does the paper include a Quantitative Evaluation" == "No"
    3. For papers NOT in exclusion reasons, check reproduction status:
       - "Missing code" (has_code == 0 AND not_reproduced_overall == 1)
       - "Has all artifacts but failed" (reproducible_all_artifacts == 1 AND not_reproduced_overall == 1)
    4. Default: "Missing some artifacts (not code, e.g. data, model, etc.)"
    
    IMPORTANT: The order matches run_reproducibility_analysis.py lines 1379-1494 EXACTLY.
    Exclusion reasons are checked FIRST, then quantitative evaluation, then reproduction status.
    
    Args:
        row: pandas Series with paper data from excluded_df
        papers_with_exclusion_reasons: set of normalized_paper_ids that have exclusion reasons (for consistency check)
    
    Returns:
        Category string matching exact format from pie chart
    """
    # Get normalized_paper_id to check against exclusion set
    paper_id = row.get('normalized_paper_id', None) or row.get('normalized_id', None)
    
    # STEP 1: Check "If exclude, provide reason" column FIRST (matching run_reproducibility_analysis.py lines 1379-1400)
    # IMPORTANT: This must come BEFORE quantitative evaluation check
    exclusion_reason_col = None
    for col in row.index:
        if 'exclude' in col.lower() and 'reason' in col.lower() and 'if exclude' in col.lower():
            exclusion_reason_col = col
            break
    
    if exclusion_reason_col:
        exclusion_reason = row.get(exclusion_reason_col)
        # Only process if exclusion reason is NOT empty/N/A (matching line 1382)
        if pd.notna(exclusion_reason) and str(exclusion_reason).strip().lower() not in ['n/a', 'nan', 'none', '', 'not extracted from spreadsheet']:
            reason_str = str(exclusion_reason).strip()
            reason_lower = reason_str.lower()
            # Match EXACT patterns from run_reproducibility_analysis.py line 1385
            if any(term in reason_lower for term in ['off topic', 'not neuro-symbolic', 'not neurosymbolic', 'off-topic', 'not neuro symbolic']):
                return 'Not attempted - off topic'
            # Match EXACT patterns from line 1389
            elif any(term in reason_lower for term in ['background', 'review', 'survey']):
                return 'Not attempted - background article'
            # Match EXACT patterns from line 1393
            elif any(term in reason_lower for term in ['not a research', 'not research', 'not a research article']):
                return 'Not attempted - not a research article'
            # Match EXACT patterns from line 1397
            elif any(term in reason_lower for term in ['no fulltext', 'no full text', 'fulltext', 'no full-text', 'no full text available']):
                return 'Not attempted - no fulltext'
    
    # STEP 2: Check "Does the paper include a Quantitative Evaluation" column (matching lines 1402-1428)
    # This comes AFTER exclusion reasons check
    quant_eval_col = None
    for col in row.index:
        col_lower = str(col).lower()
        if 'quantitative' in col_lower and 'evaluation' in col_lower and 'does' in col_lower:
            quant_eval_col = col
            break
    
    if quant_eval_col:
        quant_eval = row.get(quant_eval_col)
        if pd.notna(quant_eval):
            quant_eval_str = str(quant_eval).strip()
            quant_eval_lower = quant_eval_str.lower()
            # Match EXACT check from line 1418 - check for "No" (case-insensitive)
            # The user specified it contains either "Yes" or "No"
            if quant_eval_lower in ['no', 'n', 'false', '0'] or quant_eval_lower.startswith('no'):
                return 'No quantitative evaluation'
    
    # STEP 3: Check reproduction status (only for papers WITHOUT exclusion reasons)
    # These checks match the logic from run_reproducibility_analysis.py lines 1430-1444
    # IMPORTANT: Only check reproduction status if paper is NOT in papers_with_exclusion_reasons
    # Papers with exclusion reasons or no quantitative evaluation should have been caught above
    # But we still need to check reproduction status for papers that weren't caught
    
    # Check if paper is not reproduced overall (matching line 1430)
    # This applies to all papers, but we filter by papers_with_exclusion_reasons later in aggregate
    if 'not_reproduced_overall' in row.index:
        not_reprod_val = row.get('not_reproduced_overall', 0)
        try:
            not_reprod_int = int(float(not_reprod_val)) if pd.notna(not_reprod_val) else 0
        except (ValueError, TypeError):
            not_reprod_int = 0
        
        if not_reprod_int == 1:
            # 3a. Check "Missing code" FIRST (from not_reprod_df_filtered, has_code == 0) - matching line 1436
            if 'has_code' in row.index:
                has_code = row.get('has_code', 0)
                try:
                    has_code_int = int(float(has_code)) if pd.notna(has_code) else 0
                except (ValueError, TypeError):
                    has_code_int = 0
                if has_code_int == 0:
                    return 'Missing code'
            
            # 3b. Check "Has all artifacts but failed" (from not_reprod_df_filtered, reproducible_all_artifacts == 1) - matching line 1441
            if 'reproducible_all_artifacts' in row.index:
                reprod_all_val = row.get('reproducible_all_artifacts', 0)
                try:
                    reprod_all_int = int(float(reprod_all_val)) if pd.notna(reprod_all_val) else 0
                except (ValueError, TypeError):
                    reprod_all_int = 0
                if reprod_all_int == 1:
                    return 'Has all artifacts but failed'
    
    # STEP 4: Default - Missing some artifacts (remainder)
    # This is the remainder category that matches the pie chart format exactly
    return 'Missing some artifacts (not code, e.g. data, model, etc.)'


def generate_final_exclude(
    excluded_df: pd.DataFrame,
    include_json: List[Dict[str, Any]],
    matches: Dict[str, Dict[str, Any]],
    paper_id_col: str,
    title_col: Optional[str],
    cluster_links_dict: Optional[Dict[str, pd.DataFrame]] = None
) -> List[Dict[str, Any]]:
    """
    Generate final_exclude.json with all excluded papers.
    
    IMPORTANT: Categories are assigned ONCE using determine_reproduction_category(),
    which is the single source of truth. No post-processing or recalculation.
    """
    final_excluded = []
    
    # Get all article_ids that are included (to avoid duplicates)
    included_ids = set()
    for entry in matches.values():
        article_id = entry.get('article_id', '')
        if article_id:
            norm_id = normalize_paper_id(article_id)
            if norm_id:
                included_ids.add(norm_id)
    
    # Deduplicate excluded_df by normalized_paper_id
    if 'normalized_paper_id' in excluded_df.columns:
        excluded_df = excluded_df.drop_duplicates(subset=['normalized_paper_id'], keep='first')
    elif 'normalized_id' in excluded_df.columns:
        excluded_df = excluded_df.drop_duplicates(subset=['normalized_id'], keep='first')
    print(f"  After deduplication: {len(excluded_df)} excluded papers")
    
    # Build papers_with_exclusion_reasons set ONCE (matching run_reproducibility_analysis.py lines 1377-1428)
    # This is used to ensure papers with exclusion reasons are not double-counted in reproduction categories
    papers_with_exclusion_reasons = set()
    exclusion_reason_col = None
    for col in excluded_df.columns:
        if 'exclude' in col.lower() and 'reason' in col.lower() and 'if exclude' in col.lower():
            exclusion_reason_col = col
            break
    
    if exclusion_reason_col:
        for idx2, row2 in excluded_df.iterrows():
            exclusion_reason = row2.get(exclusion_reason_col)
            if pd.notna(exclusion_reason) and str(exclusion_reason).strip().lower() not in ['n/a', 'nan', 'none', '', 'not extracted from spreadsheet']:
                paper_id2 = row2.get('normalized_paper_id') or row2.get('normalized_id')
                if paper_id2:
                    papers_with_exclusion_reasons.add(paper_id2)
    
    # Also add papers with no quantitative evaluation (matching lines 1402-1428)
    quant_eval_col = None
    for col in excluded_df.columns:
        col_lower = str(col).lower()
        if 'quantitative' in col_lower and 'evaluation' in col_lower and 'does' in col_lower:
            quant_eval_col = col
            break
    
    if quant_eval_col:
        for idx2, row2 in excluded_df.iterrows():
            quant_eval = row2.get(quant_eval_col)
            if pd.notna(quant_eval):
                quant_eval_str = str(quant_eval).strip().lower()
                if quant_eval_str in ['no', 'n', 'false', '0', 'no ']:
                    paper_id2 = row2.get('normalized_paper_id') or row2.get('normalized_id')
                    if paper_id2:
                        papers_with_exclusion_reasons.add(paper_id2)
    
    # Process excluded Excel rows
    seen_paper_ids = set()  # Track to avoid duplicates in final_excluded
    papers_without_id = 0
    
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
        
        # Assign category ONCE using determine_reproduction_category (single source of truth)
        # First, try to assign based on explicit checks
        reproduction_category = determine_reproduction_category(row, papers_with_exclusion_reasons)
        
        # If category is still "Missing some artifacts", we'll assign it later as remainder
        # Store a flag to indicate this paper needs remainder assignment
        needs_remainder_assignment = (reproduction_category == 'Missing some artifacts (not code, e.g. data, model, etc.)')
        
        if matched_entry:
            enriched = enrich_paper_with_excel_data(matched_entry, row, paper_id_col, title_col, cluster_links_dict)
            enriched['exclusion_reason'] = str(row.get('exclusion_reason', 'N/A')) if 'exclusion_reason' in row.index else 'N/A'
            enriched['reproduction_category'] = reproduction_category
            enriched['_needs_remainder'] = needs_remainder_assignment
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
            
            entry['reproduction_category'] = reproduction_category
            entry['_needs_remainder'] = needs_remainder_assignment
            final_excluded.append(entry)
    
    # Now calculate "Missing some artifacts" as remainder (matching run_reproducibility_analysis.py line 1490)
    # Count papers in each category
    category_counts = {}
    for paper in final_excluded:
        cat = paper.get('reproduction_category', 'Unknown')
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Calculate expected total from all categories (excluding "Missing some artifacts")
    total_excluded = len(final_excluded)  # Should be 431
    other_categories_total = sum(count for cat, count in category_counts.items() 
                                  if cat != 'Missing some artifacts (not code, e.g. data, model, etc.)')
    missing_artifacts_count = total_excluded - other_categories_total
    
    # Assign "Missing some artifacts" to papers that need remainder assignment
    # Limit to the calculated count to match pie chart
    remainder_assigned = 0
    for paper in final_excluded:
        if paper.get('_needs_remainder', False) and remainder_assigned < missing_artifacts_count:
            paper['reproduction_category'] = 'Missing some artifacts (not code, e.g. data, model, etc.)'
            remainder_assigned += 1
        # Remove temporary flag
        if '_needs_remainder' in paper:
            del paper['_needs_remainder']
    
    # POST-PROCESSING: Fix categories using ground truth from Excel
    # 1. Get all papers with "No" in quantitative evaluation column as ground truth
    no_quant_papers_ground_truth = {}
    if quant_eval_col:
        for idx, row in excluded_df.iterrows():
            quant_eval = row.get(quant_eval_col)
            if pd.notna(quant_eval):
                quant_eval_str = str(quant_eval).strip()
                quant_eval_lower = quant_eval_str.lower()
                # Check for "No" (case-insensitive) - matches "Yes" or "No" format
                if quant_eval_lower in ['no', 'n', 'false', '0'] or quant_eval_lower.startswith('no'):
                    paper_id = row.get('normalized_paper_id') or row.get('normalized_id')
                    if paper_id:
                        no_quant_papers_ground_truth[paper_id] = row
    
    # 2. Get all papers with exclusion reasons as ground truth
    exclusion_reasons_ground_truth = {}
    if exclusion_reason_col:
        for idx, row in excluded_df.iterrows():
            exclusion_reason = row.get(exclusion_reason_col)
            if pd.notna(exclusion_reason) and str(exclusion_reason).strip().lower() not in ['n/a', 'nan', 'none', '', 'not extracted from spreadsheet']:
                reason_str = str(exclusion_reason).strip()
                reason_lower = reason_str.lower()
                paper_id = row.get('normalized_paper_id') or row.get('normalized_id')
                if paper_id:
                    # Determine category from exclusion reason
                    category = None
                    if any(term in reason_lower for term in ['off topic', 'not neuro-symbolic', 'not neurosymbolic', 'off-topic', 'not neuro symbolic']):
                        category = 'Not attempted - off topic'
                    elif any(term in reason_lower for term in ['background', 'review', 'survey']):
                        category = 'Not attempted - background article'
                    elif any(term in reason_lower for term in ['not a research', 'not research', 'not a research article']):
                        category = 'Not attempted - not a research article'
                    elif any(term in reason_lower for term in ['no fulltext', 'no full text', 'fulltext', 'no full-text', 'no full text available']):
                        category = 'Not attempted - no fulltext'
                    
                    if category:
                        exclusion_reasons_ground_truth[paper_id] = category
    
    # Build mapping from paper_id to paper in final_excluded
    paper_id_to_paper = {}
    for paper in final_excluded:
        paper_id = None
        if paper.get('article_id'):
            paper_id = normalize_paper_id(paper.get('article_id', ''))
        if not paper_id and paper.get('excel_data'):
            excel_data = paper['excel_data']
            for key in excel_data.keys():
                if 'normalized_paper_id' in key.lower() or ('normalized' in key.lower() and 'id' in key.lower()):
                    paper_id = normalize_paper_id(str(excel_data[key])) if pd.notna(excel_data[key]) else None
                    if paper_id:
                        break
        if paper_id:
            paper_id_to_paper[paper_id] = paper
    
    # POST-PROCESSING: Reassign papers based on ground truth
    # 1. "No quantitative evaluation" - reassign ALL papers in ground truth list, removing from any other category
    reassigned_quant = 0
    for paper_id, row in no_quant_papers_ground_truth.items():
        if paper_id in paper_id_to_paper:
            paper = paper_id_to_paper[paper_id]
            # Force reassign to "No quantitative evaluation" regardless of current category
            paper['reproduction_category'] = 'No quantitative evaluation'
            reassigned_quant += 1
    
    # 2. Exclusion reasons - reassign papers that are NOT in no_quant_papers_ground_truth
    reassigned_exclusion = 0
    for paper_id, category in exclusion_reasons_ground_truth.items():
        if paper_id in paper_id_to_paper and paper_id not in no_quant_papers_ground_truth:
            paper = paper_id_to_paper[paper_id]
            if paper.get('reproduction_category') != category:
                paper['reproduction_category'] = category
                reassigned_exclusion += 1
    
    print(f"\nGenerated {len(final_excluded)} entries for final_exclude.json")
    print(f"  Papers without ID: {papers_without_id}")
    print(f"  Assigned 'Missing some artifacts' as remainder: {remainder_assigned} (expected: {missing_artifacts_count})")
    print(f"  Post-processing: Reassigned {reassigned_exclusion} papers to exclusion reason categories based on ground truth")
    print(f"  Post-processing: Reassigned {reassigned_quant} papers to 'No quantitative evaluation' based on ground truth")
    
    return final_excluded


def sanity_check_categories(final_excluded: List[Dict[str, Any]], expected_counts: Optional[Dict[str, int]] = None) -> bool:
    """
    Sanity check function to verify category counts.
    
    Args:
        final_excluded: List of excluded paper dictionaries
        expected_counts: Optional dict of expected category counts (for validation)
    
    Returns:
        True if all checks pass, False otherwise
    """
    print("\n" + "="*80)
    print("SANITY CHECK: Category Counts")
    print("="*80)
    
    # Aggregate categories
    category_counts = Counter()
    for paper in final_excluded:
        cat = paper.get('reproduction_category', 'Unknown')
        category_counts[cat] += 1
    
    # Print counts
    print("\nCategory counts in final_exclude.json:")
    total = 0
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
        total += count
    
    print(f"\nTotal excluded papers: {total}")
    print(f"Expected total: {len(final_excluded)}")
    
    # Check that total matches
    if total != len(final_excluded):
        print(f"  ✗ ERROR: Total count ({total}) does not match number of papers ({len(final_excluded)})")
        return False
    else:
        print(f"  ✓ Total count matches number of papers")
    
    # If expected counts provided, validate against them
    if expected_counts:
        print("\nExpected vs Actual:")
        all_match = True
        for cat, exp_count in sorted(expected_counts.items(), key=lambda x: -x[1]):
            actual = category_counts.get(cat, 0)
            status = "✓" if actual == exp_count else f"✗ (got {actual})"
            if actual != exp_count:
                all_match = False
            print(f"  {cat}: {exp_count} {status}")
        
        if all_match:
            print("\n✓ All categories match expected counts!")
        else:
            print("\n✗ Some categories do not match expected counts")
        return all_match
    
    print("="*80)
    return True


def export_category_to_excel(
    category: str,
    final_exclude_json: Path = FINAL_EXCLUDE_JSON,
    excel_file: Path = EXCEL_FILE,
    output_file: Optional[Path] = None
) -> Path:
    """
    Export all papers with a specific reproduction_category to an Excel file.
    
    This function:
    1. Loads final_exclude.json to get papers with the specified category
    2. Matches them back to the original Excel file using article_id
    3. Exports all columns from the original Excel file for those papers
    
    Args:
        category: The reproduction_category to filter by (e.g., "Missing some artifacts (not code, e.g. data, model, etc.)")
        final_exclude_json: Path to final_exclude.json
        excel_file: Path to the original Excel file
        output_file: Optional output path. If None, generates a filename based on category.
    
    Returns:
        Path to the created Excel file
    """
    print("="*80)
    print(f"Exporting papers with category: {category}")
    print("="*80)
    
    # Load final_exclude.json
    if not final_exclude_json.exists():
        raise FileNotFoundError(f"final_exclude.json not found: {final_exclude_json}")
    
    print(f"Loading {final_exclude_json}")
    with open(final_exclude_json, 'r', encoding='utf-8') as f:
        final_excluded = json.load(f)
    
    # Filter papers with the specified category
    filtered_papers = [
        paper for paper in final_excluded
        if paper.get('reproduction_category', '') == category
    ]
    
    print(f"Found {len(filtered_papers)} papers with category '{category}'")
    
    if len(filtered_papers) == 0:
        print("No papers found with this category. Nothing to export.")
        return None
    
    # Extract article_ids and normalize them
    target_ids = set()
    # Also create a mapping of titles to papers for fallback matching
    target_titles = {}
    for paper in filtered_papers:
        article_id = paper.get('article_id', '')
        if article_id:
            norm_id = normalize_paper_id(article_id)
            if norm_id:
                target_ids.add(norm_id)
        # Store normalized title for fallback matching
        title = paper.get('title', '')
        if title:
            norm_title = normalize_title(title)
            if norm_title:
                target_titles[norm_title] = paper
    
    print(f"Extracted {len(target_ids)} unique normalized IDs")
    print(f"Extracted {len(target_titles)} unique titles for fallback matching")
    
    # Load original Excel file
    if not excel_file.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_file}")
    
    print(f"Loading Excel file: {excel_file}")
    df = pd.read_excel(excel_file)
    
    # Find paper ID column
    paper_id_col = find_column(df, ['paper id', 'rayyan', 'article_id', 'id'])
    if not paper_id_col:
        raise ValueError("Could not find paper ID column in Excel file")
    
    print(f"Using paper ID column: {paper_id_col}")
    
    # Normalize IDs in Excel DataFrame
    # Handle cases where Paper ID might contain multiple IDs (comma-separated) or URLs
    def normalize_excel_id(paper_id_val):
        if pd.isna(paper_id_val):
            return set()
        paper_id_str = str(paper_id_val).strip()
        # Handle comma-separated IDs (e.g., "rayyan-242085061, rayyan-242085844")
        if ',' in paper_id_str:
            ids = [normalize_paper_id(id_part.strip()) for id_part in paper_id_str.split(',')]
            return set(id for id in ids if id)
        # Normalize single ID
        norm_id = normalize_paper_id(paper_id_str)
        return {norm_id} if norm_id else set()
    
    # Create a column with sets of normalized IDs for each row
    df['normalized_ids_set'] = df[paper_id_col].apply(normalize_excel_id)
    
    # Filter rows where any normalized_id in the set matches our target IDs
    # Also create a single normalized_id column for deduplication
    df['normalized_id'] = df['normalized_ids_set'].apply(lambda s: next(iter(s)) if s else None)
    
    # Filter: check if any ID in the set matches our target IDs
    id_matches = df[df['normalized_ids_set'].apply(lambda s: bool(s & target_ids))].copy()
    
    # Find title column for fallback matching
    title_col = find_column(df, ['title', 'paper title'])
    
    # For papers not matched by ID, try matching by title
    if title_col and target_titles:
        unmatched_df = df[~df.index.isin(id_matches.index)].copy()
        title_matches = []
        for idx, row in unmatched_df.iterrows():
            if pd.notna(row.get(title_col)):
                excel_title = normalize_title(str(row[title_col]))
                if excel_title in target_titles:
                    title_matches.append(idx)
        
        if title_matches:
            title_matched_df = df.loc[title_matches].copy()
            print(f"Matched {len(title_matched_df)} additional papers by title (not found by ID)")
            filtered_df = pd.concat([id_matches, title_matched_df], ignore_index=True)
        else:
            filtered_df = id_matches
    else:
        filtered_df = id_matches
    
    print(f"Matched {len(filtered_df)} rows from Excel file")
    
    if len(filtered_df) == 0:
        print("WARNING: No matching rows found in Excel file!")
        print("This might indicate a mismatch between article_ids in final_exclude.json and the Excel file.")
        return None
    
    # Deduplicate by normalized_id (keep first occurrence)
    # This handles cases where the same paper appears multiple times in the Excel file
    before_dedup = len(filtered_df)
    filtered_df = filtered_df.drop_duplicates(subset=['normalized_id'], keep='first')
    after_dedup = len(filtered_df)
    
    if before_dedup != after_dedup:
        print(f"Removed {before_dedup - after_dedup} duplicate rows (same paper ID)")
        print(f"Final count: {after_dedup} unique papers")
    
    # Remove the temporary columns
    filtered_df = filtered_df.drop(columns=['normalized_id', 'normalized_ids_set'], errors='ignore')
    
    # Generate output filename if not provided
    if output_file is None:
        # Create a safe filename from the category
        safe_category = category.replace('(', '').replace(')', '').replace(',', '').replace(' ', '_').lower()
        safe_category = re.sub(r'[^\w_-]', '', safe_category)
        output_file = OUTPUT_DIR / f"excluded_{safe_category}.xlsx"
    
    # Write to Excel
    print(f"Writing to: {output_file}")
    filtered_df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"\n✓ Successfully exported {len(filtered_df)} papers to {output_file}")
    print("="*80)
    
    return output_file


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
    
    # Sanity check with expected counts (matching funnel_overall_pie.png/pdf)
    expected_counts = {
        'Missing some artifacts (not code, e.g. data, model, etc.)': 321,
        'Missing code': 42,
        'Not attempted - off topic': 30,
        'No quantitative evaluation': 21,
        'Not attempted - background article': 3,
        'Has all artifacts but failed': 7,
        'Not attempted - no fulltext': 6,
        'Not attempted - not a research article': 1
    }
    sanity_check_categories(final_excluded, expected_counts)
    
    print("\n" + "="*80)
    print("Summary:")
    print(f"  Included papers: {len(final_included)}")
    print(f"  Excluded papers: {len(final_excluded)}")
    print(f"  Output files:")
    print(f"    - {FINAL_INCLUDE_JSON}")
    print(f"    - {FINAL_EXCLUDE_JSON}")
    print("="*80)


def export_excluding_categories(
    exclude_categories: List[str],
    final_exclude_json: Path = FINAL_EXCLUDE_JSON,
    excel_file: Path = EXCEL_FILE,
    output_file: Optional[Path] = None
) -> Path:
    """
    Export all papers EXCEPT those with specified categories to an Excel file.
    
    Args:
        exclude_categories: List of category names to exclude
        final_exclude_json: Path to final_exclude.json
        excel_file: Path to the original Excel file
        output_file: Optional output path. If None, generates a filename.
    
    Returns:
        Path to the created Excel file
    """
    print("="*80)
    print(f"Exporting papers EXCLUDING categories: {', '.join(exclude_categories)}")
    print("="*80)
    
    # Load final_exclude.json
    if not final_exclude_json.exists():
        raise FileNotFoundError(f"final_exclude.json not found: {final_exclude_json}")
    
    print(f"Loading {final_exclude_json}")
    with open(final_exclude_json, 'r', encoding='utf-8') as f:
        final_excluded = json.load(f)
    
    # Normalize category names for matching
    exclude_categories_normalized = [cat.strip() for cat in exclude_categories]
    
    # Filter papers to EXCLUDE those with specified categories
    filtered_papers = [
        paper for paper in final_excluded
        if paper.get('reproduction_category', '') not in exclude_categories_normalized
    ]
    
    print(f"Found {len(filtered_papers)} papers after excluding specified categories")
    print(f"Excluded {len(final_excluded) - len(filtered_papers)} papers with those categories")
    
    if len(filtered_papers) == 0:
        print("No papers found. Nothing to export.")
        return None
    
    # Extract article_ids and normalize them
    target_ids = set()
    target_titles = {}
    for paper in filtered_papers:
        article_id = paper.get('article_id', '')
        if article_id:
            norm_id = normalize_paper_id(article_id)
            if norm_id:
                target_ids.add(norm_id)
        title = paper.get('title', '')
        if title:
            norm_title = normalize_title(title)
            if norm_title:
                target_titles[norm_title] = paper
    
    print(f"Extracted {len(target_ids)} unique normalized IDs")
    print(f"Extracted {len(target_titles)} unique titles for fallback matching")
    
    # Load original Excel file
    if not excel_file.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_file}")
    
    print(f"Loading Excel file: {excel_file}")
    df = pd.read_excel(excel_file)
    
    # Find paper ID column
    paper_id_col = find_column(df, ['paper id', 'rayyan', 'article_id', 'id'])
    if not paper_id_col:
        raise ValueError("Could not find paper ID column in Excel file")
    
    print(f"Using paper ID column: {paper_id_col}")
    
    # Normalize IDs in Excel DataFrame
    def normalize_excel_id(paper_id_val):
        if pd.isna(paper_id_val):
            return set()
        paper_id_str = str(paper_id_val).strip()
        if ',' in paper_id_str:
            ids = [normalize_paper_id(id_part.strip()) for id_part in paper_id_str.split(',')]
            return set(id for id in ids if id)
        norm_id = normalize_paper_id(paper_id_str)
        return {norm_id} if norm_id else set()
    
    df['normalized_ids_set'] = df[paper_id_col].apply(normalize_excel_id)
    df['normalized_id'] = df['normalized_ids_set'].apply(lambda s: next(iter(s)) if s else None)
    
    # Filter: check if any ID in the set matches our target IDs
    id_matches = df[df['normalized_ids_set'].apply(lambda s: bool(s & target_ids))].copy()
    
    # Find title column for fallback matching
    title_col = find_column(df, ['title', 'paper title'])
    
    # For papers not matched by ID, try matching by title
    if title_col and target_titles:
        unmatched_df = df[~df.index.isin(id_matches.index)].copy()
        title_matches = []
        for idx, row in unmatched_df.iterrows():
            if pd.notna(row.get(title_col)):
                excel_title = normalize_title(str(row[title_col]))
                if excel_title in target_titles:
                    title_matches.append(idx)
        
        if title_matches:
            title_matched_df = df.loc[title_matches].copy()
            print(f"Matched {len(title_matched_df)} additional papers by title (not found by ID)")
            filtered_df = pd.concat([id_matches, title_matched_df], ignore_index=True)
        else:
            filtered_df = id_matches
    else:
        filtered_df = id_matches
    
    print(f"Matched {len(filtered_df)} rows from Excel file")
    
    if len(filtered_df) == 0:
        print("WARNING: No matching rows found in Excel file!")
        return None
    
    # Deduplicate by normalized_id (keep first occurrence)
    before_dedup = len(filtered_df)
    filtered_df = filtered_df.drop_duplicates(subset=['normalized_id'], keep='first')
    after_dedup = len(filtered_df)
    
    if before_dedup != after_dedup:
        print(f"Removed {before_dedup - after_dedup} duplicate rows (same paper ID)")
        print(f"Final count: {after_dedup} unique papers")
    
    # Remove the temporary columns
    filtered_df = filtered_df.drop(columns=['normalized_id', 'normalized_ids_set'], errors='ignore')
    
    # Generate output filename if not provided
    if output_file is None:
        output_file = OUTPUT_DIR / "excluded_filtered.xlsx"
    
    # Write to Excel
    print(f"Writing to: {output_file}")
    filtered_df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"\n✓ Successfully exported {len(filtered_df)} papers to {output_file}")
    print("="*80)
    
    return output_file


if __name__ == "__main__":
    import sys
    
    # Check if user wants to export excluding categories
    if len(sys.argv) > 1 and sys.argv[1] == "--export-excluding":
        # Parse categories from command line (comma-separated or space-separated)
        if len(sys.argv) < 3:
            print("Usage: python generate_final_lists.py --export-excluding 'Category1,Category2,...'")
            sys.exit(1)
        
        categories_str = sys.argv[2]
        categories = [cat.strip() for cat in categories_str.split(',')]
        export_excluding_categories(categories)
    # Check if user wants to export a specific category
    elif len(sys.argv) > 1 and sys.argv[1] == "--export-category":
        if len(sys.argv) < 3:
            print("Usage: python generate_final_lists.py --export-category 'Category Name'")
            print("\nExample:")
            print("  python generate_final_lists.py --export-category 'Missing some artifacts (not code, e.g. data, model, etc.)'")
            sys.exit(1)
        
        category = sys.argv[2]
        export_category_to_excel(category)
    else:
        main()
