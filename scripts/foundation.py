"""Owner-operated adoption and planning for IAM, APIs, state and BigQuery."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from deployment import Deployment, ENVIRONMENTS, TERRAFORM


def has_binding(policy, role, member):
    return any(item["role"] == role and member in item.get("members", [])
               and not item.get("condition") for item in policy.get("bindings", []))


class Foundation(Deployment):
    def __init__(self, name):
        super().__init__(name, "latest")
        self.directory = TERRAFORM / "foundation"
        self.env["TF_DATA_DIR"] = str(TERRAFORM / ".terraform-data" / f"foundation-{name}")
        self.env["TF_VAR_environment"] = name
        self.plan_file = self.directory / f"{name}.tfplan"

    def tf(self, *args, capture=False, variables=False):
        return self.run(["terraform", f"-chdir={self.directory}", *args], capture)

    def init(self):
        self.tf("init", "-input=false", "-reconfigure",
                f'-backend-config=bucket={self.config["state_bucket"]}',
                f"-backend-config=prefix=foundation/{self.name}")
        self.tf("validate")

    def adopt(self):
        project, region = self.config["project_id"], self.config["region"]
        runtime, deployer = self.config["backend_runtime_service_account"], self.config["deployer_service_account"]
        member = f"serviceAccount:{deployer}"
        resources = []
        enabled = self.run(["gcloud", "services", "list", "--enabled", f"--project={project}",
                            "--format=value(config.name)"], capture=True).splitlines()
        for api in enabled:
            if api in {"run.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com",
                       "bigquery.googleapis.com", "aiplatform.googleapis.com", "iam.googleapis.com",
                       "iamcredentials.googleapis.com", "sts.googleapis.com", "storage.googleapis.com"}:
                resources.append((f'google_project_service.api["{api}"]', f"{project}/{api}"))
        accounts = json.loads(self.run(["gcloud", "iam", "service-accounts", "list", f"--project={project}",
                                       "--format=json"], capture=True))
        account_names = {item["email"] for item in accounts}
        for label, email in (("runtime", runtime), ("deployer", deployer)):
            if email in account_names:
                resources.append((f"google_service_account.{label}", f"projects/{project}/serviceAccounts/{email}"))
        bucket = self.config["state_bucket"]
        self.run(["gcloud", "storage", "buckets", "describe", f"gs://{bucket}"], capture=True)
        resources.append(("google_storage_bucket.state", bucket))
        policy = json.loads(self.run(["gcloud", "storage", "buckets", "get-iam-policy", f"gs://{bucket}",
                                      "--format=json"], capture=True))
        if has_binding(policy, "roles/storage.objectAdmin", member):
            resources.append(("google_storage_bucket_iam_member.state_writer", f"{bucket} roles/storage.objectAdmin {member}"))
        policy = json.loads(self.run(["gcloud", "projects", "get-iam-policy", project, "--format=json"], capture=True))
        for role in ("roles/bigquery.jobUser", "roles/aiplatform.user"):
            if has_binding(policy, role, f"serviceAccount:{runtime}"):
                resources.append((f'google_project_iam_member.runtime["{role}"]', f"{project} {role} serviceAccount:{runtime}"))
        if has_binding(policy, "roles/serviceusage.serviceUsageConsumer", member):
            resources.append(("google_project_iam_member.deployer_api", f"{project} roles/serviceusage.serviceUsageConsumer {member}"))
        policy = json.loads(self.run(["gcloud", "iam", "service-accounts", "get-iam-policy", runtime,
                                      f"--project={project}", "--format=json"], capture=True))
        if has_binding(policy, "roles/iam.serviceAccountUser", member):
            resources.append(("google_service_account_iam_member.act_as", f"projects/{project}/serviceAccounts/{runtime} roles/iam.serviceAccountUser {member}"))
        registry = self.config["artifact_repo_name"]
        policy = json.loads(self.run(["gcloud", "artifacts", "repositories", "get-iam-policy", registry,
                                      f"--project={project}", f"--location={region}", "--format=json"], capture=True))
        if has_binding(policy, "roles/artifactregistry.writer", member):
            resources.append(("google_artifact_registry_repository_iam_member.image_writer",
                              f"projects/{project}/locations/{region}/repositories/{registry} roles/artifactregistry.writer {member}"))
        for component in ("backend", "frontend"):
            service = f"talk-to-my-data-{component}"
            policy = json.loads(self.run(["gcloud", "run", "services", "get-iam-policy", service,
                                          f"--project={project}", f"--region={region}", "--format=json"], capture=True))
            if has_binding(policy, "roles/run.developer", member):
                resources.append((f'google_cloud_run_v2_service_iam_member.deployer["{component}"]',
                                  f"projects/{project}/locations/{region}/services/{service} roles/run.developer {member}"))
        datasets = json.loads(self.run(["bq", f"--project_id={project}", "--format=json", "ls"], capture=True))
        if any(item["datasetReference"]["datasetId"] == "retail_dw" for item in datasets):
            resources.append(("google_bigquery_dataset.retail", f"projects/{project}/datasets/retail_dw"))
            tables = json.loads(self.run(["bq", f"--project_id={project}", "--format=json", "ls", f"{project}:retail_dw"], capture=True))
            for table in tables:
                name = table["tableReference"]["tableId"]
                if name in {"sales", "products", "customers", "stores", "exchange_rates"}:
                    resources.append((f'google_bigquery_table.retail["{name}"]', f"projects/{project}/datasets/retail_dw/tables/{name}"))
                    policy = json.loads(self.run(["bq", f"--project_id={project}", "--format=json",
                                                  "get-iam-policy", f"{project}:retail_dw.{name}"], capture=True))
                    if has_binding(policy, "roles/bigquery.dataViewer", f"serviceAccount:{runtime}"):
                        resources.append((f'google_bigquery_table_iam_member.runtime_reader["{name}"]',
                                          f"projects/{project}/datasets/retail_dw/tables/{name} roles/bigquery.dataViewer serviceAccount:{runtime}"))
        if self.config["auth_mode"] == "federation":
            pool = f"projects/{project}/locations/global/workloadIdentityPools/github"
            self.run(["gcloud", "iam", "workload-identity-pools", "describe", "github",
                      f"--project={project}", "--location=global"], capture=True)
            resources.append(("google_iam_workload_identity_pool.github[0]", pool))
            resources.append(("google_iam_workload_identity_pool_provider.github[0]", pool + "/providers/talk-to-my-data"))
            number = self.run(["gcloud", "projects", "describe", project, "--format=value(projectNumber)"], capture=True).strip()
            principal = f"principalSet://iam.googleapis.com/projects/{number}/locations/global/workloadIdentityPools/github/attribute.repository_id/1351354609"
            policy = json.loads(self.run(["gcloud", "iam", "service-accounts", "get-iam-policy", deployer,
                                          f"--project={project}", "--format=json"], capture=True))
            if has_binding(policy, "roles/iam.workloadIdentityUser", principal):
                resources.append(("google_service_account_iam_member.federation[0]",
                                  f"projects/{project}/serviceAccounts/{deployer} roles/iam.workloadIdentityUser {principal}"))
        existing = set(self.tf("state", "list", capture=True).splitlines())
        for address, identifier in resources:
            if address not in existing:
                self.tf("import", "-input=false", address, identifier)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=ENVIRONMENTS)
    parser.add_argument("command", choices=("init", "adopt", "plan", "apply"))
    args = parser.parse_args()
    getattr(Foundation(args.environment), args.command)()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
