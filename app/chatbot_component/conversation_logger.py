# conversation_logger.py - Handles chat history

import json
import os

HISTORY_DIR = "data/conversations"
os.makedirs(HISTORY_DIR, exist_ok=True)
def get_history_file(user_id="guest"):
    return os.path.join(HISTORY_DIR, f"chat_history_{user_id}.json")

def load_history(user_id="guest"):
    file_path = get_history_file(user_id)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def save_history(entry, user_id="guest"):
    history = load_history(user_id)
    history.append(entry)
    with open(get_history_file(user_id), 'w') as f:
        json.dump(history, f)

def clear_history(user_id="guest"):
    file_path = get_history_file(user_id)
    if os.path.exists(file_path):
        os.remove(file_path)
