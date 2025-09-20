# src/llm_service.py

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_MODEL = "google/gemini-flash-1.5"
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found in .env file.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

def invoke_llm(prompt_text: str, is_json: bool = True) -> str | dict:
    """
    Invokes a model on OpenRouter with a given prompt.
    """
    print(f"\n\n--- 🤖 Invoking OpenRouter (Model: {OPENROUTER_MODEL}) ---")
    print(f"Prompt:\n{prompt_text[:200]}...")

    try:
        completion = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.2,
        )
        raw_response_text = completion.choices[0].message.content
        print(f"Raw LLM Response:\n{raw_response_text[:300]}...")

        if is_json:
            if "```json" in raw_response_text:
                json_text = raw_response_text.split("```json")[1].split("```")[0].strip()
            else:
                json_text = raw_response_text
            
            # --- THIS IS THE FIX ---
            # Repair common invalid JSON escape sequences produced by LLMs for shell commands.
            repaired_text = json_text.replace('\\;', '\\\\;')
            
            return json.loads(repaired_text, strict=False)
        else:
            return raw_response_text

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON from LLM response. Raw text was:\n{raw_response_text}")
        raise e
    except Exception as e:
        print(f"An unexpected error occurred while invoking the LLM: {e}")
        raise e