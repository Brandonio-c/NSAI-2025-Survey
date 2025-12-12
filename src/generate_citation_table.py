#!/usr/bin/env python3
"""
Generate a LaTeX table with citations, titles, and descriptions for included papers.

This script:
1. Parses final_included_articles.bib to extract article IDs and titles
2. Loads descriptions from NSAI-DATA_Extraction.xlsx
3. Generates a LaTeX table with \cite commands, titles, and descriptions
"""

import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BIB_FILE = PROJECT_ROOT / "docs" / "data" / "final_included_articles.bib"
EXCEL_FILE = PROJECT_ROOT.parent / "NSAI-Data-crosscheck" / "data" / "NSAI-DATA_Extraction.xlsx"
CLUSTER_FILE = PROJECT_ROOT.parent / "NSAI-Data-crosscheck" / "data" / "cluster_papers_with_links.xlsx"
OUTPUT_TEX = PROJECT_ROOT / "docs" / "data" / "included_papers_table.tex"
OUTPUT_TEX_NO_CITE = PROJECT_ROOT / "docs" / "data" / "included_papers_table_no_cite.tex"


def normalize_article_id(article_id: str) -> str:
    """Normalize article ID by removing 'rayyan-' prefix if present."""
    if not article_id:
        return ""
    article_id = str(article_id).strip()
    if article_id.lower().startswith('rayyan-'):
        return article_id[7:]
    return article_id


def parse_bibtex_file(bibtex_path: Path) -> List[Dict[str, str]]:
    """
    Parse BibTeX file and extract article IDs, titles, and abstracts.
    Returns list of dictionaries with 'id', 'title', and 'abstract' keys.
    """
    logger.info(f"Parsing BibTeX file: {bibtex_path}")
    
    with open(bibtex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    entries = []
    # Split by @article{ to find all entries
    parts = re.split(r'(@article\{)', content)
    
    current_entry = None
    for i, part in enumerate(parts):
        if part == '@article{':
            # Start of a new entry
            if current_entry:
                # Parse previous entry
                entry_dict = parse_single_entry(current_entry)
                if entry_dict:
                    entries.append(entry_dict)
            current_entry = part
        elif current_entry:
            # Continue building current entry
            current_entry += part
    
    # Don't forget the last entry
    if current_entry:
        entry_dict = parse_single_entry(current_entry)
        if entry_dict:
            entries.append(entry_dict)
    
    logger.info(f"Parsed {len(entries)} BibTeX entries")
    return entries


def parse_single_entry(entry_text: str) -> Dict[str, str]:
    """Parse a single BibTeX entry."""
    # Extract entry ID
    id_match = re.match(r'@article\{([^,]+),', entry_text)
    if not id_match:
        return None
    
    entry_id = id_match.group(1).strip()
    
    # Extract title - handle nested braces
    title = extract_field(entry_text, 'title')
    
    # Extract abstract - handle nested braces
    abstract = extract_field(entry_text, 'abstract')
    
    # Extract author - handle nested braces
    author = extract_field(entry_text, 'author')
    
    # Extract year - handle nested braces
    year = extract_field(entry_text, 'year')
    
    # Clean up abstract
    if abstract:
        abstract = re.sub(r'\s+', ' ', abstract).strip()
        # Remove trailing ellipsis if present
        if abstract.endswith('…'):
            abstract = abstract[:-1].strip()
    
    return {
        'id': entry_id,
        'title': title or "",
        'abstract': abstract or "",
        'author': author or "",
        'year': year or ""
    }


def extract_field(entry_text: str, field_name: str) -> str:
    """Extract a field value from BibTeX entry, handling nested braces."""
    pattern = rf'{field_name}=\{{(.*?)\}}'
    
    # Find the field start
    field_start = entry_text.find(f'{field_name}={{')
    if field_start == -1:
        return ""
    
    # Find the opening brace after the equals sign
    start_pos = entry_text.find('{', field_start)
    if start_pos == -1:
        return ""
    
    # Count braces to find matching closing brace
    brace_count = 0
    i = start_pos
    while i < len(entry_text):
        if entry_text[i] == '{':
            brace_count += 1
        elif entry_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                # Found the matching closing brace
                field_value = entry_text[start_pos + 1:i]
                return field_value
        i += 1
    
    return ""


def load_excel_descriptions(excel_path: Path) -> Dict[str, str]:
    """
    Load paper descriptions from Excel file.
    Returns dictionary mapping normalized article ID to description.
    """
    logger.info(f"Loading descriptions from Excel: {excel_path}")
    
    try:
        df = pd.read_excel(excel_path)
        
        # Find relevant columns
        paper_id_col = next((col for col in df.columns if 'paper id' in col.lower() or 'rayyan id' in col.lower()), None)
        description_col = next((col for col in df.columns if 'brief summary' in col.lower() or 'description' in col.lower()), None)
        
        if not paper_id_col:
            logger.warning("Could not find Paper ID column in Excel")
            return {}
        if not description_col:
            logger.warning("Could not find description column in Excel")
            return {}
        
        logger.info(f"Using columns: Paper ID='{paper_id_col}', Description='{description_col}'")
        
        descriptions = {}
        for _, row in df.iterrows():
            paper_id = str(row[paper_id_col]).strip() if pd.notna(row[paper_id_col]) else ""
            description = str(row[description_col]).strip() if pd.notna(row[description_col]) else ""
            
            if paper_id and description:
                normalized_id = normalize_article_id(paper_id)
                descriptions[normalized_id] = description
        
        logger.info(f"Loaded {len(descriptions)} descriptions from Excel")
        return descriptions
        
    except Exception as e:
        logger.error(f"Error loading Excel file: {e}")
        return {}


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters and normalize whitespace."""
    if not text:
        return ""
    
    # Normalize whitespace (replace newlines and multiple spaces with single space)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # First, escape backslashes (must be first)
    text = text.replace('\\', '\\textbackslash{}')
    
    # Escape special LaTeX characters
    # Order matters: escape braces before other characters that might use them
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    text = text.replace('&', '\\&')
    text = text.replace('%', '\\%')
    text = text.replace('$', '\\$')
    text = text.replace('#', '\\#')
    text = text.replace('^', '\\textasciicircum{}')
    text = text.replace('_', '\\_')  # Underscores must be escaped to avoid math mode
    text = text.replace('~', '\\textasciitilde{}')
    
    # Escape < and > which can cause issues
    text = text.replace('<', '\\textless{}')
    text = text.replace('>', '\\textgreater{}')
    
    return text


def generate_latex_table(bibtex_entries: List[Dict[str, str]], descriptions: Dict[str, str], use_cite: bool = True) -> str:
    """
    Generate LaTeX table code with citations, titles, and descriptions.
    
    Args:
        bibtex_entries: List of BibTeX entry dictionaries
        descriptions: Dictionary mapping article IDs to descriptions
        use_cite: If True, use \\cite commands. If False, show author/year directly.
    """
    logger.info(f"Generating LaTeX table (use_cite={use_cite})")
    
    # Build table rows
    rows = []
    for entry in bibtex_entries:
        entry_id = entry['id']
        title = entry['title']
        abstract = entry['abstract']
        author = entry.get('author', '')
        year = entry.get('year', '')
        
        # Get description from Excel, fallback to abstract
        normalized_id = normalize_article_id(entry_id)
        description = descriptions.get(normalized_id, abstract)
        
        # If still no description, use a placeholder
        if not description or description.strip() == "":
            description = "Description not available."
        
        # Escape LaTeX special characters
        title_escaped = escape_latex(title)
        description_escaped = escape_latex(description)
        
        if use_cite:
            # Create citation key (remove 'rayyan-' prefix if present)
            cite_key = entry_id.replace('rayyan-', '')
            citation_col = f"\\cite{{rayyan-{cite_key}}}"
        else:
            # Format author and year for citation - make it neater
            author_escaped = escape_latex(author)
            year_escaped = escape_latex(year)
            
            # Format citation more neatly: "Author et al. (Year)" or "Author (Year)"
            if author_escaped:
                # If author list is long, use "First Author et al."
                author_parts = [a.strip() for a in author_escaped.split(' and ')]
                if len(author_parts) > 2:
                    # Use first author + "et al." for 3+ authors
                    first_author = author_parts[0]
                    # Extract last name (part before comma or last word)
                    if ',' in first_author:
                        last_name = first_author.split(',')[0].strip()
                    else:
                        # Get last name (last word)
                        name_words = first_author.split()
                        last_name = name_words[-1] if name_words else first_author
                    citation_col = f"{last_name} et al."
                elif len(author_parts) == 2:
                    # Two authors: "Author1 and Author2" - extract last names
                    author1 = author_parts[0]
                    author2 = author_parts[1]
                    if ',' in author1:
                        name1 = author1.split(',')[0].strip()
                    else:
                        name1 = author1.split()[-1] if author1.split() else author1
                    if ',' in author2:
                        name2 = author2.split(',')[0].strip()
                    else:
                        name2 = author2.split()[-1] if author2.split() else author2
                    citation_col = f"{name1} and {name2}"
                else:
                    # Single author - extract last name
                    if ',' in author_escaped:
                        citation_col = author_escaped.split(',')[0].strip()
                    else:
                        citation_col = author_escaped.split()[-1] if author_escaped.split() else author_escaped
                
                # Add year in parentheses
                if year_escaped:
                    citation_col = f"{citation_col} ({year_escaped})"
            else:
                citation_col = year_escaped if year_escaped else entry_id.replace('rayyan-', '')
            
            # Wrap in smaller font for neater appearance and use raggedright for better line breaks
            citation_col = f"\\small\\raggedright {citation_col}"
        
        # Create table row
        row = f"    {citation_col} & {title_escaped} & {description_escaped} \\\\"
        rows.append(row)
    
    # Generate full LaTeX table
    if use_cite:
        # Table with \cite commands - standard format
        latex_table = """% This table requires the longtable package.
% Add \\usepackage{longtable} to your document preamble.
%
% All special LaTeX characters (including underscores) have been properly escaped.
%
\\begin{longtable}{|p{2cm}|p{4cm}|p{8cm}|}
\\hline
\\textbf{Citation} & \\textbf{Title} & \\textbf{Description} \\\\
\\hline
\\endfirsthead

\\hline
\\textbf{Citation} & \\textbf{Title} & \\textbf{Description} \\\\
\\hline
\\endhead

\\hline
\\endfoot

\\hline
\\endlastfoot

"""
        latex_table += "\n".join(rows)
        latex_table += "\n\\end{longtable}\n"
    else:
        # Table without \cite commands - full width, better formatting
        latex_table = """% This table requires the longtable package.
% Add \\usepackage{longtable} to your document preamble.
%
% All special LaTeX characters (including underscores) have been properly escaped.
% This table spans the full page width and includes horizontal lines between entries.
%
\\begin{onecolumn}
\\begin{longtable}{|p{0.22\\textwidth}|p{0.28\\textwidth}|p{0.48\\textwidth}|}
\\hline
\\textbf{Citation} & \\textbf{Title} & \\textbf{Description} \\\\
\\hline
\\endfirsthead

\\hline
\\textbf{Citation} & \\textbf{Title} & \\textbf{Description} \\\\
\\hline
\\endhead

\\hline
\\endfoot

\\hline
\\endlastfoot

"""
        # Add horizontal lines between each row
        rows_with_lines = []
        for row in rows:
            rows_with_lines.append(row)
            rows_with_lines.append("\\hline")
        
        latex_table += "\n".join(rows_with_lines)
        latex_table += "\n\\end{longtable}\n\\end{onecolumn}\n"
    
    logger.info(f"Generated LaTeX table with {len(rows)} rows")
    return latex_table


def main():
    """Main function."""
    logger.info("="*80)
    logger.info("Generate Citation Table")
    logger.info("="*80)
    
    # Parse BibTeX file
    bibtex_entries = parse_bibtex_file(BIB_FILE)
    
    # Load descriptions from Excel
    descriptions = load_excel_descriptions(EXCEL_FILE)
    
    # Generate LaTeX table with \cite commands
    latex_table_with_cite = generate_latex_table(bibtex_entries, descriptions, use_cite=True)
    
    # Generate LaTeX table without \cite commands (showing author/year directly)
    latex_table_no_cite = generate_latex_table(bibtex_entries, descriptions, use_cite=False)
    
    # Write output files
    logger.info(f"Writing LaTeX table with \\cite commands to: {OUTPUT_TEX}")
    with open(OUTPUT_TEX, 'w', encoding='utf-8') as f:
        f.write(latex_table_with_cite)
    
    logger.info(f"Writing LaTeX table without \\cite commands to: {OUTPUT_TEX_NO_CITE}")
    with open(OUTPUT_TEX_NO_CITE, 'w', encoding='utf-8') as f:
        f.write(latex_table_no_cite)
    
    logger.info("="*80)
    logger.info("Summary:")
    logger.info(f"  Total papers: {len(bibtex_entries)}")
    logger.info(f"  Papers with descriptions from Excel: {sum(1 for e in bibtex_entries if normalize_article_id(e['id']) in descriptions)}")
    logger.info(f"  Output files:")
    logger.info(f"    - {OUTPUT_TEX} (with \\cite commands)")
    logger.info(f"    - {OUTPUT_TEX_NO_CITE} (without \\cite commands)")
    logger.info("="*80)
    logger.info("\nTo use these tables in your LaTeX document, add:")
    logger.info("  \\usepackage{longtable}")
    logger.info(f"  \\input{{docs/data/included_papers_table.tex}}")
    logger.info("  or")
    logger.info(f"  \\input{{docs/data/included_papers_table_no_cite.tex}}")
    logger.info("="*80)


if __name__ == "__main__":
    main()

