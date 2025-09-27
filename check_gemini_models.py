import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("GEMINI_API_KEY not found!")
    exit(1)

genai.configure(api_key=api_key)

print("Available Gemini models:")
for model in genai.list_models():
    print(f"- {model.name}")