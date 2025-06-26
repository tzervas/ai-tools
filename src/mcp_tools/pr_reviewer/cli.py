import argparse
import os
import sys
from typing import List

from .config import load_config, PolicyConfig
from .git_utils import GitUtils, GitRepoError
from .policies import branch as branch_policies
from .policies import commit as commit_policies
from .policies import file as file_policies


def run_all_checks(
    config: PolicyConfig, git_utils: GitUtils, base_branch: str, head_branch: str
) -> List[str]:
    """
    Runs all configured policy checks.

    Args:
        config: The loaded PolicyConfig.
        git_utils: An instance of GitUtils.
        base_branch: The base branch for comparison (e.g., 'main').
        head_branch: The head branch to check (e.g., current feature branch, 'HEAD').

    Returns:
        A list of all violation messages.
    """
    all_violations: List[str] = []
    print(f"\n--- Running PR Policy Checks ---")
    print(f"Comparing {head_branch} against {base_branch}")

    # 1. Branch Naming Policy Check
    if config.branch_naming.enabled:
        print("\nChecking branch naming policy...")
        current_branch_name = (
            git_utils.get_current_branch_name()
        )  # Assumes head_branch is the current one
        # If head_branch is specified and different from current, this logic might need adjustment
        # For now, let's assume we're checking the currently checked-out branch if it matches head_branch.
        # A more robust approach might be to derive branch name from head_ref if it's a branch ref.
        # For now, if head_branch is 'HEAD', current_branch_name is fine.
        # If head_branch is a specific branch name, use that.
        branch_to_check = head_branch
        if (
            head_branch.upper() == "HEAD"
        ):  # get_current_branch_name handles detached HEAD
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
    commits_to_check = []
    all_changed_filepaths_in_range: set[str] = set()
    try:
        commits_to_check = git_utils.get_commits_between(base_branch, head_branch)
        if not commits_to_check:
            print(
                f"\nNo new commits found between {base_branch} and {head_branch}. Skipping commit and file checks."
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
        # Depending on severity, we might want to stop or continue if possible
        # For now, if we can't get commits, we can't do commit/file checks based on them.

    # 2. Commit Message Policy Checks
    if config.commit_messages.enabled and commits_to_check:
        print("\nChecking commit message policies...")
        commit_policy_violated = False
        for i, commit_obj in enumerate(commits_to_check):
            commit_details = git_utils.get_commit_details(commit_obj)
            # print(f"  Analyzing commit {i+1}/{len(commits_to_check)}: {commit_details['sha'][:7]} - {commit_details['message_subject']}")

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

    # 3. File Policies (Disallowed Patterns, File Size)
    # These checks are performed on each changed file at its state in the head_branch.
    if (
        config.disallowed_patterns.enabled or config.file_size.enabled
    ) and all_changed_filepaths_in_range:
        print("\nChecking file policies (content patterns, size)...")
        file_policy_violated = False

        # Create callables for policy checkers to get content/size
        # These will fetch content/size from the head_branch state of the file
        def get_content_for_check(filepath: str):
            return git_utils.get_file_content_at_revision(
                filepath, revision=head_branch
            )

        def get_size_for_check(filepath: str):
            return git_utils.get_file_size_at_revision(filepath, revision=head_branch)

        for filepath in sorted(list(all_changed_filepaths_in_range)):
            # print(f"  Analyzing file: {filepath}")
            file_specific_violations = []
            # Disallowed Patterns Check
            if config.disallowed_patterns.enabled:
                pattern_violations = file_policies.check_content_disallowed_patterns(
                    filepath, get_content_for_check, config.disallowed_patterns
                )
                if pattern_violations:
                    file_specific_violations.extend(pattern_violations)

            # File Size Check
            if config.file_size.enabled:
                size_violations = file_policies.check_file_size_policy(
                    filepath, get_size_for_check, config.file_size
                )
                if size_violations:
                    file_specific_violations.extend(size_violations)

            if file_specific_violations:
                file_policy_violated = True
                all_violations.extend(file_specific_violations)
                # Violations already include filepath, so just print them
                for v_msg in file_specific_violations:
                    print(f"  Violation: {v_msg}")

        if not file_policy_violated:
            print("  File policies (content patterns, size): OK")

    return all_violations


def main():
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
        help="The head branch or revision to check (e.g., your feature branch, 'HEAD'). Default: 'HEAD'.",
    )
    parser.add_argument(
        "--config-file",
        default=None,
        help=f"Path to the policy configuration YAML file. Defaults to searching for '.pr-policy.yml'.",
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

        violations = run_all_checks(
            config, git_utils, args.base_branch, args.head_branch
        )

        if violations:
            print(
                f"\n--- Policy Check Summary: {len(violations)} VIOLATION(S) FOUND ---"
            )
            # for i, v in enumerate(violations, 1):
            #     print(f"{i}. {v}")
            sys.exit(1)  # Exit with non-zero code if violations are found
        else:
            print("\n--- Policy Check Summary: ALL CHECKS PASSED ---")
            sys.exit(0)

    except GitRepoError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:  # For config file
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)
    except ValueError as e:  # For config parsing/validation errors
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(4)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    # To test this CLI:
    # 1. Ensure you are in a git repository.
    # 2. Create a feature branch with some commits off 'main' (or your default base).
    #    - Try violating some policies (e.g., bad commit message, large file, disallowed pattern).
    # 3. Optionally create a .pr-policy.yml file.
    # 4. Run: python -m src.mcp_tools.pr_reviewer.cli --base-branch main --head-branch your-feature-branch
    #    (Adjust base/head branches as needed for your test repo)
    #    If src is in PYTHONPATH or you install the package, you might run it as a script.
    main()
