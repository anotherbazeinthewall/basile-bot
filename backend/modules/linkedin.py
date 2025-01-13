import re
import time
import requests
import logging
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

# Initialize logger
logger = logging.getLogger("uvicorn")

# Constants
BASE_URL = "https://www.google.com/search?q="
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)
SEARCH_QUERY = "site:linkedin.com/in awbasile"
CACHE_DURATION = 3600  # 1 hour in seconds

class LinkedInAPI:
    """Handles LinkedIn data fetching and caching."""
    
    def __init__(self, bypass_cache: bool = False) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
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
    
    def _fetch_url(self, url: str, cache_key: str = None) -> Optional[str]:
        """Fetch data from URL with caching."""
        if cache_key:
            if self._is_cache_valid(cache_key):
                logger.info(f"Using cached data for {cache_key}")
                return self._cache[cache_key]
            logger.info(f"Fetching fresh data for {cache_key}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.text
            
            if cache_key:
                self._cache[cache_key] = data
                self._cache_timestamps[cache_key] = time.time()
            
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
    
    def fetch_google_results(self) -> Optional[str]:
        """Fetch Google search results for the LinkedIn profile."""
        search_url = f"{BASE_URL}{SEARCH_QUERY.replace(' ', '+')}"
        return self._fetch_url(search_url, cache_key="linkedin_google_results")

# Create a module-level instance
linkedin_api = LinkedInAPI()

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

def pull_linkedin(bypass_cache: bool = False) -> str:
    """
    Fetch and generate a digest of LinkedIn information for a predefined user.
    
    Args:
        bypass_cache (bool): If True, bypass the cache and fetch fresh data
    
    Returns:
        str: A summary of the user's LinkedIn profile. Returns an empty string if any error occurs.
    """
    try:
        # Use the module-level instance
        global linkedin_api
        if bypass_cache:
            linkedin_api = LinkedInAPI(bypass_cache=True)
        
        # Fetch search results
        html = linkedin_api.fetch_google_results()
        if not html:
            return ""
            
        # Extract and format profile data
        title, link, snippet, followers = _extract_profile_data(html)
        
        # Format the output
        return (
            f"YOUR LINKEDIN PROFILE:\n\n"
            f"Title: {title}\n"
            f"About: {snippet}\n"
            f"Link: {link}\n"
            f"Followers: {followers}\n"
            "\n"
        )
    except Exception as e:
        logger.error(f"Error generating LinkedIn digest: {e}")
        return ""

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch LinkedIn profile information')
    parser.add_argument('--fresh', action='store_true', 
                       help='Bypass cache and fetch fresh data')
    args = parser.parse_args()
    
    if args.fresh:
        logger.info("Bypassing cache and fetching fresh data")
    
    print(pull_linkedin(bypass_cache=args.fresh))