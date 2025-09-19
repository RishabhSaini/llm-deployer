# src/analyzer.py

import os
import subprocess
import tempfile
import shutil
from .llm_service import invoke_llm

# A list of filenames that are highly indicative of the project's stack and configuration.
# We will read the content of these files to send to the LLM.
HIGH_SIGNAL_FILES = [
    'requirements.txt', 'package.json', 'Dockerfile', 'docker-compose.yml',
    'pom.xml', 'build.gradle', 'Gemfile', 'go.mod', 'Procfile',
    'app.py', 'main.py', 'server.js', 'index.js', 'wsgi.py',
]

def _clone_repo(repo_url: str, temp_dir: str):
    """Clones a git repository into a temporary directory."""
    try:
        print(f"Cloning repository: {repo_url}...")
        subprocess.run(
            ['git', 'clone', repo_url, temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e.stderr}")
        raise

def _summarize_repo_structure(repo_path: str) -> str:
    """Walks the repo, creates a file tree, and extracts content from high-signal files."""
    summary = "File Tree:\n"
    file_contents = "\n\nKey File Contents:\n"
    
    for root, dirs, files in os.walk(repo_path):
        # Exclude git directory from the summary
        if '.git' in dirs:
            dirs.remove('.git')

        level = root.replace(repo_path, '').count(os.sep)
        indent = ' ' * 4 * level
        summary += f"{indent}{os.path.basename(root)}/\n"
        
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            summary += f"{sub_indent}{f}\n"
            if f in HIGH_SIGNAL_FILES:
                try:
                    file_path = os.path.join(root, f)
                    with open(file_path, 'r', encoding='utf-8') as file_content:
                        content = file_content.read(2000) # Read first 2000 chars
                        file_contents += f"\n--- Content of {f} ---\n{content}\n"
                except Exception as e:
                    file_contents += f"\n--- Could not read {f}: {e} ---\n"
    
    return summary + file_contents

def analyze_codebase(repo_url: str) -> dict:
    """
    Clones a repository, summarizes its contents, and uses an LLM to analyze it.

    Args:
        repo_url: The URL of the GitHub repository.

    Returns:
        A dictionary with the code analysis.
    """
    # Create a temporary directory that will be automatically cleaned up
    with tempfile.TemporaryDirectory() as temp_dir:
        _clone_repo(repo_url, temp_dir)
        repo_summary = _summarize_repo_structure(temp_dir)

        prompt = f"""
            System: You are a senior full-stack developer. Analyze the provided code summary
            and return a JSON object. **Your output must strictly follow the JSON schema provided below.**

            JSON Schema:
            {{
              "language": "string",
              "framework": "string or null",
              "build_steps": ["string"],
              "start_command": "string",
              "exposed_port": "integer"
            }}
            
            Guidelines:
            - For 'start_command', provide the command for a production setting (e.g., use gunicorn for Flask).
            - If a 'Dockerfile' is present, it is the most reliable source of truth.
            - If no port is explicitly defined, use a conventional default (e.g., 5000 for Flask).
            
            Repository Summary:
            {repo_summary}

            Now, provide the structured JSON analysis adhering strictly to the schema.
        """

        try:
            analysis_json = invoke_llm(prompt, is_json=True)
            if not isinstance(analysis_json, dict) or "language" not in analysis_json:
                raise ValueError("LLM did not return the expected JSON structure for the analysis.")
            return analysis_json
        except Exception as e:
            print(f"Error during codebase analysis: {e}")
            raise
        finally:
            # The 'with' statement handles the cleanup
            print(f"Cleaned up temporary directory: {temp_dir}")