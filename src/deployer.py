# src/deployer.py

import os
import subprocess
import json
import time
import paramiko

# --- Constants ---
WORKDIR_NAME = "deploy_workdir"
PRIVATE_KEY_FILENAME = "deploy_key.pem"
PUBLIC_KEY_FILENAME = "deploy_key.pub"
REMOTE_USERNAME = "gcp-user" # As defined in the generator prompt

def _generate_ssh_key(workdir_path: str):
    """Generates an SSH key pair in the working directory."""
    private_key_path = os.path.join(workdir_path, PRIVATE_KEY_FILENAME)
    public_key_path = os.path.join(workdir_path, PUBLIC_KEY_FILENAME)

    if not os.path.exists(private_key_path):
        print("Generating SSH key pair...")
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file(private_key_path)
        
        with open(public_key_path, "w") as f:
            # Format needed for GCP metadata is slightly different than a standard .pub file
            f.write(f"{key.get_name()} {key.get_base64()}")
        
        os.chmod(private_key_path, 0o600)
    return private_key_path, public_key_path

def _run_remote_script(hostname, username, private_key_path, local_script_path):
    """Connects to a remote server, uploads a script, and executes it."""
    print(f"\n--- 🚀 Starting remote deployment to {hostname} ---")
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Retry connection as the VM might still be booting
    for i in range(10):
        try:
            print(f"Connecting to server (attempt {i+1})...")
            ssh_client.connect(hostname=hostname, username=username, key_filename=private_key_path, timeout=20)
            print("✅ Connected to server.")
            break
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 15 seconds...")
            time.sleep(15)
    else:
        raise RuntimeError("Could not connect to the SSH server after multiple attempts.")

    try:
        # 1. Upload the script
        remote_script_path = f"/tmp/{os.path.basename(local_script_path)}"
        print(f"Uploading {local_script_path} to {remote_script_path}...")
        with ssh_client.open_sftp() as sftp:
            sftp.put(local_script_path, remote_script_path)
            sftp.chmod(remote_script_path, 0o755) # Make it executable
        print("✅ Script uploaded.")

        # 2. Execute the script
        command = f"sudo {remote_script_path}"
        print(f"Executing remote command: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command, get_pty=True)

        # 3. Stream output
        print("\n--- 📜 Remote Script Output ---")
        for line in iter(stdout.readline, ""):
            print(line, end="")
        
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print("\n--- ❌ Remote Script Errors ---")
            print(stderr.read().decode(), end="")
            raise RuntimeError(f"Remote script failed with exit code {exit_status}")

        print("\n--- ✅ Remote script executed successfully. ---")

    finally:
        ssh_client.close()
        print("SSH connection closed.")


def _run_command(command: list[str], working_dir: str, stream_output=True):
    """Runs a shell command."""
    print(f"\n> Running command: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=working_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if stream_output else subprocess.PIPE,
        text=True,
    )
    
    output = ""
    if stream_output:
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
            output += line
    
    process.wait()
    if process.returncode != 0:
        if not stream_output:
             _, stderr = process.communicate()
             print(stderr)
        raise RuntimeError(f"Command failed with exit code {process.returncode}")
    
    return process.communicate()[0] if not stream_output else output

def _get_gcp_project_id() -> str:
    """Gets the active GCP project ID from the gcloud CLI."""
    try:
        command = ['gcloud', 'config', 'get-value', 'project']
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        project_id = process.stdout.strip()
        if not project_id:
            raise ValueError("No GCP project is configured. Please run 'gcloud config set project [PROJECT_ID]'.")
        return project_id
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise RuntimeError("Failed to get GCP project ID. Is gcloud configured correctly?")

def execute_deployment(assets: dict, auto_approve: bool):
    """Fully automates infrastructure provisioning and application deployment."""
    workdir_path = os.path.abspath(WORKDIR_NAME)
    os.makedirs(workdir_path, exist_ok=True)
    
    terraform_content = assets["terraform_code"]
    if isinstance(terraform_content, dict):
        terraform_content = list(terraform_content.values())[0]

    project_id = _get_gcp_project_id()
    placeholders = ["YOUR_GCP_PROJECT_ID", "YOUR_GOOGLE_PROJECT_ID"]
    for placeholder in placeholders:
        terraform_content = terraform_content.replace(placeholder, project_id)

    tf_file_path = os.path.join(workdir_path, "main.tf")
    script_file_path = os.path.join(workdir_path, "deploy.sh")
    with open(tf_file_path, "w") as f: f.write(terraform_content)
    with open(script_file_path, "w") as f: f.write(assets["deployment_script"])
    print("Terraform and deployment script files saved.")

    private_key_path, public_key_path = _generate_ssh_key(workdir_path)
    with open(public_key_path, 'r') as f: public_key_content = f.read().strip()
    
    _run_command(['terraform', 'init', '-input=false'], workdir_path)
    
    apply_command = [
        'terraform', 'apply', 
        f'-var=ssh_public_key={public_key_content}', 
    ]
    if auto_approve:
        apply_command.append('-auto-approve')

    _run_command(apply_command, workdir_path)
    print("\n✅ Terraform apply complete.")

    print("Fetching server IP from Terraform output...")
    output_json = _run_command(['terraform', 'output', '-json'], workdir_path, stream_output=False)
    server_ip = json.loads(output_json)['nat_ip']['value']
    print(f"✅ Server IP found: {server_ip}")

    _run_remote_script(server_ip, REMOTE_USERNAME, private_key_path, script_file_path)
    
    # Extract the port from the analysis to display in the final URL
    try:
        port = assets['analysis']['exposed_port']
    except KeyError:
        port = 80 # Default to 80 if not found
    print(f"\n🎉 Fully automated deployment complete! Your app should be accessible at http://{server_ip}:{port}")


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
        _run_command(['terraform', 'init', '-input=false'], workdir_path)
        _run_command(destroy_command, workdir_path)
        print("\n✅ De-provisioning complete.")
    except Exception as e:
        print(f"\n❌ An error occurred during de-provisioning: {e}")