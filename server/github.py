import requests
from collections import Counter

def pull_github() -> str:
    """
    Fetch and generate a digest of GitHub information for a predefined user.

    Returns:
        str: A summary of the user's GitHub profile, including repositories, languages, and starred repos.
    """
    username = "anotherbazeinthewall"
    base_url = "https://api.github.com"

    def fetch_url(url):
        """Helper function to fetch data from a URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching URL {url}: {e}")
            return None

    def get_repos():
        """Fetch the list of repositories for the user."""
        url = f"{base_url}/users/{username}/repos?type=owner&per_page=100"
        repos = fetch_url(url)
        return repos if repos else []

    def get_contributed_repos():
        """Fetch the repositories the user has contributed to."""
        url = f"{base_url}/users/{username}/events/public"
        events = fetch_url(url)
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

    def merge_repos(own_repos, contributed_repos):
        """Merge own and contributed repositories without duplicates."""
        repo_dict = {repo.get("url"): repo for repo in own_repos}
        for repo in contributed_repos:
            if repo.get("url") not in repo_dict:
                repo_dict[repo.get("url")] = repo
        return list(repo_dict.values())

    def get_top_active_repos(repos, top_n=5):
        """Get the top repositories based on recent activity."""
        sorted_repos = sorted(repos, key=lambda repo: repo.get('updated_at', ''), reverse=True)
        return sorted_repos[:top_n]

    def get_languages(repos):
        """Get the most used programming languages across repositories."""
        languages = []
        for repo in repos:
            if repo.get("language"):
                languages.append(repo["language"])
        return Counter(languages)

    def get_starred_repos():
        """Fetch the repositories starred by the user."""
        url = f"{base_url}/users/{username}/starred"
        starred_repos = fetch_url(url)
        return starred_repos if starred_repos else []

    # Fetch user's repositories
    own_repos = get_repos()

    # Fetch contributed repositories
    contributed_repos = get_contributed_repos()

    # Merge own and contributed repositories
    all_repos = merge_repos(own_repos, contributed_repos)

    # Top repositories by activity
    top_active_repos = get_top_active_repos(all_repos)

    # Languages used
    language_stats = get_languages(own_repos)

    # Starred repositories
    starred_repos = get_starred_repos()

    # Generate digest output as a string
    digest = []

    digest.append("Top Repositories (by Recent Activity):")
    for repo in top_active_repos:
        digest.append(f"- {repo['name']} (Last updated: {repo.get('updated_at', 'N/A')})")

    digest.append("Languages Used:")
    for language, count in language_stats.most_common():
        digest.append(f"- {language}: {count} repos")

    digest.append("Starred Repositories:")
    for repo in starred_repos[:5]:
        digest.append(f"- {repo['full_name']} ({repo['html_url']})")

    digest = "\n".join(digest)
    return f"YOUR GITHUB PROFILE:\n\n{digest}\n\n"

if __name__ == "__main__":
    print(pull_github())
