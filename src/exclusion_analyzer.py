import json
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ExclusionAnalyzer:
    """Class to analyze exclusion criteria from exclude.json and enrich screening_overview.json"""
    
    def __init__(self, exclude_json_path: str = "output/exclude.json", 
                 screening_overview_path: str = "../data/screening_overview.json"):
        self.exclude_json_path = Path(exclude_json_path)
        self.screening_overview_path = Path(screening_overview_path)
        
        # Define exclusion criteria categories
        self.exclusion_categories = {
            "__EXR__off-topic": "Off-topic/Not neuro-symbolic",
            "__EXR__no-codebase": "No codebase/implementation",
            "__EXR__survey": "Survey/review paper",
            "__EXR__background article": "Background article",
            "__EXR__not-research": "Not research paper",
            "__EXR__no-eval": "No evaluation",
            "__EXR__duplicate": "Duplicate",
            "__EXR__review": "Review paper",
            "__EXR__c": "Other/Unclear"
        }
    
    def load_exclude_data(self) -> List[Dict]:
        """Load the exclude.json file"""
        try:
            with open(self.exclude_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} articles from exclude.json")
            return data
        except Exception as e:
            logger.error(f"Error loading exclude.json: {e}")
            return []
    
    def load_screening_overview(self) -> Dict:
        """Load the screening_overview.json file"""
        try:
            with open(self.screening_overview_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("Loaded screening_overview.json")
            return data
        except Exception as e:
            logger.error(f"Error loading screening_overview.json: {e}")
            return {}
    
    def extract_exclusion_criteria(self, article: Dict) -> Set[str]:
        """Extract all exclusion criteria for a single article"""
        criteria = set()
        
        if 'customizations' in article:
            for customization in article['customizations']:
                key = customization.get('key', '')
                value = customization.get('value', '')
                
                # Check if this is an exclusion criterion
                if key.startswith('"__EXR__') and value in ['1', 'deleted']:
                    # Extract the criterion name
                    criterion = key.strip('"')
                    criteria.add(criterion)
        
        return criteria
    
    def analyze_exclusions(self, articles: List[Dict]) -> Dict:
        """Analyze exclusion criteria across all articles"""
        logger.info("Analyzing exclusion criteria...")
        
        # Count individual criteria
        individual_counts = Counter()
        
        # Track articles with multiple criteria
        multi_criteria_articles = []
        single_criteria_articles = []
        
        # Track all unique criteria combinations
        criteria_combinations = Counter()
        
        for article in articles:
            criteria = self.extract_exclusion_criteria(article)
            
            if criteria:
                # Count individual criteria
                for criterion in criteria:
                    individual_counts[criterion] += 1
                
                # Track articles by number of criteria
                if len(criteria) > 1:
                    multi_criteria_articles.append({
                        'article_id': article['article_id'],
                        'title': article['title'],
                        'criteria': list(criteria)
                    })
                    # Sort criteria for consistent combination tracking
                    sorted_criteria = tuple(sorted(criteria))
                    criteria_combinations[sorted_criteria] += 1
                else:
                    single_criteria_articles.append({
                        'article_id': article['article_id'],
                        'title': article['title'],
                        'criteria': list(criteria)
                    })
        
        # Create detailed breakdown
        breakdown = {
            'total_excluded_articles': len(articles),
            'articles_with_exclusion_criteria': len([a for a in articles if self.extract_exclusion_criteria(a)]),
            'articles_without_explicit_criteria': len([a for a in articles if not self.extract_exclusion_criteria(a)]),
            'individual_criteria_counts': {},
            'articles_with_single_criterion': len(single_criteria_articles),
            'articles_with_multiple_criteria': len(multi_criteria_articles),
            'criteria_combinations': {},
            'detailed_breakdown': {
                'single_criterion_articles': single_criteria_articles,
                'multi_criterion_articles': multi_criteria_articles
            }
        }
        
        # Add individual criteria counts with human-readable names
        for criterion, count in individual_counts.most_common():
            readable_name = self.exclusion_categories.get(criterion, criterion)
            breakdown['individual_criteria_counts'][readable_name] = {
                'criterion_code': criterion,
                'count': count,
                'percentage': round((count / len(articles)) * 100, 1)
            }
        
        # Add criteria combinations
        for combination, count in criteria_combinations.most_common():
            readable_combination = []
            for criterion in combination:
                readable_name = self.exclusion_categories.get(criterion, criterion)
                readable_combination.append(readable_name)
            
            breakdown['criteria_combinations'][', '.join(readable_combination)] = {
                'criteria_codes': list(combination),
                'count': count,
                'percentage': round((count / len(articles)) * 100, 1)
            }
        
        return breakdown
    
    def enrich_screening_overview(self, original_data: Dict, exclusion_analysis: Dict) -> Dict:
        """Enrich the screening overview with detailed exclusion analysis"""
        enriched_data = original_data.copy()
        
        # Add detailed exclusion breakdown
        enriched_data['detailed_exclusion_analysis'] = exclusion_analysis
        
        # Update the rayyan_screening section with more detail
        if 'rayyan_screening' in enriched_data:
            enriched_data['rayyan_screening']['excluded_out_of_scope'] = {
                'total_count': exclusion_analysis['total_excluded_articles'],
                'breakdown': exclusion_analysis
            }
        
        return enriched_data
    
    def save_enriched_overview(self, enriched_data: Dict, output_path: str = "../data/screening_overview_enriched.json"):
        """Save the enriched screening overview"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved enriched screening overview to {output_path}")
        except Exception as e:
            logger.error(f"Error saving enriched overview: {e}")
    
    def generate_summary_report(self, exclusion_analysis: Dict) -> str:
        """Generate a human-readable summary report"""
        report = []
        report.append("=" * 80)
        report.append("EXCLUSION CRITERIA ANALYSIS SUMMARY")
        report.append("=" * 80)
        report.append("")
        
        # Overall statistics
        report.append(f"Total excluded articles: {exclusion_analysis['total_excluded_articles']}")
        report.append(f"Articles with explicit exclusion criteria: {exclusion_analysis['articles_with_exclusion_criteria']}")
        report.append(f"Articles without explicit criteria: {exclusion_analysis['articles_without_explicit_criteria']}")
        report.append("")
        
        # Individual criteria breakdown
        report.append("INDIVIDUAL EXCLUSION CRITERIA:")
        report.append("-" * 50)
        for criterion_name, data in exclusion_analysis['individual_criteria_counts'].items():
            report.append(f"{criterion_name}: {data['count']} articles ({data['percentage']}%)")
        report.append("")
        
        # Multiple criteria
        report.append(f"Articles with single criterion: {exclusion_analysis['articles_with_single_criterion']}")
        report.append(f"Articles with multiple criteria: {exclusion_analysis['articles_with_multiple_criteria']}")
        report.append("")
        
        # Criteria combinations
        if exclusion_analysis['criteria_combinations']:
            report.append("MOST COMMON CRITERIA COMBINATIONS:")
            report.append("-" * 50)
            for combination, data in list(exclusion_analysis['criteria_combinations'].items())[:10]:
                report.append(f"{combination}: {data['count']} articles ({data['percentage']}%)")
        
        return "\n".join(report)
    
    def run_analysis(self):
        """Run the complete analysis"""
        logger.info("Starting exclusion criteria analysis...")
        
        # Load data
        articles = self.load_exclude_data()
        if not articles:
            logger.error("No articles loaded. Exiting.")
            return
        
        screening_overview = self.load_screening_overview()
        if not screening_overview:
            logger.error("No screening overview loaded. Exiting.")
            return
        
        # Analyze exclusions
        exclusion_analysis = self.analyze_exclusions(articles)
        
        # Enrich screening overview
        enriched_overview = self.enrich_screening_overview(screening_overview, exclusion_analysis)
        
        # Save enriched overview
        self.save_enriched_overview(enriched_overview)
        
        # Generate and save summary report
        summary_report = self.generate_summary_report(exclusion_analysis)
        with open("exclusion_analysis_report.txt", 'w', encoding='utf-8') as f:
            f.write(summary_report)
        logger.info("Saved exclusion analysis report to exclusion_analysis_report.txt")
        
        # Print summary
        print("\n" + summary_report)
        
        logger.info("Analysis complete!")

def main():
    """Main function to run the exclusion analyzer"""
    analyzer = ExclusionAnalyzer()
    analyzer.run_analysis()

if __name__ == "__main__":
    main() 