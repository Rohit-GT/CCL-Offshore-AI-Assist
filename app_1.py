
# PART 1 > “Hey Python, I want to use Google’s AI tools.”

# Gives Python access to your computer’s environment
import os   

# Lets Python read your .env file where your secret API key is stored.
from dotenv import load_dotenv

# This gives access to Google’s Gemini AI library.
from google import genai

##################################################################################################################

# PART 2 > Load your API Key safely
# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

# If the key is missing → stop the program and show an error.
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

##################################################################################################################

# PART 3: Create the Gemini client (connection)
# Create client
client = genai.Client(api_key=API_KEY)

##################################################################################################################

#PART 4: The function that talks to Gemini
def ask_gemini(question: str) -> str:
    interaction = client.interactions.create(
        model="gemini-3-flash-preview",
        input=question
    )

    return interaction.outputs[-1].text   


if __name__ == "__main__":
    print(" Gemini AI is running!")
    print("Type 'exit' to stop.\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() == "exit":
            break

        try:
            response = ask_gemini(user_input)
            print("\nGemini:", response)
        except Exception as e:
            print("\n Error:", e)
