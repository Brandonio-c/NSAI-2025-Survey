# NSAI-2025-Survey Data Processor

This script processes the data from the NSAI-2025-Survey project and generates JSON and Excel files with the combined information from articles.bib and customizations_log.csv files.

## Overview

The script processes data from four folders:
- `included/` - Articles that were included in the survey
- `conflict/` - Articles with conflicts that were included
- `excluded/` - Articles that were excluded from the survey  
- `maybe/` - Articles that were marked as "maybe" (excluded)

## Output Files

The script generates four output files in the `output/` directory:

### Include Files
- `include.json` - JSON format containing articles from `included/` and `conflict/` folders
- `include.xlsx` - Excel format with the same data, including separate sheets for articles and customizations

### Exclude Files  
- `exclude.json` - JSON format containing articles from `excluded/` and `maybe/` folders
- `exclude.xlsx` - Excel format with the same data, including separate sheets for articles and customizations

## Data Structure

Each article entry contains:
- `article_id` - The unique identifier (e.g., "rayyan-242083763")
- `title` - Article title
- `year` - Publication year
- `author` - Author names
- `url` - Article URL (if available)
- `abstract` - Article abstract
- `note` - Additional notes from the BibTeX file
- `customizations` - Array of customization entries from the CSV file

Each customization entry contains:
- `created_at` - Timestamp of the customization
- `user_id` - User ID who made the customization
- `user_email` - Email of the user
- `key` - Customization key (e.g., "included", "note-12345")
- `value` - Customization value

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the script:
   ```bash
   python data_processor.py
   ```

3. Check the `output/` directory for the generated files.

## Requirements

- Python 3.7+
- pandas
- openpyxl

## Script Architecture

The script uses a class-oriented design with the following main classes:

- `Article` - Data class representing an article entry
- `BibTeXParser` - Parses BibTeX files and extracts article information
- `CustomizationsParser` - Parses CSV files and extracts customization data
- `DataProcessor` - Main class that orchestrates the data processing and file generation

## Notes

- The script uses relative paths and expects to be run from the `src/` directory
- BibTeX parsing handles multi-line fields and complex content
- Customizations are linked to articles by matching the numeric part of the article ID
- Excel files include separate sheets for articles and customizations for better data organization 