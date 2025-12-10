#!/usr/bin/env python3
"""
Script to generate a publication count per year bar chart from BibTeX files.

Input files:
    - data/included/articles.bib
    - data/excluded/articles.bib
    - data/maybe/articles.bib

Output file:
    - output/publications_year_counts_plot.svg
"""

import re
import os
from collections import Counter
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib

# Set matplotlib to use a non-interactive backend
matplotlib.use('Agg')

def parse_bibtex_year(bibtex_file: str) -> list:
    """
    Parse BibTeX file and extract year values.
    Returns a list of year strings found in the file.
    """
    years = []
    
    try:
        with open(bibtex_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match year field: year={YYYY} or year = {YYYY}
        # This handles single-line and multi-line fields
        year_pattern = re.compile(r'year\s*=\s*\{([^}]+)\}', re.IGNORECASE)
        matches = year_pattern.findall(content)
        
        for match in matches:
            year = match.strip()
            if year and year.isdigit():
                years.append(year)
    
    except Exception as e:
        print(f"Warning: Error parsing {bibtex_file}: {e}")
    
    return years

def count_publications_per_year_from_bibtex(bibtex_files: dict) -> dict:
    """
    Count publications per year from multiple BibTeX files.
    
    Args:
        bibtex_files: Dictionary mapping category name to file path
        
    Returns:
        Dictionary mapping year (as string) to total count
    """
    all_years = Counter()
    
    for category, file_path in bibtex_files.items():
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            continue
        
        print(f"Processing {category} articles from: {file_path}")
        years = parse_bibtex_year(file_path)
        category_count = Counter(years)
        all_years.update(category_count)
        
        print(f"  Found {len(years)} entries with year data")
        if category_count:
            print(f"  Year range: {min(category_count.keys(), key=int)} - {max(category_count.keys(), key=int)}")
    
    # Convert to regular dict and sort by year
    year_counts_dict = dict(sorted(all_years.items(), key=lambda x: int(x[0])))
    return year_counts_dict

def create_year_counts_plot(year_counts: dict, output_file: str):
    """
    Create a bar chart showing publication counts per year.
    """
    if not year_counts:
        print("Warning: No year data found. Cannot create plot.")
        return
    
    # Extract years and counts
    years = [int(year) for year in year_counts.keys()]
    counts = list(year_counts.values())
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create bar chart
    bars = ax.bar(years, counts, color='#1f77b4', alpha=0.7, edgecolor='black', linewidth=0.5)
    
    # Customize the plot
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Count of Papers Published Per Year', fontsize=12, fontweight='bold')
    ax.set_title('Publications Per Year', fontsize=14, fontweight='bold', pad=20)
    
    # Set x-axis to show all years
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=90, ha='center')
    
    # Add grid for better readability
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=9)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Save as SVG
    plt.savefig(output_file, format='svg', bbox_inches='tight', dpi=300)
    print(f"Successfully saved plot to: {output_file}")
    
    # Print summary statistics
    total_publications = sum(counts)
    min_year = min(years)
    max_year = max(years)
    max_count = max(counts)
    max_year_for_count = years[counts.index(max_count)]
    
    print(f"\nSummary Statistics:")
    print(f"  Total publications: {total_publications}")
    print(f"  Year range: {min_year} - {max_year}")
    print(f"  Maximum publications in a year: {max_count} (in {max_year_for_count})")
    print(f"  Years with data: {len(years)}")

def main():
    # File paths (using relative paths from script location)
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir.parent / 'data'
    
    # Define BibTeX files to process
    bibtex_files = {
        'included': str(data_dir / 'included' / 'articles.bib'),
        'excluded': str(data_dir / 'excluded' / 'articles.bib'),
        'maybe': str(data_dir / 'maybe' / 'articles.bib')
    }
    
    output_dir = script_dir / 'output'
    output_file = output_dir / 'publications_year_counts_plot.svg'
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("Processing BibTeX files to extract publication year information")
    print("=" * 80)
    
    # Count publications per year from all BibTeX files
    year_counts = count_publications_per_year_from_bibtex(bibtex_files)
    
    if not year_counts:
        print("Error: No valid year data found in BibTeX files.")
        return
    
    print(f"\nTotal publications found in {len(year_counts)} different years")
    
    print("\nGenerating plot...")
    create_year_counts_plot(year_counts, str(output_file))
    
    print("\nDone!")

if __name__ == "__main__":
    main()

