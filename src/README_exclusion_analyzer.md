# Exclusion Criteria Analyzer

This script analyzes the exclusion criteria from the `exclude.json` file and enriches the `screening_overview.json` with detailed breakdown information.

## Overview

The script provides a comprehensive analysis of why articles were excluded during the systematic review screening process, including:

- Individual exclusion criteria counts and percentages
- Articles with single vs. multiple exclusion criteria
- Most common combinations of exclusion criteria
- Detailed breakdown for each excluded article

## Key Findings

From the analysis of 1,851 excluded articles:

### Top Exclusion Reasons:
1. **No codebase/implementation** (45.7%) - 845 articles
2. **Off-topic/Not neuro-symbolic** (24.7%) - 458 articles  
3. **Background article** (7.8%) - 144 articles
4. **Not research paper** (6.5%) - 120 articles
5. **No evaluation** (5.9%) - 109 articles

### Multiple Criteria Analysis:
- **1,493 articles** (80.7%) were excluded for a single reason
- **216 articles** (11.7%) were excluded for multiple reasons
- **142 articles** (7.7%) had no explicit exclusion criteria recorded

### Most Common Multiple Criteria Combinations:
1. **No codebase + No evaluation** (2.6%) - 48 articles
2. **Background article + No codebase** (1.7%) - 31 articles
3. **No codebase + Off-topic** (1.2%) - 22 articles

## Output Files

### 1. Enriched Screening Overview
- **File**: `../data/screening_overview_enriched.json`
- **Content**: Original screening overview + detailed exclusion analysis
- **Structure**: 
  - Original data preserved
  - New `detailed_exclusion_analysis` section added
  - Enhanced `rayyan_screening.excluded_out_of_scope` section

### 2. Analysis Report
- **File**: `exclusion_analysis_report.txt`
- **Content**: Human-readable summary of all findings
- **Format**: Text report with statistics and breakdowns

## Exclusion Criteria Categories

The script recognizes and categorizes the following exclusion criteria:

| Code | Human-Readable Name | Description |
|------|-------------------|-------------|
| `__EXR__no-codebase` | No codebase/implementation | Articles without available code or implementation |
| `__EXR__off-topic` | Off-topic/Not neuro-symbolic | Articles not related to neuro-symbolic AI |
| `__EXR__survey` | Survey/review paper | Survey or review papers |
| `__EXR__background article` | Background article | Background/contextual articles |
| `__EXR__not-research` | Not research paper | Non-research publications |
| `__EXR__no-eval` | No evaluation | Articles without evaluation |
| `__EXR__duplicate` | Duplicate | Duplicate articles |
| `__EXR__review` | Review paper | Review papers |
| `__EXR__no-fulltext` | No fulltext | Articles without full text available |
| `__EXR__not-in-english` | Not in English | Non-English articles |
| `__EXR__foreign language` | Foreign language | Articles in foreign languages |

## Usage

1. Ensure the `exclude.json` file exists in the `output/` directory
2. Ensure the `screening_overview.json` file exists in the `../data/` directory
3. Run the script:
   ```bash
   python exclusion_analyzer.py
   ```

## Script Architecture

The script uses a class-oriented design with the `ExclusionAnalyzer` class that:

- **Loads data** from JSON files
- **Extracts exclusion criteria** from article customizations
- **Analyzes patterns** in exclusion reasons
- **Generates statistics** for individual and combined criteria
- **Enriches the screening overview** with detailed breakdown
- **Creates reports** in both JSON and text formats

## Data Quality Notes

- The script handles articles with multiple exclusion criteria
- It distinguishes between articles with explicit criteria vs. those without
- It provides both raw counts and percentages for easy interpretation
- It preserves all original data while adding new analysis layers

## Integration with Existing Workflow

This script complements the `data_processor.py` script by:
- Using the processed `exclude.json` file as input
- Enriching the existing `screening_overview.json` 
- Providing detailed insights into the exclusion process
- Supporting transparency and reproducibility in systematic reviews 