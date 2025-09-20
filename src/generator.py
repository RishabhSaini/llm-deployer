# src/generator.py

from .llm_service import invoke_llm

def generate_deployment_assets(intent: dict, analysis: dict, repo_url: str) -> dict:
    """
    Generates Terraform code and a deployment script using the LLM.
    Dynamically adjusts the prompt for either AWS or GCP.
    """
    cloud_provider = intent.get("cloud_provider", "aws")
    
    # --- FINAL, MOST ROBUST SCRIPT GUIDELINES ---
    script_guidelines = f"""
    2.  **Deployment Script**:
        -   The script must be non-interactive and start with `#!/bin/bash` followed by `set -euxo pipefail`.
        -   **Shell Scripting Rules**: Do NOT use `sudo` for shell built-in commands like `cd`. Change directory with `cd /path/to/dir`.
        -   Run `sudo apt-get update -y` and then `sudo apt-get install -y git python3-pip`.
        -   Handle code deployment in `/opt/app`: If `/opt/app/.git` exists, `cd /opt/app` and run `sudo git pull`. Otherwise, `sudo git clone {repo_url} /opt/app`.
        -   **Dynamically find the application directory**: `APP_DIR=$(find /opt/app -name requirements.txt -printf '%h' | head -n 1)`.
        -   `cd "$APP_DIR"`.
        -   Run `sudo pip3 install -r requirements.txt` from within `$APP_DIR`.
        -   **Systemd Service Rules**:
            -   Create a systemd service file.
            -   The service's `WorkingDirectory` MUST be `$APP_DIR`.
            -   The `ExecStart` MUST be the direct command to run the app, using the full path to the executable (e.g., `/usr/local/bin/gunicorn`). It MUST NOT contain `cd`. The start command is: `{analysis['start_command']}`.
            -   The service must be reloaded, enabled, and restarted.
    """

    if cloud_provider == 'gcp':
        region = intent.get('region', 'us-central1')
        zone = f"{region}-a"
        port = analysis.get('exposed_port', 80)
        
        terraform_guidelines = f"""
        1.  **Terraform Code (GCP)**:
            -   Start with a `provider "google"` block setting `project` to `YOUR_GCP_PROJECT_ID` and `region` to `{region}`.
            -   Define a `ssh_public_key` variable.
            -   Create a `google_compute_instance` using `e2-micro` in the `{zone}` zone. It MUST include `allow_stopping_for_update = true`. Use an Ubuntu 22.04 LTS image.
            -   Add `metadata` with `ssh-keys` set to `gcp-user:${{var.ssh_public_key}}`.
            -   The `network_interface` must include `network = "default"` and an empty `access_config {{}}`.
            -   Create a `google_compute_firewall` rule named 'allow-app-port-{port}' that allows TCP traffic on port `{port}` from `source_ranges = [\"0.0.0.0/0\"]`.
            -   Include an `output` for the server's public `nat_ip`.
    """
    else: # Default to AWS
        # (AWS guidelines would be similarly constrained)
        region = intent.get('region', 'us-east-1')
        terraform_guidelines = f"""...""" # (Same as before)

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