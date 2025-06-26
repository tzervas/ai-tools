import pytest
import yaml
import os
import re
from pydantic import ValidationError

# Adjust import path based on where tests are run from and project structure
# Assuming tests are run from project root, and src is in PYTHONPATH
from src.mcp_tools.pr_reviewer.config import (
    PolicyConfig,
    BranchNamingPolicy,
    CommitMessagePolicy,
    ConventionalCommitPolicy,
    RequireIssueNumberPolicy,
    DisallowedPatternsPolicy,
    DisallowedPatternItem,
    FileSizePolicy,
    load_config,
    DEFAULT_CONFIG_FILENAME,
)


@pytest.fixture
def temp_config_file(tmp_path):
    """Fixture to create a temporary config file and clean it up."""
    file_path = tmp_path / DEFAULT_CONFIG_FILENAME

    def _create_config(content_dict):
        with open(file_path, "w") as f:
            yaml.dump(content_dict, f)
        return file_path

    yield _create_config
    # No explicit cleanup needed for tmp_path, pytest handles it


def test_load_config_default_values():
    """Test loading config when no file exists, should return defaults."""
    config = load_config(
        config_path="non_existent_file.yml"
    )  # Should trigger default loading path if not found
    assert isinstance(config, PolicyConfig)
    assert config.branch_naming.enabled is True
    assert (
        config.branch_naming.pattern.pattern
        == "^(feature|fix|chore|docs|style|refactor|test)/[a-zA-Z0-9_.-]+$"
    )
    assert config.commit_messages.enabled is True
    assert config.file_size.max_bytes == 1048576


def test_load_config_from_file(temp_config_file):
    """Test loading a valid configuration from a YAML file."""
    custom_config_data = {
        "branch_naming": {"pattern": "^custom/.+$", "enabled": True},
        "commit_messages": {
            "conventional_commit": {"types": ["task", "bugfix"]},
            "require_issue_number": {"enabled": True, "pattern": "TASK-\\d+"},
            "enabled": True,
        },
        "disallowed_patterns": {
            "patterns": [
                {"pattern": "TEMP_SECRET", "message": "Do not commit temp secrets."}
            ],
            "enabled": True,
        },
        "file_size": {"max_bytes": 5000, "enabled": False},
    }
    config_file_path = temp_config_file(custom_config_data)

    # Temporarily change CWD to where tmp_path created the file for auto-detection
    original_cwd = os.getcwd()
    os.chdir(config_file_path.parent)
    try:
        config = load_config()  # Test auto-detection
    finally:
        os.chdir(original_cwd)

    assert config.branch_naming.pattern.pattern == "^custom/.+$"
    assert config.commit_messages.conventional_commit.types == ["task", "bugfix"]
    assert config.commit_messages.require_issue_number.enabled is True
    assert config.commit_messages.require_issue_number.pattern.pattern == "TASK-\\d+"
    assert len(config.disallowed_patterns.patterns) == 1
    assert config.disallowed_patterns.patterns[0].pattern.pattern == "TEMP_SECRET"
    assert config.file_size.max_bytes == 5000
    assert config.file_size.enabled is False


def test_load_config_empty_file(temp_config_file):
    """Test loading an empty YAML file, should use defaults."""
    config_file_path = temp_config_file({})  # Empty dict makes an empty YAML file

    original_cwd = os.getcwd()
    os.chdir(config_file_path.parent)
    try:
        config = load_config()
    finally:
        os.chdir(original_cwd)

    assert isinstance(config, PolicyConfig)
    assert config.branch_naming.enabled is True  # Check a default value


def test_load_config_partial_config(temp_config_file):
    """Test loading a file with only some sections defined."""
    partial_data = {"branch_naming": {"enabled": False}}
    config_file_path = temp_config_file(partial_data)
    original_cwd = os.getcwd()
    os.chdir(config_file_path.parent)
    try:
        config = load_config()
    finally:
        os.chdir(original_cwd)

    assert config.branch_naming.enabled is False
    assert config.commit_messages.enabled is True  # Default
    assert config.file_size.max_bytes == 1048576  # Default


def test_load_config_invalid_yaml(temp_config_file):
    """Test loading a file with invalid YAML content."""
    file_path = temp_config_file(None)  # Create empty file first
    with open(file_path, "w") as f:
        f.write("branch_naming: {pattern: 'foo', enabled: true")  # Missing closing }

    original_cwd = os.getcwd()
    os.chdir(file_path.parent)
    with pytest.raises(ValueError, match="Error parsing YAML configuration file"):
        try:
            load_config()
        finally:
            os.chdir(original_cwd)


def test_load_config_validation_error(temp_config_file):
    """Test loading a file with valid YAML but data that fails Pydantic validation."""
    invalid_data = {"file_size": {"max_bytes": "not-an-integer"}}
    config_file_path = temp_config_file(invalid_data)
    original_cwd = os.getcwd()
    os.chdir(config_file_path.parent)
    with pytest.raises(ValueError, match="Configuration validation error"):
        try:
            load_config()
        finally:
            os.chdir(original_cwd)


def test_regex_compilation_in_models():
    """Test that regex patterns are compiled correctly in Pydantic models."""
    bn_policy = BranchNamingPolicy(pattern="^test/.+$")
    assert isinstance(bn_policy.pattern, re.Pattern)
    assert bn_policy.pattern.pattern == "^test/.+$"

    ri_policy = RequireIssueNumberPolicy(pattern="^T-\\d+$", enabled=True)
    assert isinstance(ri_policy.pattern, re.Pattern)
    assert ri_policy.pattern.pattern == "^T-\\d+$"

    dp_item = DisallowedPatternItem(pattern="secret")
    assert isinstance(dp_item.pattern, re.Pattern)
    assert dp_item.pattern.pattern == "secret"


def test_invalid_regex_pattern_in_models():
    """Test that invalid regex patterns raise ValueError during model instantiation."""
    with pytest.raises(ValidationError):  # Pydantic wraps it in ValidationError
        BranchNamingPolicy(pattern="*invalidregex")

    with pytest.raises(ValidationError):
        RequireIssueNumberPolicy(pattern="[", enabled=True)

    with pytest.raises(ValidationError):
        DisallowedPatternItem(pattern="(?<invalid)")


def test_default_config_file_search_logic(tmp_path):
    """Test the search logic for the default config file."""
    # Setup: create a .pr-policy.yml in a subdirectory
    project_root = tmp_path
    sub_dir = project_root / "subdir1" / "subdir2"
    sub_dir.mkdir(parents=True)

    config_content = {"branch_naming": {"pattern": "^search_logic_test/.+$"}}
    with open(sub_dir / DEFAULT_CONFIG_FILENAME, "w") as f:
        yaml.dump(config_content, f)

    # Test 1: Run from a deeper directory, should find the file in parent
    current_deeper_dir = sub_dir / "deeper"
    current_deeper_dir.mkdir()

    original_cwd = os.getcwd()
    os.chdir(current_deeper_dir)
    try:
        config = load_config()  # No explicit path, should search up
        assert config.branch_naming.pattern.pattern == "^search_logic_test/.+$"
    finally:
        os.chdir(original_cwd)

    # Test 2: Run from a directory where it doesn't exist (and not in parents up to a point)
    # This should use defaults if it doesn't find it all the way up to where test is run
    # For this test, we ensure it's NOT in tmp_path itself
    other_dir = tmp_path / "other_dir_no_config"
    other_dir.mkdir()
    os.chdir(other_dir)
    try:
        config_defaults = load_config()
        assert (
            config_defaults.branch_naming.pattern.pattern
            == BranchNamingPolicy().pattern.pattern
        )  # Default
    finally:
        os.chdir(original_cwd)


# Test specific model default values
def test_branch_naming_policy_defaults():
    policy = BranchNamingPolicy()
    assert policy.enabled is True
    assert (
        policy.pattern.pattern
        == "^(feature|fix|chore|docs|style|refactor|test)/[a-zA-Z0-9_.-]+$"
    )


def test_conventional_commit_policy_defaults():
    policy = ConventionalCommitPolicy()
    assert policy.enabled is True
    assert policy.types == ["feat", "fix", "docs", "style", "refactor", "test", "chore"]


def test_require_issue_number_policy_defaults():
    policy = RequireIssueNumberPolicy()
    assert policy.enabled is False
    assert policy.pattern.pattern == "\\[[A-Z]+-[0-9]+\\]"
    assert policy.in_commit_body is True


def test_disallowed_patterns_policy_defaults():
    policy = DisallowedPatternsPolicy()
    assert policy.enabled is True
    assert policy.patterns == []


def test_file_size_policy_defaults():
    policy = FileSizePolicy()
    assert policy.enabled is True
    assert policy.max_bytes == 1048576
    assert policy.ignore_extensions == []
    assert policy.ignore_paths == []
