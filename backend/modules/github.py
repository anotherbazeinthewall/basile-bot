import requests
from collections import Counter
from typing import List, Dict, Optional, Any
from datetime import datetime

# Constants
USERNAME = "anotherbazeinthewall"
BASE_URL = "https://api.github.com"
TOP_REPOS_LIMIT = 5

class GitHubAPI:
    """Handles GitHub API interactions and data processing."""
    
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def _fetch_url(self, url: str) -> Optional[Any]:
        """
        Fetch data from a GitHub API endpoint.
        
        Args:
            url (str): The API endpoint URL
            
        Returns:
            Optional[Any]: JSON response data or None if request fails
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching URL {url}: {e}")
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
        
        # Top repositories section
        sections.append("Top Repositories (by Recent Activity):")
        for repo in top_repos:
            sections.append(
                f"- {repo['name']} "
                f"(Last updated: {repo.get('updated_at', 'N/A')})"
            )
        
        # Languages section
        sections.append("\nLanguages Used:")
        for language, count in language_stats.most_common():
            sections.append(f"- {language}: {count} repos")
        
        # Starred repositories section
        sections.append("\nStarred Repositories:")
        for repo in starred_repos[:TOP_REPOS_LIMIT]:
            sections.append(
                f"- {repo['full_name']} "
                f"({repo['html_url']})"
            )
        
        return "YOUR GITHUB PROFILE:\n\n" + "\n".join(sections) + "\n\n"

def pull_github() -> str:
    """
    Fetch and generate a digest of GitHub information for a predefined user.
    
    Returns:
        str: A summary of the user's GitHub profile, including repositories,
             languages, and starred repos.
    """
    api = GitHubAPI()
    digest = GitHubDigest()
    
    # Fetch data
    own_repos = api.get_repos()
    contributed_repos = api.get_contributed_repos()
    starred_repos = api.get_starred_repos()
    
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

if __name__ == "__main__":
    print(pull_github())