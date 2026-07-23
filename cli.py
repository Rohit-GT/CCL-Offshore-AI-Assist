import os
import sys
import time
import warnings

# Suppress warnings for a clean CLI experience
warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from fastapi import HTTPException
from pydantic import ValidationError

# Import functions from main.py
try:
    from main import query_roster, QueryRequest, reindex_database, get_resources
except ImportError as e:
    print(f"Error importing from main.py: {e}")
    sys.exit(1)

# ANSI colors for beautiful terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GRAY = '\033[90m'

def print_header():
    print(f"{Colors.BOLD}{Colors.CYAN}=================================================={Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}         ROSTER AI ASSISTANT (CLI Mode)           {Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}=================================================={Colors.ENDC}")

def run_query(question: str):
    try:
        # Wrap the question in QueryRequest
        req = QueryRequest(question=question)
        print(f"\n{Colors.BOLD}{Colors.BLUE}[*] Querying: \"{question}\"...{Colors.ENDC}")
        
        # Call the roster query logic directly
        response = query_roster(req)
        
        # Print AI answer
        print(f"\n{Colors.BOLD}{Colors.GREEN}[AI ANSWER]{Colors.ENDC}")
        print(response.answer)
        
        # Print sources if available
        if response.sources:
            print(f"\n{Colors.BOLD}{Colors.GRAY}[SOURCES USED]{Colors.ENDC}")
            for idx, source in enumerate(response.sources, 1):
                date_str = source.get("date", "Unknown Date")
                day_str = source.get("day", "Unknown Day")
                week_str = source.get("week", "Unknown Week")
                print(f"{Colors.GRAY}  {idx}. [{week_str} | {day_str} {date_str}]{Colors.ENDC}")
                text_snippet = source.get("text", "").replace("\n", " ")
                if len(text_snippet) > 80:
                    text_snippet = text_snippet[:80] + "..."
                print(f"{Colors.GRAY}     Snippet: {text_snippet}{Colors.ENDC}")
        print(f"\n{Colors.CYAN}--------------------------------------------------{Colors.ENDC}")
    except HTTPException as he:
        print(f"\n{Colors.FAIL}[ERROR] {he.detail}{Colors.ENDC}")
    except ValidationError as ve:
        print(f"\n{Colors.FAIL}[ERROR] Invalid query structure: {ve}{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}[ERROR] An unexpected error occurred: {e}{Colors.ENDC}")

def run_reindex():
    print(f"\n{Colors.BOLD}{Colors.WARNING}[*] Re-indexing database from source data...{Colors.ENDC}")
    try:
        res = reindex_database()
        print(f"{Colors.BOLD}{Colors.GREEN}[SUCCESS] {res.get('message', 'Database re-indexed successfully.')}{Colors.ENDC}")
        print(f"{Colors.GREEN}Indexed count: {res.get('count', 0)}{Colors.ENDC}")
    except HTTPException as he:
        print(f"\n{Colors.FAIL}[ERROR] Re-indexing failed: {he.detail}{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}[ERROR] An unexpected error occurred during reindexing: {e}{Colors.ENDC}")
    print(f"\n{Colors.CYAN}--------------------------------------------------{Colors.ENDC}")

def interactive_loop():
    print_header()
    print(f"{Colors.BOLD}{Colors.CYAN}[*] Initializing local resources (models, database)...{Colors.ENDC}")
    try:
        get_resources()
    except Exception as e:
        print(f"{Colors.FAIL}[ERROR] Failed to load resources: {e}{Colors.ENDC}")
        sys.exit(1)
        
    print(f"{Colors.GREEN}[*] Initialization complete! Ready to answer questions.{Colors.ENDC}")
    print(f"\n{Colors.BOLD}Options:{Colors.ENDC}")
    print(f"  - Enter your question (e.g., 'Who is working next Saturday?')")
    print(f"  - Type {Colors.BOLD}/reindex{Colors.ENDC} to re-index the roster data")
    print(f"  - Type {Colors.BOLD}/exit{Colors.ENDC} or {Colors.BOLD}exit{Colors.ENDC} to quit")
    print(f"{Colors.CYAN}=================================================={Colors.ENDC}")

    while True:
        try:
            user_input = input(f"\n{Colors.BOLD}Ask a question: {Colors.ENDC}").strip()
            if not user_input:
                continue
                
            if user_input.lower() in ['/exit', 'exit', 'quit', '/quit']:
                print(f"\n{Colors.BLUE}Goodbye!{Colors.ENDC}")
                break
                
            if user_input.lower() == '/reindex':
                run_reindex()
                continue
                
            run_query(user_input)
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.BLUE}Goodbye!{Colors.ENDC}")
            break

def main():
    # If arguments are passed, run a single query and exit
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg in ['--help', '-h']:
            print("Roster AI Assistant - Command Line Interface")
            print("\nUsage:")
            print("  python cli.py               - Run in interactive chat mode")
            print("  python cli.py --reindex     - Re-index the database and exit")
            print("  python cli.py \"<question>\"  - Run a single query and exit")
            sys.exit(0)
        elif arg == '--reindex':
            run_reindex()
            sys.exit(0)
        else:
            question = " ".join(sys.argv[1:])
            run_query(question)
            sys.exit(0)
    else:
        interactive_loop()

if __name__ == "__main__":
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
            
    main()
