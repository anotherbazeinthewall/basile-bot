import re
import requests
import logging
from bs4 import BeautifulSoup
from typing import Optional

# Initialize logger
logger = logging.getLogger("uvicorn")  # Use uvicorn's logger instead of creating a new one

# Constants
BASE_URL = "https://www.google.com/search?q="
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)
SEARCH_QUERY = "site:linkedin.com/in awbasile"

def _fetch_google_results() -> Optional[str]:
    """
    Fetch Google search results for the LinkedIn profile.
    
    Returns:
        Optional[str]: Raw HTML response or None if request fails
    """
    headers = {"User-Agent": USER_AGENT}
    search_url = f"{BASE_URL}{SEARCH_QUERY.replace(' ', '+')}"
    
    try:
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching Google search results: {e}")
        return None

def _extract_profile_data(html: str) -> tuple[str, str, str, str]:
    """
    Extract LinkedIn profile data from Google search results.
    
    Args:
        html (str): Raw HTML from Google search
        
    Returns:
        tuple: (title, link, snippet, followers)
    """
    soup = BeautifulSoup(html, "html.parser")
    results = soup.find_all("div", class_="tF2Cxc")
    
    # Extract basic info
    first_result = results[0] if results else None
    title = first_result.find("h3").text if first_result and first_result.find("h3") else "No title found"
    link = first_result.find("a")["href"] if first_result and first_result.find("a") else "No link found"
    
    # Extract snippet
    snippet_matches = re.findall(r'"Technical Program Manager.*?SaaS environments.*?"', html)
    snippets = list(set(match.strip('"') for match in snippet_matches))
    snippet = snippets[0] if snippets else "No description found"
    
    # Extract follower count
    follower_matches = re.findall(r'(\d{1,3}\+?)\s+followers', html, re.IGNORECASE)
    followers = follower_matches[0] if follower_matches else "Not available"
    
    return title, link, snippet, followers

def pull_linkedin() -> str:
    """
    Fetch and generate a digest of LinkedIn information for a predefined user.
    
    Returns:
        str: A summary of the user's LinkedIn profile. Returns an empty string if any error occurs.
    """
    try:
        # Fetch search results
        html = _fetch_google_results()
        if not html:
            return ""
            
        # Extract and format profile data
        title, link, snippet, followers = _extract_profile_data(html)
        
        # Format the output
        return (
            f"YOUR LINKEDIN PROFILE:\n\n"
            f"Followers: {followers}\n"
            f"Link: {link}\n"
            f"Title: {title}\n"
            f"About: {snippet}\n"
            "\n"
        )
    except Exception as e:
        logger.error(f"Error generating LinkedIn digest: {e}")
        return ""

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    print(pull_linkedin())
