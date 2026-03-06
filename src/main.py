import sys
import os
import logging

# Configure logging for observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Ensure the project root is on sys.path so 'src' is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.orchestrator import process_query

def main():
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

if __name__ == "__main__":
    main()
