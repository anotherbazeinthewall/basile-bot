import io
import re
import logging
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

# Initialize logger
logger = logging.getLogger("uvicorn")

# Constants
BASE_URL = "https://resume.alexbasile.com"
SECTION_KEYWORDS = {'experience', 'education', 'skills', 'projects', 'contact'}
MONTHS = {
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
}

class ResumeFetcher:
    """Handles fetching and extracting PDF content from URL."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
    
    def _get_pdf_url(self) -> Optional[str]:
        """
        Extract PDF URL from the base page.
        
        Returns:
            Optional[str]: The PDF URL or None if not found
        """
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
        """
        Fetch PDF content from the URL.
        
        Returns:
            Optional[bytes]: PDF content or None if fetch fails
        """
        pdf_url = self._get_pdf_url()
        if not pdf_url:
            return None
            
        try:
            response = self.session.get(pdf_url)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"Error fetching PDF from {pdf_url}: {e}")
            return None

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
        """
        Parse PDF content and format it as readable text.
        
        Args:
            pdf_content (bytes): Raw PDF content
            
        Returns:
            str: Formatted text from the PDF
        """
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

def pull_resume() -> str:
    """
    Fetch and process a PDF resume from a predefined URL.
    
    Returns:
        str: Extracted and formatted text from the PDF.
        Returns an empty string if any error occurs.
    """
    try:
        # Fetch PDF content
        fetcher = ResumeFetcher()
        pdf_content = fetcher.get_pdf_content()
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
    print(pull_resume())