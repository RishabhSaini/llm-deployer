# LLM-Powered Cloud Deployer

An AI-driven system that automates application deployment from a natural language prompt and a GitHub repository. It analyzes code, provisions infrastructure on GCP with Terraform, and deploys the application.

---
## Features

* Deploys from natural language prompts.
* Auto-analyzes repository for stack and build steps.
* Auto-refactors frontend code to fix `localhost` URLs.
* Generates Terraform & `deploy.sh` scripts on the fly.
* Fully automates provisioning and remote script execution.

---
## Setup

1.  **Install Python packages:**
    ```
    pip install -r requirements.txt
    ```
2.  **Create `.env` file** in the project root:
    ```
    OPENROUTER_API_KEY="sk-or-..."
    ```
3.  **Install CLI tools:**
    * [Terraform](https://developer.hashicorp.com/terraform/downloads)
    * [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

4.  **Authenticate with GCP:**
    ```bash
    gcloud auth login
    gcloud config set project [YOUR_PROJECT_ID]
    ```

---
## Usage

* **To Deploy an Application:**
    ```bash
    python main.py --prompt "Deploy this python app on GCP" --repo "[https://github.com/Arvo-AI/hello_world](https://github.com/Arvo-AI/hello_world)"
    ```
* **To Destroy All Resources:**
    ```bash
    python main.py --destroy
    ```
    *(Add `--auto-approve` to either command to skip confirmation prompts.)*

---
## Dependencies & Sources

#### Python Libraries
* **python-dotenv**: ([PyPI](https://pypi.org/project/python-dotenv/)) - Loads environment variables from `.env`.
* **openai**: ([PyPI](https://pypi.org/project/openai/)) - Client for OpenRouter's OpenAI-compatible API.
* **paramiko**: ([PyPI](https://pypi.org/project/paramiko/)) - Handles the SSH connection for remote deployment.

#### Tools & Services
* **Terraform**: ([Website](https://www.terraform.io/)) - Core IaC tool for provisioning cloud resources.
* **Git**: ([Website](https://git-scm.com/)) - Clones the source repository for analysis.
* **OpenRouter**: ([Website](https://openrouter.ai/)) - LLM provider for all AI-driven analysis and generation.
* **Google Cloud Platform**: ([Website](https://cloud.google.com/)) - Target cloud for resource provisioning.
