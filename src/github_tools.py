import os
import requests
from crewai.tools import tool

from config import get_available_users

def get_github_headers(user_name: str):
    users = get_available_users()
    user_name_lower = user_name.lower()
    if user_name_lower not in users:
        raise ValueError(f"Unknown user {user_name}")

    token = users[user_name_lower].get('github_token')
    if not token:
        raise ValueError(f"GitHub token for {user_name} is missing securely from environment.")
        
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def get_github_username(user_name: str):
    users = get_available_users()
    user_name_lower = user_name.lower()
    if user_name_lower not in users:
        raise ValueError(f"Unknown user {user_name}")
    
    github_username = users[user_name_lower].get('github_username')
    if not github_username:
        raise ValueError(f"GitHub username for {user_name} is missing securely from environment.")
    return github_username

@tool("Get Open Pull Requests")
def get_open_pull_requests(user_name: str) -> str:
    """Useful to get open pull requests for a specific user."""
    try:
        headers = get_github_headers(user_name)
        gh_user = get_github_username(user_name)
        url = f"https://api.github.com/search/issues?q=is:pr+is:open+author:{gh_user}"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        pr_list = [f"{i+1}. {item['title']} (#{item['number']})" for i, item in enumerate(data.get('items', [])[:10])]
        if not pr_list:
            return f"{user_name} has no open pull requests."
        return f"{user_name} has {len(pr_list)} open pull requests:\n" + "\n".join(pr_list)
    except Exception as e:
        return f"Error fetching pull requests for {user_name}: {str(e)}"

@tool("Get Repositories")
def get_repositories(user_name: str) -> str:
    """Useful to list repositories for a specific user."""
    try:
        headers = get_github_headers(user_name)
        gh_user = get_github_username(user_name)
        url = f"https://api.github.com/users/{gh_user}/repos?sort=updated&per_page=10"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        repo_list = [f"{i+1}. {r['name']}" for i, r in enumerate(data)]
        if not repo_list:
            return f"{user_name} has no repositories."
        return f"{user_name} has {len(repo_list)} repositories:\n" + "\n".join(repo_list)
    except Exception as e:
        return f"Error fetching repositories for {user_name}: {str(e)}"

@tool("Get Assigned Issues")
def get_assigned_issues(user_name: str) -> str:
    """Useful to get assigned issues for a specific user in GitHub."""
    try:
        headers = get_github_headers(user_name)
        gh_user = get_github_username(user_name)
        url = f"https://api.github.com/search/issues?q=is:issue+is:open+assignee:{gh_user}"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        issue_list = [f"- {item['title']} (#{item['number']})" for item in data.get('items', [])[:10]]
        if not issue_list:
            return f"{user_name} has no assigned issues."
        return f"{user_name} has {len(issue_list)} issues assigned:\n" + "\n".join(issue_list)
    except Exception as e:
        return f"Error fetching assigned issues for {user_name}: {str(e)}"
