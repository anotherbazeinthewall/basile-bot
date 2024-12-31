import time
import logging
import argparse
import requests
from collections import Counter
from typing import List, Dict, Optional, Any

# Initialize logger
logger = logging.getLogger("uvicorn")

# Constants
USERNAME = "anotherbazeinthewall"
BASE_URL = "https://api.github.com"
TOP_REPOS_LIMIT = 5
CACHE_DURATION = 3600  # 1 hour in seconds

class GitHubAPI:
    """Handles GitHub API interactions and data processing."""

    def __init__(self, bypass_cache: bool = False) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json'
        })
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
    
    def _fetch_url(self, url: str, cache_key: str = None) -> Optional[Any]:
        """
        Fetch data from a GitHub API endpoint with time-based caching.
        
        Args:
            url (str): The API endpoint URL
            cache_key (str): Optional key for caching the response
        
        Returns:
            Optional[Any]: JSON response data or None if request fails
        """
        if cache_key and self._is_cache_valid(cache_key):
            logger.info(f"Using cached data for {cache_key}")
            return self._cache[cache_key]

        try:
            logger.info(f"Fetching fresh data for {cache_key}")
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if cache_key:
                self._cache[cache_key] = data
                self._cache_timestamps[cache_key] = time.time()
            
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
    
    def get_repos(self) -> List[Dict]:
        """Fetch user's owned repositories."""
        url = f"{BASE_URL}/users/{USERNAME}/repos?type=owner&per_page=100"
        return self._fetch_url(url) or []
    
    def get_contributed_repos(self) -> List[Dict]:
        """Fetch repositories the user has contributed to."""
        url = f"{BASE_URL}/users/{USERNAME}/events/public"
        events = self._fetch_url(url)
        if not events:
            return []
        
        contributed_repos = {}
        for event in events:
            if event.get("type") in ["PushEvent", "PullRequestEvent"]:
                repo = event.get("repo")
                if repo:
                    contributed_repos[repo["name"]] = {
                        "name": repo["name"],
                        "url": repo["url"],
                    }
        return list(contributed_repos.values())
    
    def get_starred_repos(self) -> List[Dict]:
        """Fetch repositories starred by the user."""
        url = f"{BASE_URL}/users/{USERNAME}/starred"
        return self._fetch_url(url) or []

class GitHubDigest:
    """Processes and formats GitHub data into a readable digest."""

    @staticmethod
    def merge_repos(own_repos: List[Dict], contributed_repos: List[Dict]) -> List[Dict]:
        """Merge owned and contributed repositories without duplicates."""
        repo_dict = {repo.get("url"): repo for repo in own_repos}
        for repo in contributed_repos:
            if repo.get("url") not in repo_dict:
                repo_dict[repo.get("url")] = repo
        return list(repo_dict.values())
    
    @staticmethod
    def get_top_active_repos(repos: List[Dict], limit: int = TOP_REPOS_LIMIT) -> List[Dict]:
        """Get the most recently active repositories."""
        sorted_repos = sorted(
            repos,
            key=lambda repo: repo.get('updated_at', ''),
            reverse=True
        )
        return sorted_repos[:limit]
    
    @staticmethod
    def get_languages(repos: List[Dict]) -> Counter:
        """Calculate language usage statistics."""
        return Counter(
            repo["language"] for repo in repos
            if repo.get("language")
        )
    
    @staticmethod
    def format_digest(
        top_repos: List[Dict],
        language_stats: Counter,
        starred_repos: List[Dict]
    ) -> str:
        """Format the GitHub data into a readable string."""
        sections = []
        
        # Languages section
        sections.append("\nYOUR PROGRAMMING LANGUAGES (ON GITHUB):\n")
        for language, count in language_stats.most_common():
            sections.append(f"- {language}: {count} repos")

        # Top repositories section
        sections.append("\nYOUR PERSONAL GITHUB REPOS:\n")
        for repo in top_repos:
            description = repo.get('description', 'No description available')
            sections.append(
                f"""- {repo['full_name']}: "{description}" ({repo['html_url']})"""
            )
        
        # Starred repositories section
        sections.append("\nYOUR WATCHED GITHUB REPOS:\n")
        for repo in starred_repos[:TOP_REPOS_LIMIT]:
            description = repo.get('description', '[No description available]')
            sections.append(
                f"""- {repo['full_name']}: "{description}" ({repo['html_url']})"""
            )
        
        return "\n".join(sections) + "\n\n"

def pull_github(bypass_cache: bool = False) -> str:
    """
    Fetch and generate a digest of GitHub information for a predefined user.
    
    Args:
        bypass_cache (bool): If True, bypass the cache and fetch fresh data
    
    Returns:
        str: A summary of the user's GitHub profile, including repositories,
             languages, and starred repos.
    """
    try:
        api = GitHubAPI(bypass_cache=bypass_cache)
        digest = GitHubDigest()
        
        # Fetch data
        own_repos = api.get_repos()
        contributed_repos = api.get_contributed_repos()
        starred_repos = api.get_starred_repos()
        
        # If any of the data fetches failed, return an empty string
        if not own_repos or not contributed_repos or not starred_repos:
            return ""
        
        # Process data
        all_repos = digest.merge_repos(own_repos, contributed_repos)
        top_active_repos = digest.get_top_active_repos(all_repos)
        language_stats = digest.get_languages(own_repos)
        
        # Format output
        return digest.format_digest(
            top_active_repos,
            language_stats,
            starred_repos
        )
    except Exception as e:
        logger.error(f"Error generating GitHub digest: {e}")
        return ""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch GitHub profile information')
    parser.add_argument('--fresh', action='store_true', 
                       help='Bypass cache and fetch fresh data')
    args = parser.parse_args()
    
    if args.fresh:
        logger.info("Bypassing cache and fetching fresh data")
    
    print(pull_github(bypass_cache=args.fresh))
