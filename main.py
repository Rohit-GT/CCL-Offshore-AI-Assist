import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
import chromadb
from fastembed import TextEmbedding
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.api_core.exceptions import ResourceExhausted

# Import our ingestion parser function
from ingest import fetch_db_roster

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("[WARNING] GEMINI_API_KEY not found in .env file! AI queries may fail.")

# Configure Gemini
genai.configure(api_key=API_KEY)

# Initialize FastAPI
app = FastAPI(title="CCL Offshore AI Assist API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy loading variables
model = None
chroma_client = None
collection = None

def get_resources():
    """Lazily load and cache lightweight ONNX models and database connections"""
    global model, chroma_client, collection
    if model is None:
        print("Loading lightweight fastembed ONNX model...")
        model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    if chroma_client is None:
        print("Connecting to ChromaDB...")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        chroma_db_path = os.path.join(current_dir, "chroma_db")
        chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        collection = chroma_client.get_or_create_collection(name="schedule")
    return model, collection

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: list

@app.get("/api/status")
def get_status():
    try:
        _, coll = get_resources()
        count = coll.count()
        return {
            "status": "ready",
            "indexed_records": count,
            "database_path": os.path.abspath("chroma_db"),
            "has_api_key": bool(API_KEY)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/reindex")
def reindex_database():
    try:
        model_local, coll = get_resources()
        docs = fetch_db_roster()
        if not docs:
            raise HTTPException(status_code=400, detail="No data extracted from SQL Server database.")
            
        # Clear collection
        global chroma_client
        try:
            chroma_client.delete_collection(name="schedule")
        except Exception:
            pass
        coll = chroma_client.create_collection(name="schedule")
        
        # Embed
        texts = [doc['text'] for doc in docs]
        embeddings_list = [emb.tolist() for emb in model_local.embed(texts)]
        
        # Insert
        ids = [f"doc_{i}" for i in range(len(docs))]
        metadatas = [doc['metadata'] for doc in docs]
        coll.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings_list,
            metadatas=metadatas
        )
        
        # Update global collection reference
        globals()['collection'] = coll
        
        return {
            "status": "success",
            "message": f"Successfully re-indexed {len(docs)} entries from SQL Server.",
            "count": coll.count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_date_from_query(query: str) -> str:
    import re
    query = query.lower()
    months = {
        "april": "04",
        "may": "05",
        "june": "06",
        "july": "07"
    }
    
    # 1. Check for standard YYYY-MM-DD pattern
    match_iso = re.search(r'\b(2026)-(0[4-7]|1[0-2])-([0-2][0-9]|3[0-1])\b', query)
    if match_iso:
        return f"{match_iso.group(1)}-{match_iso.group(2)}-{match_iso.group(3)}"
        
    # 2. Check for MM-DD or M-D patterns (assuming year 2026)
    # e.g., 04-13 or 4/13 or 04/13
    match_slash = re.search(r'\b(0?[4-7])[-/]([0-2]?[0-9]|3[0-1])\b', query)
    if match_slash:
        m = int(match_slash.group(1))
        d = int(match_slash.group(2))
        return f"2026-{m:02d}-{d:02d}"
        
    # 3. Check for text month and day
    # e.g. "april 13", "13th of april", "april 13th"
    for month_name, month_num in months.items():
        if month_name in query:
            numbers = re.findall(r'\b([1-9]|[1-2][0-9]|3[0-1])\b', query.replace(month_name, ''))
            ordinals = re.findall(r'\b([1-9]|[1-2][0-9]|3[0-1])(?:st|nd|rd|th)\b', query)
            
            day = None
            if ordinals:
                day = int(ordinals[0])
            elif numbers:
                day = int(numbers[0])
                
            if day:
                return f"2026-{month_num}-{day:02d}"
                
    return None

def extract_weekend_dates_from_query(query: str) -> list:
    """
    Detects relative time words like 'this weekend', 'today', 'tomorrow', 'this saturday',
    'this sunday' and returns a list of exact YYYY-MM-DD date strings to filter by.
    """
    import re
    from datetime import datetime, timedelta
    query_lower = query.lower()
    today = datetime.now()
    weekday = today.weekday()  # Monday=0, Sunday=6
    dates = []
    
    # "today"
    if "today" in query_lower:
        dates.append(today.strftime("%Y-%m-%d"))
    
    # "tomorrow"
    if "tomorrow" in query_lower:
        dates.append((today + timedelta(days=1)).strftime("%Y-%m-%d"))
    
    # "this weekend" or "weekend" → upcoming Saturday and Sunday
    if "weekend" in query_lower or "this week end" in query_lower:
        days_until_saturday = (5 - weekday) % 7
        if days_until_saturday == 0 and today.hour >= 20:  # Late Saturday → next Saturday
            days_until_saturday = 7
        saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)
        dates.append(saturday.strftime("%Y-%m-%d"))
        dates.append(sunday.strftime("%Y-%m-%d"))
    
    # "this saturday"
    elif "saturday" in query_lower:
        days_until = (5 - weekday) % 7 or 7
        dates.append((today + timedelta(days=days_until)).strftime("%Y-%m-%d"))
    
    # "this sunday"
    elif "sunday" in query_lower:
        days_until = (6 - weekday) % 7 or 7
        dates.append((today + timedelta(days=days_until)).strftime("%Y-%m-%d"))
    
    # "this monday" through "this friday"
    day_names = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
    for day_name_str, day_num in day_names.items():
        if day_name_str in query_lower and "weekend" not in query_lower:
            days_until = (day_num - weekday) % 7 or 7
            dates.append((today + timedelta(days=days_until)).strftime("%Y-%m-%d"))
            break
    
    return dates

def extract_week_from_query(query: str) -> str:
    import re
    query = query.lower()
    match = re.search(r'\bweek\s*(\d+)\b', query)
    if match:
        week_num = int(match.group(1))
        # Roster excel has "Week  1" (two spaces) for week 1, and "Week 2", "Week 3" etc for others
        if week_num == 1:
            return "Week  1"
        return f"Week {week_num}"
    return None

@app.post("/api/query", response_model=QueryResponse)
def query_roster(request: QueryRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
        
    try:
        model_local, coll = get_resources()
        
        # If DB is empty, advise re-indexing
        if coll.count() == 0:
            return QueryResponse(
                answer="The database is currently empty. Please trigger a re-indexing to parse the Excel file.",
                sources=[]
            )
            
        retrieved_docs = []
        retrieved_metadatas = []
        filter_applied = None
        
        # 1. Resolve relative dates ("this weekend", "today", "tomorrow", "this saturday", etc.)
        relative_dates = extract_weekend_dates_from_query(question)
        if relative_dates:
            print(f"[HYBRID] Relative date filter: {relative_dates}")
            all_docs = []
            all_metas = []
            for rd in relative_dates:
                results = coll.query(
                    query_embeddings=[[0.0]*384],
                    where={"date": rd},
                    n_results=1
                )
                if results['documents'] and results['documents'][0]:
                    all_docs.extend(results['documents'][0])
                    all_metas.extend(results['metadatas'][0])
            if all_docs:
                # Sort chronologically
                zipped = sorted(zip(all_docs, all_metas), key=lambda x: x[1].get('date', ''))
                retrieved_docs = [z[0] for z in zipped]
                retrieved_metadatas = [z[1] for z in zipped]
                filter_applied = f"Relative Date Filter: {relative_dates}"
                
        # 2. Try explicit date-based metadata filtering (e.g. "April 13th", "2026-05-14")
        if not retrieved_docs:
            date_filter = extract_date_from_query(question)
            if date_filter:
                print(f"[HYBRID] Extracted date filter: {date_filter}")
                results = coll.query(
                    query_embeddings=[[0.0]*384],
                    where={"date": date_filter},
                    n_results=1
                )
                if results['documents'] and results['documents'][0]:
                    retrieved_docs = results['documents'][0]
                    retrieved_metadatas = results['metadatas'][0]
                    filter_applied = f"Date Filter: {date_filter}"
                    
        # 3. Try week-based metadata filtering (e.g. "Week 2", "week 7")
        if not retrieved_docs:
            week_filter = extract_week_from_query(question)
            if week_filter:
                print(f"[HYBRID] Extracted week filter: {week_filter}")
                results = coll.query(
                    query_embeddings=[[0.0]*384],
                    where={"week": week_filter},
                    n_results=10
                )
                if results['documents'] and results['documents'][0]:
                    zipped = list(zip(results['documents'][0], results['metadatas'][0]))
                    zipped.sort(key=lambda x: x[1].get('date', ''))
                    retrieved_docs = [z[0] for z in zipped]
                    retrieved_metadatas = [z[1] for z in zipped]
                    filter_applied = f"Week Filter: {week_filter}"
                    
        # 4. Fallback to standard vector similarity search
        if not retrieved_docs:
            print(f"[HYBRID] Falling back to semantic search for query: '{question}'")
            query_vector = list(model_local.embed([question]))[0].tolist()
            results = coll.query(
                query_embeddings=[query_vector],
                n_results=7
            )
            retrieved_docs = results['documents'][0] if results['documents'] else []
            retrieved_metadatas = results['metadatas'][0] if results['metadatas'] else []
            
        if not retrieved_docs:
            return QueryResponse(
                answer="I could not find any matching schedule data in the database.",
                sources=[]
            )
            
        context = "\n\n=== Roster Entry ===\n".join(retrieved_docs)

        # Inject today's date so Gemini can resolve relative terms like "this weekend", "today", "tomorrow"
        from datetime import datetime
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        day_name = now.strftime("%A")
        
        # 4. Formulate prompt for Gemini
        prompt = f"""
You are a Schedule and Roster Assistant. You answer questions about the team's shift schedule.
Use ONLY the provided schedule database entries to answer the user's question.
Be clear, direct, and present shift information accurately.

IMPORTANT CONTEXT:
- Today's date is {today_str} ({day_name}).
- Use this to resolve relative terms like "today", "tomorrow", "this weekend", "next week", etc.
- "This weekend" means the upcoming Saturday ({today_str} onwards) and Sunday.
- If a specific date is mentioned, look it up in the entries below.
- If the answer cannot be determined from the provided entries, say so clearly.

SCHEDULE DATABASE ENTRIES:
{context}

QUESTION:
{question}

ANSWER:
"""
        
        # 5. Generate content using Gemini
        llm = genai.GenerativeModel("gemini-2.5-flash")
        
        answer_text = "Error: Could not retrieve answer."
        
        # Simple retry logic for free tier limits
        for attempt in range(3):
            try:
                response = llm.generate_content(prompt)
                answer_text = response.text
                break
            except ResourceExhausted:
                print(f"[WAIT] ResourceExhausted. Waiting to retry (attempt {attempt+1}/3)...")
                time.sleep(10)
            except Exception as e:
                answer_text = f"API Error: {str(e)}"
                break
                
        # 6. Format sources list for the frontend
        sources = []
        for doc, meta in zip(retrieved_docs, retrieved_metadatas):
            sources.append({
                "date": meta.get("date", "Unknown Date"),
                "day": meta.get("day", "Unknown Day"),
                "week": meta.get("week", "Unknown Week"),
                "text": doc
            })
            
        return QueryResponse(answer=answer_text, sources=sources)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files folder (ensure index.html is served at the root)
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Pre-load resources on startup
    get_resources()
    uvicorn.run(app, host="0.0.0.0", port=8000)
