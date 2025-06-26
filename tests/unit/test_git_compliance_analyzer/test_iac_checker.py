import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from src.mcp_tools.git_compliance_analyzer.models import ComplianceFinding
from src.mcp_tools.git_compliance_analyzer.config import (
    IaCValidationRules,
    IaCValidationRuleItem,
)
from src.mcp_tools.git_compliance_analyzer.checkers import iac_checker


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def temp_repo_path(tmp_path: Path) -> Path:
    """Creates a dummy directory structure to simulate a repo for path checks."""
    repo_root = tmp_path / "test_repo_for_iac"
    repo_root.mkdir()
    (repo_root / "infra").mkdir()
    (repo_root / "modules" / "module_a").mkdir(parents=True)
    (repo_root / "infra" / "main.tf").touch()  # Dummy file for chdir target
    return repo_root


# --- Tests for run_iac_validation_command ---


def test_run_iac_validation_command_terraform_validate_success(
    mock_subprocess_run: MagicMock, temp_repo_path: Path
):
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Terraform validation successful."
    mock_process.stderr = ""
    mock_subprocess_run.return_value = mock_process

    rule = IaCValidationRuleItem(
        type="terraform_validate", paths=["infra"], severity="High", enabled=True
    )
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)

    assert not findings
    expected_cmd = ["terraform", "validate", "-no-color"]
    # Check that subprocess.run was called in the correct directory
    # The call object's args[0] is the command list, kwargs['cwd'] is the directory.
    # This is a bit tricky as os.chdir is used. We can check call_args.
    # For simplicity here, let's assume if it didn't error on path, chdir worked.
    # A more robust test might mock os.chdir and os.getcwd.
    mock_subprocess_run.assert_called_once_with(
        expected_cmd, capture_output=True, text=True, check=False
    )
    # To check CWD, you'd need to mock os.chdir and assert it was called with temp_repo_path / "infra"


def test_run_iac_validation_command_terraform_validate_failure(
    mock_subprocess_run: MagicMock, temp_repo_path: Path
):
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "Error: Invalid configuration."
    mock_subprocess_run.return_value = mock_process

    rule = IaCValidationRuleItem(
        type="terraform_validate", paths=["infra"], severity="High", enabled=True
    )
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "TERRAFORM_VALIDATE_FAILED"
    assert finding.severity == "High"
    assert "terraform validate' failed" in finding.message
    assert finding.file_path == "infra"
    assert "Error: Invalid configuration." in finding.details["stderr"]  # type: ignore


def test_run_iac_validation_command_cmd_not_found(
    mock_subprocess_run: MagicMock, temp_repo_path: Path
):
    mock_subprocess_run.side_effect = FileNotFoundError("terraform command not found")

    rule = IaCValidationRuleItem(
        type="terraform_validate", paths=["infra"], enabled=True
    )
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)

    assert len(findings) == 1
    assert findings[0].rule_id == "TERRAFORM_VALIDATE_CMD_NOT_FOUND"
    assert "command 'terraform' not found" in findings[0].message


def test_run_iac_validation_command_unknown_type(temp_repo_path: Path):
    rule = IaCValidationRuleItem(type="unknown_validator", paths=["."], enabled=True)
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)
    assert len(findings) == 1
    assert findings[0].rule_id == "IAC_VALIDATION_UNKNOWN_TYPE"


def test_run_iac_validation_command_path_not_dir(temp_repo_path: Path):
    rule = IaCValidationRuleItem(
        type="terraform_validate", paths=["infra/main.tf"], enabled=True
    )  # Path is a file
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)
    assert len(findings) == 1
    assert findings[0].rule_id == "IAC_VALIDATION_PATH_NOT_DIR"


def test_run_iac_validation_command_path_outside_repo(temp_repo_path: Path):
    # Create a path that tries to go outside. Use absolute path for outside.
    # Or relative like ../../outside_dir
    # The check is `repo_root_path not in check_dir_abs.parents and check_dir_abs != repo_root_path`
    # So, `../` from repo_root will fail this.
    rule = IaCValidationRuleItem(
        type="terraform_validate", paths=["../outside_repo_sim"], enabled=True
    )
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)
    assert len(findings) == 1
    assert findings[0].rule_id == "IAC_VALIDATION_PATH_OUTSIDE_REPO"


def test_run_iac_validation_command_rule_disabled(
    mock_subprocess_run: MagicMock, temp_repo_path: Path
):
    rule = IaCValidationRuleItem(
        type="terraform_validate", paths=["infra"], enabled=False
    )
    findings = iac_checker.run_iac_validation_command(temp_repo_path, rule)
    assert not findings
    mock_subprocess_run.assert_not_called()


# --- Tests for check_iac_validations (orchestrator) ---


def test_check_iac_validations_multiple_rules(
    mock_subprocess_run: MagicMock, temp_repo_path: Path
):
    # First rule success, second rule failure
    mock_success = MagicMock(returncode=0, stdout="Success", stderr="")
    mock_failure = MagicMock(returncode=1, stdout="", stderr="Failure in module_a")
    mock_subprocess_run.side_effect = [mock_success, mock_failure]

    rules_config = IaCValidationRules(
        rules=[
            IaCValidationRuleItem(
                type="terraform_validate",
                paths=["infra"],
                severity="High",
                enabled=True,
            ),
            IaCValidationRuleItem(
                type="terraform_validate",
                paths=["modules/module_a"],
                severity="Medium",
                enabled=True,
            ),
        ],
        enabled=True,
    )

    findings = iac_checker.check_iac_validations(str(temp_repo_path), rules_config)

    assert len(findings) == 1  # Only the failure should be reported
    assert findings[0].rule_id == "TERRAFORM_VALIDATE_FAILED"
    assert findings[0].file_path == "modules/module_a"
    assert "Failure in module_a" in findings[0].details["stderr"]  # type: ignore
    assert mock_subprocess_run.call_count == 2


def test_check_iac_validations_parent_rules_disabled(
    mock_subprocess_run: MagicMock, temp_repo_path: Path
):
    rules_config = IaCValidationRules(
        rules=[
            IaCValidationRuleItem(
                type="terraform_validate", paths=["infra"], enabled=True
            )
        ],
        enabled=False,
    )  # Parent group disabled

    findings = iac_checker.check_iac_validations(str(temp_repo_path), rules_config)
    assert not findings
    mock_subprocess_run.assert_not_called()


def test_check_iac_validations_invalid_repo_path():
    rules_config = IaCValidationRules(
        rules=[IaCValidationRuleItem(type="terraform_validate", paths=["."])],
        enabled=True,
    )
    findings = iac_checker.check_iac_validations(
        "/path/to/non_existent_repo_for_iac_check", rules_config
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "IAC_VALIDATION_REPO_PATH_INVALID"
    assert "Repository path for IaC validation is invalid" in findings[0].message
