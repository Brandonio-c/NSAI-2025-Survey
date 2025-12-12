#!/usr/bin/env python3
"""
Filter BibTeX entries to create final_included_articles.bib.

This script:
1. Reads final_exclude.json to get a list of excluded article IDs
2. Reads included_articles.bib to get all BibTeX entries
3. Filters out excluded papers from the BibTeX entries
4. Writes the remaining entries to final_included_articles.bib
"""

import json
import re
from pathlib import Path
from typing import Set, List, Tuple

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
FINAL_EXCLUDE_JSON = PROJECT_ROOT / "docs" / "data" / "final_exclude.json"
INCLUDED_ARTICLES_BIB = PROJECT_ROOT / "docs" / "data" / "included_articles.bib"
FINAL_INCLUDED_ARTICLES_BIB = PROJECT_ROOT / "docs" / "data" / "final_included_articles.bib"


def normalize_article_id(article_id: str) -> str:
    """Normalize article ID by removing 'rayyan-' prefix if present."""
    if not article_id:
        return ""
    article_id = str(article_id).strip()
    # Remove 'rayyan-' prefix if present
    if article_id.lower().startswith('rayyan-'):
        article_id = article_id[7:]
    return article_id.lower()


def load_excluded_ids(exclude_json_path: Path) -> Set[str]:
    """Load excluded article IDs from JSON file."""
    print(f"Loading excluded article IDs from: {exclude_json_path}")
    
    with open(exclude_json_path, 'r', encoding='utf-8') as f:
        excluded_data = json.load(f)
    
    excluded_ids = set()
    for entry in excluded_data:
        article_id = entry.get('article_id', '')
        if article_id:
            normalized_id = normalize_article_id(article_id)
            excluded_ids.add(normalized_id)
    
    print(f"Found {len(excluded_ids)} unique excluded article IDs")
    return excluded_ids


def parse_bibtex_entry(bibtex_text: str) -> Tuple[str, str]:
    """
    Parse a single BibTeX entry.
    Returns (entry_id, full_entry_text).
    """
    # Match @article{entry_id, ... }
    match = re.match(r'@article\{([^,]+),', bibtex_text)
    if not match:
        return None, None
    
    entry_id = match.group(1).strip()
    
    # Find the matching closing brace for the entire entry
    # We need to handle nested braces properly
    brace_count = 0
    start_pos = bibtex_text.find('{')
    if start_pos == -1:
        return None, None
    
    for i in range(start_pos, len(bibtex_text)):
        if bibtex_text[i] == '{':
            brace_count += 1
        elif bibtex_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                # Found the closing brace
                entry_text = bibtex_text[:i+1].strip()
                return entry_id, entry_text
    
    # If we didn't find a closing brace, return the whole text
    return entry_id, bibtex_text.strip()


def parse_bibtex_file(bibtex_path: Path) -> List[Tuple[str, str]]:
    """
    Parse BibTeX file and return list of (entry_id, entry_text) tuples.
    """
    print(f"Parsing BibTeX file: {bibtex_path}")
    
    with open(bibtex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    entries = []
    # Split by @article{ to find all entries
    parts = re.split(r'(@article\{)', content)
    
    # Reconstruct entries (parts[0] is text before first @article, then pairs of @article{ and content)
    current_entry = None
    for i, part in enumerate(parts):
        if part == '@article{':
            # Start of a new entry
            if current_entry:
                # Save previous entry
                entry_id, entry_text = parse_bibtex_entry(current_entry)
                if entry_id and entry_text:
                    entries.append((entry_id, entry_text))
            current_entry = part
        elif current_entry:
            # Continue building current entry
            current_entry += part
    
    # Don't forget the last entry
    if current_entry:
        entry_id, entry_text = parse_bibtex_entry(current_entry)
        if entry_id and entry_text:
            entries.append((entry_id, entry_text))
    
    print(f"Parsed {len(entries)} BibTeX entries")
    return entries


def filter_bibtex_entries(entries: List[Tuple[str, str]], excluded_ids: Set[str]) -> List[str]:
    """
    Filter out entries whose IDs are in excluded_ids.
    Returns list of entry texts (not tuples).
    """
    included_entries = []
    excluded_count = 0
    
    for entry_id, entry_text in entries:
        normalized_id = normalize_article_id(entry_id)
        
        if normalized_id in excluded_ids:
            excluded_count += 1
            continue
        
        included_entries.append(entry_text)
    
    print(f"Filtered out {excluded_count} excluded entries")
    print(f"Kept {len(included_entries)} included entries")
    
    return included_entries


def write_bibtex_file(entries: List[str], output_path: Path):
    """Write BibTeX entries to file."""
    print(f"Writing {len(entries)} entries to: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries):
            f.write(entry)
            # Add blank line between entries (except after the last one)
            if i < len(entries) - 1:
                f.write('\n\n')
    
    print(f"Successfully wrote BibTeX file")


def main():
    """Main function."""
    print("="*80)
    print("Filter BibTeX Entries")
    print("="*80)
    
    # Load excluded IDs
    excluded_ids = load_excluded_ids(FINAL_EXCLUDE_JSON)
    
    # Parse BibTeX file
    bibtex_entries = parse_bibtex_file(INCLUDED_ARTICLES_BIB)
    
    # Filter entries
    included_entries = filter_bibtex_entries(bibtex_entries, excluded_ids)
    
    # Write output file
    write_bibtex_file(included_entries, FINAL_INCLUDED_ARTICLES_BIB)
    
    print("\n" + "="*80)
    print("Summary:")
    print(f"  Total entries in original BibTeX: {len(bibtex_entries)}")
    print(f"  Excluded entries: {len(bibtex_entries) - len(included_entries)}")
    print(f"  Final included entries: {len(included_entries)}")
    print(f"  Output file: {FINAL_INCLUDED_ARTICLES_BIB}")
    print("="*80)


if __name__ == "__main__":
    main()

