import argparse
import os
import sys
from pathlib import Path
from typing import List

from .config import load_compliance_rules, ComplianceRuleConfig
from .models import ComplianceFinding
from ..common.git_utils import GitUtils, GitRepoError  # Common GitUtils

# Import checker modules
from .checkers import file_checker
from .checkers import commit_checker
from .checkers import iac_checker


def run_all_compliance_checks(
    config: ComplianceRuleConfig,
    git_utils: GitUtils,
    repo_path: Path,  # Absolute path to repo root
    target_branch_or_rev: str,  # For file/content checks at a specific state
    base_branch_for_commit_history: Optional[str],  # For commit history comparison
) -> List[ComplianceFinding]:
    """
    Runs all configured compliance checks.
    """
    all_findings: List[ComplianceFinding] = []
    print(f"\n--- Running Git Compliance Analyzer ---")
    print(f"Target Repository: {repo_path}")
    print(f"Analyzing state at revision: {target_branch_or_rev}")
    if base_branch_for_commit_history:
        print(
            f"Commit history will be compared against: {base_branch_for_commit_history}"
        )

    # 1. File Existence Checks
    if config.file_checks and config.file_checks.enabled:
        print("\nChecking file existence policies...")
        findings = file_checker.check_file_existence(
            git_utils, target_branch_or_rev, config.file_checks
        )
        if findings:
            all_findings.extend(findings)
            # for f in findings: print(f"  Finding: {f}") # Detailed printing later
        else:
            print("  File existence policies: OK")

    # 2. File Content Checks
    if config.file_content_checks and config.file_content_checks.enabled:
        print("\nChecking file content policies...")
        findings = file_checker.check_file_content(
            git_utils, target_branch_or_rev, config.file_content_checks
        )
        if findings:
            all_findings.extend(findings)
        else:
            print("  File content policies: OK")

    # 3. Commit History Checks
    if (
        config.commit_history_checks
        and config.commit_history_checks.enabled
        and base_branch_for_commit_history
    ):
        print("\nChecking commit history policies...")
        findings = commit_checker.check_commit_history(
            git_utils,
            base_branch_for_commit_history,
            target_branch_or_rev,  # Usually current branch HEAD for commit history
            config.commit_history_checks,
        )
        if findings:
            all_findings.extend(findings)
        else:
            print("  Commit history policies: OK")
    elif (
        config.commit_history_checks
        and config.commit_history_checks.enabled
        and not base_branch_for_commit_history
    ):
        print("\nSkipping commit history checks: --base-branch not provided.")

    # 4. IaC Validation Checks
    if config.iac_validation_checks and config.iac_validation_checks.enabled:
        print("\nChecking IaC validation policies...")
        # iac_checker needs the absolute path to the repo root to correctly chdir
        findings = iac_checker.check_iac_validations(
            str(repo_path), config.iac_validation_checks
        )
        if findings:
            all_findings.extend(findings)
        else:
            print(
                "  IaC validation policies: OK (or no relevant rules triggered errors)"
            )

    return all_findings


def main():
    parser = argparse.ArgumentParser(description="Git Repository Compliance Analyzer.")
    parser.add_argument(
        "repo_path",
        type=str,
        nargs="?",
        default=".",
        help="Path to the local Git repository to analyze (default: current directory).",
    )
    parser.add_argument(
        "--branch",
        "-b",
        type=str,
        default="HEAD",
        help="The branch, tag, or commit SHA to analyze the state of (default: HEAD).",
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        default=None,  # e.g. main, develop
        help="The base branch for commit history comparison. If not set, commit history checks are skipped.",
    )
    parser.add_argument(
        "--rules-file",
        default=None,
        help="Path to the compliance rules configuration YAML file. Defaults to searching for '.compliance-rules.yml'.",
    )

    args = parser.parse_args()

    repo_abs_path = Path(args.repo_path).resolve()

    if not repo_abs_path.is_dir():
        print(
            f"Error: Repository path '{repo_abs_path}' is not a valid directory.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        git_utils = GitUtils(
            repo_path=str(repo_abs_path)
        )  # GitUtils handles search_parent_dirs
        # Verify it's a git repo by trying a simple operation, or let GitUtils constructor handle it
        # print(f"Successfully initialized Git repo at: {git_utils.repo.working_dir}")
    except GitRepoError as e:
        print(
            f"Error initializing Git repository at '{repo_abs_path}': {e}",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:  # Catch other potential GitPython errors
        print(f"Unexpected Git error for path '{repo_abs_path}': {e}", file=sys.stderr)
        sys.exit(2)

    print(
        f"Loading compliance rules (file: {args.rules_file or 'auto-detect .compliance-rules.yml'})..."
    )
    try:
        rules_config = load_compliance_rules(config_path=args.rules_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading compliance rules: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"An unexpected error occurred while loading rules: {e}", file=sys.stderr)
        sys.exit(3)

    all_findings = run_all_compliance_checks(
        rules_config,
        git_utils,
        repo_abs_path,
        args.branch,  # target_branch_or_rev
        args.base_branch,  # base_branch_for_commit_history
    )

    if all_findings:
        print(f"\n--- Compliance Analyzer Summary: {len(all_findings)} FINDING(S) ---")
        # Sort by severity (High > Medium > Low > Informational) then by other fields for consistent output
        severity_order = {"High": 0, "Medium": 1, "Low": 2, "Informational": 3}
        sorted_findings = sorted(
            all_findings,
            key=lambda f: (
                severity_order.get(f.severity, 99),
                f.rule_id,
                f.file_path or "",
                f.commit_sha or "",
            ),
        )
        for i, finding in enumerate(sorted_findings, 1):
            print(
                f"\nFinding {i}/{len(all_findings)}: {str(finding)}"
            )  # Uses ComplianceFinding.__str__
            if finding.details:
                print(f"  Details: {finding.details}")
        sys.exit(1)
    else:
        print(
            "\n--- Compliance Analyzer Summary: ALL CHECKS PASSED (or no relevant rules triggered) ---"
        )
        sys.exit(0)


if __name__ == "__main__":
    # To test this CLI:
    # 1. Set up a test Git repository with various conditions to check.
    #    (e.g., missing LICENSE, files with "TODO"s, specific commit messages, dummy .tf files)
    # 2. Optionally, create a .compliance-rules.yml file in that repo or specify one with --rules-file.
    # 3. Run from the project root (or ensure src is in PYTHONPATH):
    #    python -m src.mcp_tools.git_compliance_analyzer.cli /path/to/your/test_repo --branch main --base-branch develop
    #    (Adjust paths and branches as needed)
    main()
