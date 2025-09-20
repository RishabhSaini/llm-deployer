# src/deployer.py

import os
import subprocess
import json
import time
import paramiko
import tarfile

WORKDIR_NAME = "deploy_workdir"
PRIVATE_KEY_FILENAME = "deploy_key.pem"
PUBLIC_KEY_FILENAME = "deploy_key.pub"
REMOTE_USERNAME = "gcp-user"

def _generate_ssh_key(workdir_path: str):
    private_key_path = os.path.join(workdir_path, PRIVATE_KEY_FILENAME)
    public_key_path = os.path.join(workdir_path, PUBLIC_KEY_FILENAME)
    if not os.path.exists(private_key_path):
        print("Generating SSH key pair...")
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file(private_key_path)
        with open(public_key_path, "w") as f:
            f.write(f"{key.get_name()} {key.get_base64()}")
        os.chmod(private_key_path, 0o600)
    return private_key_path, public_key_path

def _upload_assets(ssh_client, workdir_path, local_refactored_path):
    """Creates a tarball of the app code and uploads it with the deploy script."""
    with ssh_client.open_sftp() as sftp:
        local_script_path = os.path.join(workdir_path, "deploy.sh")
        remote_script_path = "/tmp/deploy.sh"
        print(f"Uploading {local_script_path} to {remote_script_path}...")
        sftp.put(local_script_path, remote_script_path)
        sftp.chmod(remote_script_path, 0o755)
        print("✅ Deploy script uploaded.")

        local_tar_path = os.path.join(workdir_path, "app.tar.gz")
        remote_tar_path = "/tmp/app.tar.gz"
        print(f"Creating application archive: {local_tar_path}...")
        with tarfile.open(local_tar_path, "w:gz") as tar:
            tar.add(local_refactored_path, arcname='.')
        print(f"Uploading application archive to {remote_tar_path}...")
        sftp.put(local_tar_path, remote_tar_path)
        print("✅ Application archive uploaded.")

def _run_remote_deployment(hostname, username, private_key_path, workdir_path, local_refactored_path):
    """Connects, uploads assets, and executes the deploy script."""
    print(f"\n--- 🚀 Starting remote deployment to {hostname} ---")
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
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
        _upload_assets(ssh_client, workdir_path, local_refactored_path)
        command = "sudo /tmp/deploy.sh"
        print(f"Executing remote command: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command, get_pty=True)

        print("\n--- 📜 Remote Script Output ---")
        for line in iter(stdout.readline, ""):
            print(line, end="")
        
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print("\n--- ❌ Remote Script Errors ---")
            error_output = stderr.read().decode()
            if error_output: print(error_output, end="")
            raise RuntimeError(f"Remote script failed with exit code {exit_status}")
        print("\n--- ✅ Remote script executed successfully. ---")
    finally:
        ssh_client.close()
        print("SSH connection closed.")

def _run_command(command: list[str], working_dir: str, stream_output=True):
    print(f"\n> Running command: {' '.join(command)}")
    process = subprocess.Popen(command, cwd=working_dir, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if stream_output else subprocess.PIPE, text=True)
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
    try:
        command = ['gcloud', 'config', 'get-value', 'project']
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        project_id = process.stdout.strip()
        if not project_id:
            raise ValueError("No GCP project configured.")
        return project_id
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise RuntimeError("Failed to get GCP project ID. Is gcloud configured?")

def execute_deployment(assets: dict, auto_approve: bool, local_refactored_path: str):
    workdir_path = os.path.abspath(WORKDIR_NAME)
    os.makedirs(workdir_path, exist_ok=True)
    
    terraform_content = assets["terraform_code"]
    if isinstance(terraform_content, dict):
        terraform_content = list(terraform_content.values())[0]

    project_id = _get_gcp_project_id()
    placeholders = ["YOUR_GCP_PROJECT_ID", "YOUR_GOOGLE_PROJECT_ID"]
    for placeholder in placeholders:
        terraform_content = terraform_content.replace(placeholder, project_id)

    with open(os.path.join(workdir_path, "main.tf"), "w") as f: f.write(terraform_content)
    with open(os.path.join(workdir_path, "deploy.sh"), "w") as f: f.write(assets["deployment_script"])
    print("Terraform and deployment script files saved.")

    private_key_path, public_key_path = _generate_ssh_key(workdir_path)
    with open(public_key_path, 'r') as f: public_key_content = f.read().strip()
    
    _run_command(['terraform', 'init', '-input=false'], workdir_path)
    
    apply_command = ['terraform', 'apply', f'-var=ssh_public_key={public_key_content}']
    if auto_approve: apply_command.append('-auto-approve')

    _run_command(apply_command, workdir_path)
    print("\n✅ Terraform apply complete.")

    print("Fetching server IP from Terraform output...")
    output_json = _run_command(['terraform', 'output', '-json'], workdir_path, stream_output=False)
    server_ip = json.loads(output_json)['nat_ip']['value']
    print(f"✅ Server IP found: {server_ip}")

    _run_remote_deployment(server_ip, REMOTE_USERNAME, private_key_path, workdir_path, local_refactored_path)
    
    port = assets['analysis'].get('exposed_port', 80)
    print(f"\n🎉 Fully automated deployment complete! Your app should be accessible at http://{server_ip}:{port}")

def destroy_resources(auto_approve: bool):
    workdir_path = os.path.abspath(WORKDIR_NAME)
    if not os.path.exists(workdir_path):
        print("Working directory not found. Nothing to destroy.")
        return
    print(f"--- ոչ Destroying all resources in {workdir_path} ---")
    destroy_command = ['terraform', 'destroy']
    if auto_approve: destroy_command.append('-auto-approve')
    try:
        _run_command(['terraform', 'init', '-input=false'], workdir_path)
        _run_command(destroy_command, workdir_path)
        print("\n✅ De-provisioning complete.")
    except Exception as e:
        print(f"\n❌ An error occurred during de-provisioning: {e}")