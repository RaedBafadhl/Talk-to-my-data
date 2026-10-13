import base64
import json

import pytest

from scripts.deployment import Deployment, load_environment, reject_deletions, validate_credentials
from src.llm.schema_context import build_system_prompt, get_project_id


def test_environments_have_isolated_state_and_images():
    raed = Deployment("raed", "test-commit")
    personal = Deployment("personal", "test-commit")
    assert raed.config["state_bucket"] != personal.config["state_bucket"]
    assert raed.env["TF_DATA_DIR"] != personal.env["TF_DATA_DIR"]
    assert "/tgs-talk-to-data/" in raed.images["backend_image"]
    assert "/talk-to-my-data-508110/" in personal.images["backend_image"]


def test_unknown_environment_is_rejected():
    with pytest.raises(ValueError):
        load_environment("../personal")


@pytest.mark.parametrize("actions", [["delete"], ["delete", "create"], ["create", "delete"]])
def test_plans_cannot_delete_or_replace_resources(actions):
    with pytest.raises(RuntimeError, match="backend"):
        reject_deletions({"resource_changes": [{"address": "backend", "change": {"actions": actions}}]})


def test_create_and_update_plans_are_allowed():
    reject_deletions({"resource_changes": [{"address": "backend", "change": {"actions": ["update"]}}]})


@pytest.mark.parametrize("project", ["tgs-talk-to-data", "talk-to-my-data-508110"])
def test_sql_prompt_uses_selected_project(monkeypatch, project):
    monkeypatch.setenv("GCP_PROJECT_ID", project)
    assert f"{project}.retail_dw.sales" in build_system_prompt("count sales units")


def test_missing_project_fails_instead_of_querying_another_account(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        get_project_id()


def test_bad_secret_is_rejected_without_echoing_its_contents():
    secret = "/private/sensitive-key-path.json"
    with pytest.raises(ValueError) as error:
        validate_credentials(secret, "deployer@example.com")
    assert secret not in str(error.value)


@pytest.mark.parametrize("encoded", [False, True])
def test_service_account_key_can_be_json_or_base64(encoded):
    value = json.dumps({"type": "service_account", "client_email": "deployer@example.com",
                        "private_key": "-----BEGIN PRIVATE KEY-----\nfixture only"})
    if encoded:
        value = base64.b64encode(value.encode()).decode()
    validate_credentials(value, "deployer@example.com")


def test_credentials_from_another_project_are_rejected():
    value = json.dumps({"type": "service_account", "client_email": "other@example.com"})
    with pytest.raises(ValueError, match="must belong"):
        validate_credentials(value, "deployer@example.com")
