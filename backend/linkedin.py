import re
import requests
from bs4 import BeautifulSoup

def pull_linkedin() -> str:
    """
    Fetch and generate a digest of LinkedIn information for a predefined user.

    Returns:
        str: A summary of the user's LinkedIn profile.
    """
    base_url = "https://www.google.com/search?q="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    query = "site:linkedin.com/in awbasile"

    try:
        # Format the search URL
        search_url = f"{base_url}{query.replace(' ', '+')}"

        # Send a GET request to the search URL
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()

        # Parse the HTML response
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract the first search result
        results = soup.find_all("div", class_="tF2Cxc")
        if not results:
            return "Error: No search results found."

        first_result = results[0]
        title = first_result.find("h3").text if first_result.find("h3") else "No title found"
        link = first_result.find("a")["href"] if first_result.find("a") else "No link found"

        # Look for raw data-based snippets
        raw_data = response.text

        # Extract snippet
        snippet_matches = re.findall(r'"Technical Program Manager.*?SaaS environments.*?"', raw_data)
        snippets = list(set([match.strip('"') for match in snippet_matches]))  # Deduplicate
        snippet = snippets[0] if snippets else "No description found"

        # Extract follower count
        follower_matches = re.findall(r'(\d{1,3}\+?)\s+followers', raw_data, re.IGNORECASE)
        followers = follower_matches[0] if follower_matches else "Not available"

        # Format the output as a single string
        profile_string = (
            f"YOUR LINKEDIN PROFILE:\n\n"
            f"Followers: {followers}\n"
            f"Link: {link}\n"
            f"Title: {title}\n"
            f"About: {snippet}\n"
            "\n"
        )
        return profile_string

    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    print(pull_linkedin())
