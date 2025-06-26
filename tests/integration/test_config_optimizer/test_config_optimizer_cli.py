import pytest
import subprocess
import os
import json
import yaml
from pathlib import Path

CLI_MODULE_PATH = "src.mcp_tools.config_optimizer.cli"
DEFAULT_OPTIMIZER_RULES_FILENAME = ".config-optimizer-rules.yml"

# Sample Terraform state content for testing
SAMPLE_TFSTATE_CONTENT = {
    "version": 4,
    "terraform_version": "1.1.0",
    "resources": [
        {  # EC2 - Old generation
            "mode": "managed",
            "type": "aws_instance",
            "name": "old_gen_ec2",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {"attributes": {"id": "i-t2instance", "instance_type": "t2.large"}}
            ],
        },
        {  # EC2 - Large type, should be flagged by default rules
            "mode": "managed",
            "type": "aws_instance",
            "name": "big_ec2",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {"attributes": {"id": "i-m5huge", "instance_type": "m5.24xlarge"}}
            ],
        },
        {  # S3 - No encryption, no versioning, no PAB
            "mode": "managed",
            "type": "aws_s3_bucket",
            "name": "insecure_bucket",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {"attributes": {"id": "bucket-insecure", "bucket": "bucket-insecure"}}
            ],
        },
        {  # S3 - Good config (matching default optimizer expectations for "no recs")
            "mode": "managed",
            "type": "aws_s3_bucket",
            "name": "secure_bucket",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {
                    "attributes": {
                        "id": "bucket-secure",
                        "bucket": "bucket-secure",
                        "server_side_encryption_configuration": {
                            "rule": {
                                "apply_server_side_encryption_by_default": {
                                    "sse_algorithm": "AES256"
                                }
                            }
                        },
                        "versioning": [{"enabled": True}],
                        "public_access_block": [
                            {
                                "block_public_acls": True,
                                "block_public_policy": True,
                                "ignore_public_acls": True,
                                "restrict_public_buckets": True,
                            }
                        ],
                    }
                }
            ],
        },
    ],
}


@pytest.fixture
def temp_tfstate_file_optimizer(tmp_path: Path) -> Path:
    file_path = tmp_path / "test_optimizer.tfstate"
    with open(file_path, "w") as f:
        json.dump(SAMPLE_TFSTATE_CONTENT, f)
    return file_path


@pytest.fixture
def temp_optimizer_rules_file_custom(tmp_path: Path):
    def _create_rules_file(rules_content: dict):
        file_path = tmp_path / "custom.rules.yml"
        with open(file_path, "w") as f:
            yaml.dump(rules_content, f)
        return file_path

    return _create_rules_file


def run_optimizer_cli(cwd_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    cmd = ["python", "-m", CLI_MODULE_PATH] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd_path)


# --- CLI Tests ---


def test_cli_optimizer_help_message():
    result = subprocess.run(
        ["python", "-m", CLI_MODULE_PATH, "--help"], capture_output=True, text=True
    )
    assert "usage: cli.py" in result.stdout
    assert "--tf-state-file" in result.stdout
    assert "--rules-file" in result.stdout
    assert result.returncode == 0


def test_cli_optimizer_no_tfstate_file_error(tmp_path: Path):
    result = run_optimizer_cli(
        tmp_path, ["--iac-type", "terraform"]
    )  # Missing --tf-state-file
    assert result.returncode != 0  # Should be 2
    assert "Error: For Terraform, --tf-state-file must be provided." in result.stderr


def test_cli_optimizer_tfstate_not_found_error(tmp_path: Path):
    result = run_optimizer_cli(tmp_path, ["--tf-state-file", "nonexistent.tfstate"])
    assert result.returncode != 0  # Should be 2
    assert "Error: Terraform state file nonexistent.tfstate not found." in result.stderr


def test_cli_optimizer_default_rules_produce_recommendations(
    temp_tfstate_file_optimizer: Path, tmp_path: Path
):
    """Test with sample tfstate and default optimizer rules."""
    tfstate_abs_path = str(temp_tfstate_file_optimizer.resolve())
    args = ["--tf-state-file", tfstate_abs_path]  # Uses default rules

    result = run_optimizer_cli(tmp_path, args)
    # print("STDOUT Default Rules:", result.stdout)
    # print("STDERR Default Rules:", result.stderr)

    assert result.returncode == 1  # Recommendations expected
    assert "OPTIMIZATION RECOMMENDATION(S) FOUND" in result.stdout

    # Check for EC2 t2.large -> newer gen (e.g. t3.large)
    assert "AWS_EC2_NEWER_GENERATION_MAPPED" in result.stdout
    assert "instance type 't2.large'" in result.stdout
    assert "t3.large" in result.stdout  # Default map t2->t3

    # Check for EC2 m5.24xlarge flagged as large
    assert "AWS_EC2_LARGE_INSTANCE_TYPE" in result.stdout
    assert "instance type 'm5.24xlarge' is a large instance" in result.stdout

    # Check for insecure_bucket recommendations (SSE, Versioning, PAB)
    assert "AWS_S3_ENCRYPTION_DISABLED" in result.stdout
    assert "insecure_bucket" in result.stdout
    assert "AWS_S3_VERSIONING_DISABLED" in result.stdout
    assert "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" in result.stdout

    # Secure bucket should not have these recommendations
    assert not (
        "secure_bucket" in result.stdout
        and "AWS_S3_ENCRYPTION_DISABLED" in result.stdout
    )


def test_cli_optimizer_custom_rules_file(
    temp_tfstate_file_optimizer: Path, temp_optimizer_rules_file_custom, tmp_path: Path
):
    custom_rules = {
        "aws_ec2": {
            "instance_type_optimization": {
                "enabled": True,
                "suggest_newer_generations": False,  # Disable newer gen check
                "large_instance_types_to_flag": ["t2.large"],  # Flag t2.large as large
            }
        },
        "aws_s3": {"enabled": False},  # Disable all S3 checks
    }
    rules_file_path = temp_optimizer_rules_file_custom(custom_rules)
    rules_file_abs_path = str(rules_file_path.resolve())
    tfstate_abs_path = str(temp_tfstate_file_optimizer.resolve())

    args = ["--tf-state-file", tfstate_abs_path, "--rules-file", rules_file_abs_path]
    result = run_optimizer_cli(tmp_path, args)

    # print("STDOUT Custom Rules:", result.stdout)
    # print("STDERR Custom Rules:", result.stderr)

    assert result.returncode == 1  # Still expect t2.large to be flagged
    assert "OPTIMIZATION RECOMMENDATION(S) FOUND" in result.stdout

    # Newer gen for t2.large should NOT be there
    assert not (
        "AWS_EC2_NEWER_GENERATION_MAPPED" in result.stdout
        and "t2.large" in result.stdout
    )

    # t2.large should be flagged as "large" by custom rule
    assert "AWS_EC2_LARGE_INSTANCE_TYPE" in result.stdout
    assert "instance type 't2.large' is a large instance" in result.stdout

    # m5.24xlarge should NOT be flagged as "large" by this custom rule (it's not in the list)
    assert not (
        "AWS_EC2_LARGE_INSTANCE_TYPE" in result.stdout
        and "m5.24xlarge" in result.stdout
    )

    # All S3 checks should be disabled, so no S3 recommendations for insecure_bucket
    assert not ("insecure_bucket" in result.stdout and "AWS_S3_" in result.stdout)


def test_cli_optimizer_no_recommendations(
    tmp_path: Path, temp_optimizer_rules_file_custom
):
    """Test scenario where no recommendations are generated."""
    # tfstate with only the "secure_bucket" which should pass default-like rules
    # if other resources that trigger recs are removed.
    # Let's use a tfstate with only the secure_bucket
    tfstate_secure_only = {
        "version": 4,
        "resources": [SAMPLE_TFSTATE_CONTENT["resources"][3]],  # Only secure_bucket
    }
    tfstate_file = tmp_path / "secure.tfstate"
    with open(tfstate_file, "w") as f:
        json.dump(tfstate_secure_only, f)

    # Use default rules (by not specifying a rules file)
    args = ["--tf-state-file", str(tfstate_file.resolve())]
    result = run_optimizer_cli(tmp_path, args)

    # print("STDOUT No Recs:", result.stdout)
    # print("STDERR No Recs:", result.stderr)
    assert result.returncode == 0
    assert "NO OPTIMIZATION RECOMMENDATIONS FOUND" in result.stdout


# Future tests:
# - Invalid rules file (YAML error, Pydantic validation error)
# - Empty tfstate file
# - tfstate file with no *relevant* resources (e.g. only null_resource)
# - More complex resource attributes and rule interactions
# - Error handling for IaC parsing failures (if parser raises specific exceptions)
# - Different --iac-type when supported
# - Interaction with actual cloud connectors (would need extensive mocking or dedicated test accounts)
