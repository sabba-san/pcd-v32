import os
import requests

url = "https://api.groq.com/openai/v1/models"

# Load keys from environment (never hardcode secrets in source files)
api_key = os.getenv("GROQ_API_KEY_REPORT", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
response = requests.get(url, headers=headers)
print("REPORT KEY STATUS:", response.status_code, response.text)

api_key2 = os.getenv("GROQ_API_KEY", "")
headers2 = {
    "Authorization": f"Bearer {api_key2}",
    "Content-Type": "application/json"
}
response2 = requests.get(url, headers=headers2)
print("DEFAULT KEY STATUS:", response2.status_code, response2.text)

api_key3 = os.getenv("GROQ_API_KEY_CHATBOT", "")
headers3 = {
    "Authorization": f"Bearer {api_key3}",
    "Content-Type": "application/json"
}
response3 = requests.get(url, headers=headers3)
print("CHATBOT KEY STATUS:", response3.status_code, response3.text)
