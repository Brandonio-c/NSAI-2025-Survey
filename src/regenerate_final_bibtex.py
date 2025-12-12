#!/usr/bin/env python3
"""
Master script to regenerate final_included_articles.bib with all enrichment.

This script runs the complete workflow:
1. Filter BibTeX entries (exclude papers from final_exclude.json)
2. Enrich entries with journal and URL from Excel
3. Remove note and abstract fields
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "src"

def run_script(script_name: str, description: str):
    """Run a Python script and check for errors."""
    print(f"\n{'='*80}")
    print(f"Step: {description}")
    print(f"{'='*80}")
    
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: {script_name} failed with return code {result.returncode}")
        sys.exit(1)
    
    print(f"✓ {description} completed successfully")

def main():
    """Run the complete workflow."""
    print("="*80)
    print("Regenerate Final Included Articles BibTeX")
    print("="*80)
    print("\nThis script will:")
    print("  1. Filter BibTeX entries (exclude papers from final_exclude.json)")
    print("  2. Enrich entries with journal and URL from Excel")
    print("  3. Remove note and abstract fields")
    print("="*80)
    
    # Step 1: Filter entries
    run_script("filter_bibtex.py", "Filter BibTeX entries")
    
    # Step 2: Enrich with Excel data
    run_script("enrich_bibtex.py", "Enrich entries with journal and URL")
    
    # Step 3: Remove note and abstract fields
    run_script("remove_notes_from_bib.py", "Remove note and abstract fields")
    
    print("\n" + "="*80)
    print("Workflow completed successfully!")
    print("="*80)
    print(f"\nOutput file: {PROJECT_ROOT / 'docs' / 'data' / 'final_included_articles.bib'}")
    print("="*80)

if __name__ == "__main__":
    main()

