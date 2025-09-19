# src/generator.py

from .llm_service import invoke_llm

def generate_deployment_assets(intent: dict, analysis: dict, repo_url: str) -> dict:
    """
    Generates Terraform code and a deployment script using the LLM.
    Dynamically adjusts the prompt for either AWS or GCP.
    """
    cloud_provider = intent.get("cloud_provider", "aws") # Default to aws
    
    # --- Base guidelines for the deployment script (cloud-agnostic) ---
    script_guidelines = """
    2.  **Deployment Script**:
        -   The script should be non-interactive and start with `#!/bin/bash` and `set -e`.
        -   Update system packages (`apt-get update` or `yum update`).
        -   Install dependencies like git and the language runtime (e.g., python3-pip, nodejs).
        -   Clone the application repository into a home directory (e.g., /home/ubuntu/app).
        -   Run the application's build steps (e.g., `pip install -r requirements.txt`).
        -   Set up a 'systemd' service to run the application persistently and start it.
    """

    # --- Dynamically set Terraform guidelines based on the cloud provider ---
    if cloud_provider == 'gcp':
        terraform_guidelines = """
        1.  **Terraform Code (GCP)**:
            -   Use the 'google' provider.
            -   Create a 'google_compute_instance'. For a 'small' instance, use machine type 'e2-micro'.
            -   Use an Ubuntu 22.04 LTS image (e.g., from the 'ubuntu-os-cloud' project).
            -   The 'network_interface' block MUST include an empty 'access_config {{}}' block to ensure a public IP is assigned.
            -   Create a 'google_compute_firewall' rule to allow inbound TCP traffic on the application's exposed port from the internet ('0.0.0.0/0').
            -   Include an 'output' block for the server's public IP address (`nat_ip`).
    """
    else: # Default to AWS
        terraform_guidelines = """
        1.  **Terraform Code (AWS)**:
            -   Use the 'aws' provider.
            -   Create an 'aws_instance'. For a 'small' instance, use instance type 't2.micro'.
            -   Use an Ubuntu 22.04 LTS AMI.
            -   Create an 'aws_security_group' to allow inbound traffic on the application's exposed port and SSH (port 22) from the internet ('0.0.0.0/0').
            -   Include an 'output' block for the server's 'public_ip'.
    """

    combined_context = {
        "deployment_request": intent,
        "application_analysis": analysis,
        "repository_url": repo_url
    }

    prompt = f"""
        System: You are an expert Cloud Architect. Your task is to generate a complete deployment
        plan as a single JSON object with two keys: "terraform_code" and "deployment_script".

        Deployment Guidelines:
        {terraform_guidelines}
        {script_guidelines}

        Here is the combined context:
        {combined_context}

        Now, generate the JSON output.
    """

    try:
        asset_json = invoke_llm(prompt, is_json=True)
        if not all(k in asset_json for k in ["terraform_code", "deployment_script"]):
            raise ValueError("LLM did not return the expected keys for deployment assets.")
        return asset_json
    except Exception as e:
        print(f"Error during deployment asset generation: {e}")
        raise e