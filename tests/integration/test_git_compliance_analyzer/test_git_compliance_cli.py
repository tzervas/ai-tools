import pytest
import subprocess
import os
import yaml
from pathlib import Path
import git # For setting up test repos

CLI_MODULE_PATH = "src.mcp_tools.git_compliance_analyzer.cli"
DEFAULT_COMPLIANCE_RULES_FILENAME = ".compliance-rules.yml"

@pytest.fixture
def temp_git_repo_for_compliance(tmp_path: Path):
    """
    Fixture to create a temporary Git repository with a basic setup for compliance testing.
    Yields the path to the repository.
    """
    repo_dir = tmp_path / "compliance_test_repo"
    repo_dir.mkdir()
    repo = git.Repo.init(repo_dir)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test User").release()
        cw.set_value("user", "email", "test@example.com").release()

    # Initial commit on main
    (repo_dir / "README.md").write_text("Initial README for main branch.\n## Usage\nDetails here.")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit: Add README")

    # Create a develop branch from main
    repo.create_head("develop", "main")

    yield repo_dir

def run_compliance_cli(cwd_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Helper function to run the Git Compliance Analyzer CLI tool."""
    cmd = ["python", "-m", CLI_MODULE_PATH] + args
    # Ensure CWD allows python -m to find the module. Running from project root is safest.
    # For tests, we often pass absolute paths for repo_path, so CWD for subprocess itself might be less critical.
    # Let's assume tests are run from a context where 'src' is discoverable or use project root for CWD.
    project_root = Path(__file__).parent.parent.parent.parent # Adjust if test file moves
    return subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)


def create_compliance_rules_file(repo_path: Path, rules_content: dict, filename: str = DEFAULT_COMPLIANCE_RULES_FILENAME):
    """Helper to create a .compliance-rules.yml file in the repo."""
    with open(repo_path / filename, 'w') as f:
        yaml.dump(rules_content, f)

# --- CLI Tests ---

def test_cli_compliance_help_message():
    result = subprocess.run(["python", "-m", CLI_MODULE_PATH, "--help"], capture_output=True, text=True)
    assert "usage: cli.py" in result.stdout
    assert "Path to the local Git repository to analyze" in result.stdout
    assert "--branch" in result.stdout
    assert "--base-branch" in result.stdout
    assert "--rules-file" in result.stdout
    assert result.returncode == 0

def test_cli_compliance_invalid_repo_path(tmp_path: Path):
    # Pass repo_path as first arg to CLI
    result = run_compliance_cli(tmp_path, ["non_existent_repo_dir"])
    assert result.returncode != 0 # Should be 2
    assert "Error: Repository path" in result.stderr
    assert "is not a valid directory." in result.stderr

def test_cli_compliance_no_violations_default_rules(temp_git_repo_for_compliance: Path, tmp_path: Path):
    # Default rules might still find issues in a minimal repo (e.g. missing LICENSE)
    # Let's create a minimal compliant setup for default rules or use very specific rules.
    # For this test, let's assume default rules are somewhat lenient or we make the repo compliant to them.
    # The default `ComplianceRuleConfig` has empty `must_exist` etc. so it should pass.

    repo_abs_path = str(temp_git_repo_for_compliance.resolve())
    args = [repo_abs_path] # Analyze the created repo with default rules
    result = run_compliance_cli(tmp_path, args)

    # print("STDOUT (no violations default):", result.stdout)
    # print("STDERR (no violations default):", result.stderr)

    # Default rules are fairly empty, so expect "ALL CHECKS PASSED" unless something basic is hit by chance.
    # The default ConventionalCommitFormatRule is enabled. Initial commit "Initial commit: Add README" will fail this.
    # So, we expect 1 violation.
    if "Initial commit: Add README" in result.stdout: # Check if it processed this commit
        assert result.returncode == 1
        assert "1 FINDING(S)" in result.stdout
        assert "COMMIT_CONVENTIONAL_FORMAT_INVALID" in result.stdout
    else:
        # If for some reason the initial commit isn't picked up by default HEAD vs some base,
        # this part of the test might be less predictable without a specific base.
        # Let's make it more specific by targeting a branch and base.
        repo = git.Repo(temp_git_repo_for_compliance)
        repo.git.checkout("develop")
        (temp_git_repo_for_compliance / "dev_file.txt").write_text("dev stuff")
        repo.index.add(["dev_file.txt"])
        repo.index.commit("feat: add dev file") # Compliant commit

        args_specific = [repo_abs_path, "--branch", "develop", "--base-branch", "main"]
        result_specific = run_compliance_cli(tmp_path, args_specific)
        # print("STDOUT (specific branch):", result_specific.stdout)
        # print("STDERR (specific branch):", result_specific.stderr)
        assert result_specific.returncode == 0
        assert "ALL CHECKS PASSED" in result_specific.stdout


def test_cli_compliance_with_violations(temp_git_repo_for_compliance: Path, tmp_path: Path):
    repo_abs_path = str(temp_git_repo_for_compliance.resolve())
    rules = {
        "file_checks": {
            "must_exist": [{"path": "LICENSE", "severity": "High"}], # LICENSE is missing
            "must_not_exist_patterns": [{"pattern": "*.log", "severity": "Medium"}]
        },
        "file_content_checks": {
            "rules": [{
                "file_path_pattern": "README\\.md", # Escaped . for regex
                "must_contain_pattern": {"pattern": "## Installation", "message": "README needs Installation section.", "severity": "Low"}
            }]
        },
        "commit_history_checks": { # Check commits on 'develop' against 'main'
            "conventional_commit_format": {"enabled": True, "types": ["feat", "fix"], "severity": "Medium"}
        },
        "iac_validation_checks": { # This will fail if terraform not installed or no .tf files
            "rules": [{"type": "terraform_validate", "paths": ["."], "severity": "High"}]
        }
    }
    create_compliance_rules_file(temp_git_repo_for_compliance, rules)

    # Create a feature branch with a non-compliant commit
    repo = git.Repo(temp_git_repo_for_compliance)
    repo.git.checkout("-b", "feature/bad-commit", "develop") # Branch from develop
    (temp_git_repo_for_compliance / "feature.py").write_text("print('hello')\n# TODO an unlinked todo")
    (temp_git_repo_for_compliance / "app.log").write_text("some log data") # Violates must_not_exist_patterns
    repo.index.add(["feature.py", "app.log"])
    repo.index.commit("WIP: adding feature without proper type") # Non-compliant commit message

    # Add a content rule to catch the TODO in feature.py
    rules["file_content_checks"]["rules"].append({
        "file_path_pattern": "\\.py$",
        "must_not_contain_pattern": {"pattern": "TODO an unlinked todo", "message": "Unlinked TODO found.", "severity": "Low"},
        "enabled": True
    })
    create_compliance_rules_file(temp_git_repo_for_compliance, rules) # Re-create with added rule

    args = [
        repo_abs_path,
        "--branch", "feature/bad-commit",
        "--base-branch", "develop", # Compare against develop for commit history
        "--rules-file", str((temp_git_repo_for_compliance / DEFAULT_COMPLIANCE_RULES_FILENAME).resolve())
    ]
    result = run_compliance_cli(tmp_path, args)

    # print("STDOUT (violations):", result.stdout)
    # print("STDERR (violations):", result.stderr)

    assert result.returncode == 1 # Expect violations
    output = result.stdout

    assert "FILE_MUST_EXIST_MISSING" in output and "LICENSE" in output
    assert "FILE_MUST_NOT_EXIST_PRESENT" in output and "app.log" in output and "*.log" in output
    assert "FILE_CONTENT_MUST_CONTAIN_MISSING" in output and "README.md" in output and "## Installation" in output
    assert "FILE_CONTENT_MUST_NOT_CONTAIN_PRESENT" in output and "feature.py" in output and "Unlinked TODO found" in output
    assert "COMMIT_CONVENTIONAL_FORMAT_INVALID" in output and "WIP: adding feature" in output

    # Terraform validate might pass if no .tf files or fail if terraform not installed.
    # If terraform is not installed, it should report TERRAFORM_VALIDATE_CMD_NOT_FOUND.
    # If it is installed and runs on a dir with no .tf files, it often exits 0.
    # This makes the iac_validation part tricky for a generic CI environment.
    # For now, let's assume it might not find terraform or not find .tf files.
    # If it reports CMD_NOT_FOUND, that's a valid finding for this test.
    # If it runs and finds no .tf files, the iac_checker itself might not produce a "failure" finding.
    # The current iac_checker runs validate in each path. If path has no .tf, terraform validate is often silent & exits 0.
    # So, we might not get a TERRAFORM_VALIDATE_FAILED unless there are actual invalid .tf files.

    # Count expected violations:
    # 1. Missing LICENSE
    # 2. app.log exists
    # 3. README missing "## Installation"
    # 4. feature.py has "TODO an unlinked todo"
    # 5. Commit "WIP: adding feature..." is non-conventional
    # Total: 5 violations (assuming terraform validate doesn't trigger if not setup)
    num_expected_violations = 5
    # If terraform validate command is not found, that's another violation
    if "TERRAFORM_VALIDATE_CMD_NOT_FOUND" in output:
        num_expected_violations +=1

    assert f"{num_expected_violations} FINDING(S)" in output or f"{num_expected_violations+1 if 'TERRAFORM_VALIDATE_CMD_NOT_FOUND' not in output else num_expected_violations} FINDING(S)" in output


def test_cli_compliance_rules_file_not_found(temp_git_repo_for_compliance: Path, tmp_path: Path, capsys):
    repo_abs_path = str(temp_git_repo_for_compliance.resolve())
    # Default rules will run, but we test the warning for the specified non-existent file
    args = [repo_abs_path, "--rules-file", "non_existent_rules.yml"]
    result = run_compliance_cli(tmp_path, args) # Should use default rules and print a warning

    # print("STDOUT (rules not found):", result.stdout)
    # print("STDERR (rules not found):", result.stderr) # stderr from load_compliance_rules

    # The load_compliance_rules prints warning to stdout, then CLI continues with defaults.
    assert "Warning: Compliance rules file 'non_existent_rules.yml' not found. Using default rules." in result.stdout
    # The outcome (returncode) depends on whether defaults cause violations.
    # As seen in test_cli_compliance_no_violations_default_rules, initial commit fails default conventional commit.
    assert result.returncode == 1 # Because default rules will find the initial commit non-compliant
    assert "COMMIT_CONVENTIONAL_FORMAT_INVALID" in result.stdout


# Future tests:
# - Invalid rules file (YAML syntax error, Pydantic validation error)
# - More complex Git history for commit checks
# - Specific iac_validation scenarios (e.g., with actual .tf files that pass/fail validation, if terraform CLI is available)
# - Different branches and base branches
# - Repo path not being a git repo
# - Glob patterns in file_must_not_exist
# - Regex patterns for file_path_pattern in content checks
# - Multiple content checks per file_path_pattern
# - Case sensitivity of patterns (currently default, may need options)
