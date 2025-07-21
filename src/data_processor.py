import os
import json
import pandas as pd
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Article:
    """Data class to represent an article entry"""
    article_id: str
    title: str = ""
    year: str = ""
    author: str = ""
    url: str = ""
    abstract: str = ""
    note: str = ""
    customizations: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.customizations is None:
            self.customizations = []
    
    def __post_init__(self):
        if self.customizations is None:
            self.customizations = []

class BibTeXParser:
    """Class to parse BibTeX files"""
    
    def __init__(self):
        # Pattern to match @article entries - use non-greedy matching to the last }
        self.article_pattern = re.compile(
            r'@article\{([^,]+),'
            r'(.*?)'
            r'\n\}',
            re.DOTALL
        )
        # Pattern to match field=value pairs
        self.field_pattern = re.compile(r'(\w+)\s*=\s*\{([^}]*)\}', re.DOTALL)
    
    def parse_bibtex_file(self, file_path: str) -> List[Article]:
        """Parse a BibTeX file and return list of Article objects"""
        articles = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Find all article entries
            matches = self.article_pattern.findall(content)
            
            for article_id, article_content in matches:
                article = Article(article_id=article_id.strip())
                
                # Parse fields using a more robust approach
                # Split by lines and process each line
                lines = article_content.strip().split('\n')
                current_field = None
                current_value = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this line starts a new field
                    field_match = re.match(r'(\w+)\s*=\s*\{', line)
                    if field_match:
                        # Save previous field if exists
                        if current_field and current_value:
                            self._set_article_field(article, current_field, '\n'.join(current_value))
                        
                        # Start new field
                        current_field = field_match.group(1).lower()
                        # Extract the value part after the opening brace
                        value_part = line[line.find('{') + 1:]
                        if value_part.endswith('}'):
                            # Single line field
                            self._set_article_field(article, current_field, value_part[:-1])
                            current_field = None
                            current_value = []
                        else:
                            # Multi-line field
                            current_value = [value_part]
                    elif current_field and line.endswith('}'):
                        # End of multi-line field
                        current_value.append(line[:-1])
                        self._set_article_field(article, current_field, '\n'.join(current_value))
                        current_field = None
                        current_value = []
                    elif current_field:
                        # Continuation of multi-line field
                        current_value.append(line)
                
                articles.append(article)
                
        except Exception as e:
            logger.error(f"Error parsing BibTeX file {file_path}: {e}")
        
        return articles
    
    def _set_article_field(self, article: Article, field_name: str, value: str):
        """Set the appropriate field on the article object"""
        value = value.strip()
        # Remove trailing }, if present
        if value.endswith('},'):
            value = value[:-2]
        elif value.endswith('}'):
            value = value[:-1]
        
        if field_name == 'title':
            article.title = value
        elif field_name == 'year':
            article.year = value
        elif field_name == 'author':
            article.author = value
        elif field_name == 'url':
            article.url = value
        elif field_name == 'abstract':
            article.abstract = value
        elif field_name == 'note':
            article.note = value

class CustomizationsParser:
    """Class to parse customizations log CSV files"""
    
    def parse_customizations_file(self, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse a customizations CSV file and return dict mapping article_id to customizations"""
        customizations = {}
        
        try:
            df = pd.read_csv(file_path)
            
            for _, row in df.iterrows():
                article_id = str(row['article_id'])
                if article_id not in customizations:
                    customizations[article_id] = []
                
                customization = {
                    'created_at': row['created_at'],
                    'user_id': row['user_id'],
                    'user_email': row['user_email'],
                    'key': row['key'],
                    'value': row['value']
                }
                customizations[article_id].append(customization)
                
        except Exception as e:
            logger.error(f"Error parsing customizations file {file_path}: {e}")
        
        return customizations

class DataProcessor:
    """Main class to process data and generate output files"""
    
    def __init__(self, data_dir: str = "../data"):
        self.data_dir = Path(data_dir)
        self.bibtex_parser = BibTeXParser()
        self.customizations_parser = CustomizationsParser()
        
    def process_folder(self, folder_name: str) -> Tuple[List[Article], Dict[str, List[Dict[str, Any]]]]:
        """Process a specific folder and return articles and customizations"""
        folder_path = self.data_dir / folder_name
        
        if not folder_path.exists():
            logger.warning(f"Folder {folder_path} does not exist")
            return [], {}
        
        # Parse BibTeX file
        bibtex_file = folder_path / "articles.bib"
        articles = []
        if bibtex_file.exists():
            articles = self.bibtex_parser.parse_bibtex_file(str(bibtex_file))
            logger.info(f"Parsed {len(articles)} articles from {bibtex_file}")
        else:
            logger.warning(f"BibTeX file not found: {bibtex_file}")
        
        # Parse customizations file
        customizations_file = folder_path / "customizations_log.csv"
        customizations = {}
        if customizations_file.exists():
            customizations = self.customizations_parser.parse_customizations_file(str(customizations_file))
            logger.info(f"Parsed customizations for {len(customizations)} articles from {customizations_file}")
        else:
            logger.warning(f"Customizations file not found: {customizations_file}")
        
        # Merge customizations with articles
        for article in articles:
            # Extract numeric part from article_id (remove "rayyan-" prefix)
            numeric_id = article.article_id.replace("rayyan-", "")
            if numeric_id in customizations:
                article.customizations = customizations[numeric_id]
        
        return articles, customizations
    
    def combine_data(self, folder_names: List[str]) -> Tuple[List[Article], Dict[str, List[Dict[str, Any]]]]:
        """Combine data from multiple folders"""
        all_articles = []
        all_customizations = {}
        
        for folder_name in folder_names:
            articles, customizations = self.process_folder(folder_name)
            all_articles.extend(articles)
            all_customizations.update(customizations)
        
        return all_articles, all_customizations
    
    def articles_to_dict_list(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Convert list of Article objects to list of dictionaries"""
        return [asdict(article) for article in articles]
    
    def save_json(self, data: List[Dict[str, Any]], output_file: str):
        """Save data to JSON file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved JSON file: {output_file}")
        except Exception as e:
            logger.error(f"Error saving JSON file {output_file}: {e}")
    
    def save_excel(self, data: List[Dict[str, Any]], output_file: str):
        """Save data to Excel file"""
        try:
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Create Excel writer
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Main data sheet
                df.to_excel(writer, sheet_name='Articles', index=False)
                
                # Create separate sheet for customizations if they exist
                customizations_data = []
                for article in data:
                    if article['customizations']:
                        for customization in article['customizations']:
                            customizations_data.append({
                                'article_id': article['article_id'],
                                'title': article['title'],
                                **customization
                            })
                
                if customizations_data:
                    customizations_df = pd.DataFrame(customizations_data)
                    customizations_df.to_excel(writer, sheet_name='Customizations', index=False)
            
            logger.info(f"Saved Excel file: {output_file}")
        except Exception as e:
            logger.error(f"Error saving Excel file {output_file}: {e}")
    
    def process_and_save(self):
        """Main method to process data and save output files"""
        logger.info("Starting data processing...")
        
        # Process include data (included + conflict folders)
        logger.info("Processing include data...")
        include_articles, include_customizations = self.combine_data(['included', 'conflict'])
        include_data = self.articles_to_dict_list(include_articles)
        
        # Process exclude data (excluded + maybe folders)
        logger.info("Processing exclude data...")
        exclude_articles, exclude_customizations = self.combine_data(['excluded', 'maybe'])
        exclude_data = self.articles_to_dict_list(exclude_articles)
        
        # Create output directory
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Save include files
        self.save_json(include_data, str(output_dir / "include.json"))
        self.save_excel(include_data, str(output_dir / "include.xlsx"))
        
        # Save exclude files
        self.save_json(exclude_data, str(output_dir / "exclude.json"))
        self.save_excel(exclude_data, str(output_dir / "exclude.xlsx"))
        
        logger.info(f"Processing complete!")
        logger.info(f"Include data: {len(include_articles)} articles")
        logger.info(f"Exclude data: {len(exclude_articles)} articles")

def main():
    """Main function to run the data processor"""
    processor = DataProcessor()
    processor.process_and_save()

if __name__ == "__main__":
    main() 