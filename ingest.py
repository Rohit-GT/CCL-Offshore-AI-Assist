import os
import datetime
import subprocess
from sentence_transformers import SentenceTransformer
import chromadb

def clean_val(val):
    val_str = str(val).strip()
    if not val_str or val_str.lower() == 'null' or val_str.lower() == 'none':
        return "None"
    return val_str

def calculate_week(date_str):
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        start_date = datetime.date(2026, 4, 13) # April 13, 2026 is start of Week 1
        days_diff = (dt - start_date).days
        if days_diff < 0:
            return "Unknown"
        week_num = (days_diff // 7) + 1
        # Match original formatting: "Week  1" (two spaces), and "Week 2", etc.
        if week_num == 1:
            return "Week  1"
        return f"Week {week_num}"
    except Exception:
        return "Unknown"

def fetch_db_roster():
    print("Fetching shift roster data from SQL Server table [CCL Offshore Team Shift Roaster]...")
    query = """
    SET NOCOUNT ON;
    SELECT CONCAT(
        Date, '||', 
        Day, '||', 
        ISNULL([4AM - 1PM           After Business hours], 'None'), '||', 
        ISNULL([1:00 PM - 10:00 PM   Production ], 'None'), '||', 
        ISNULL([7:00PM - 4:00AM Business hours], 'None'), '||', 
        ISNULL([Week off], 'None'), '||', 
        ISNULL(Comments, 'None')
    ) 
    FROM [CCL Offshore Team Shift Roaster]
    ORDER BY Date;
    """
    
    try:
        result = subprocess.run(
            ['sqlcmd', '-S', '.\\SQLEXPRESS', '-E', '-C', '-d', 'OffshoreShiftRosterDB', '-W', '-Q', query],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Connection to SQL Server failed: {e.stderr}")
        return []
        
    lines = result.stdout.strip().splitlines()
    if not lines or len(lines) < 2:
        print("[ERROR] No records returned from the database.")
        return []
        
    # The first line is the '-' separator from sqlcmd formatting, we skip it
    data_lines = [line for line in lines if '||' in line]
    
    formatted_docs = []
    for line in data_lines:
        parts = line.split('||')
        if len(parts) < 7:
            continue
            
        date_val = clean_val(parts[0])
        day_val = clean_val(parts[1])
        shift_4am = clean_val(parts[2])
        shift_1pm = clean_val(parts[3])
        shift_7pm = clean_val(parts[4])
        week_off = clean_val(parts[5])
        comments = clean_val(parts[6])
        
        week_val = calculate_week(date_val)
        
        # Structure metadata
        metadata = {
            'date': date_val,
            'day': day_val,
            'week': week_val,
            'shift_4am_1pm': shift_4am,
            'shift_1pm_10pm': shift_1pm,
            'shift_7pm_4am': shift_7pm,
            'week_off': week_off,
            'daily_comment': comments
        }
        
        # Build text chunk exactly keeping column names present
        doc_text = f"Date: {date_val}\n"
        doc_text += f"Day: {day_val}\n"
        doc_text += f"4AM - 1PM           After Business hours: {shift_4am}\n"
        doc_text += f"1:00 PM - 10:00 PM   Production : {shift_1pm}\n"
        doc_text += f"7:00PM - 4:00AM Business hours: {shift_7pm}\n"
        doc_text += f"Week off: {week_off}\n"
        doc_text += f"Comments: {comments}"
        
        formatted_docs.append({
            'metadata': metadata,
            'text': doc_text
        })
        
    print(f"Successfully fetched and parsed {len(formatted_docs)} rows from SQL Server.")
    return formatted_docs

def main():
    # 1. Fetch data from DB
    docs = fetch_db_roster()
    if not docs:
        print("[ERROR] No database records extracted.")
        return
        
    # 2. Load Local Embedding Model
    print("Loading local SentenceTransformer model ('all-MiniLM-L6-v2')...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # 3. Generate Embeddings
    print("Generating embeddings for database chunks...")
    texts = [doc['text'] for doc in docs]
    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings_list = [emb.tolist() for emb in embeddings]
    
    # 4. Setup ChromaDB
    print("Initializing ChromaDB database at './chroma_db'...")
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    
    # Drop existing collection to ensure clean reload
    collection_name = "schedule"
    try:
        chroma_client.delete_collection(name=collection_name)
        print(f"Cleared existing '{collection_name}' collection.")
    except Exception:
        pass
        
    collection = chroma_client.create_collection(name=collection_name)
    
    # 5. Insert documents, embeddings and metadata
    print("Inserting data into ChromaDB...")
    ids = [f"doc_{i}" for i in range(len(docs))]
    metadatas = [doc['metadata'] for doc in docs]
    
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings_list,
        metadatas=metadatas
    )
    
    print("[SUCCESS] Ingestion and indexing completed successfully!")
    print(f"Total indexed entries in ChromaDB: {collection.count()}")

if __name__ == "__main__":
    main()
