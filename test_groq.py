import os
import requests

api_key = "REMOVED_GROQ_KEY_1"
url = "https://api.groq.com/openai/v1/models"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
response = requests.get(url, headers=headers)
print("REPORT KEY STATUS:", response.status_code, response.text)

api_key2 = "REMOVED_GROQ_KEY_2"
headers2 = {
    "Authorization": f"Bearer {api_key2}",
    "Content-Type": "application/json"
}
response2 = requests.get(url, headers=headers2)
print("DEFAULT KEY STATUS:", response2.status_code, response2.text)

api_key3 = "REMOVED_GROQ_KEY_3"
headers3 = {
    "Authorization": f"Bearer {api_key3}",
    "Content-Type": "application/json"
}
response3 = requests.get(url, headers=headers3)
print("CHATBOT KEY STATUS:", response3.status_code, response3.text)

