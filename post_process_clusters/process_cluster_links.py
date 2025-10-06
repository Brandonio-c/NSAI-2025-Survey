#!/usr/bin/env python3
"""
Script to process cluster papers Excel file and add link columns based on include.json data.
For each sheet in the Excel workbook, adds three columns:
- codebase: GitHub and other code repository links
- data: Hugging Face and other data repository links  
- other_links: All other links found in the JSON data
"""

import pandas as pd
import json
import re
import os
from typing import Dict, List, Tuple

def clean_and_deduplicate_urls(urls: List[str]) -> List[str]:
    """
    Clean URLs by removing trailing punctuation and deduplicate.
    """
    cleaned_urls = []
    seen_urls = set()
    
    for url in urls:
        if not url or not url.strip():
            continue
            
        # Clean the URL
        clean_url = url.strip().rstrip('.,;:"')
        
        # Normalize GitHub URLs (remove trailing slashes, etc.)
        if 'github.com' in clean_url:
            clean_url = clean_url.rstrip('/')
        
        # Add to list if not seen before
        if clean_url not in seen_urls and clean_url.startswith('http'):
            cleaned_urls.append(clean_url)
            seen_urls.add(clean_url)
    
    return cleaned_urls

def extract_links_from_note(note: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Extract different types of links from the note field with comprehensive pattern matching.
    Returns: (codebase_links, data_links, other_links)
    """
    if not note:
        return [], [], []
    
    codebase_links = []
    data_links = []
    other_links = []
    
    # Comprehensive patterns for different types of links
    patterns = {
        'github': [
            r'https://github\.com/[^\s\]\},]+',  # Clean GitHub URLs
            r'github:[\s]*\[(https://github\.com/[^\s\]]+)\]',  # GitHub with brackets
            r'github:[\s]*\{(https://github\.com/[^\s\}]+)\}',  # GitHub with curly braces
        ],
        'gitlab': [
            r'https://gitlab\.com/[^\s\]\},]+',
            r'gitlab:[\s]*\[(https://gitlab\.com/[^\s\]]+)\]',
        ],
        'bitbucket': [
            r'https://bitbucket\.org/[^\s\]\},]+',
            r'bitbucket:[\s]*\[(https://bitbucket\.org/[^\s\]]+)\]',
        ],
        'huggingface': [
            r'https://huggingface\.co/[^\s\]\},]+',
            r'huggingface:[\s]*\[(https://huggingface\.co/[^\s\]]+)\]',
        ],
        'data_repos': [
            r'https://zenodo\.org/[^\s\]\},]+',
            r'https://figshare\.com/[^\s\]\},]+',
            r'https://kaggle\.com/[^\s\]\},]+',
            r'dataset[^\s]*[\s]*\[(https?://[^\s\]]+)\]',
        ],
        'papers': [
            r'https://arxiv\.org/[^\s\]\},]+',
            r'https://openreview\.net/[^\s\]\},]+',
            r'paper:[\s]*\[(https?://[^\s\]]+)\]',
        ],
        'general': [
            r'https?://[^\s\]\},]+',  # Catch-all for any URL
        ]
    }
    
    # Extract codebase links (GitHub, GitLab, Bitbucket)
    for pattern in patterns['github'] + patterns['gitlab'] + patterns['bitbucket']:
        matches = re.findall(pattern, note, re.IGNORECASE)
        for match in matches:
            # Handle both direct URLs and captured groups
            if isinstance(match, tuple):
                clean_url = match[0] if match[0] else match[1] if len(match) > 1 else None
            else:
                clean_url = match
            
            if clean_url and clean_url.startswith('http'):
                # Remove any trailing punctuation
                clean_url = clean_url.rstrip('.,;:"')
                if clean_url not in codebase_links:
                    codebase_links.append(clean_url)
    
    # Extract data links (Hugging Face, datasets, etc.)
    for pattern in patterns['huggingface'] + patterns['data_repos']:
        matches = re.findall(pattern, note, re.IGNORECASE)
        for match in matches:
            # Handle both direct URLs and captured groups
            if isinstance(match, tuple):
                clean_url = match[0] if match[0] else match[1] if len(match) > 1 else None
            else:
                clean_url = match
            
            if clean_url and clean_url.startswith('http'):
                # Remove any trailing punctuation
                clean_url = clean_url.rstrip('.,;:"')
                if clean_url not in data_links:
                    data_links.append(clean_url)
    
    # Extract all remaining URLs and categorize them
    all_urls = re.findall(patterns['general'][0], note)
    for url in all_urls:
        # Skip if already categorized
        if url in codebase_links or url in data_links:
            continue
            
        # Check if it's a paper link
        if any(domain in url.lower() for domain in ['arxiv.org', 'openreview.net', 'aclweb.org', 'acl-anthology.org']):
            if url not in other_links:
                other_links.append(url)
        # Check if it's a data-related link
        elif any(keyword in url.lower() for keyword in ['dataset', 'data', 'zenodo', 'figshare', 'kaggle', 'drive.google.com']):
            if url not in data_links:
                data_links.append(url)
        # Check if it's a code-related link (other than GitHub/GitLab/Bitbucket)
        elif any(keyword in url.lower() for keyword in ['code', 'source', 'repository', 'repo']):
            if url not in codebase_links:
                codebase_links.append(url)
        # Everything else goes to other_links
        else:
            if url not in other_links:
                other_links.append(url)
    
    # Clean and deduplicate all link lists
    codebase_links = clean_and_deduplicate_urls(codebase_links)
    data_links = clean_and_deduplicate_urls(data_links)
    other_links = clean_and_deduplicate_urls(other_links)
    
    return codebase_links, data_links, other_links

def load_json_data(json_file: str) -> Dict[str, Dict]:
    """
    Load JSON data and create a mapping by article_id (Rayyan ID).
    """
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Create mapping by article_id
    json_mapping = {}
    for entry in data:
        article_id = entry.get('article_id', '')
        if article_id:
            json_mapping[article_id] = entry
    
    return json_mapping

def process_excel_sheet(sheet_name: str, df: pd.DataFrame, json_mapping: Dict[str, Dict]) -> pd.DataFrame:
    """
    Process a single Excel sheet by adding the three link columns.
    """
    # Create new columns
    df['codebase'] = ''
    df['data'] = ''
    df['other_links'] = ''
    
    # Statistics tracking
    stats = {
        'total_rows': len(df),
        'matched_entries': 0,
        'entries_with_codebase': 0,
        'entries_with_data': 0,
        'entries_with_other': 0,
        'total_codebase_links': 0,
        'total_data_links': 0,
        'total_other_links': 0
    }
    
    # Process each row
    for idx, row in df.iterrows():
        paper_id = row['paper_id']
        
        if paper_id in json_mapping:
            stats['matched_entries'] += 1
            entry = json_mapping[paper_id]
            note = entry.get('note', '')
            
            # Extract links from the note
            codebase_links, data_links, other_links = extract_links_from_note(note)
            
            # Update statistics
            if codebase_links:
                stats['entries_with_codebase'] += 1
                stats['total_codebase_links'] += len(codebase_links)
            if data_links:
                stats['entries_with_data'] += 1
                stats['total_data_links'] += len(data_links)
            if other_links:
                stats['entries_with_other'] += 1
                stats['total_other_links'] += len(other_links)
            
            # Join links with semicolon separator
            df.at[idx, 'codebase'] = '; '.join(codebase_links)
            df.at[idx, 'data'] = '; '.join(data_links)
            df.at[idx, 'other_links'] = '; '.join(other_links)
    
    # Print detailed statistics
    print(f"  Detailed stats for {sheet_name}:")
    print(f"    Total rows: {stats['total_rows']}")
    print(f"    Matched entries: {stats['matched_entries']} ({stats['matched_entries']/stats['total_rows']*100:.1f}%)")
    print(f"    Entries with codebase links: {stats['entries_with_codebase']} ({stats['total_codebase_links']} total links)")
    print(f"    Entries with data links: {stats['entries_with_data']} ({stats['total_data_links']} total links)")
    print(f"    Entries with other links: {stats['entries_with_other']} ({stats['total_other_links']} total links)")
    
    return df

def main():
    # File paths
    excel_file = '/Users/coleloughbc/Documents/VSCode-Local/NSAI-2025-Survey/post_process_clusters/data/cluster_papers.xlsx'
    json_file = '/Users/coleloughbc/Documents/VSCode-Local/NSAI-2025-Survey/post_process_clusters/data/include.json'
    output_dir = '/Users/coleloughbc/Documents/VSCode-Local/NSAI-2025-Survey/post_process_clusters/output'
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print("Loading JSON data...")
    json_mapping = load_json_data(json_file)
    print(f"Loaded {len(json_mapping)} entries from JSON file")
    
    print("Processing Excel file...")
    # Read all sheets
    excel_file_obj = pd.ExcelFile(excel_file)
    sheet_names = excel_file_obj.sheet_names
    
    print(f"Found {len(sheet_names)} sheets: {sheet_names}")
    print("=" * 80)
    
    # Overall statistics
    total_stats = {
        'total_papers': 0,
        'total_matched': 0,
        'total_codebase_entries': 0,
        'total_data_entries': 0,
        'total_other_entries': 0,
        'total_codebase_links': 0,
        'total_data_links': 0,
        'total_other_links': 0
    }
    
    # Dictionary to store all processed sheets
    processed_sheets = {}
    
    # Process each sheet
    for sheet_name in sheet_names:
        print(f"Processing sheet: {sheet_name}")
        
        # Read the sheet
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        print(f"  Original shape: {df.shape}")
        
        # Process the sheet
        processed_df = process_excel_sheet(sheet_name, df, json_mapping)
        
        # Store the processed sheet
        processed_sheets[sheet_name] = processed_df
        
        # Count non-empty entries for this sheet
        codebase_count = (processed_df['codebase'] != '').sum()
        data_count = (processed_df['data'] != '').sum()
        other_links_count = (processed_df['other_links'] != '').sum()
        
        # Update overall statistics
        total_stats['total_papers'] += len(processed_df)
        total_stats['total_matched'] += (processed_df['codebase'] != '').sum() + (processed_df['data'] != '').sum() + (processed_df['other_links'] != '').sum()
        total_stats['total_codebase_entries'] += codebase_count
        total_stats['total_data_entries'] += data_count
        total_stats['total_other_entries'] += other_links_count
        
        # Count total links
        for col in ['codebase', 'data', 'other_links']:
            for links in processed_df[col]:
                if links and links.strip():
                    link_count = len([l for l in links.split(';') if l.strip()])
                    if col == 'codebase':
                        total_stats['total_codebase_links'] += link_count
                    elif col == 'data':
                        total_stats['total_data_links'] += link_count
                    else:
                        total_stats['total_other_links'] += link_count
        
        print(f"  Summary - Codebase: {codebase_count}, Data: {data_count}, Other: {other_links_count}")
        print()
    
    # Save all processed sheets to a single Excel workbook
    output_file = os.path.join(output_dir, "cluster_papers_with_links.xlsx")
    print(f"Saving all sheets to single workbook: {output_file}")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name, processed_df in processed_sheets.items():
            processed_df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"  Added sheet: {sheet_name} ({len(processed_df)} rows)")
    
    print(f"Successfully saved all {len(processed_sheets)} sheets to: {output_file}")
    print()
    
    # Print overall summary
    print("=" * 80)
    print("OVERALL SUMMARY:")
    print(f"Total papers processed: {total_stats['total_papers']}")
    print(f"Papers with any links: {total_stats['total_matched']} ({total_stats['total_matched']/total_stats['total_papers']*100:.1f}%)")
    print(f"Papers with codebase links: {total_stats['total_codebase_entries']} ({total_stats['total_codebase_links']} total links)")
    print(f"Papers with data links: {total_stats['total_data_entries']} ({total_stats['total_data_links']} total links)")
    print(f"Papers with other links: {total_stats['total_other_entries']} ({total_stats['total_other_links']} total links)")
    print(f"Total links extracted: {total_stats['total_codebase_links'] + total_stats['total_data_links'] + total_stats['total_other_links']}")
    print("Processing complete!")

if __name__ == "__main__":
    main()
