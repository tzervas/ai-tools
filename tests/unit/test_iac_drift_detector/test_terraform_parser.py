import pytest
import json
from pathlib import Path
from typing import List

from src.mcp_tools.iac_drift_detector.models import ParsedResource
from src.mcp_tools.iac_drift_detector.parsers.terraform_parser import (
    parse_terraform_state_file,
    parse_terraform_plan_json_file,
)

# --- Fixtures for Sample Data ---


@pytest.fixture
def sample_tfstate_content() -> dict:
    return {
        "version": 4,
        "terraform_version": "1.1.0",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "web_server",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "i-0123456789abcdef0",
                            "ami": "ami-123",
                            "instance_type": "t2.micro",
                            "tags": {"Name": "web-server-prod"},
                        },
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "my_data_bucket",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {
                        "attributes": {
                            "id": "my-prod-data-bucket-unique-name",
                            "bucket": "my-prod-data-bucket-unique-name",
                            "acl": "private",
                        }
                    }
                ],
            },
            {  # Data source - should be ignored
                "mode": "data",
                "type": "aws_caller_identity",
                "name": "current",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [{"attributes": {"account_id": "123456789012"}}],
            },
            {  # Resource with a different provider name format
                "mode": "managed",
                "type": "null_resource",
                "name": "wait_for_setup",
                "provider": 'provider["registry.terraform.io/hashicorp/null"]',  # hashicorp/null
                "instances": [{"attributes": {"id": "7011749228923900571"}}],
            },
        ],
    }


@pytest.fixture
def temp_tfstate_file(tmp_path: Path, sample_tfstate_content: dict) -> Path:
    file_path = tmp_path / "test.tfstate"
    with open(file_path, "w") as f:
        json.dump(sample_tfstate_content, f)
    return file_path


@pytest.fixture
def sample_tfplan_json_content() -> dict:
    return {
        "format_version": "1.0",
        "resource_changes": [
            {
                "address": "aws_instance.web_server_new",
                "type": "aws_instance",
                "name": "web_server_new",
                "change": {
                    "actions": ["create"],
                    "after": {"instance_type": "t3.micro"},
                },
            },
            {
                "address": "aws_s3_bucket.my_data_bucket",
                "type": "aws_s3_bucket",
                "name": "my_data_bucket",
                "change": {
                    "actions": ["update"],
                    "before": {"acl": "private"},
                    "after": {"acl": "public-read"},
                },
            },
            {
                "address": "aws_instance.no_change_instance",
                "type": "aws_instance",
                "name": "no_change_instance",
                "change": {"actions": ["no-op"]},
            },
        ],
    }


@pytest.fixture
def temp_tfplan_json_file(tmp_path: Path, sample_tfplan_json_content: dict) -> Path:
    file_path = tmp_path / "test_plan.json"
    with open(file_path, "w") as f:
        json.dump(sample_tfplan_json_content, f)
    return file_path


# --- Tests for parse_terraform_state_file ---


def test_parse_tfstate_valid_file(temp_tfstate_file: Path):
    resources = parse_terraform_state_file(str(temp_tfstate_file))
    assert (
        len(resources) == 3
    )  # 2 managed resources + 1 null_resource, data source ignored

    instance_res = next((r for r in resources if r.type == "aws_instance"), None)
    assert instance_res is not None
    assert instance_res.id == "i-0123456789abcdef0"
    assert instance_res.name == "web_server"
    assert instance_res.provider_name == "aws"
    assert instance_res.attributes["instance_type"] == "t2.micro"
    assert instance_res.attributes["tags"] == {"Name": "web-server-prod"}

    s3_res = next((r for r in resources if r.type == "aws_s3_bucket"), None)
    assert s3_res is not None
    assert s3_res.id == "my-prod-data-bucket-unique-name"
    assert s3_res.name == "my_data_bucket"
    assert s3_res.provider_name == "aws"
    assert s3_res.attributes["acl"] == "private"

    null_res = next((r for r in resources if r.type == "null_resource"), None)
    assert null_res is not None
    assert null_res.name == "wait_for_setup"
    assert null_res.provider_name == "null"  # Check provider name extraction


def test_parse_tfstate_empty_resources():
    empty_tfstate = {"version": 4, "resources": []}
    # Use Path object from tmp_path for writing
    file_path = Path(
        Path(__file__).parent / "empty.tfstate"
    )  # Not ideal, should use tmp_path
    with open(file_path, "w") as f:
        json.dump(empty_tfstate, f)

    resources = parse_terraform_state_file(str(file_path))
    assert len(resources) == 0
    file_path.unlink()  # Clean up


def test_parse_tfstate_no_resources_key(tmp_path: Path):
    no_res_key_tfstate = {"version": 4}  # Missing 'resources' key
    file_path = tmp_path / "no_res.tfstate"
    with open(file_path, "w") as f:
        json.dump(no_res_key_tfstate, f)

    resources = parse_terraform_state_file(str(file_path))
    assert len(resources) == 0


def test_parse_tfstate_file_not_found(capsys):
    resources = parse_terraform_state_file("non_existent_file.tfstate")
    assert len(resources) == 0
    captured = capsys.readouterr()
    assert "Error: Terraform state file not found" in captured.err


def test_parse_tfstate_invalid_json(tmp_path: Path, capsys):
    file_path = tmp_path / "invalid.tfstate"
    file_path.write_text("this is not json")

    resources = parse_terraform_state_file(str(file_path))
    assert len(resources) == 0
    captured = capsys.readouterr()
    assert "Error: Invalid JSON" in captured.err


# --- Tests for parse_terraform_plan_json_file ---


def test_parse_tfplan_valid_file(temp_tfplan_json_file: Path):
    changes = parse_terraform_plan_json_file(str(temp_tfplan_json_file))
    assert len(changes) == 3  # Includes no-op for now

    create_change = next(
        (c for c in changes if c["change"]["actions"] == ["create"]), None
    )
    assert create_change is not None
    assert create_change["address"] == "aws_instance.web_server_new"
    assert create_change["change"]["after"]["instance_type"] == "t3.micro"

    update_change = next(
        (c for c in changes if c["change"]["actions"] == ["update"]), None
    )
    assert update_change is not None
    assert update_change["address"] == "aws_s3_bucket.my_data_bucket"
    assert update_change["change"]["after"]["acl"] == "public-read"


def test_parse_tfplan_file_not_found(capsys):
    changes = parse_terraform_plan_json_file("non_existent_plan.json")
    assert len(changes) == 0
    captured = capsys.readouterr()
    assert "Error: Terraform plan JSON file not found" in captured.err


def test_parse_tfplan_invalid_json(tmp_path: Path, capsys):
    file_path = tmp_path / "invalid_plan.json"
    file_path.write_text("{not_json_at_all")

    changes = parse_terraform_plan_json_file(str(file_path))
    assert len(changes) == 0
    captured = capsys.readouterr()
    assert "Error: Invalid JSON" in captured.err


def test_parse_tfplan_empty_changes(tmp_path: Path):
    plan_content = {"format_version": "1.0", "resource_changes": []}
    file_path = tmp_path / "empty_changes_plan.json"
    with open(file_path, "w") as f:
        json.dump(plan_content, f)
    changes = parse_terraform_plan_json_file(str(file_path))
    assert len(changes) == 0


def test_parse_tfstate_resource_missing_id_type_name(tmp_path: Path, capsys):
    # Test case where a resource instance might be malformed (e.g., missing 'id')
    malformed_tfstate_content = {
        "version": 4,
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "bad_instance",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {"attributes": {"ami": "ami-123"}}  # Missing "id" in attributes
                ],
            }
        ],
    }
    file_path = tmp_path / "malformed.tfstate"
    with open(file_path, "w") as f:
        json.dump(malformed_tfstate_content, f)

    resources = parse_terraform_state_file(str(file_path))
    assert len(resources) == 0
    # captured = capsys.readouterr() # Optional: check for warning message if you add one
    # assert "Warning: Skipping resource instance due to missing id" in captured.err (if you uncomment print in parser)
