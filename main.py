# main.py

import argparse
import sys
import tempfile
import shutil
from src.parser import parse_intent
from src.analyzer import analyze_codebase
from src.generator import generate_deployment_assets
from src.deployer import execute_deployment, destroy_resources

def main():
    """The main entrypoint for the LLM Deployer CLI."""
    cli_parser = argparse.ArgumentParser(description="Automated application deployment using an LLM.")
    
    cli_parser.add_argument("--prompt", type=str, help="Natural language description of deployment requirements.")
    cli_parser.add_argument("--repo", type=str, help="URL to the GitHub repository of the application.")
    cli_parser.add_argument("--destroy", action="store_true", help="Destroy all provisioned resources.")
    cli_parser.add_argument("--auto-approve", action="store_true", help="Automatically approve Terraform actions.")

    args = cli_parser.parse_args()

    if args.destroy:
        destroy_resources(args.auto_approve)
        sys.exit(0)

    if not args.prompt or not args.repo:
        cli_parser.error("--prompt and --repo are required for deployment.")
        sys.exit(1)
        
    # Create a single temporary directory for the entire operation
    temp_code_dir = tempfile.mkdtemp()
    print(f"Created temporary workspace at: {temp_code_dir}")

    try:
        print("🚀 Starting LLM-Powered Deployment Process...")
        
        # Stage 1: Parse Intent
        print("\n--- 📝 Stage 1: Parsing User Intent ---")
        intent = parse_intent(args.prompt)
        print("✅ Intent Parsed Successfully:", intent)

        # Stage 2: Analyze & Refactor Code (in the shared workspace)
        print("\n--- 🔍 Stage 2: Analyzing & Refactoring Code Repository ---")
        analysis = analyze_codebase(args.repo, temp_code_dir)
        print("✅ Code Analysis Complete:", analysis)

        # Stage 3: Generate Deployment Assets
        print("\n--- 🛠️ Stage 3: Generating Deployment Assets ---")
        deployment_assets = generate_deployment_assets(intent, analysis)
        print("✅ Deployment Assets Generated Successfully.")

        # Stage 4: Provision and Deploy (using the refactored code from the workspace)
        print("\n--- ☁️ Stage 4: Provisioning and Deploying ---")
        execute_deployment(deployment_assets, args.auto_approve, temp_code_dir)
        
    except Exception as e:
        print(f"\n❌ An error occurred during the deployment process: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up the temporary directory
        print(f"Cleaning up temporary workspace: {temp_code_dir}")
        shutil.rmtree(temp_code_dir)

if __name__ == "__main__":
    main()