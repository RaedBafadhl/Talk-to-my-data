"""
Run this after setting up your .env file to confirm your local environment
is correctly linked to the shared GCP project.

Usage:
    python scripts/verify_setup.py

If it prints your project ID and a list of datasets (even an empty list),
everything is linked correctly. If it errors, read the error message —
it will tell you exactly which link is broken (auth, project ID, or API
not enabled).
"""

import os
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")

if not project_id or project_id == "your-project-id-here":
    print("❌ GCP_PROJECT_ID is not set. Copy .env.example to .env and fill in the real project ID.")
    exit(1)

print(f"Connecting to project: {project_id}")

try:
    client = bigquery.Client(project=project_id)
    datasets = list(client.list_datasets())
    print(f"✅ Connected successfully. Found {len(datasets)} dataset(s) in this project.")
    if datasets:
        for d in datasets:
            print(f"   - {d.dataset_id}")
    else:
        print("   (No datasets yet — that's expected before Pillar 1 loads real data.)")
except Exception as e:
    print("❌ Connection failed. Common causes:")
    print("   1. You haven't run: gcloud auth application-default login")
    print("   2. You haven't been added to the project's IAM yet — ask Raed")
    print("   3. The BigQuery API isn't enabled on this project")
    print(f"\nActual error: {e}")
