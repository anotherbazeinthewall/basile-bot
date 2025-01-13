import io
import re
import time
import logging
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
from pypdf import PdfReader

# Initialize logger
logger = logging.getLogger("uvicorn")

# Constants
BASE_URL = "https://resume.alexbasile.com"
CACHE_DURATION = 3600  # 1 hour in seconds
SECTION_KEYWORDS = {'experience', 'education', 'skills', 'projects', 'contact'}
MONTHS = {
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
}

class ResumeFetcher:
    """Handles fetching and extracting PDF content from URL with caching."""
    
    def __init__(self, base_url: str = BASE_URL, bypass_cache: bool = False):
        self.base_url = base_url
        self.session = requests.Session()
        self._cache = {}
        self._cache_timestamps = {}
        self.bypass_cache = bypass_cache
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if self.bypass_cache:
            return False
            
        if cache_key not in self._cache_timestamps:
            return False
            
        elapsed_time = time.time() - self._cache_timestamps[cache_key]
        return elapsed_time < CACHE_DURATION
    
    def _fetch_url(self, url: str, cache_key: str = None) -> Optional[bytes]:
        """Fetch data from URL with caching."""
        if cache_key:
            if self._is_cache_valid(cache_key):
                logger.info(f"Using cached data for {cache_key}")
                return self._cache[cache_key]
            logger.info(f"Fetching fresh data for {cache_key}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.content
            
            if cache_key:
                self._cache[cache_key] = data
                self._cache_timestamps[cache_key] = time.time()
            
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
    
    def _get_pdf_url(self) -> Optional[str]:
        """Extract PDF URL from the base page."""
        try:
            response = self.session.get(self.base_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            
            if not meta_refresh or 'content' not in meta_refresh.attrs:
                logger.error("No meta refresh tag found in base page")
                return None
                
            pdf_path = re.search(r'url=(.+)', meta_refresh['content'])
            if not pdf_path:
                logger.error("No PDF URL found in meta refresh content")
                return None
                
            return requests.compat.urljoin(self.base_url, pdf_path.group(1).strip())
        except requests.RequestException as e:
            logger.error(f"Error fetching base URL {self.base_url}: {e}")
            return None
    
    def get_pdf_content(self) -> Optional[bytes]:
        """Fetch PDF content from the URL with caching."""
        pdf_url = self._get_pdf_url()
        if not pdf_url:
            return None
        
        return self._fetch_url(pdf_url, cache_key="resume_pdf_content")

# Create a module-level instance
resume_fetcher = ResumeFetcher()

class ResumeParser:
    """Handles parsing and formatting of PDF resume content."""
    
    @staticmethod
    def is_section_header(line: str) -> bool:
        """Check if a line is likely a section header."""
        line_lower = line.lower()
        return (
            line.isupper() or
            (len(line) < 40 and any(
                keyword in line_lower for keyword in SECTION_KEYWORDS
            ))
        )
    
    @staticmethod
    def is_subsection(line: str) -> bool:
        """Check if a line is likely a subsection (e.g., job title/date)."""
        line_lower = line.lower()
        return (
            len(line) < 50 and
            ('20' in line or any(
                month in line_lower for month in MONTHS
            ))
        )
    
    def parse_pdf(self, pdf_content: bytes) -> str:
        """Parse PDF content and format it as readable text."""
        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            formatted_sections = []
            current_section = []
            
            for page in reader.pages:
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if self.is_section_header(line):
                        if current_section:
                            formatted_sections.append('\n'.join(current_section))
                        current_section = []
                        current_section.append(f"\n## {line}")
                    elif self.is_subsection(line):
                        current_section.append(f"\n**{line}**")
                    else:
                        current_section.append(line)
            
            if current_section:
                formatted_sections.append('\n'.join(current_section))
            
            # Join and clean up the text
            final_text = '\n'.join(formatted_sections)
            return re.sub(r'\n\s*\n', '\n\n', final_text)
        except Exception as e:
            logger.error(f"Error parsing PDF content: {e}")
            return ""

def pull_resume(bypass_cache: bool = False) -> str:
    """
    Fetch and process a PDF resume from a predefined URL.
    
    Args:
        bypass_cache (bool): If True, bypass the cache and fetch fresh data
    
    Returns:
        str: Extracted and formatted text from the PDF.
        Returns an empty string if any error occurs.
    """
    try:
        # Use the module-level instance
        global resume_fetcher
        if bypass_cache:
            resume_fetcher = ResumeFetcher(bypass_cache=True)
        
        # Fetch PDF content
        pdf_content = resume_fetcher.get_pdf_content()
        if not pdf_content:
            return ""
        
        # Parse and format content
        parser = ResumeParser()
        formatted_text = parser.parse_pdf(pdf_content)
        if not formatted_text:
            return ""
        
        return f"YOUR RESUME:\n\n{formatted_text}\n\n"
    except Exception as e:
        logger.error(f"Error generating resume digest: {e}")
        return ""

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch and parse resume')
    parser.add_argument('--fresh', action='store_true', 
                       help='Bypass cache and fetch fresh data')
    args = parser.parse_args()
    
    if args.fresh:
        logger.info("Bypassing cache and fetching fresh data")
    
    print(pull_resume(bypass_cache=args.fresh))