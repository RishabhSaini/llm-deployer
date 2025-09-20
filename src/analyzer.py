# src/analyzer.py

import os
import subprocess
import tempfile
import shutil
from .llm_service import invoke_llm

HIGH_SIGNAL_FILES = [
    'requirements.txt', 'package.json', 'Dockerfile', 'docker-compose.yml',
    'pom.xml', 'build.gradle', 'Gemfile', 'go.mod', 'Procfile',
    'app.py', 'main.py', 'server.js', 'index.js', 'wsgi.py',
    'README.md',
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
                    # Get the relative path for context
                    relative_path = os.path.relpath(os.path.join(root, f), repo_path)
                    with open(os.path.join(root, f), 'r', encoding='utf-8') as file_content:
                        content = file_content.read(4000) 
                        file_contents += f"\n--- Content of ./{relative_path} ---\n{content}\n"
                except Exception as e:
                    file_contents += f"\n--- Could not read {f}: {e} ---\n"
    
    return summary + file_contents

def analyze_codebase(repo_url: str) -> dict:
    """
    Clones a repository, summarizes its contents, and uses an LLM to analyze it.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        _clone_repo(repo_url, temp_dir)
        repo_summary = _summarize_repo_structure(temp_dir)

        # --- FINAL, MOST EXPLICIT PROMPT ---
        prompt = f"""
            System: You are an expert software engineer. Your task is to analyze the provided code
            repository summary and return a structured JSON object.

            Your output MUST strictly follow this JSON schema:
            {{
              "language": "string",
              "framework": "string or null",
              "build_steps": ["string containing full command with correct paths"],
              "start_command": "string",
              "exposed_port": "integer"
            }}
            
            Analysis Guidelines:
            1.  **File Paths are Critical**: The repository summary shows the full path to key files
                (e.g., `./app/requirements.txt`). Your `build_steps` MUST use these correct paths.
                If a `requirements.txt` is in a subdirectory, the command must be, for example,
                `pip3 install -r app/requirements.txt`.
            2.  **README is Priority**: Read the `README.md` first for explicit instructions.
            3.  **Production Commands**: The 'start_command' must be for a production environment.
            
            Repository Summary:
            {repo_summary}

            Now, provide the structured JSON analysis, paying close attention to the file paths.
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
            print(f"Cleaned up temporary directory: {temp_dir}")