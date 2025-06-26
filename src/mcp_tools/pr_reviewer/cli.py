"""
CLI for the Automated PR Review Helper tool.

Checks code changes in a Git repository against configurable policies for branch naming,
commit messages, disallowed file content, and file size. Intended to be run before creating a
Pull Request or as part of CI/CD pipelines.
"""

import argparse
import os
import sys
from typing import List

from .config import load_config, PolicyConfig  # noqa: F401, F403 # pylint: disable=W0718
from ..common.git_utils import GitUtils, GitRepoError  # noqa: F401, F403 # pylint: disable=W0718
from .policies import branch as branch_policies
from .policies import commit as commit_policies
from .policies import file as file_policies


def run_all_checks(
    config: PolicyConfig, git_utils: GitUtils, base_branch: str, head_branch: str
) -> List[str]:
    """
    Run all configured policy checks for a PR.

    This function orchestrates the following checks:
    - Branch naming policy (checks if the branch name matches configured patterns)
    - Commit message policies (conventional commit, issue number, etc.)
    - File policies (disallowed content patterns, file size limits)

    Args:
        config (PolicyConfig): The loaded policy configuration object.
        git_utils (GitUtils): Utility for interacting with the git repository.
        base_branch (str): The base branch for comparison (e.g., 'main').
        head_branch (str): The head branch to check (e.g., current feature branch, 'HEAD').

    Returns:
        List[str]: A list of all violation messages found during the checks.

    Notes:
        - If head_branch is specified and different from current, this logic might need adjustment.
        - For now, we assume we're checking the currently checked-out branch if it matches
        head_branch.
        - A more robust approach might be to derive branch name from head_ref if it's a branch ref.
        - If head_branch is 'HEAD', current_branch_name is fine. If head_branch is a specific
          branch name, use that.
        - If we can't get commits, we can't do commit/file checks based on them.
        - TODO: update to logging via DynEL
    """
    all_violations: List[str] = []
    print("\n--- Running PR Policy Checks ---")
    print(f"Comparing {head_branch} against {base_branch}")

    # Branch naming policy check
    if config.branch_naming.enabled:
        print("\nChecking branch naming policy..."
        current_branch_name = git_utils.get_current_branch_name()
        branch_to_check = head_branch
        if head_branch.upper() == "HEAD":
            branch_to_check = current_branch_name
        branch_violations = branch_policies.check_branch_name_policy(
            branch_to_check, config.branch_naming
        )
        if branch_violations:
            all_violations.extend(branch_violations)
            for v in branch_violations:
                print(f"  Violation: {v}")
        else:
            print("  Branch naming policy: OK")

    # Get commits and changed files for further checks
    commits_to_check: List[str] = []
    all_changed_filepaths_in_range: set[str] = set()
    try:
        commits_to_check = git_utils.get_commits_between(base_branch, head_branch)
        if not commits_to_check:
            print(
                f"\nNo new commits found between {base_branch} and {head_branch}. "
                "Skipping commit and file checks."
            )
        else:
            print(f"\nFound {len(commits_to_check)} new commit(s) to analyze.")
            all_changed_filepaths_in_range = git_utils.get_all_changed_files_in_range(
                base_branch, head_branch
            )
            print(
                f"Found {len(all_changed_filepaths_in_range)} unique changed files in this range."
            )

    except GitRepoError as e:
        all_violations.append(f"Error accessing Git data: {e}")
        print(f"  Error: Could not retrieve commits/files: {e}")

    # Commit message policy checks
    if config.commit_messages.enabled and commits_to_check:
        print("\nChecking commit message policies...")
        commit_policy_violated = False
        for i, commit_obj in enumerate(commits_to_check):
            commit_details = git_utils.get_commit_details(commit_obj)
            print(
                f"  Analyzing commit {i+1}/{len(commits_to_check)}: "
                f"{commit_details['sha'][:7]} - {commit_details['message_subject']}"
            )
            # TODO: Pass PR title/body if available and configured for issue number checks
            # pr_title = None
            # pr_body = None
            commit_msg_violations = commit_policies.check_commit_message_policies(
                commit_details, config.commit_messages
            )
            if commit_msg_violations:
                commit_policy_violated = True
                all_violations.extend(commit_msg_violations)
                for v in commit_msg_violations:
                    print(f"  Violation: {v}")
        if not commit_policy_violated:
            print("  Commit message policies: OK")

    # File policies (disallowed patterns, file size)
    # These checks are performed on each changed file at its state in the head_branch.
    if (
        config.disallowed_patterns.enabled or config.file_size.enabled
    ) and all_changed_filepaths_in_range:
        print("\nChecking file policies (content patterns, size)...")
        file_policy_violated = False


        def get_content_for_check(filepath: str) -> str:
            """
            Fetch file content from the head_branch state of the file.

            Args:
                filepath (str): Path to the file to fetch content for.
            Returns:
                str: The file content at the specified revision.
            """
            return git_utils.get_file_content_at_revision(filepath, revision=head_branch)


        def get_size_for_check(filepath: str) -> int:
            """
            Fetch file size from the head_branch state of the file.

            Args:
                filepath (str): Path to the file to fetch size for.
            Returns:
                int: The file size at the specified revision in bytes.
            """
            return git_utils.get_file_size_at_revision(filepath, revision=head_branch)

        for filepath in sorted(list(all_changed_filepaths_in_range)):
            file_specific_violations: List[str] = []
            if config.disallowed_patterns.enabled:
                pattern_violations = file_policies.check_content_disallowed_patterns(
                    filepath, get_content_for_check, config.disallowed_patterns
                )
                if pattern_violations:
                    file_specific_violations.extend(pattern_violations)
            if config.file_size.enabled:
                size_violations = file_policies.check_file_size_policy(
                    filepath, get_size_for_check, config.file_size
                )
                if size_violations:
                    file_specific_violations.extend(size_violations)
            if file_specific_violations:
                file_policy_violated = True
                all_violations.extend(file_specific_violations)
                for v_msg in file_specific_violations:
                    print(f"  Violation: {v_msg}")
        if not file_policy_violated:
            print("  File policies (content patterns, size): OK")
    return all_violations


def main() -> None:
    """
    Entry point for the PR Policy Review Tool CLI.

    Parses command-line arguments, loads configuration, runs all policy checks, and exits with
    appropriate status codes based on the results.

    Exits:
        0: All checks passed
        1: Policy violations found
        2: Git repository error
        3: Config file not found
        4: Config parsing/validation error
        5: Unexpected error
    """
    parser = argparse.ArgumentParser(
        description="PR Policy Review Tool: Checks code changes against configured policies."
    )
    parser.add_argument(
        "--base-branch",
        default="main",
        help="The base branch to compare against (e.g., main, develop). Default: 'main'.",
    )
    parser.add_argument(
        "--head-branch",
        default="HEAD",
        help=(
            "The head branch or revision to check (e.g., your feature branch, 'HEAD'). "
            "Default: 'HEAD'."
        ),
    )
    parser.add_argument(
        "--config-file",
        default=None,
        help=(
            "Path to the policy configuration YAML file. "
            "Defaults to searching for '.pr-policy.yml'."
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Path to the Git repository. Defaults to current working directory.",
    )
    args = parser.parse_args()
    try:
        print(f"Initializing repository at: {args.repo_path or os.getcwd()}")
        git_utils = GitUtils(repo_path=args.repo_path)

        print(
            f"Loading configuration (file: {args.config_file or 'auto-detect .pr-policy.yml'})..."
        )
        config = load_config(config_path=args.config_file)
        violations = run_all_checks(config, git_utils, args.base_branch, args.head_branch)
        if violations:
            print(f"\n--- Policy Check Summary: {len(violations)} VIOLATION(S) FOUND ---")
            sys.exit(1)
        else:
            print("\n--- Policy Check Summary: ALL CHECKS PASSED ---")
            sys.exit(0)
    except GitRepoError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(4)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    """
    To test this CLI:
    1. Ensure you are in a git repository.
    2. Create a feature branch with some commits off 'main' (or your default base).
       Try violating some policies (e.g., bad commit message, large file, disallowed pattern).
    3. Optionally create a .pr-policy.yml file.
    4. Run:
       python -m src.mcp_tools.pr_reviewer.cli --base-branch main --head-branch your-feature-branch
       (Adjust base/head branches as needed for your test repo)
       If src is in PYTHONPATH or you install the package, you might run it as a script.
    """
    main()
