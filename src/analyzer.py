# src/analyzer.py

import os
import re # Import the regular expression module
import subprocess
import tempfile
from .llm_service import invoke_llm

HIGH_SIGNAL_FILES = [
    'requirements.txt', 'package.json', 'Dockerfile', 'README.md',
    'app.py', 'main.py', 'server.js', 'index.js',
]
FRONTEND_FILE_EXTS = ('.html', '.js', '.jsx', '.tsx', '.vue')

def _clone_repo(repo_url: str, temp_dir: str):
    """Clones a git repository into a temporary directory."""
    try:
        print(f"Cloning repository: {repo_url}...")
        subprocess.run(['git', 'clone', repo_url, temp_dir], check=True, capture_output=True, text=True)
        print("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e.stderr}")
        raise

def _refactor_frontend_code_with_regex(repo_path: str):
    """Finds frontend files and uses regex to replace localhost URLs."""
    print("\n--- ⚙️ Starting deterministic frontend refactoring ---")
    # This simpler regex just finds and removes the http://localhost:port part.
    localhost_regex = re.compile(r'https?://(?:localhost|127\.0\.0\.1):\d+')

    for root, _, files in os.walk(repo_path):
        if '.git' in root:
            continue
        for file in files:
            if file.endswith(FRONTEND_FILE_EXTS):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r+', encoding='utf-8') as f:
                        original_content = f.read()
                        
                        # Replace the matched localhost URL with an empty string, leaving just the relative path.
                        refactored_content, num_replacements = localhost_regex.subn('', original_content)
                        
                        if num_replacements > 0:
                            print(f"Found and replaced {num_replacements} localhost URL(s) in {file_path}")
                            f.seek(0)
                            f.write(refactored_content)
                            f.truncate()

                except Exception as e:
                    print(f"Could not refactor file {file_path}: {e}")
    print("--- ✅ Frontend refactoring finished ---")


def _summarize_repo_structure(repo_path: str) -> str:
    """Walks the repo, creates a file tree, and extracts content from high-signal files."""
    summary = "File Tree:\n"
    file_contents = "\n\nKey File Contents:\n"
    
    for root, dirs, files in os.walk(repo_path):
        if '.git' in dirs: continue
        level = root.replace(repo_path, '').count(os.sep)
        indent = ' ' * 4 * level
        summary += f"{indent}{os.path.basename(root)}/\n"
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            summary += f"{sub_indent}{f}\n"
            if f in HIGH_SIGNAL_FILES:
                try:
                    relative_path = os.path.relpath(os.path.join(root, f), repo_path)
                    with open(os.path.join(root, f), 'r', encoding='utf-8') as file_content:
                        content = file_content.read(4000) 
                        file_contents += f"\n--- Content of ./{relative_path} ---\n{content}\n"
                except Exception as e:
                    file_contents += f"\n--- Could not read {f}: {e} ---\n"
    
    return summary + file_contents

def analyze_codebase(repo_url: str, temp_dir: str) -> dict:
    """
    Clones, refactors, and analyzes a repository.
    """
    _clone_repo(repo_url, temp_dir)
    _refactor_frontend_code_with_regex(temp_dir)
    repo_summary = _summarize_repo_structure(temp_dir)

    prompt = f"""
        System: You are an expert software engineer. Analyze the provided code summary and return a JSON object.
        Your output MUST strictly follow this JSON schema:
        {{
          "language": "string", "framework": "string or null", "build_steps": ["string"],
          "start_command": "string", "exposed_port": "integer"
        }}
        Analysis Guidelines:
        1. File Paths are Critical: Your `build_steps` MUST use correct relative paths (e.g., `pip3 install -r app/requirements.txt`).
        2. README is Priority: Use `README.md` for instructions if available.
        3. Production Commands: The 'start_command' must be for production (e.g., gunicorn).
        
        Repository Summary:
        {repo_summary}
    """

    try:
        analysis_json = invoke_llm(prompt, is_json=True)
        if not isinstance(analysis_json, dict) or "language" not in analysis_json:
            raise ValueError("LLM did not return the expected JSON structure for the analysis.")
        return analysis_json
    except Exception as e:
        print(f"Error during codebase analysis: {e}")
        raise