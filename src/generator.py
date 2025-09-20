# src/generator.py

from .llm_service import invoke_llm

def generate_deployment_assets(intent: dict, analysis: dict) -> dict:
    """
    Generates Terraform code and a deployment script that works with an uploaded archive.
    """
    cloud_provider = intent.get("cloud_provider", "aws")
    
    # --- FINAL, PRODUCTION-GRADE SCRIPT GUIDELINES ---
    script_guidelines = f"""
    2.  **Deployment Script**:
        -   The script will receive the application code in a compressed archive at `/tmp/app.tar.gz`.
        -   Start with `#!/bin/bash` followed by `set -euxo pipefail`.
        -   Clean and update apt: Run `sudo apt-get clean && sudo rm -rf /var/lib/apt/lists/* && sudo apt-get update -y`.
        -   Install required packages: `sudo apt-get install -y git python3-pip`.
        -   Create and empty the application directory `/opt/app`.
        -   Uncompress the archive with `sudo tar -xzf /tmp/app.tar.gz -C /opt/app`.
        -   Dynamically find the application directory using this exact command: `APP_DIR=$(find /opt/app -name 'requirements.txt' -printf '%h' | head -n 1)`.
        -   `cd "$APP_DIR"`.
        -   Run `sudo pip3 install -r requirements.txt` and `sudo pip3 install gunicorn`.
        -   Create and start a 'systemd' service for the app, ensuring `WorkingDirectory` is `$APP_DIR` and `ExecStart` uses `python3 -m gunicorn`.
    """

    if cloud_provider == 'gcp':
        region = intent.get('region', 'us-central1')
        zone = f"{region}-a"
        port = analysis.get('exposed_port', 80)
        terraform_guidelines = f"""
        1.  **Terraform Code (GCP)**:
            -   The code MUST begin with the `variable "ssh_public_key" {{ type = string }}` block.
            -   Next, include a `provider "google"` block setting `project` to `YOUR_GCP_PROJECT_ID` and `region` to `{region}`.
            -   Create a `google_compute_instance` using `e2-micro` in the `{zone}` zone. It MUST include `allow_stopping_for_update = true`. Use an Ubuntu 22.04 LTS image.
            -   Add `metadata` with `ssh-keys` set to `gcp-user:${{var.ssh_public_key}}`.
            -   The `network_interface` must include `network = "default"` and an empty `access_config {{}}`.
            -   Create a `google_compute_firewall` rule named 'allow-app-port-{port}' that allows TCP traffic on port `{port}` from `source_ranges = [\"0.0.0.0/0\"]`.
            -   Include an `output` for the server's public `nat_ip`.
    """
    else: # Default to AWS
        region = intent.get('region', 'us-east-1')
        terraform_guidelines = f"""..."""

    combined_context = {"deployment_request": intent, "application_analysis": analysis}
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
            raise ValueError("LLM did not return the expected keys.")
        asset_json['analysis'] = analysis 
        return asset_json
    except Exception as e:
        print(f"Error during deployment asset generation: {e}")
        raise e