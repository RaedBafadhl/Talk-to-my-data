# GCP deployment

Pushes to `main` deploy to **personal**, project `talk-to-my-data-508110` in
`europe-west4`. GitHub Actions also supports a manual `target` selection:
`raed` or `personal`. Each environment has its own configuration, local
Terraform working directory, remote state bucket and deployment concurrency
group. The default deployment uses federation and does not depend on
Raed's `GCP_CREDENTIALS` secret. Raed is an optional manually selected target.

## Configuration and authentication

The single source of environment settings is
`terraform/environments/<environment>.tfvars.json`. Application SQL reads
`GCP_PROJECT_ID`; it has no hardcoded fallback to another project.

- `raed`: `GCP_CREDENTIALS` must contain credentials for
  `github-deployer@tgs-talk-to-data.iam.gserviceaccount.com`.
  Store the full JSON key content (or its base64 encoding), not the file path
  or service account email. The workflow validates its format and expected
  account without printing the credential. Secret changes require rerunning
  the failed workflow; pushing code alone does not repair a malformed key.
- `personal`: uses the existing GitHub Workload Identity Federation provider.
- Both environments use backend port 8080, frontend port 8501, minimum 1 and
  maximum 2 instances. Frontend connects to its environment's backend `/ask`.

Raed's state is temporarily hosted in the personal project, as agreed:
`gs://talk-to-my-data-508110-tfstate-raed`. Personal state uses
`gs://talk-to-my-data-508110-tfstate-personal`. Both buckets have versioning,
uniform access and public access prevention. Each deployer has Storage Object
Admin only on its own environment's bucket. State prefixes are
`application/<environment>` and `foundation/<environment>`.

## Application deployment

`terraform/` manages Artifact Registry, Cloud Run services, public invoker
memberships, image versions, environment variables and scaling. It adds IAM
members without replacing existing policies. Existing resources are imported
before planning. Registry-only targeting is used solely to create a missing
repository before the first image build; every deployment subsequently plans
and applies the entire application stack.

The pipeline refuses resource deletion or replacement, applies the saved
plan and checks both health endpoints plus a live BigQuery-backed question.
Deployment identities need registry permissions, Cloud Run permissions,
permission to act as the runtime account and access to their state bucket.
Terraform additionally needs project-level `run.operations.get` to wait for
deployment operations. The foundation grants only that permission through
the custom `cloudRunOperationReader` role; service update permissions remain
scoped to the application services in the personal environment.
Raed's existing Cloud Run Admin allows initial service creation and public
invoker configuration. Personal uses its previously created services and
resource-scoped permissions.

Local commands, with credentials for the selected project:

```sh
python scripts/deployment.py personal init
python scripts/deployment.py personal adopt --image-tag COMMIT_SHA
python scripts/deployment.py personal registry --image-tag COMMIT_SHA
# Build and push both images for COMMIT_SHA before planning service updates.
python scripts/deployment.py personal plan --image-tag COMMIT_SHA
python scripts/deployment.py personal apply --image-tag COMMIT_SHA
python scripts/deployment.py personal verify
```

## Foundation management

`terraform/foundation/` defines API enablement, service accounts, runtime and
deployer permissions, optional GitHub federation, state storage, BigQuery
dataset and table schemas. Data rows are not managed by Terraform. Existing
table data is protected against destruction; runtime reader permissions are
managed as additive table IAM members. Existing dataset/team access is
preserved, including legacy dataset-reader entries created before Terraform.

Foundation operations are separate from routine application deployment and
require a project-owner/platform identity with API, IAM, BigQuery and state
bucket management permissions. The application deployer is not given these
extra privileges. Raed's foundation cannot be adopted by the local user with
the currently granted application-only roles. The source is ready for the
project owner to adopt after the initial application deployment:

```sh
python scripts/foundation.py raed init
python scripts/foundation.py raed adopt
python scripts/foundation.py raed plan
# Review the saved plan before applying it.
python scripts/foundation.py raed apply
```

The same commands with `personal` manage the personal foundation. New environments
still require an owner to establish billing, enable initial APIs, create a
runtime/deployer identity and bootstrap the remote-state bucket before
remote Terraform initialization. Import is mandatory for existing resources.

To move Raed's state into his project later, pause deployments, create a
versioned bucket there, grant the deployer bucket-scoped Object Admin, update
`state_bucket` and `state_project_id`, then run `terraform init -migrate-state`
for both stacks using their respective existing Terraform data directories.
Do not use `-reconfigure` to migrate state; the normal deployment `init`
command deliberately only reconnects to the configured backend.

SQL helper templates are environment-independent:

```sh
python scripts/bigquery/run_sql.py personal scripts/eda_queries.sql --dry-run
```

Cloud Build image paths use `$PROJECT_ID`. Select the project explicitly if
using Cloud Build separately from GitHub Actions.
