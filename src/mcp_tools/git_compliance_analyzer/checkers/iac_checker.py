import subprocess
import os
from pathlib import Path
from typing import List, Optional

from ..models import ComplianceFinding
from ..config import IaCValidationRules, IaCValidationRuleItem

def run_iac_validation_command(
    repo_root_path: Path, # Absolute path to the root of the Git repository
    rule: IaCValidationRuleItem
) -> List[ComplianceFinding]:
    """
    Runs a configured IaC validation command (e.g., 'terraform validate').
    """
    findings: List[ComplianceFinding] = []
    if not rule.enabled:
        return findings

    if rule.type == "terraform_validate":
        command = ["terraform", "validate", "-no-color"]
        # Add "-json" in future if we want to parse structured output,
        # but that requires Terraform v0.15+ and changes how errors are reported.
        # For now, capture stdout/stderr as text.
    # Elif rule.type == "terrascan_run":
    #    command = ["terrascan", "scan", "-i", "terraform", "-p", "."] # Example
    else:
        findings.append(ComplianceFinding(
            rule_id="IAC_VALIDATION_UNKNOWN_TYPE",
            severity="Medium", # Or configurable
            message=f"Unknown IaC validation type specified in rule: '{rule.type}'.",
            details={"configured_rule_type": rule.type}
        ))
        return findings

    for relative_path_to_check in rule.paths:
        # Ensure path is within the repo and exists
        check_dir_abs = (repo_root_path / relative_path_to_check).resolve()

        # Security check: ensure check_dir_abs is still within repo_root_path
        if repo_root_path not in check_dir_abs.parents and check_dir_abs != repo_root_path:
            findings.append(ComplianceFinding(
                rule_id="IAC_VALIDATION_PATH_OUTSIDE_REPO",
                severity="High",
                message=f"IaC validation path '{relative_path_to_check}' resolves outside the repository root. Skipping.",
                file_path=str(relative_path_to_check)
            ))
            continue

        if not check_dir_abs.is_dir():
            findings.append(ComplianceFinding(
                rule_id="IAC_VALIDATION_PATH_NOT_DIR",
                severity="Medium",
                message=f"Path specified for IaC validation '{relative_path_to_check}' is not a directory or does not exist: {check_dir_abs}",
                file_path=str(relative_path_to_check)
            ))
            continue

        original_cwd = os.getcwd()
        try:
            os.chdir(check_dir_abs) # Run the command from within the target directory
            print(f"  Running '{' '.join(command)}' in '{check_dir_abs}'...")
            process = subprocess.run(command, capture_output=True, text=True, check=False) # check=False to handle non-zero exits

            if process.returncode != 0:
                findings.append(ComplianceFinding(
                    rule_id=f"{rule.type.upper()}_FAILED", # e.g., TERRAFORM_VALIDATE_FAILED
                    severity=rule.severity,
                    message=f"IaC validation command '{' '.join(command)}' failed in '{check_dir_abs}'. Exit code: {process.returncode}.",
                    file_path=str(relative_path_to_check), # Path relative to repo root
                    details={
                        "command": " ".join(command),
                        "stdout": process.stdout.strip(),
                        "stderr": process.stderr.strip(),
                        "exit_code": process.returncode
                    }
                ))
            # Even if returncode is 0, some tools might print warnings to stderr.
            # For now, only non-zero exit code is a failure.
            # Could add checks for specific output patterns if needed.

        except FileNotFoundError: # Command not found (e.g. terraform not in PATH)
             findings.append(ComplianceFinding(
                rule_id=f"{rule.type.upper()}_CMD_NOT_FOUND",
                severity="High",
                message=f"IaC validation command '{command[0]}' not found. Ensure it is installed and in PATH.",
                file_path=str(relative_path_to_check),
                details={"command_tried": command[0]}
            ))
        except Exception as e:
            findings.append(ComplianceFinding(
                rule_id=f"{rule.type.upper()}_EXECUTION_ERROR",
                severity="High",
                message=f"Error executing IaC validation command '{' '.join(command)}' in '{check_dir_abs}': {e}",
                file_path=str(relative_path_to_check)
            ))
        finally:
            os.chdir(original_cwd)

    return findings


def check_iac_validations(
    repo_root_path_str: str, # Path to the root of the Git repository being analyzed
    rules: IaCValidationRules
) -> List[ComplianceFinding]:
    """
    Runs all configured IaC validation checks.
    """
    findings: List[ComplianceFinding] = []
    if not rules.enabled or not rules.rules:
        return findings

    repo_root = Path(repo_root_path_str).resolve()
    if not repo_root.is_dir():
        findings.append(ComplianceFinding(
            rule_id="IAC_VALIDATION_REPO_PATH_INVALID",
            severity="High",
            message=f"Repository path for IaC validation is invalid or not a directory: {repo_root_path_str}",
        ))
        return findings

    for rule_item in rules.rules:
        findings.extend(run_iac_validation_command(repo_root, rule_item))

    return findings


if __name__ == '__main__':
    # This block requires a test setup where 'terraform' CLI is available
    # and a directory with sample .tf files exists.
    # Unit tests in dedicated test files with mocking subprocess will be more robust.
    print("IaC validation checker logic. Run unit tests for detailed checks.")

    # Conceptual example:
    # test_repo_path = Path("path/to/a/temp/git/repo/with/terraform/files").resolve()
    # if test_repo_path.exists() and test_repo_path.is_dir():
    #     # Create a dummy main.tf for terraform validate to work on
    #     # (test_repo_path / "infra").mkdir(exist_ok=True)
    #     # with open(test_repo_path / "infra" / "main.tf", "w") as f:
    #     #     f.write('resource "null_resource" "example" {}\n') # Valid TF
    #         # f.write('resource "null_resource" "example" { INVALID }\n') # Invalid TF

    #     mock_rules_config = IaCValidationRules(rules=[
    #         IaCValidationRuleItem(type="terraform_validate", paths=["infra"], severity="High", enabled=True)
    #     ], enabled=True)

    #     findings = check_iac_validations(str(test_repo_path), mock_rules_config)
    #     print("\nIaC Validation Findings:")
    #     for f in findings:
    #         print(f"  - {f}")
    #         if f.details:
    #             print(f"    Details - stdout: {f.details.get('stdout', '')}")
    #             print(f"    Details - stderr: {f.details.get('stderr', '')}")
    # else:
    #     print(f"Test repo path {test_repo_path} not found for example run.")
    pass
