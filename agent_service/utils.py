import os
from openai import OpenAI



def call_openai():
    # Load API keys
    OPENAI_API_KEY = None
    try:
        key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'openaikey')
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                OPENAI_API_KEY = f.read().strip()
        else:
            key_path = '/usr1/data/weiweis/chat_server/openaikey'
            if os.path.exists(key_path):
                with open(key_path, 'r') as f:
                    OPENAI_API_KEY = f.read().strip()
    except Exception as e:
        print(f"Warning: Could not load OpenAI API key: {e}")

    openai_client = None
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized successfully")
    return openai_client

