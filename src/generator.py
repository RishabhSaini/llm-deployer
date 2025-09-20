# src/generator.py

from .llm_service import invoke_llm

def generate_deployment_assets(intent: dict, analysis: dict, repo_url: str) -> dict:
    """
    Generates Terraform code and a deployment script using the LLM.
    Dynamically adjusts the prompt for either AWS or GCP.
    """
    cloud_provider = intent.get("cloud_provider", "aws")
    
    # --- UPDATED SCRIPT GUIDELINES ---
    script_guidelines = f"""
    2.  **Deployment Script**:
        -   The script must be non-interactive and start with `#!/bin/bash` followed by `set -euxo pipefail`.
        -   It must be runnable with `sudo` privileges.
        -   First, run `apt-get update`. Then, install the required packages: `git` and `python3-pip`.
        -   Create a directory at `/opt/app` if it doesn't exist.
        -   Handle code updates: Check if `/opt/app/.git` exists. If so, `cd` into `/opt/app`, run `git reset --hard`, and `git pull`. Otherwise, `git clone {repo_url}` into `/opt/app`.
        -   Ensure all subsequent commands are run from within the `/opt/app` directory.
        -   Run the application's build steps using `pip3 install -r requirements.txt`.
        -   Set up a 'systemd' service to run the application. The service's `WorkingDirectory` must be `/opt/app`. Restart the service to apply changes.
    """

    if cloud_provider == 'gcp':
        region = intent.get('region', 'us-central1')
        zone = f"{region}-a"
        
        terraform_guidelines = f"""
        1.  **Terraform Code (GCP)**:
            -   The code MUST start with a `provider "google"` block setting the `project` to `YOUR_GCP_PROJECT_ID` and `region` to `{region}`.
            -   Define a `ssh_public_key` variable.
            -   Create a `google_compute_instance`. For 'small', use `e2-micro`. It MUST be in the `{zone}` zone. Use an Ubuntu 22.04 LTS image.
            -   Add a `metadata` block to the instance with `ssh-keys` set to `gcp-user:${{var.ssh_public_key}}`.
            -   The `network_interface` block MUST include `network = "default"` and an empty `access_config {{}}` block.
            -   Create a `google_compute_firewall` rule with `source_ranges = [\"0.0.0.0/0\"]` to allow inbound traffic on the app's port.
            -   Include an `output` block for the server's public `nat_ip`.
    """
    else: # Default to AWS
        region = intent.get('region', 'us-east-1')
        terraform_guidelines = f"""
        1.  **Terraform Code (AWS)**:
            -   The code MUST start with a `provider "aws"` block that uses the `region` '{region}'.
            -   Define a `ssh_public_key` variable.
            -   Create an `aws_key_pair` resource using the `ssh_public_key` variable.
            -   Create an `aws_instance`. For 'small', use `t2-micro`. Use an Ubuntu 22.04 LTS AMI and associate the `aws_key_pair` with it.
            -   Create an `aws_security_group` for the app's exposed port and SSH.
            -   Include an `output` block for the server's `public_ip`.
    """

    combined_context = {
        "deployment_request": intent,
        "application_analysis": analysis
    }

    prompt = f"""
        System: You are an expert Cloud Architect. Generate a complete deployment
        plan as a single JSON object with two keys: "terraform_code" and "deployment_script".

        Deployment Guidelines:
        {terraform_guidelines}
        {script_guidelines}

        Here is the combined context: {combined_context}
        Now, generate the JSON output.
    """

    try:
        asset_json = invoke_llm(prompt, is_json=True)
        if not all(k in asset_json for k in ["terraform_code", "deployment_script"]):
            raise ValueError("LLM did not return the expected keys for deployment assets.")
        asset_json['analysis'] = analysis 
        return asset_json
    except Exception as e:
        print(f"Error during deployment asset generation: {e}")
        raise e