import os
import sys
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from pydantic import BaseModel
from typing import Literal, Optional
import instructor
from openai import OpenAI
import contextlib
import io

@contextlib.contextmanager
def suppress_stdout_stderr():
    new_out, new_err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err

# Tools
from src.tools.github_tools import get_open_pull_requests, get_repositories, get_assigned_issues, get_starred_repos
from src.tools.linear_tools import get_linear_assigned_issues, get_linear_projects, get_linear_teams
from src.core.config import get_available_users

env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

# Set up Ollama with Instructor for routing
client = instructor.from_openai(
    OpenAI(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1",
        api_key="ollama",  # required, but unused
    ),
    mode=instructor.Mode.JSON,
)

class QueryClassification(BaseModel):
    is_out_of_scope: bool
    domain: Optional[Literal["github", "linear", "both"]] = None
    target_user: Optional[str] = None
    clarification_needed: bool

# Set up CrewAI LLM
crewai_llm = LLM(
    model="ollama/" + os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)

github_agent = Agent(
    role="GitHub Expert",
    goal="Answer user queries about GitHub repositories, issues, and pull requests.",
    backstory="You are a super smart GitHub assistant. You use your tools to fetch data and present it clearly. If you don't know the answer, say so.",
    verbose=False,
    allow_delegation=False,
    tools=[get_open_pull_requests, get_repositories, get_assigned_issues, get_starred_repos],
    llm=crewai_llm,
    max_iter=3
)

linear_agent = Agent(
    role="Linear Expert",
    goal="Answer user queries about Linear issues, projects, and teams.",
    backstory="You are a super smart Linear assistant. You use your tools to fetch data and present it clearly.",
    verbose=False,
    allow_delegation=False,
    tools=[get_linear_assigned_issues, get_linear_projects, get_linear_teams],
    llm=crewai_llm,
    max_iter=3
)

def process_query(query: str):
    users = get_available_users()
    user_names = [u['name'] for u in users.values()]
    
    if not user_names:
        return "System configuration error: No users defined in the environment."
        
    user_names_str = ", ".join([f"'{name}'" for name in user_names])
    user_names_or = " or ".join([f"{name}" for name in user_names])

    mentioned_users = [name for name in user_names if name.lower() in query.lower()]
    
    # Step 1: Classify Query (LLM with keyword fallback)
    classification = None
    try:
        sys_prompt = f"""You are a specialized routing assistant. Classify the user query exactly.
Respond with a flat JSON object with these exact keys:
- "is_out_of_scope": boolean
- "domain": "github" or "linear" or null
- "target_user": one of {user_names_or} or null
- "clarification_needed": boolean

Rules:
- domain is 'github' for repos, pull requests, commits, github issues.
- domain is 'linear' for linear issues, projects, teams.
- target_user should be set ONLY if the user's name appears in the query.
- is_out_of_scope is true ONLY for completely unrelated queries (weather, sports, etc).
- If the query mentions 'issues', 'repos', 'pull requests', 'linear', or 'github', it is NOT out of scope."""

        classification = client.chat.completions.create(
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": query},
            ],
            response_model=QueryClassification,
        )
        print("✅ [Classification] LLM classification succeeded.")
    except Exception as e:
        print(f"⚠️ [Classification] LLM classification failed: {e}")
        print("🔄 [Classification] Falling back to keyword-based classification...")
        
        # Keyword-based fallback classification
        query_lower = query.lower()
        
        # Determine domain from keywords
        github_keywords = ["github", "repo", "repository", "pull request", "pr", "commit", "star"]
        linear_keywords = ["linear", "project", "team"]
        
        domain = None
        if any(kw in query_lower for kw in github_keywords):
            domain = "github"
        elif any(kw in query_lower for kw in linear_keywords):
            domain = "linear"
        
        # Check for issue-related queries (could be either platform)
        if domain is None and "issue" in query_lower:
            domain = "github"  # default issues to github unless linear is mentioned
        
        # Determine if out of scope
        is_out_of_scope = domain is None and not any(kw in query_lower for kw in ["issue", "assigned"])
        
        # Determine target user
        target_user = mentioned_users[0] if len(mentioned_users) == 1 else None
        clarification_needed = len(mentioned_users) == 0 and not is_out_of_scope
        
        classification = QueryClassification(
            is_out_of_scope=is_out_of_scope,
            domain=domain,
            target_user=target_user,
            clarification_needed=clarification_needed,
        )
        print(f"✅ [Classification] Fallback result: domain={classification.domain}, user={classification.target_user}, out_of_scope={classification.is_out_of_scope}")

    # Step 2: Handle special cases according to requirements
    print(f"\n🔍 [Routing Log] Query: '{query}'")
    print(f"🔍 [Routing Log] Domain detected by LLM: {classification.domain}")
    
    if classification.is_out_of_scope:
        print("❌ [Routing Log] Query classified as completely out of scope.")
        return "I cannot answer this question"
        
    print(f"🔍 [Routing Log] Users explicitly mentioned: {mentioned_users}")
    if not mentioned_users:
        print("⚠️ [Routing Log] No specific users mentioned, clarification will be needed.")
        classification.target_user = None
        classification.clarification_needed = True
    elif len(mentioned_users) == 1:
        print(f"✅ [Routing Log] Found exactly 1 mentioned user '{mentioned_users[0]}', overriding LLM target_user guess.")
        classification.target_user = mentioned_users[0]
        classification.clarification_needed = False

    if classification.clarification_needed or not classification.target_user:
        print("⚠️ [Routing Log] Asking user for clarification...")
        if "issue" in query.lower() and "github" not in query.lower():
            return f"I can help with that! Which user's issues would you like to see - {user_names_or}?"
        elif classification.domain == "github" or "pull request" in query.lower() or "repository" in query.lower():
            return f"I can help with that! Which user's pull requests would you like to see - {user_names_or}?"
        elif classification.domain == "linear":
            return f"I can help with that! Which user's issues would you like to see - {user_names_or}?"
        else:
            return f"I can help with that! Which user would you like to see - {user_names_or}?"

    # Step 3: Route to the appropriate Agent
    user_name = classification.target_user
    agent = None
    
    if classification.domain == "github":
        agent = github_agent
        print(f"🚀 [Execution Log] Routing to GitHub Agent for user '{user_name}'...")
    elif classification.domain == "linear":
        agent = linear_agent
        print(f"🚀 [Execution Log] Routing to Linear Agent for user '{user_name}'...")
    else:
        # Default to github if unclear
        agent = github_agent
        print(f"🚀 [Execution Log] Domain unclear, defaulting route to GitHub Agent for user '{user_name}'...")
        
    task = Task(
        description=f"Answer this user query accurately: '{query}'. Use your tools exactly once for user '{user_name}' to get the real data. Present the data smoothly.",
        expected_output="A well-formatted conversational paragraph or list string containing the requested data exactly as given by tools. Give ONLY the conversational response directly, do not output JSON.",
        agent=agent
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=False
    )
    
    with suppress_stdout_stderr():
        result = crew.kickoff()
    
    raw = result.raw
    
    # Post-processing: if the LLM returned a raw JSON tool call instead of
    # executing the tool, manually invoke the appropriate tool.
    import json
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "name" in parsed and "parameters" in parsed:
            tool_name = parsed["name"]
            params = parsed["parameters"]
            print(f"🔄 [Post-Process] Agent returned raw tool call for '{tool_name}', executing manually...")
            
            # Map tool names to actual functions
            tool_map = {
                "get_open_pull_requests": get_open_pull_requests,
                "get_repositories": get_repositories,
                "get_assigned_issues": get_assigned_issues,
                "get_starred_repos": get_starred_repos,
                "get_linear_assigned_issues": get_linear_assigned_issues,
                "get_linear_projects": get_linear_projects,
                "get_linear_teams": get_linear_teams,
            }
            
            if tool_name in tool_map:
                tool_fn = tool_map[tool_name]
                raw = tool_fn.run(**params)
                print(f"✅ [Post-Process] Tool '{tool_name}' executed successfully.")
            else:
                print(f"⚠️ [Post-Process] Unknown tool '{tool_name}', returning raw output.")
    except (json.JSONDecodeError, TypeError, KeyError):
        pass  # Not JSON, normal response — return as-is
    
    return raw
