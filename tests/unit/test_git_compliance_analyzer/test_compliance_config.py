import pytest
import yaml
import os
import re
from pathlib import Path
from pydantic import ValidationError

from src.mcp_tools.git_compliance_analyzer.config import (
    ComplianceRuleConfig,
    FileExistenceRules, FileExistenceRuleItem, FilePatternRuleItem,
    FileContentRules, FileContentRuleItem, ContentPatternRule,
    CommitHistoryRules, ConventionalCommitFormatRule,
    IaCValidationRules, IaCValidationRuleItem,
    load_compliance_rules, DEFAULT_COMPLIANCE_RULES_FILENAME
)

@pytest.fixture
def temp_compliance_rules_file(tmp_path: Path):
    """Fixture to create a temporary .compliance-rules.yml file."""
    file_path = tmp_path / DEFAULT_COMPLIANCE_RULES_FILENAME
    def _create_rules(content_dict):
        with open(file_path, 'w') as f:
            yaml.dump(content_dict, f)
        return file_path
    yield _create_rules

# --- Test Default Values and Structure ---
def test_default_compliance_rule_config():
    config = ComplianceRuleConfig()
    assert isinstance(config.file_checks, FileExistenceRules)
    assert config.file_checks.enabled is True
    assert config.file_checks.must_exist == []
    assert config.file_checks.must_not_exist_patterns == []

    assert isinstance(config.file_content_checks, FileContentRules)
    assert config.file_content_checks.enabled is True
    assert config.file_content_checks.rules == []

    assert isinstance(config.commit_history_checks, CommitHistoryRules) # Optional, but default_factory creates it
    assert config.commit_history_checks.enabled is True
    assert isinstance(config.commit_history_checks.conventional_commit_format, ConventionalCommitFormatRule)
    assert config.commit_history_checks.conventional_commit_format.enabled is True

    assert isinstance(config.iac_validation_checks, IaCValidationRules) # Optional, but default_factory
    assert config.iac_validation_checks.enabled is True
    assert config.iac_validation_checks.rules == []


# --- Test Regex Compilation in Models ---
def test_content_pattern_rule_regex_compilation():
    rule = ContentPatternRule(pattern="^valid.*$", message="Test", severity="Low")
    assert isinstance(rule.pattern, re.Pattern)
    with pytest.raises(ValidationError): # Pydantic v2 raises ValidationError for validator issues
        ContentPatternRule(pattern="[invalid(", message="Test", severity="Low")

def test_file_content_rule_item_regex_compilation():
    item = FileContentRuleItem(file_path_pattern=".*\\.py$", enabled=True) # No content patterns needed for this test
    assert isinstance(item.file_path_pattern, re.Pattern)
    with pytest.raises(ValidationError):
        FileContentRuleItem(file_path_pattern="[invalid(", enabled=True)

# --- Test Loading Logic ---
def test_load_compliance_rules_no_file(tmp_path: Path):
    # Run in a clean temp directory to ensure no default file is found upwards
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        config = load_compliance_rules() # Should use defaults
        assert config.file_checks.must_exist == []
        assert config.commit_history_checks.conventional_commit_format.types is not None # Check a default list
    finally:
        os.chdir(original_cwd)


def test_load_compliance_rules_from_file(temp_compliance_rules_file):
    rules_data = {
        "file_checks": {
            "must_exist": [{"path": "LICENSE.txt", "severity": "High"}],
            "must_not_exist_patterns": [{"pattern": "*.exe", "message": "Executables not allowed"}]
        },
        "file_content_checks": {
            "rules": [{
                "file_path_pattern": "\\.py$",
                "must_not_contain_pattern": {"pattern": "pdb.set_trace()", "message": "No pdb allowed", "severity": "High"},
                "enabled": True
            }]
        },
        "commit_history_checks": {
            "conventional_commit_format": {"enabled": False, "types": ["custom"], "severity": "Low"},
            "enabled": True
        },
        "iac_validation_checks": {
            "rules": [{"type": "terraform_validate", "paths": ["./infra"], "severity": "High"}],
            "enabled": False
        }
    }
    config_file = temp_compliance_rules_file(rules_data)

    # To test auto-detection, change CWD to where the file is
    original_cwd = Path.cwd()
    os.chdir(config_file.parent)
    try:
        config = load_compliance_rules() # Auto-detect DEFAULT_COMPLIANCE_RULES_FILENAME
    finally:
        os.chdir(original_cwd)

    assert len(config.file_checks.must_exist) == 1
    assert config.file_checks.must_exist[0].path == "LICENSE.txt"
    assert config.file_checks.must_exist[0].severity == "High"
    assert len(config.file_checks.must_not_exist_patterns) == 1
    assert config.file_checks.must_not_exist_patterns[0].pattern == "*.exe"

    assert len(config.file_content_checks.rules) == 1
    assert config.file_content_checks.rules[0].file_path_pattern.pattern == "\\.py$"
    assert config.file_content_checks.rules[0].must_not_contain_pattern.pattern.pattern == "pdb.set_trace()" # type: ignore

    assert config.commit_history_checks.conventional_commit_format.enabled is False # type: ignore
    assert config.commit_history_checks.conventional_commit_format.types == ["custom"] # type: ignore

    assert config.iac_validation_checks.enabled is False # type: ignore
    assert len(config.iac_validation_checks.rules) == 1 # type: ignore
    assert config.iac_validation_checks.rules[0].type == "terraform_validate" # type: ignore

def test_load_compliance_rules_empty_file(temp_compliance_rules_file, capsys):
    config_file = temp_compliance_rules_file({}) # Empty YAML
    config = load_compliance_rules(str(config_file))
    assert config.file_checks.enabled is True # Default value
    captured = capsys.readouterr()
    assert "Warning: Compliance rules file" in captured.out
    assert "is empty. Using default rules." in captured.out

def test_load_compliance_rules_partial_config(temp_compliance_rules_file):
    partial_data = {"file_checks": {"enabled": False}}
    config_file = temp_compliance_rules_file(partial_data)
    config = load_compliance_rules(str(config_file))
    assert config.file_checks.enabled is False
    assert config.file_content_checks.enabled is True # Default

def test_load_compliance_rules_invalid_yaml_syntax(temp_compliance_rules_file):
    file_path = temp_compliance_rules_file(None) # Create empty file
    with open(file_path, 'w') as f:
        f.write("file_checks: { must_exist: [{path: 'LIC'") # Invalid YAML
    with pytest.raises(ValueError, match="Error parsing YAML compliance rules file"):
        load_compliance_rules(str(file_path))

def test_load_compliance_rules_pydantic_validation_error(temp_compliance_rules_file):
    invalid_data = {"file_checks": {"must_exist": [{"path": 123}]}} # path should be str
    config_file = temp_compliance_rules_file(invalid_data)
    with pytest.raises(ValueError, match="Compliance rules validation error"):
        load_compliance_rules(str(config_file))

def test_load_rules_explicit_path_not_found(capsys):
    config = load_compliance_rules(config_path="non_existent_rules.yml")
    assert config.file_checks.enabled is True # Defaults
    captured = capsys.readouterr()
    assert "Warning: Compliance rules file 'non_existent_rules.yml' not found." in captured.out
