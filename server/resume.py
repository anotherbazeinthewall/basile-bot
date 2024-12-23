import io
import re
import fitz as pymupdf
import requests
from bs4 import BeautifulSoup

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
    doc = pymupdf.open(stream=io.BytesIO(pdf_content), filetype="pdf")

    # Extract and format the text from the PDF
    text = "".join(
        f"\n## {span['text']}\n" if span["size"] > 13
        else f"**{span['text']}** " if span["flags"] & 1
        else f"{span['text']} " + ('\n' if span == line["spans"][-1] else '')
        for page in doc
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    )

    return f"YOUR RESUME:\n{text}\n"

if __name__ == "__main__":
    resume = pull_resume()
    print(resume)
