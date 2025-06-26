import yaml
import os
import re
from typing import List, Optional, Pattern, Dict
from pydantic import BaseModel, Field, field_validator, ValidationError

DEFAULT_COMPLIANCE_RULES_FILENAME = ".compliance-rules.yml"

# --- Individual Rule Models ---

class FileExistenceRuleItem(BaseModel):
    path: str # Exact path relative to repo root
    severity: str = Field(default="Medium", pattern=r"^(High|Medium|Low|Informational)$")
    message: Optional[str] = None # Custom message if needed

class FilePatternRuleItem(BaseModel):
    pattern: str # Glob pattern
    severity: str = Field(default="High", pattern=r"^(High|Medium|Low|Informational)$")
    message: Optional[str] = None

class FileExistenceRules(BaseModel):
    must_exist: List[FileExistenceRuleItem] = Field(default_factory=list)
    must_not_exist_patterns: List[FilePatternRuleItem] = Field(default_factory=list)
    enabled: bool = True

class ContentPatternRule(BaseModel):
    pattern: Pattern # Compiled regex
    message: str
    severity: str = Field(default="Medium", pattern=r"^(High|Medium|Low|Informational)$")

    @field_validator('pattern', mode='before')
    def compile_content_pattern(cls, v):
        if isinstance(v, str):
            try:
                return re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{v}': {e}")
        return v # Assume already compiled if not str (e.g. during model copy)

class FileContentRuleItem(BaseModel):
    file_path_pattern: Pattern # Regex for file paths to check (e.g., "\\.py$", "README\\.md")
    must_contain_pattern: Optional[ContentPatternRule] = None
    must_not_contain_pattern: Optional[ContentPatternRule] = None
    enabled: bool = True

    @field_validator('file_path_pattern', mode='before')
    def compile_file_path_pattern(cls, v):
        if isinstance(v, str):
            try:
                return re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern for file_path_pattern '{v}': {e}")
        return v

    @field_validator('must_contain_pattern', 'must_not_contain_pattern', mode='before')
    def ensure_at_least_one_content_check(cls, v, values):
        # This validator is a bit tricky with Pydantic v2 for cross-field validation this way.
        # A root_validator would be better if we need to ensure one of them exists.
        # For now, assume if the item is present, its sub-fields are valid or will be caught.
        return v


class FileContentRules(BaseModel):
    rules: List[FileContentRuleItem] = Field(default_factory=list)
    enabled: bool = True


class ConventionalCommitFormatRule(BaseModel):
    enabled: bool = True
    types: List[str] = Field(default_factory=lambda: ["feat", "fix", "docs", "style", "refactor", "test", "chore", "ci", "build", "perf"])
    severity: str = Field(default="Medium", pattern=r"^(High|Medium|Low|Informational)$")

class CommitHistoryRules(BaseModel):
    # Check commits on current branch against base_branch
    conventional_commit_format: Optional[ConventionalCommitFormatRule] = Field(default_factory=ConventionalCommitFormatRule)
    # require_issue_in_commit: Optional[IssueInCommitRule] = None # Example for future
    enabled: bool = True


class IaCValidationRuleItem(BaseModel):
    type: str # e.g., "terraform_validate", "terrascan_run"
    paths: List[str] = Field(default_factory=lambda: ["."]) # Directories to run in, relative to repo root
    severity: str = Field(default="High", pattern=r"^(High|Medium|Low|Informational)$")
    enabled: bool = True

class IaCValidationRules(BaseModel):
    rules: List[IaCValidationRuleItem] = Field(default_factory=list)
    enabled: bool = True


# --- Main Compliance Configuration Model ---

class ComplianceRuleConfig(BaseModel):
    file_checks: FileExistenceRules = Field(default_factory=FileExistenceRules)
    file_content_checks: FileContentRules = Field(default_factory=FileContentRules)
    commit_history_checks: Optional[CommitHistoryRules] = Field(default_factory=CommitHistoryRules)
    iac_validation_checks: Optional[IaCValidationRules] = Field(default_factory=IaCValidationRules)

# --- Loading Function ---

def load_compliance_rules(config_path: Optional[str] = None) -> ComplianceRuleConfig:
    """
    Loads compliance rules from a YAML file.
    If config_path is None, tries to load from '.compliance-rules.yml'.
    If no file is found or path is invalid, returns default rule configuration.
    """
    actual_config_path = config_path
    if not actual_config_path:
        current_dir = os.getcwd()
        while True:
            default_path_try = os.path.join(current_dir, DEFAULT_COMPLIANCE_RULES_FILENAME)
            if os.path.exists(default_path_try):
                actual_config_path = default_path_try
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir: break
            current_dir = parent_dir

    if actual_config_path and os.path.exists(actual_config_path):
        print(f"Loading compliance rules from: {actual_config_path}")
        try:
            with open(actual_config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            if config_data is None:
                print(f"Warning: Compliance rules file '{actual_config_path}' is empty. Using default rules.")
                return ComplianceRuleConfig()
            return ComplianceRuleConfig(**config_data)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML compliance rules file {actual_config_path}: {e}")
        except ValidationError as e:
            raise ValueError(f"Compliance rules validation error in {actual_config_path}:\n{e}")
        except Exception as e:
            raise ValueError(f"Unexpected error loading compliance rules from {actual_config_path}: {e}")
    else:
        if config_path:
             print(f"Warning: Compliance rules file '{config_path}' not found. Using default rules.")
        else:
            print(f"No compliance rules file '{DEFAULT_COMPLIANCE_RULES_FILENAME}' found. Using default rules.")
        return ComplianceRuleConfig()

if __name__ == '__main__':
    try:
        print("--- Testing with default compliance rules (no file) ---")
        default_cfg = load_compliance_rules()
        assert default_cfg.file_checks.enabled is True
        assert default_cfg.commit_history_checks.enabled is True # type: ignore

        dummy_rules = {
            "file_checks": {
                "must_exist": [{"path": "Makefile", "severity": "Low"}],
                "must_not_exist_patterns": [{"pattern": "*.tmp", "severity": "Informational"}]
            },
            "file_content_checks": {
                "rules": [{
                    "file_path_pattern": "\\.md$",
                    "must_contain_pattern": {"pattern": "License", "message": "MD files should mention License.", "severity": "Low"},
                    "enabled": True
                }]
            },
            "commit_history_checks": {
                "conventional_commit_format": {"enabled": False, "severity": "Low"},
                "enabled": True
            },
            "iac_validation_checks": {
                "rules": [{"type": "terraform_validate", "paths": ["./iac"], "severity": "High"}],
                "enabled": True
            }
        }
        with open(DEFAULT_COMPLIANCE_RULES_FILENAME, 'w') as f:
            yaml.dump(dummy_rules, f)

        print(f"\n--- Testing with dummy {DEFAULT_COMPLIANCE_RULES_FILENAME} ---")
        loaded_cfg = load_compliance_rules()
        assert len(loaded_cfg.file_checks.must_exist) == 1
        assert loaded_cfg.file_checks.must_exist[0].path == "Makefile"
        assert loaded_cfg.file_content_checks.rules[0].must_contain_pattern.pattern.pattern == "License" # type: ignore
        assert loaded_cfg.commit_history_checks.conventional_commit_format.enabled is False # type: ignore
        assert len(loaded_cfg.iac_validation_checks.rules) == 1 # type: ignore

    except Exception as e:
        print(f"Error during example usage: {e}", file=sys.stderr)
    finally:
        if os.path.exists(DEFAULT_COMPLIANCE_RULES_FILENAME):
            os.remove(DEFAULT_COMPLIANCE_RULES_FILENAME)
        pass
