import pytest
import subprocess
import os
import shutil
import yaml
from pathlib import Path
import git  # For setting up test repos

# Assuming the CLI script is callable via python -m src.mcp_tools.pr_reviewer.cli
CLI_MODULE_PATH = "src.mcp_tools.pr_reviewer.cli"
DEFAULT_POLICY_FILENAME = ".pr-policy.yml"


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """
    Fixture to create a temporary Git repository for testing.
    Yields the path to the repository.
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize Git repo
    repo = git.Repo.init(repo_dir)

    # Initial commit on main branch
    (repo_dir / "initial.txt").write_text("Initial content")
    repo.index.add(["initial.txt"])
    repo.index.commit("Initial commit on main")

    # Set user details for commits (important for GitPython/git)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test User").release()
        cw.set_value("user", "email", "test@example.com").release()

    yield repo_dir

    # Cleanup (though tmp_path should handle most of it)
    # shutil.rmtree(repo_dir, ignore_errors=True)


def run_cli(repo_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Helper function to run the CLI tool."""
    cmd = ["python", "-m", CLI_MODULE_PATH] + args
    # print(f"Running CLI: CWD={repo_path}, CMD={' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)


def create_policy_file(repo_path: Path, policy_content: dict):
    """Helper to create a .pr-policy.yml file in the repo."""
    with open(repo_path / DEFAULT_POLICY_FILENAME, "w") as f:
        yaml.dump(policy_content, f)


# --- Basic CLI Tests ---


def test_cli_no_args_runs_with_defaults(temp_git_repo: Path):
    """Test running the CLI with no arguments in a simple repo. Expects defaults."""
    # Create a feature branch
    repo = git.Repo(temp_git_repo)
    repo.git.checkout("-b", "feature/good-branch")
    (temp_git_repo / "feature_file.txt").write_text("Feature content")
    repo.index.add(["feature_file.txt"])
    repo.index.commit("feat: add feature file")

    # Run CLI (should default to base=main, head=HEAD)
    result = run_cli(temp_git_repo, [])

    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)

    assert "ALL CHECKS PASSED" in result.stdout
    assert result.returncode == 0


def test_cli_help_message():
    """Test if the CLI shows a help message."""
    # Run from anywhere, doesn't need a repo for --help
    result = subprocess.run(
        ["python", "-m", CLI_MODULE_PATH, "--help"], capture_output=True, text=True
    )
    assert "usage: cli.py" in result.stdout  # cli.py from argparse default prog name
    assert "--base-branch" in result.stdout
    assert result.returncode == 0


# --- Policy Violation Tests ---


def test_cli_branch_name_violation(temp_git_repo: Path):
    policy = {"branch_naming": {"pattern": "^feature/.+$", "enabled": True}}
    create_policy_file(temp_git_repo, policy)

    repo = git.Repo(temp_git_repo)
    repo.git.checkout("-b", "badbranchname")  # Does not match "feature/.+"
    (temp_git_repo / "f.txt").write_text("content")
    repo.index.add(["f.txt"])
    repo.index.commit("feat: some commit")

    result = run_cli(
        temp_git_repo, ["--base-branch", "main", "--head-branch", "badbranchname"]
    )
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 1
    assert "Branch name 'badbranchname' does not match" in result.stdout


def test_cli_commit_message_conventional_type_violation(temp_git_repo: Path):
    policy = {
        "commit_messages": {
            "conventional_commit": {"types": ["feat", "fix"], "enabled": True},
            "enabled": True,
        }
    }
    create_policy_file(temp_git_repo, policy)

    repo = git.Repo(temp_git_repo)
    repo.git.checkout("-b", "feature/test-conv-commit")
    (temp_git_repo / "f.txt").write_text("content")
    repo.index.add(["f.txt"])
    repo.index.commit("docs: this type is not allowed by policy")  # 'docs' not in types

    result = run_cli(
        temp_git_repo,
        ["--base-branch", "main", "--head-branch", "feature/test-conv-commit"],
    )
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 1
    assert "Type 'docs' is not one of the allowed types: feat, fix" in result.stdout


def test_cli_commit_message_missing_issue_violation(temp_git_repo: Path):
    policy = {
        "commit_messages": {
            "require_issue_number": {
                "pattern": "TASK-\\d+",
                "in_commit_body": True,
                "enabled": True,
            },
            "enabled": True,
        }
    }
    create_policy_file(temp_git_repo, policy)

    repo = git.Repo(temp_git_repo)
    repo.git.checkout("-b", "feature/test-issue")
    (temp_git_repo / "f.txt").write_text("content")
    repo.index.add(["f.txt"])
    repo.index.commit("feat: some work\n\nThis commit has no issue number in the body.")

    result = run_cli(
        temp_git_repo, ["--base-branch", "main", "--head-branch", "feature/test-issue"]
    )
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 1
    assert (
        "No issue number matching pattern 'TASK-\\d+' found in commit message body"
        in result.stdout
    )


def test_cli_disallowed_pattern_violation(temp_git_repo: Path):
    policy = {
        "disallowed_patterns": {
            "patterns": [
                {
                    "pattern": "DO_NOT_COMMIT",
                    "message": "Found forbidden string",
                    "enabled": True,
                }
            ],
            "enabled": True,
        }
    }
    create_policy_file(temp_git_repo, policy)

    repo = git.Repo(temp_git_repo)
    repo.git.checkout("-b", "feature/disallowed")
    (temp_git_repo / "secret_file.txt").write_text(
        "This file contains DO_NOT_COMMIT string."
    )
    repo.index.add(["secret_file.txt"])
    repo.index.commit("feat: add secret file")

    result = run_cli(
        temp_git_repo, ["--base-branch", "main", "--head-branch", "feature/disallowed"]
    )
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 1
    assert (
        "File 'secret_file.txt', line 1: Found forbidden string (Matched: 'DO_NOT_COMMIT')"
        in result.stdout
    )


def test_cli_file_size_violation(temp_git_repo: Path):
    policy = {"file_size": {"max_bytes": 100, "enabled": True}}  # Max 100 bytes
    create_policy_file(temp_git_repo, policy)

    repo = git.Repo(temp_git_repo)
    repo.git.checkout("-b", "feature/large-file")
    # Create a file larger than 100 bytes
    large_content = "a" * 200
    (temp_git_repo / "large_file.txt").write_text(large_content)
    repo.index.add(["large_file.txt"])
    repo.index.commit("feat: add large file")

    result = run_cli(
        temp_git_repo, ["--base-branch", "main", "--head-branch", "feature/large-file"]
    )
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 1
    assert (
        "File 'large_file.txt' (size: 200 bytes) exceeds maximum allowed size of 100 bytes"
        in result.stdout
    )


def test_cli_multiple_violations(temp_git_repo: Path):
    policy = {
        "branch_naming": {"pattern": "^feature/.+$", "enabled": True},
        "commit_messages": {
            "conventional_commit": {"types": ["feat"], "enabled": True},
            "enabled": True,
        },
        "file_size": {"max_bytes": 50, "enabled": True},
    }
    create_policy_file(temp_git_repo, policy)

    repo = git.Repo(temp_git_repo)
    # Branch name violation
    repo.git.checkout("-b", "fix/wrong-type-branch-for-policy")
    # File size violation + commit type violation
    (temp_git_repo / "big.txt").write_text(
        "This content is definitely more than fifty bytes long for sure."
    )
    repo.index.add(["big.txt"])
    repo.index.commit(
        "docs: add big file and wrong commit type"
    )  # 'docs' type violation

    result = run_cli(
        temp_git_repo,
        ["--base-branch", "main", "--head-branch", "fix/wrong-type-branch-for-policy"],
    )
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 1
    assert (
        "Branch name 'fix/wrong-type-branch-for-policy' does not match" in result.stdout
    )
    assert "Type 'docs' is not one of the allowed types: feat" in result.stdout
    assert (
        "File 'big.txt' (size: 68 bytes) exceeds maximum allowed size of 50 bytes"
        in result.stdout
    )
    assert "3 VIOLATION(S) FOUND" in result.stdout


def test_cli_no_new_commits(temp_git_repo: Path):
    """Test behavior when there are no new commits between base and head."""
    create_policy_file(temp_git_repo, {})  # Default policy

    repo = git.Repo(temp_git_repo)
    # main branch is already HEAD here as it's the only commit

    result = run_cli(temp_git_repo, ["--base-branch", "main", "--head-branch", "main"])
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)

    assert "No new commits found between main and main." in result.stdout
    assert (
        "ALL CHECKS PASSED" in result.stdout
    )  # No commits means no commit/file violations
    assert result.returncode == 0


def test_cli_non_existent_config_file(temp_git_repo: Path):
    result = run_cli(temp_git_repo, ["--config-file", "non_existent.yml"])
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode != 0  # Should be 3 based on cli.py
    assert (
        "Configuration file not found: non_existent.yml" in result.stderr
    )  # Error message to stderr


# More tests could include:
# - Invalid repo path
# - Invalid base/head branch names
# - Config file with invalid YAML structure
# - Config file with invalid Pydantic data (e.g., wrong types for policy values)
# - Behavior with detached HEAD state (if current branch check is important)
# - Tests for ignore_paths and ignore_extensions in file size policy
# - Tests for more complex disallowed patterns (e.g. case insensitive, multiline)
# - Tests for commits that are merges (how are they handled by get_commits_between and diffs)
# - Testing with unicode characters in branch names, commit messages, file names, file content
# - Testing various combinations of enabled/disabled policies in the config file
# - Testing specific edge cases for each policy (e.g. empty commit message, empty file)
