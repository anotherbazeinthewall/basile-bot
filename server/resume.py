import io
import re
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

def pull_resume() -> str:
    """
    Fetch and process a PDF resume from a predefined URL.
    Returns:
    str: Extracted and formatted text from the PDF.
    """
    base_url = "https://resume.alexbasile.com"
    
    # Fetch the base page and extract the PDF URL
    response = requests.get(base_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
    pdf_url = re.search(r'url=(.+)', meta_refresh['content']).group(1).strip()
    pdf_url = requests.compat.urljoin(base_url, pdf_url)
    
    # Fetch the PDF content
    pdf_content = requests.get(pdf_url).content
    pdf_file = io.BytesIO(pdf_content)
    
    # Extract text
    reader = PdfReader(pdf_file)
    
    # Process each page with improved formatting
    formatted_sections = []
    for page in reader.pages:
        text = page.extract_text()
        
        # Split into lines and process
        lines = text.split('\n')
        current_section = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Attempt to detect headers/sections (you might need to adjust these patterns)
            if line.isupper() or (len(line) < 40 and any(word in line.lower() for word in 
                ['experience', 'education', 'skills', 'projects', 'contact'])):
                if current_section:
                    formatted_sections.append('\n'.join(current_section))
                    current_section = []
                current_section.append(f"\n## {line}")
            # Detect potential subsections (like job titles/dates)
            elif len(line) < 50 and ('20' in line or any(month in line.lower() for month in 
                ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 
                'september', 'october', 'november', 'december'])):
                current_section.append(f"\n**{line}**")
            else:
                # Regular content
                current_section.append(line)
        
        if current_section:
            formatted_sections.append('\n'.join(current_section))
    
    # Join all sections
    final_text = '\n'.join(formatted_sections)
    
    # Clean up extra whitespace while preserving intentional line breaks
    final_text = re.sub(r'\n\s*\n', '\n\n', final_text)
    
    return f"YOUR RESUME:\n\n{final_text}\n"

if __name__ == "__main__":
    resume = pull_resume()
    print(resume)