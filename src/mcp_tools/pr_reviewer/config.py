"""Configuration and policy models for PR reviewer tool."""

import os
import re
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

DEFAULT_CONFIG_FILENAME = ".pr-policy.yml"

# --- Policy Specific Models ---


class BranchNamingPolicy(BaseModel):
    """Policy for branch naming conventions."""

    pattern: Optional[str] = (
        "^(feature|fix|chore|docs|style|refactor|test)/[a-zA-Z0-9_.-]+$"
    )
    enabled: bool = True

    @classmethod
    def __get_validators__(cls):
        yield cls.compile_pattern_branch

    @staticmethod
    def compile_pattern_branch(v):
        """Compile the branch naming regex pattern."""
        if v is None:
            return None
        try:
            return re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{v}': {e}") from e


class ConventionalCommitPolicy(BaseModel):
    """Policy for conventional commit types."""

    enabled: bool = True
    types: List[str] = Field(
        default_factory=lambda: [
            "feat",
            "fix",
            "docs",
            "style",
            "refactor",
            "test",
            "chore",
        ]
    )


class RequireIssueNumberPolicy(BaseModel):
    """Policy for requiring issue numbers in commits."""

    pattern: Optional[str] = "\\[[A-Z]+-[0-9]+\\]"  # Example: [PROJ-123]
    in_commit_body: bool = True  # Check commit message body
    in_pr_title: bool = False  # Placeholder for future PR title check
    in_pr_body: bool = False  # Placeholder for future PR body check
    enabled: bool = False

    @field_validator("pattern", mode="before")
    @classmethod
    def compile_pattern_issue(cls, v):
        """Compile the issue number regex pattern."""
        if v is None:
            return None
        try:
            return re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{v}': {e}") from e

    def is_enabled(self) -> bool:
        """Return whether the issue number policy is enabled."""
        return self.enabled


class CommitMessagePolicy(BaseModel):
    """Policy for commit messages."""

    conventional_commit: ConventionalCommitPolicy = Field(
        default_factory=ConventionalCommitPolicy
    )
    require_issue_number: RequireIssueNumberPolicy = Field(
        default_factory=RequireIssueNumberPolicy
    )
    enabled: bool = True


class DisallowedPatternItem(BaseModel):
    """Item for disallowed patterns in code."""

    pattern: str
    message: Optional[str] = None
    enabled: bool = True

    @field_validator("pattern", mode="before")
    @classmethod
    def compile_pattern_disallowed(cls, v):
        """Compile the disallowed pattern regex."""
        if v is None:
            raise ValueError("Pattern for DisallowedPatternItem cannot be None")
        try:
            return re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{v}': {e}") from e

    def is_enabled(self) -> bool:
        """Return whether this disallowed pattern item is enabled."""
        return self.enabled


class DisallowedPatternsPolicy(BaseModel):
    """Policy for disallowed patterns."""

    patterns: List[DisallowedPatternItem] = Field(default_factory=list)
    enabled: bool = True


class FileSizePolicy(BaseModel):
    """Policy for file size limits."""

    max_bytes: int = 1048576  # 1MB
    ignore_extensions: List[str] = Field(default_factory=list)
    ignore_paths: List[str] = Field(default_factory=list)
    enabled: bool = True


# --- Main Configuration Model ---


class PolicyConfig(BaseModel):
    """Main configuration for PR reviewer policies."""

    branch_naming: BranchNamingPolicy = Field(default_factory=BranchNamingPolicy)
    commit_messages: CommitMessagePolicy = Field(default_factory=CommitMessagePolicy)
    disallowed_patterns: DisallowedPatternsPolicy = Field(
        default_factory=DisallowedPatternsPolicy
    )
    file_size: FileSizePolicy = Field(default_factory=FileSizePolicy)

    # Future policies can be added here
    # documentation_changes: Optional[dict] = None


# --- Loading Function ---


def load_config(config_path: Optional[str] = None) -> PolicyConfig:
    """
    Loads policy configuration from a YAML file.
    If config_path is None, tries to load from '.pr-policy.yml' in the current or
    parent directories. If no file is found, returns default configuration.
    """
    if config_path:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
    else:
        # Search for default config file in current and parent directories
        current_dir = os.getcwd()
        while True:
            default_path = os.path.join(current_dir, DEFAULT_CONFIG_FILENAME)
            if os.path.exists(default_path):
                config_path = default_path
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached root directory
                break
            current_dir = parent_dir

    if config_path:
        print(f"Loading PR policy configuration from: {config_path}")
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config_data = yaml.safe_load(config_file)
            if config_data is None:  # Empty YAML file
                print(
                    "Warning: Configuration file is empty. Using default policies."
                )
                return PolicyConfig()
            return PolicyConfig(**config_data)
        except yaml.YAMLError as e:
            raise ValueError(
                f"Error parsing YAML configuration file {config_path}: {e}"
            ) from e
        except ValidationError as e:
            raise ValueError(
                f"Configuration validation error in {config_path}:\n{e}"
            ) from e
        except Exception as e:
            raise ValueError(
                f"Unexpected error loading configuration from {config_path}: {e}"
            ) from e
    else:
        print(
            f"No configuration file '{DEFAULT_CONFIG_FILENAME}' found. "
            "Using default policies."
        )
        return PolicyConfig()


if __name__ == "__main__":
    import sys

    try:
        # Create a dummy .pr-policy.yml for testing
        DUMMY_CONFIG_CONTENT = """
branch_naming:
  pattern: "^(feat|fix)/.+$"
  enabled: true

commit_messages:
  conventional_commit:
    enabled: true
    types: ["feat", "fix"]
  require_issue_number:
    pattern: "ISSUE-[0-9]+"
    enabled: true
  enabled: true

disallowed_patterns:
  patterns:
    - pattern: "DO NOT COMMIT"
      message: "Found 'DO NOT COMMIT' string."
      enabled: true
  enabled: true

file_size:
  max_bytes: 500000 # 500KB
  ignore_extensions: [".log"]
  enabled: true
"""
        with open(DEFAULT_CONFIG_FILENAME, "w", encoding="utf-8") as dummy_file:
            dummy_file.write(DUMMY_CONFIG_CONTENT)

        print("--- Testing with dummy .pr-policy.yml ---")
        config = load_config()
        print("\nLoaded configuration:")
        print(
            "  Branch Naming Pattern:",
            config.branch_naming.pattern.pattern
            if config.branch_naming.pattern
            else "Not set/Invalid",
        )
        print(
            "  Conventional Commit Types:",
            config.commit_messages.conventional_commit.types,
        )
        print(
            "  Issue Number Pattern:",
            config.commit_messages.require_issue_number.pattern.pattern
            if config.commit_messages.require_issue_number.pattern
            else "Not set/Invalid",
        )
        if config.disallowed_patterns.patterns:
            print(
                "  Disallowed Pattern Example:",
                config.disallowed_patterns.patterns[0].pattern.pattern,
            )
        print(f"  Max File Size: {config.file_size.max_bytes}")

        # Test with non-existent explicit path
        # print("\n--- Testing with non-existent explicit path ---")
        # try:
        #     load_config("non_existent_config.yml")
        # except FileNotFoundError as e:
        #     print(f"Caught expected error: {e}")

        # Test with default (after removing dummy)
        os.remove(DEFAULT_CONFIG_FILENAME)
        print("\n--- Testing with no .pr-policy.yml (should use defaults) ---")
        default_config = load_config()
        print("\nDefault configuration:")
        print(
            "  Branch Naming Pattern:",
            default_config.branch_naming.pattern.pattern
            if default_config.branch_naming.pattern
            else "Not set/Invalid",
        )
        print(f"  Max File Size: {default_config.file_size.max_bytes}")

    except (FileNotFoundError, ValidationError, yaml.YAMLError) as e:
        print(
            f"Error during example usage: {e}", file=sys.stderr
        )
    finally:
        if os.path.exists(DEFAULT_CONFIG_FILENAME):
            os.remove(DEFAULT_CONFIG_FILENAME)
