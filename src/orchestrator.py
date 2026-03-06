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
from github_tools import get_open_pull_requests, get_repositories, get_assigned_issues
from linear_tools import get_linear_assigned_issues, get_linear_projects, get_linear_teams
from config import get_available_users

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
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
    tools=[get_open_pull_requests, get_repositories, get_assigned_issues],
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
    
    # Step 1: Classify Query
    try:
        classification = client.chat.completions.create(
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            messages=[
                {
                    "role": "system",
                    "content": f"You are a specialized routing assistant. Classify the user query exactly: \n- Identify domain as 'github' or 'linear'.\n- Identify target_user. It should be one of {user_names_or} ONLY if their exact name is present in the query.\n- If none of these specific users are mentioned, set clarification_needed=True and target_user=null.\n- If the query is unrelated, set is_out_of_scope=True."
                },
                {"role": "user", "content": query},
            ],
            response_model=QueryClassification,
        )
    except Exception as e:
        print(f"Error in classification: {e}")
        return "Internal system error during classification."

    # Step 2: Handle special cases according to requirements
    if classification.is_out_of_scope:
        return "I cannot answer this question"
        
    if not mentioned_users:
        classification.target_user = None
        classification.clarification_needed = True

    if classification.clarification_needed or not classification.target_user:
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
    elif classification.domain == "linear":
        agent = linear_agent
    else:
        # Default to github if unclear
        agent = github_agent
        
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
    return result.raw

if __name__ == "__main__":
    import sys
    # For direct testing via command line arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"System: {process_query(query)}")
    else:
        print("Multi-Agent System started! (Type 'exit' to quit)")
        while True:
            try:
                q = input("User: ")
                if not q.strip(): continue
                if q.lower() in ['exit', 'quit']:
                    break
                response = process_query(q)
                print(f"System: {response}\n")
            except KeyboardInterrupt:
                break
