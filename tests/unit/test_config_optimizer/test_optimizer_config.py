import pytest
import yaml
import os
from pathlib import Path

from src.mcp_tools.config_optimizer.config import (
    OptimizerRuleConfig,
    AWSEC2Rules, EC2InstanceTypeRule,
    AWSS3Rules, S3BucketEncryptionRule, S3BucketVersioningRule, S3BucketPublicAccessBlockRule,
    load_optimizer_rules,
    DEFAULT_OPTIMIZER_RULES_FILENAME
)
from pydantic import ValidationError

@pytest.fixture
def temp_optimizer_rules_file(tmp_path: Path):
    """Fixture to create a temporary optimizer rules file and clean it up."""
    file_path = tmp_path / DEFAULT_OPTIMIZER_RULES_FILENAME
    def _create_config(content_dict):
        with open(file_path, 'w') as f:
            yaml.dump(content_dict, f)
        return file_path
    yield _create_config
    # tmp_path handles cleanup

# --- Test Default Values and Structure ---

def test_default_optimizer_rule_config():
    config = OptimizerRuleConfig()
    assert isinstance(config.aws_ec2, AWSEC2Rules)
    assert config.aws_ec2.enabled is True
    assert isinstance(config.aws_ec2.instance_type_optimization, EC2InstanceTypeRule)
    assert config.aws_ec2.instance_type_optimization.enabled is True
    assert config.aws_ec2.instance_type_optimization.suggest_newer_generations is True

    assert isinstance(config.aws_s3, AWSS3Rules)
    assert config.aws_s3.enabled is True
    assert isinstance(config.aws_s3.encryption, S3BucketEncryptionRule)
    assert config.aws_s3.encryption.enabled is True
    assert config.aws_s3.encryption.require_sse_kms is False
    assert isinstance(config.aws_s3.versioning, S3BucketVersioningRule)
    assert config.aws_s3.versioning.enabled is True
    assert isinstance(config.aws_s3.public_access_block, S3BucketPublicAccessBlockRule)
    assert config.aws_s3.public_access_block.enabled is True
    assert config.aws_s3.public_access_block.require_all_blocks_true is True

# --- Test Loading Logic ---

def test_load_optimizer_rules_no_file_present():
    """Test loading when no config file exists; should return defaults."""
    # Ensure no default file exists in CWD for this test if CWD is part of search path
    original_cwd = os.getcwd()
    # Run in a temp dir that won't have the file unless we create it
    with pytest.MonkeyPatch.context() as mp:
        temp_dir = Path(original_cwd) / "temp_test_dir_for_load_config_no_file" # Avoid using tmp_path directly here to control CWD
        temp_dir.mkdir(exist_ok=True)
        mp.chdir(temp_dir)
        try:
            config = load_optimizer_rules(config_path="non_existent_rules.yml") # Explicit non-existent
            assert config.aws_ec2.instance_type_optimization.suggest_newer_generations is True # Default

            config_auto = load_optimizer_rules() # Auto-detect (should also be default)
            assert config_auto.aws_s3.encryption.require_sse_kms is False # Default
        finally:
            if (temp_dir / DEFAULT_OPTIMIZER_RULES_FILENAME).exists():
                 (temp_dir / DEFAULT_OPTIMIZER_RULES_FILENAME).unlink()
            temp_dir.rmdir()


def test_load_optimizer_rules_from_file(temp_optimizer_rules_file):
    custom_rules_data = {
        "aws_ec2": {
            "enabled": True,
            "instance_type_optimization": {
                "enabled": True,
                "suggest_newer_generations": False,
                "generation_map": {"t1": "t2"},
                "large_instance_types_to_flag": ["m1.xlarge"]
            }
        },
        "aws_s3": {
            "enabled": False, # Disable all S3 checks
            "encryption": {"enabled": True, "require_sse_kms": True}, # This won't be checked due to parent
            "versioning": {"enabled": False}
        }
    }
    config_file_path = temp_optimizer_rules_file(custom_rules_data)

    # Test loading via explicit path
    config = load_optimizer_rules(str(config_file_path))
    assert config.aws_ec2.instance_type_optimization.suggest_newer_generations is False
    assert config.aws_ec2.instance_type_optimization.generation_map == {"t1": "t2"}
    assert config.aws_ec2.instance_type_optimization.large_instance_types_to_flag == ["m1.xlarge"]
    assert config.aws_s3.enabled is False
    assert config.aws_s3.encryption.require_sse_kms is True # Still parsed, just not used if aws_s3 disabled
    assert config.aws_s3.versioning.enabled is False
    assert config.aws_s3.public_access_block.enabled is True # Default, as aws_s3.public_access_block was not in file

def test_load_optimizer_rules_empty_file(temp_optimizer_rules_file, capsys):
    config_file_path = temp_optimizer_rules_file({}) # Empty dict -> empty YAML
    config = load_optimizer_rules(str(config_file_path))
    assert isinstance(config, OptimizerRuleConfig)
    assert config.aws_ec2.enabled is True # Should be default
    captured = capsys.readouterr()
    assert "Warning: Optimizer rules file" in captured.out
    assert "is empty. Using default rules." in captured.out


def test_load_optimizer_rules_partial_config(temp_optimizer_rules_file):
    partial_data = {
        "aws_ec2": {
            "instance_type_optimization": {"suggest_newer_generations": False}
        }
        # aws_s3 section is missing, should use defaults
    }
    config_file_path = temp_optimizer_rules_file(partial_data)
    config = load_optimizer_rules(str(config_file_path))

    assert config.aws_ec2.instance_type_optimization.suggest_newer_generations is False
    assert config.aws_ec2.enabled is True # Default for AWSEC2Rules
    assert config.aws_s3.enabled is True # Default for AWSS3Rules
    assert config.aws_s3.encryption.enabled is True # Default for S3BucketEncryptionRule

def test_load_optimizer_rules_invalid_yaml(temp_optimizer_rules_file):
    file_path = temp_optimizer_rules_file(None) # Create empty file
    with open(file_path, 'w') as f:
        f.write("aws_ec2: { instance_type_optimization: { enabled: true") # Invalid YAML

    with pytest.raises(ValueError, match="Error parsing YAML optimizer rules file"):
        load_optimizer_rules(str(file_path))

def test_load_optimizer_rules_validation_error(temp_optimizer_rules_file):
    invalid_data = {
        "aws_ec2": {
            "instance_type_optimization": {"suggest_newer_generations": "not-a-boolean"}
        }
    }
    config_file_path = temp_optimizer_rules_file(invalid_data)
    with pytest.raises(ValueError, match="Optimizer rules validation error"):
        load_optimizer_rules(str(config_file_path))

def test_default_file_search_logic_optimizer(tmp_path: Path):
    """Test the search logic for the default optimizer rules file."""
    project_root = tmp_path
    sub_dir = project_root / "project_A" / "module_B"
    sub_dir.mkdir(parents=True)

    rules_content = {"aws_s3": {"versioning": {"enabled": False}}}
    with open(project_root / DEFAULT_OPTIMIZER_RULES_FILENAME, 'w') as f: # Place in project_root
        yaml.dump(rules_content, f)

    original_cwd = os.getcwd()
    os.chdir(sub_dir) # Run from a subdirectory
    try:
        config = load_optimizer_rules() # No explicit path, should search up to project_root
        assert config.aws_s3.versioning.enabled is False
        assert config.aws_ec2.enabled is True # Default
    finally:
        os.chdir(original_cwd)
        (project_root / DEFAULT_OPTIMIZER_RULES_FILENAME).unlink()
        # Cleanup sub_dir if needed, though tmp_path should handle it.
        # For robustness:
        # shutil.rmtree(project_root / "project_A", ignore_errors=True)

def test_load_optimizer_rules_explicit_path_not_found(capsys):
    config = load_optimizer_rules(config_path="non_existent_rules.yml")
    assert config.aws_ec2.enabled is True # Defaults are used
    captured = capsys.readouterr()
    assert "Warning: Optimizer rules file 'non_existent_rules.yml' not found. Using default rules." in captured.out
