#!/usr/bin/env python3
"""
Remove note and abstract fields from BibTeX file.

This script removes all 'note=' and 'abstract=' fields from BibTeX entries.
"""

import re
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BIB_FILE = PROJECT_ROOT / "docs" / "data" / "final_included_articles.bib"


def clean_special_characters(content: str) -> str:
    """
    Clean special characters that may cause LaTeX issues.
    Escapes underscores in URLs and other problematic characters.
    """
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Skip note fields (they'll be removed separately)
        if re.match(r'^\s*note\s*=\s*\{', line):
            cleaned_lines.append(line)
            continue
        
        # For URL fields, escape underscores and other special characters
        if re.match(r'^\s*url\s*=\s*\{', line):
            # Extract the URL content - handle nested braces
            url_start = line.find('{')
            if url_start != -1:
                brace_count = 1
                url_end = url_start + 1
                while url_end < len(line) and brace_count > 0:
                    if line[url_end] == '{':
                        brace_count += 1
                    elif line[url_end] == '}':
                        brace_count -= 1
                    url_end += 1
                
                if brace_count == 0:
                    url_content = line[url_start + 1:url_end - 1]
                    # Escape underscores in URLs (but not if already escaped)
                    url_content_escaped = re.sub(r'(?<!\\)_', r'\\_', url_content)
                    line = line[:url_start + 1] + url_content_escaped + line[url_end - 1:]
        
        # For abstract and other text fields, escape underscores that aren't already escaped
        # But preserve underscores in URLs within the text
        if '=' in line and '{' in line and not line.strip().startswith('url'):
            # Check if line contains a URL pattern
            if 'http' in line.lower() or 'www.' in line.lower():
                # Extract field value and escape underscores in URLs
                field_match = re.match(r'^(\s*)([^=]+)=\s*(\{.*\})\s*$', line)
                if field_match:
                    indent = field_match.group(1)
                    field_name = field_match.group(2).strip()
                    field_value = field_match.group(3)
                    
                    # Escape underscores in URLs within the field value
                    # Find URLs and escape underscores in them
                    def escape_url_underscores(match):
                        url = match.group(0)
                        # Escape underscores that aren't already escaped
                        url_escaped = re.sub(r'(?<!\\)_', r'\\_', url)
                        return url_escaped
                    
                    # Find URLs and escape underscores in them
                    field_value_escaped = re.sub(
                        r'https?://[^\s}]+|www\.[^\s}]+',
                        escape_url_underscores,
                        field_value
                    )
                    line = f"{indent}{field_name}={field_value_escaped}"
        
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def remove_field(content: str, field_name: str) -> str:
    """
    Remove all fields of a given name from BibTeX content.
    Handles fields that may span multiple lines or contain nested braces.
    
    Args:
        content: BibTeX content as string
        field_name: Name of the field to remove (e.g., 'note', 'abstract')
    
    Returns:
        Content with specified fields removed
    """
    lines = content.split('\n')
    result_lines = []
    i = 0
    fields_removed = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts the specified field
        pattern_start = rf'^\s*{re.escape(field_name)}\s*=\s*\{{'
        if re.match(pattern_start, line):
            # This is the start of the field
            field_start_line = i
            
            # Find the opening brace position in this line
            brace_pos = line.find('{')
            if brace_pos == -1:
                # No opening brace found, keep the line
                result_lines.append(line)
                i += 1
                continue
            
            # Count braces to find the matching closing brace
            brace_count = 1
            j = i
            found_closing = False
            
            # Process characters starting from the opening brace
            while j < len(lines) and brace_count > 0:
                current_line = lines[j]
                # Start position: after opening brace on first line, beginning of line otherwise
                start_pos = brace_pos + 1 if j == i else 0
                
                # Process each character in the line
                for k in range(start_pos, len(current_line)):
                    char = current_line[k]
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found the matching closing brace
                            found_closing = True
                            break
                
                if found_closing:
                    break
                    
                # Move to next line if we haven't found the closing brace
                if brace_count > 0:
                    j += 1
            
            if found_closing:
                # Skip all lines from field_start_line to j (inclusive)
                i = j + 1
                fields_removed += 1
                continue
            else:
                # Didn't find closing brace - keep the line to avoid data loss
                logger.warning(f"Could not find closing brace for {field_name} field starting at line {field_start_line + 1}")
                result_lines.append(line)
                i += 1
                continue
        
        result_lines.append(line)
        i += 1
    
    logger.info(f"Removed {fields_removed} {field_name} fields")
    return '\n'.join(result_lines)


def remove_note_fields(content: str) -> str:
    """
    Remove all note fields from BibTeX content.
    Handles note fields that may span multiple lines or contain nested braces.
    """
    return remove_field(content, 'note')


def remove_abstract_fields(content: str) -> str:
    """
    Remove all abstract fields from BibTeX content.
    Handles abstract fields that may span multiple lines or contain nested braces.
    """
    return remove_field(content, 'abstract')


def main():
    """Main function."""
    logger.info("="*80)
    logger.info("Remove Note and Abstract Fields from BibTeX")
    logger.info("="*80)
    
    # Read the BibTeX file
    logger.info(f"Reading BibTeX file: {BIB_FILE}")
    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count original note and abstract fields
    original_notes = len(re.findall(r'^\s*note\s*=\s*\{', content, re.MULTILINE))
    original_abstracts = len(re.findall(r'^\s*abstract\s*=\s*\{', content, re.MULTILINE))
    logger.info(f"Found {original_notes} note fields to remove")
    logger.info(f"Found {original_abstracts} abstract fields to remove")
    
    # Clean special characters first (before removing fields, so we can see what's in them)
    logger.info("Cleaning special characters...")
    content = clean_special_characters(content)
    
    # Remove note fields
    content = remove_note_fields(content)
    
    # Remove abstract fields (do this after notes to avoid confusion)
    logger.info("Removing abstract fields...")
    content = remove_abstract_fields(content)
    
    # Write back to file
    logger.info(f"Writing updated BibTeX file: {BIB_FILE}")
    with open(BIB_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info("="*80)
    logger.info("Successfully removed all note and abstract fields from BibTeX file")
    logger.info("="*80)


if __name__ == "__main__":
    main()

