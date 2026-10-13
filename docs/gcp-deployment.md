# GCP deployment

The application runs in `talk-to-my-data-508110`, owned by
`muhammeddulger01@gmail.com`, in `europe-west4`.

- Backend: `talk-to-my-data-backend`, port 8080.
- Frontend: `talk-to-my-data-frontend`, port 8501.
- Both services use minimum 1 and maximum 2 instances.
- Runtime account: `talk-to-my-data-backend@talk-to-my-data-508110.iam.gserviceaccount.com`.
- BigQuery dataset: `talk-to-my-data-508110.retail_dw`.
- Artifact Registry: `europe-west4-docker.pkg.dev/talk-to-my-data-508110/talk-to-my-data-repo`.

GitHub Actions deploys pushes to `main` using Workload Identity Federation,
with no JSON service account key or `GCP_CREDENTIALS` secret required.
The provider is restricted to repository ID `1351354609`, owner ID `259883354`,
and `refs/heads/main`.

The deployer account is `github-deployer@talk-to-my-data-508110.iam.gserviceaccount.com`.
It has Cloud Run Developer on the two application services, Artifact Registry
Writer on the application repository, Service Account User on the runtime
account, and Service Usage Consumer on the project. Initial creation of the
repository, services, and their public invoker policies is performed by the
project owner; the workflow updates existing resources.

The runtime account has BigQuery Job User and Vertex AI User on the project,
and reader access on the `retail_dw` dataset. Frontend `BACKEND_API_URL` is set
from the deployed backend URL with `/ask` appended.

Cloud Build configuration uses `$PROJECT_ID` for image paths. Submit builds
with an explicit `--project=talk-to-my-data-508110`.

Existing Terraform resources created outside Terraform must be imported into
the correct state before applying Terraform. Do not apply old state against a
different GCP project.
