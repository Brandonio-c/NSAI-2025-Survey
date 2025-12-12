#!/usr/bin/env python3
"""
Enrich BibTeX entries with missing fields from Excel data.

This script:
1. Reads final_included_articles.bib
2. Loads enrichment data from NSAI-DATA_Extraction.xlsx
3. Adds missing fields like journal, DOI, URL, etc.
4. Writes enriched BibTeX file
"""

import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BIB_FILE = PROJECT_ROOT / "docs" / "data" / "final_included_articles.bib"
EXCEL_FILE = PROJECT_ROOT.parent / "NSAI-Data-crosscheck" / "data" / "NSAI-DATA_Extraction.xlsx"
OUTPUT_BIB = PROJECT_ROOT / "docs" / "data" / "final_included_articles.bib"


def normalize_article_id(article_id: str) -> str:
    """Normalize article ID by removing 'rayyan-' prefix if present."""
    if not article_id:
        return ""
    article_id = str(article_id).strip()
    if article_id.lower().startswith('rayyan-'):
        return article_id[7:]
    return article_id.lower()


def load_excel_data(excel_path: Path) -> Dict[str, Dict[str, str]]:
    """Load enrichment data from Excel file."""
    logger.info(f"Loading Excel file: {excel_path}")
    
    try:
        df = pd.read_excel(excel_path)
        
        # Find relevant columns
        paper_id_col = next((col for col in df.columns if 'paper id' in col.lower() or 'rayyan id' in col.lower()), None)
        journal_col = next((col for col in df.columns if 'journal' in col.lower() or 'conference' in col.lower()), None)
        doi_url_col = next((col for col in df.columns if ('doi' in col.lower() or 'url' in col.lower()) and 'paper' in col.lower()), None)
        
        if not paper_id_col:
            logger.error("Could not find Paper ID column in Excel")
            return {}
        
        logger.info(f"Found columns: Paper ID='{paper_id_col}', Journal='{journal_col}', DOI/URL='{doi_url_col}'")
        
        enrichment_data = {}
        for _, row in df.iterrows():
            paper_id = str(row[paper_id_col]).strip() if pd.notna(row[paper_id_col]) else ""
            if not paper_id:
                continue
            
            normalized_id = normalize_article_id(paper_id)
            enrichment_data[normalized_id] = {}
            
            if journal_col and pd.notna(row[journal_col]):
                enrichment_data[normalized_id]['journal'] = str(row[journal_col]).strip()
            
            if doi_url_col and pd.notna(row[doi_url_col]):
                enrichment_data[normalized_id]['doi_url'] = str(row[doi_url_col]).strip()
        
        logger.info(f"Loaded enrichment data for {len(enrichment_data)} papers")
        return enrichment_data
        
    except Exception as e:
        logger.error(f"Error loading Excel file: {e}")
        return {}


def extract_field(entry_text: str, field_name: str) -> Optional[str]:
    """Extract a field value from BibTeX entry."""
    pattern = rf'{re.escape(field_name)}\s*=\s*\{{'
    match = re.search(pattern, entry_text)
    if not match:
        return None
    
    # Find the opening brace
    brace_start = match.end() - 1  # Position of '{'
    brace_count = 1
    i = brace_start + 1
    
    while i < len(entry_text) and brace_count > 0:
        if entry_text[i] == '{':
            brace_count += 1
        elif entry_text[i] == '}':
            brace_count -= 1
        i += 1
    
    if brace_count == 0:
        field_value = entry_text[brace_start + 1:i - 1]
        return field_value
    
    return None


def has_field(entry_text: str, field_name: str) -> bool:
    """Check if entry has a field."""
    pattern = rf'^\s*{re.escape(field_name)}\s*=\s*\{{'
    return bool(re.search(pattern, entry_text, re.MULTILINE))


def add_field(entry_text: str, field_name: str, field_value: str, after_field: Optional[str] = None) -> str:
    """Add a field to BibTeX entry."""
    if has_field(entry_text, field_name):
        # Field already exists, don't add
        return entry_text
    
    # Escape special characters in field value
    field_value_escaped = field_value.replace('\\', '\\textbackslash{}')
    field_value_escaped = field_value_escaped.replace('&', '\\&')
    field_value_escaped = field_value_escaped.replace('_', '\\_')
    
    new_field = f"  {field_name}={{{field_value_escaped}}},\n"
    
    if after_field:
        # Insert after specified field
        pattern = rf'({re.escape(after_field)}\s*=\s*\{{[^}}]*\}}\s*,?\s*\n)'
        if re.search(pattern, entry_text):
            entry_text = re.sub(pattern, r'\1' + new_field, entry_text, count=1)
            return entry_text
    
    # Insert before closing brace
    entry_text = re.sub(r'(\n\})', new_field + r'\1', entry_text, count=1)
    return entry_text


def enrich_bibtex_entry(entry_text: str, enrichment: Dict[str, str], entry_id: str) -> str:
    """Enrich a single BibTeX entry with missing fields."""
    normalized_id = normalize_article_id(entry_id)
    
    if normalized_id not in enrichment:
        return entry_text
    
    data = enrichment[normalized_id]
    
    # Add journal field if missing and available
    if 'journal' in data and data['journal'] and not has_field(entry_text, 'journal'):
        entry_text = add_field(entry_text, 'journal', data['journal'], after_field='year')
    
    # Add URL field if missing and DOI/URL available
    if 'doi_url' in data and data['doi_url']:
        # Check if URL already exists
        existing_url = extract_field(entry_text, 'url')
        if not existing_url or not existing_url.strip():
            # Add URL if missing or empty
            entry_text = add_field(entry_text, 'url', data['doi_url'], after_field='journal')
    
    return entry_text


def parse_bibtex_file(bibtex_path: Path) -> List[tuple]:
    """Parse BibTeX file and return list of (entry_id, entry_text) tuples."""
    logger.info(f"Parsing BibTeX file: {bibtex_path}")
    
    with open(bibtex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    entries = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts an article entry
        match = re.match(r'@article\{([^,]+),', line)
        if match:
            entry_id = match.group(1).strip()
            entry_start = i
            entry_lines = [line]
            i += 1
            
            # Find the closing brace of the entry
            brace_count = 1  # We already have the opening brace from @article{
            while i < len(lines) and brace_count > 0:
                current_line = lines[i]
                entry_lines.append(current_line)
                
                # Count braces in this line
                for char in current_line:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found the closing brace
                            break
                
                i += 1
            
            # Join all lines of this entry
            entry_text = '\n'.join(entry_lines)
            entries.append((entry_id, entry_text))
        else:
            i += 1
    
    logger.info(f"Parsed {len(entries)} BibTeX entries")
    return entries


def main():
    """Main function."""
    logger.info("="*80)
    logger.info("Enrich BibTeX Entries")
    logger.info("="*80)
    
    # Load enrichment data
    enrichment_data = load_excel_data(EXCEL_FILE)
    
    # Parse BibTeX file
    entries = parse_bibtex_file(BIB_FILE)
    
    # Enrich entries
    enriched_entries = []
    enriched_count = 0
    for entry_id, entry_text in entries:
        original_text = entry_text
        enriched_text = enrich_bibtex_entry(entry_text, enrichment_data, entry_id)
        if enriched_text != original_text:
            enriched_count += 1
        enriched_entries.append(enriched_text)
    
    # Write enriched BibTeX file
    logger.info(f"Writing enriched BibTeX file: {OUTPUT_BIB}")
    logger.info(f"Enriched {enriched_count} entries")
    
    with open(OUTPUT_BIB, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(enriched_entries):
            f.write(entry)
            if i < len(enriched_entries) - 1:
                f.write('\n\n')
    
    logger.info("="*80)
    logger.info("Successfully enriched BibTeX file")
    logger.info("="*80)


if __name__ == "__main__":
    main()

