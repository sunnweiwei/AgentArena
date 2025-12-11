import os
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Attempt to load API key from .env or known file locations
def load_api_key():
    # Try .env first
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        return api_key
    
    # Fallback to openaikey file for backward compatibility
    paths = [
        "openaikey",
        "../openaikey",
        "/usr1/data/weiweis/chat_server/openaikey"
    ]
    for path in paths:
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    
    print("Error: OPENAI_API_KEY not found in .env and openaikey file not found in known locations")
    print("Please set OPENAI_API_KEY in .env file or create an 'openaikey' file")
    sys.exit(1)


client = OpenAI(api_key=load_api_key())


def debug_stream(model_name: str):
    print(f"\nStreaming debug for {model_name}")
    stream = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "Say hello and describe yourself in two sentences."}
        ],
        stream=True,
    )

    for idx, chunk in enumerate(stream):
        choice = chunk.choices[0]
        delta = choice.delta
        print(f"Chunk {idx}: finish_reason={choice.finish_reason}")
        print(f"Raw delta: {delta}")
        if delta.content:
            for part in delta.content:
                if getattr(part, "type", "") == "text":
                    print(f"Text part: {part.text!r}")
        print("---")


if __name__ == "__main__":
    debug_stream("gpt-5-nano")



