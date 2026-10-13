"""Deploy either GCP environment using isolated, locked Terraform state."""

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "terraform"
ENVIRONMENTS = ("raed", "personal")


def load_environment(name):
    if name not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {name}")
    config = json.loads((TERRAFORM / "environments" / f"{name}.tfvars.json").read_text())
    project = config["project_id"]
    for key in ("backend_runtime_service_account", "deployer_service_account"):
        if not config[key].endswith(f"@{project}.iam.gserviceaccount.com"):
            raise ValueError(f"{key} belongs to a different project")
    if not 0 <= config["min_instances"] <= config["max_instances"]:
        raise ValueError("Invalid instance limits")
    return config


def reject_deletions(plan):
    deleted = [item["address"] for item in plan.get("resource_changes", [])
               if "delete" in item["change"]["actions"]]
    if deleted:
        raise RuntimeError("Deployment refuses deletion/replacement: " + ", ".join(deleted))


def validate_credentials(raw, expected_account):
    try:
        credentials = json.loads(raw)
    except ValueError:
        try:
            credentials = json.loads(base64.b64decode(raw, validate=True))
        except (ValueError, UnicodeDecodeError):
            raise ValueError("GCP_CREDENTIALS must contain the service account JSON key, not a file path or account email") from None
    if not isinstance(credentials, dict) or credentials.get("type") != "service_account":
        raise ValueError("GCP_CREDENTIALS is not a service account key")
    if credentials.get("client_email") != expected_account:
        raise ValueError(f"GCP_CREDENTIALS must belong to {expected_account}")
    if not credentials.get("private_key", "").startswith("-----BEGIN PRIVATE KEY-----"):
        raise ValueError("GCP_CREDENTIALS has no valid private_key field")


class Deployment:
    def __init__(self, name, image_tag):
        self.name = name
        self.config = load_environment(name)
        self.env = os.environ.copy()
        self.env["TF_DATA_DIR"] = str(TERRAFORM / ".terraform-data" / name)
        self.env["TF_IN_AUTOMATION"] = "true"
        image_base = (f'{self.config["region"]}-docker.pkg.dev/'
                      f'{self.config["project_id"]}/{self.config["artifact_repo_name"]}')
        self.images = {"backend_image": f"{image_base}/backend:{image_tag}",
                       "frontend_image": f"{image_base}/frontend:{image_tag}"}
        for key, value in self.images.items():
            self.env[f"TF_VAR_{key}"] = value
        self.var_file = TERRAFORM / "environments" / f"{name}.tfvars.json"
        self.plan_file = TERRAFORM / f"{name}.tfplan"

    def run(self, args, capture=False):
        try:
            result = subprocess.run(args, cwd=ROOT, env=self.env, check=True,
                                    text=True, capture_output=capture)
        except subprocess.CalledProcessError as error:
            if capture and error.stderr:
                print(error.stderr, file=sys.stderr)
            raise
        return result.stdout if capture else ""

    def validate_credentials(self):
        validate_credentials(os.getenv("GCP_CREDENTIALS", ""), self.config["deployer_service_account"])
        print("Deployment credential format and account verified")

    def tf(self, *args, capture=False, variables=False):
        command = ["terraform", f"-chdir={TERRAFORM}", *args]
        if variables:
            command.append(f"-var-file={self.var_file}")
        return self.run(command, capture)

    def init(self):
        self.tf("init", "-input=false", "-reconfigure",
                f'-backend-config=bucket={self.config["state_bucket"]}',
                f"-backend-config=prefix=application/{self.name}")
        self.tf("validate")

    def adopt(self):
        existing = set(self.tf("state", "list", capture=True).splitlines())
        project, region = self.config["project_id"], self.config["region"]
        registry_id = f'projects/{project}/locations/{region}/repositories/{self.config["artifact_repo_name"]}'
        resources = []
        registry_address = "google_artifact_registry_repository.docker_repo"
        if registry_address not in existing:
            repository = self.describe_if_exists([
                "gcloud", "artifacts", "repositories", "describe", self.config["artifact_repo_name"],
                f"--project={project}", f"--location={region}", "--format=json"])
            if repository:
                resources.append((registry_address, registry_id))
        for component in ("backend", "frontend"):
            service = f"talk-to-my-data-{component}"
            service_address = f"google_cloud_run_v2_service.{component}"
            public_address = f'google_cloud_run_v2_service_iam_member.public["{component}"]'
            resource_id = f"projects/{project}/locations/{region}/services/{service}"
            if service_address not in existing:
                resource = self.describe_if_exists([
                    "gcloud", "run", "services", "describe", service,
                    f"--project={project}", f"--region={region}", "--format=json"])
                if not resource:
                    continue
                resources.append((service_address, resource_id))
            if public_address in existing:
                continue
            policy = json.loads(self.run([
                "gcloud", "run", "services", "get-iam-policy", service,
                f"--project={project}", f"--region={region}", "--format=json"], capture=True))
            if any(binding["role"] == "roles/run.invoker" and "allUsers" in binding["members"]
                   and not binding.get("condition") for binding in policy.get("bindings", [])):
                resources.append((public_address,
                                  f"{resource_id} roles/run.invoker allUsers"))
        for address, resource_id in resources:
            if address not in existing:
                self.tf("import", "-input=false", f"-var-file={self.var_file}",
                        address, resource_id)

    def describe_if_exists(self, command):
        try:
            return json.loads(self.run(command, capture=True))
        except subprocess.CalledProcessError as error:
            message = error.stderr or ""
            if "NOT_FOUND" in message or "Cannot find service" in message:
                return None
            raise

    def plan(self, registry_only=False):
        args = ["plan", "-input=false", "-lock-timeout=120s", f"-out={self.plan_file}"]
        if registry_only:
            args.append("-target=google_artifact_registry_repository.docker_repo")
        self.tf(*args, variables=True)
        reject_deletions(json.loads(self.tf("show", "-json", str(self.plan_file), capture=True)))

    def apply(self):
        reject_deletions(json.loads(self.tf("show", "-json", str(self.plan_file), capture=True)))
        self.tf("apply", "-input=false", "-lock-timeout=120s", str(self.plan_file))

    def registry(self):
        if "google_artifact_registry_repository.docker_repo" not in self.tf("state", "list", capture=True).splitlines():
            # A first deployment needs the registry before its images can be built.
            self.plan(registry_only=True)
            self.apply()

    def verify(self):
        outputs = json.loads(self.tf("output", "-json", capture=True))
        backend, frontend = outputs["backend_url"]["value"], outputs["frontend_url"]["value"]
        for url in (backend + "/health", frontend + "/_stcore/health"):
            with urllib.request.urlopen(url, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError(f"Health check failed: {url}")
        request = urllib.request.Request(backend + "/ask", method="POST",
                                        data=json.dumps({"question": "How many stores are there?"}).encode(),
                                        headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        if result.get("status") != "ok" or f'{self.config["project_id"]}.retail_dw.' not in (result.get("sql") or ""):
            raise RuntimeError(f"Live data check failed: {result}")
        print(f"Frontend: {frontend}\nBackend: {backend}\nLive data: {result['table']}")
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as handle:
                handle.write(f"### {self.name} deployment\n\n[Open application]({frontend})\n\n"
                             f"Project: `{self.config['project_id']}`. Health and live data checks passed.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=ENVIRONMENTS)
    parser.add_argument("command", choices=("configure", "validate-credentials", "init", "adopt", "registry", "plan", "apply", "verify"))
    parser.add_argument("--image-tag", default=os.getenv("GITHUB_SHA", "latest"))
    args = parser.parse_args()
    deployment = Deployment(args.environment, args.image_tag)
    if args.command == "configure":
        values = {**deployment.config, **deployment.images, "environment": args.environment}
        output = os.getenv("GITHUB_OUTPUT")
        if output:
            with open(output, "a") as handle:
                for key, value in values.items():
                    handle.write(f"{key}={value}\n")
        else:
            print(json.dumps(values, indent=2))
    else:
        getattr(deployment, args.command.replace("-", "_"))()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
