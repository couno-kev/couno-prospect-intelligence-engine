import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("APOLLO_API_KEY")

if api_key:
    print("Apollo API Key loaded successfully.")
    print(f"First 6 characters: {api_key[:6]}******")
else:
    print("Apollo API Key NOT found.")
