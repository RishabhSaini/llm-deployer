# main.py

import argparse
import sys
from src.parser import parse_intent
from src.analyzer import analyze_codebase
from src.generator import generate_deployment_assets
from src.deployer import execute_deployment, destroy_resources # Import the new function

def main():
    """The main entrypoint for the LLM Deployer CLI."""
    cli_parser = argparse.ArgumentParser(description="Automated application deployment using an LLM.")
    
    # Deployment arguments
    cli_parser.add_argument("--prompt", type=str, help="Natural language description of deployment requirements.")
    cli_parser.add_argument("--repo", type=str, help="URL to the GitHub repository of the application.")
    
    # Action flags
    cli_parser.add_argument("--destroy", action="store_true", help="Destroy all provisioned resources.")
    cli_parser.add_argument("--auto-approve", action="store_true", help="Automatically approve Terraform actions without a prompt.")

    args = cli_parser.parse_args()

    # --- ACTION ROUTING ---
    if args.destroy:
        destroy_resources(args.auto_approve)
        sys.exit(0)

    # --- DEPLOYMENT FLOW ---
    if not args.prompt or not args.repo:
        cli_parser.error("--prompt and --repo are required for deployment.")
        sys.exit(1)

    print("🚀 Starting LLM-Powered Deployment Process...")
    try:
        # Stage 1: Parse the user's intent
        print("\n--- 📝 Stage 1: Parsing User Intent ---")
        intent = parse_intent(args.prompt)
        print("✅ Intent Parsed Successfully:", intent)

        # Stage 2: Analyze the code repository
        print("\n--- 🔍 Stage 2: Analyzing Code Repository ---")
        analysis = analyze_codebase(args.repo)
        print("✅ Code Analysis Complete:", analysis)

        # Stage 3: Generate Deployment Assets
        print("\n--- 🛠️ Stage 3: Generating Deployment Assets ---")
        deployment_assets = generate_deployment_assets(intent, analysis, args.repo)
        print("✅ Deployment Assets Generated Successfully.")

        # Stage 4: Provision and Deploy
        print("\n--- ☁️ Stage 4: Provisioning and Deploying ---")
        execute_deployment(deployment_assets, args.auto_approve)
        
    except Exception as e:
        print(f"\n❌ An error occurred during the deployment process: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()