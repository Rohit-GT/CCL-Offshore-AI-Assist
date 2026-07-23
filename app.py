import os
import math
from dotenv import load_dotenv
from docx import Document
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import time
from google.api_core.exceptions import ResourceExhausted
model = SentenceTransformer('all-MiniLM-L6-v2')



# Load API key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)

# -------------------------------
# Load all resumes from folder
# -------------------------------
def load_resumes(folder_path="resumes"):
    resumes = {}

    for file in os.listdir(folder_path):
        if file.endswith(".docx"):
            doc = Document(os.path.join(folder_path, file))
            text = "\n".join(
                [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            )
            resumes[file] = text

    return resumes


# -------------------------------
# STEP 1: Get embedding
# -------------------------------

def get_embedding(text):
    return model.encode(text)

# -------------------------------
# STEP 2: Create embeddings for all resumes
# -------------------------------
def create_resume_embeddings(resumes):
    resume_embeddings = {}

    for name, text in resumes.items():
        print(f"Creating embedding for {name}...")
        embedding = get_embedding(text)
        resume_embeddings[name] = embedding

    return resume_embeddings


# -------------------------------
# STEP 3: Cosine similarity
# -------------------------------
def cosine_similarity(vec1, vec2):
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0

    return dot / (norm1 * norm2)


# -------------------------------
# STEP 4: Find relevant resumes using embeddings
# -------------------------------
def find_relevant_resumes(question, resume_embeddings, top_k=2):
    query_embedding = get_embedding(question)

    scores = {}

    for name, emb in resume_embeddings.items():
        score = cosine_similarity(query_embedding, emb)
        scores[name] = score

    sorted_resumes = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [name for name, _ in sorted_resumes[:top_k]]


# -------------------------------
# Ask Gemini
# -------------------------------
def ask_from_resume(question, context):
    prompt = f"""
You are a resume assistant.

Answer ONLY using the resumes below.
If not found, say:
"I don't know based on the given resumes."

RESUME CONTENT:
{context}

QUESTION:
{question}

ANSWER:
"""

    # 👇 Put it HERE
    llm = genai.GenerativeModel("gemini-2.5-flash")
    
    # Add retry logic for strict Free Tier limits (5 requests/minute)
    for attempt in range(3):
        try:
            response = llm.generate_content(prompt)
            return response.text
        except ResourceExhausted as e:
            print(f"\n[WAIT] Google API Quota exceeded. Details:\n{e}")
            print("\nWaiting 35 seconds to retry...")
            time.sleep(35)
        except Exception as e:
            print(f"\n[ERROR] API Error: {e}")
            break
            
    return "Error: Could not get a response from the AI."
# -------------------------------
# Main Program
# -------------------------------
if __name__ == "__main__":
    print("Multi-Resume AI Assistant (Embedding-Based RAG)")
    print("Place your resumes inside 'resumes/' folder")
    print("Type 'exit' to stop\n")

    resumes = load_resumes()

    if not resumes:
        print("[ERROR] No resumes found!")
        exit()

    print(f"[OK] Loaded {len(resumes)} resumes")

    # Create embeddings (runs once)
    resume_embeddings = create_resume_embeddings(resumes)

    print("[OK] Embeddings ready!\n")

    while True:
        question = input("You: ")

        if question.lower() == "exit":
            break

        # Step 1: Retrieve relevant resumes (Change top_k to pass more resumes to the AI)
        top_resumes = find_relevant_resumes(question, resume_embeddings, top_k=6)

        # Step 2: Combine selected resumes
        context = "\n\n".join([resumes[name] for name in top_resumes])

        # Step 3: Ask LLM
        answer = ask_from_resume(question, context)

        print(f"\n[INFO] Using resumes: {top_resumes}")
        print("AI:", answer)