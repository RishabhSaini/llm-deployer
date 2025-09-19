# src/deployer.py

import os
import subprocess

# Define the name for our temporary working directory
WORKDIR_NAME = "deploy_workdir"

def _get_gcp_project_id() -> str:
    """Gets the active GCP project ID from the gcloud CLI."""
    try:
        print("Fetching active GCP project ID from gcloud config...")
        command = ['gcloud', 'config', 'get-value', 'project']
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        project_id = process.stdout.strip()
        if not project_id:
            raise ValueError("No GCP project is configured. Please run 'gcloud config set project [PROJECT_ID]'.")
        print(f"Found active project: {project_id}")
        return project_id
    except FileNotFoundError:
        raise FileNotFoundError("`gcloud` command not found. Is the Google Cloud SDK installed and in your PATH?")
    except subprocess.CalledProcessError:
        raise RuntimeError("Failed to get GCP project ID. Is gcloud configured correctly?")

def _run_command(command: list[str], working_dir: str):
    """Runs a shell command in a specified directory and streams its output."""
    print(f"\n> Running command: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        
        process.stdout.close()
        return_code = process.wait()
        
        if return_code:
            raise subprocess.CalledProcessError(return_code, command)

    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is Terraform installed and in your PATH?")
        raise
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(e.cmd)}. Return code: {e.returncode}")
        raise

def execute_deployment(assets: dict, auto_approve: bool):
    """
    Saves the generated assets and runs Terraform to deploy the application.
    """
    workdir_path = os.path.abspath(WORKDIR_NAME)
    os.makedirs(workdir_path, exist_ok=True)
    print(f"Created temporary working directory at: {workdir_path}")

    # --- THIS IS THE UPDATED LOGIC ---
    terraform_content = assets["terraform_code"]
    if isinstance(terraform_content, dict):
        print("Detected nested dictionary for Terraform code. Extracting content.")
        terraform_content = list(terraform_content.values())[0]

    # Get the project ID and replace any placeholders
    project_id = _get_gcp_project_id()
    placeholders = ["YOUR_GCP_PROJECT_ID", "YOUR_GOOGLE_PROJECT_ID"]
    for placeholder in placeholders:
        terraform_content = terraform_content.replace(placeholder, project_id)
    
    # Save the generated files
    tf_file_path = os.path.join(workdir_path, "main.tf")
    script_file_path = os.path.join(workdir_path, "deploy.sh")

    with open(tf_file_path, "w") as f:
        f.write(terraform_content)
    print("Terraform file 'main.tf' saved.")

    with open(script_file_path, "w") as f:
        f.write(assets["deployment_script"])
    os.chmod(script_file_path, 0o755) # Make the script executable
    print("Deployment script 'deploy.sh' saved.")
    
    # --- Execute Terraform ---
    _run_command(['terraform', 'init'], workdir_path)
    
    apply_command = ['terraform', 'apply']
    if auto_approve:
        apply_command.append('-auto-approve')
    
    _run_command(apply_command, workdir_path)
    
    print("\nTerraform apply complete. Infrastructure should be provisioned.")

    # Add this function to the end of src/deployer.py

def destroy_resources(auto_approve: bool):
    """Destroys all Terraform-managed resources in the workdir."""
    workdir_path = os.path.abspath(WORKDIR_NAME)
    if not os.path.exists(workdir_path):
        print("Working directory not found. Nothing to destroy.")
        return

    print(f"--- ոչ Destroying all resources in {workdir_path} ---")

    destroy_command = ['terraform', 'destroy']
    if auto_approve:
        destroy_command.append('-auto-approve')

    try:
        # We need to run init first to make sure providers are ready
        _run_command(['terraform', 'init', '-input=false'], workdir_path)
        _run_command(destroy_command, workdir_path)
        print("\n✅ De-provisioning complete.")
    except Exception as e:
        print(f"\n❌ An error occurred during de-provisioning: {e}")
