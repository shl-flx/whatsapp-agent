import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=20
    )
    print("✓ Connection successful!")
    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens used: {response.usage.total_tokens}")
except Exception as e:
    print(f"✗ Error: {e}")
