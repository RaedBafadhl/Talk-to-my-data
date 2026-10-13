import pytest

from scripts.deployment import Deployment, load_environment, reject_deletions
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
