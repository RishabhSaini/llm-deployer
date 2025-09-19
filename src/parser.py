# src/parser.py

from .llm_service import invoke_llm

def parse_intent(user_prompt: str) -> dict:
    """
    Uses the LLM to parse the user's natural language prompt into a structured
    JSON object containing key deployment parameters.

    Args:
        user_prompt: The natural language string from the user.

    Returns:
        A dictionary with the parsed intent.
    """
    # This prompt is carefully engineered to guide the LLM.
    # It provides a "system" instruction, defines the expected output format,
    # and gives a clear task.
    prompt = f"""
        System: You are an expert DevOps assistant. Your task is to parse the user's 
        deployment request and extract key information into a structured JSON object. 
        Only output the JSON object, with no other text or explanations.

        The possible cloud providers are 'aws', 'gcp', 'azure'. Default to 'gcp' if not specified.
        The possible instance sizes are 'small', 'medium', 'large'. A 'test' or 'dev' instance
        should be considered 'small'. Default to 'small' if not specified.

        User Request: "{user_prompt}"

        Now, provide the structured JSON output.
    """

    try:
        parsed_json = invoke_llm(prompt, is_json=True)
        
        # Basic validation to ensure the LLM returned the expected structure
        if not isinstance(parsed_json, dict) or "cloud_provider" not in parsed_json:
            raise ValueError("LLM did not return the expected JSON structure for the intent.")
            
        return parsed_json

    except Exception as e:
        print(f"Error while parsing intent: {e}")
        # Re-raise the exception to be caught by the main handler
        raise
