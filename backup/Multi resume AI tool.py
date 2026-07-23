import os
from dotenv import load_dotenv
from google import genai
from docx import Document

# Load API key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)


def load_resume_text():
    """Read resume and return full text"""
    doc = Document("resume.docx")
    full_text = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            full_text.append(text)

    return "\n".join(full_text)




def ask_from_resume(question, context):
    prompt = f"""
Answer the following question using the provided resume content.
If the answer is not in the resume, explicitly say "I don't know based on the given resume."

RESUME CONTENT:
{context}

QUESTION:
{question}
"""

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    return response.text


if __name__ == "__main__":
    print("Resume-based AI Assistant (Improved Accuracy)")
    print("Ask questions based on resume.docx")
    print("Type 'exit' to stop\n")

    resume_text = load_resume_text()
    print(f"DEBUG: Loaded resume ({len(resume_text)} characters)")

    while True:
        question = input("You: ")

        if question.lower() == "exit":
            break

        answer = ask_from_resume(question, resume_text)
        print("\nAI:", answer)
