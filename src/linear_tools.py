import os
import requests
from crewai.tools import tool

from config import get_available_users

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"

def get_linear_headers(user_name: str):
    users = get_available_users()
    user_name_lower = user_name.lower()
    
    if user_name_lower not in users:
        raise ValueError(f"Unknown user {user_name}")
    
    token = users[user_name_lower].get('linear_token')
    if not token:
        raise ValueError(f"Linear token for {user_name} is missing securely from environment.")
        
    return {"Authorization": f"{token}", "Content-Type": "application/json"}

@tool("Get Linear Assigned Issues")
def get_linear_assigned_issues(user_name: str) -> str:
    """Useful to get assigned issues for a specific user in Linear."""
    headers = get_linear_headers(user_name)
    try:
        query = """
        query {
          viewer {
            assignedIssues(first: 10, filter: { state: { type: { neq: "canceled" } } }) {
              nodes {
                id
                identifier
                title
                state {
                  name
                }
              }
            }
          }
        }
        """
        response = requests.post(LINEAR_GRAPHQL_URL, json={"query": query}, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        nodes = data.get("data", {}).get("viewer", {}).get("assignedIssues", {}).get("nodes", [])
        if not nodes:
            return f"{user_name} has no assigned issues in Linear."
            
        issue_list = [f"- [{node['identifier']}] {node['title']} ({node['state']['name']})" for node in nodes]
        return f"{user_name} has {len(issue_list)} issues assigned:\n" + "\n".join(issue_list)
    except Exception as e:
        return f"Error fetching Linear issues for {user_name}: {str(e)}"

@tool("Get Linear Projects")
def get_linear_projects(user_name: str) -> str:
    """Useful to get projects for a specific user in Linear."""
    headers = get_linear_headers(user_name)
    try:
        query = """
        query {
          projects(first: 10) {
            nodes {
              id
              name
              state
            }
          }
        }
        """
        response = requests.post(LINEAR_GRAPHQL_URL, json={"query": query}, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        nodes = data.get("data", {}).get("projects", {}).get("nodes", [])
        if not nodes:
            return f"{user_name} has no projects in Linear."
            
        project_list = [f"- {node['name']} ({node['state']})" for node in nodes]
        return f"{user_name} has {len(project_list)} projects:\n" + "\n".join(project_list)
    except Exception as e:
        return f"Error fetching Linear projects for {user_name}: {str(e)}"

@tool("Get Linear Teams")
def get_linear_teams(user_name: str) -> str:
    """Useful to get teams for a specific user in Linear."""
    headers = get_linear_headers(user_name)
    try:
        query = """
        query {
          viewer {
            teams(first: 10) {
              nodes {
                id
                name
                key
              }
            }
          }
        }
        """
        response = requests.post(LINEAR_GRAPHQL_URL, json={"query": query}, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        nodes = data.get("data", {}).get("viewer", {}).get("teams", {}).get("nodes", [])
        if not nodes:
            return f"{user_name} is not a member of any teams in Linear."
            
        team_list = [f"- {node['name']} ({node['key']})" for node in nodes]
        return f"{user_name} is in {len(team_list)} teams:\n" + "\n".join(team_list)
    except Exception as e:
        return f"Error fetching Linear teams for {user_name}: {str(e)}"
