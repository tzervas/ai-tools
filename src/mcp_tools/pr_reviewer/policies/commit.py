"""
Policies for validating commit messages in PR Reviewer tools.

This module provides functions to check commit messages for compliance with Conventional Commits
and issue number requirements, as well as utilities for integrating with future PR context features.
"""

# flake8: noqa
from typing import List, Pattern, Optional, Dict, Tuple  # noqa: F401,F403 # pylint: disable=W0611

try:
    # Relative import for development and when run as part of a package
    from ..config import (
        CommitMessagePolicy,
        ConventionalCommitPolicy,
        RequireIssueNumberPolicy,
    )
except ImportError:
    # Fallback to absolute import for packaged/production use
    from mcp_tools.pr_reviewer.policies.config import (
        CommitMessagePolicy,
        ConventionalCommitPolicy,
        RequireIssueNumberPolicy,
    )
import re

CONVENTIONAL_COMMIT_REGEX = re.compile(
    r"^(?P<type>[a-zA-Z_]+)(?:\((?P<scope>[^\)]+)\))?(?P<breaking>!)?: (?P<subject>.+)$"
)


def check_conventional_commit_format(
    commit_subject: str,  # The first line of the commit message
    commit_sha: str,  # For context in violation messages
    policy: ConventionalCommitPolicy,
) -> List[str]:
    """
    Checks if the commit subject line adheres to Conventional Commits format.
    Example: feat(scope)!: broadcast errors

    Args:
        commit_subject: The first line of the commit message.
        commit_sha: SHA of the commit for error reporting.
        policy: The ConventionalCommitPolicy configuration.

    Returns:
        A list of violation messages. Empty if no violations.
    """
    violations: List[str] = []
    if not policy.enabled:
        return violations

    match = CONVENTIONAL_COMMIT_REGEX.match(commit_subject)
    if not match:
        violations.append(
            f"Commit {commit_sha[:7]}: Subject line '{commit_subject}' does not follow "
            "Conventional Commits format (e.g., 'feat(scope): description' or 'fix: description')."
        )
        return violations  # No further checks if basic format fails

    commit_type = match.group("type")
    if policy.types and commit_type not in policy.types:
        violations.append(
            f"Commit {commit_sha[:7]}: Type '{commit_type}' is not one of the allowed types: "
            f"{', '.join(policy.types)}."
        )

    # Could add more checks: scope format, subject length, presence of body for breaking change,
    # etc. For now, focusing on type and basic structure.

    return violations


def check_commit_for_issue_number(
    commit_message_body: str,  # Full commit message body (excluding subject, or full message)
    pr_title: Optional[str],  # Placeholder for future use  # noqa: ARG001
    pr_body: Optional[str],  # Placeholder for future use  # noqa: ARG001
    commit_sha: str,  # For context in violation messages
    policy: RequireIssueNumberPolicy,
) -> List[str]:
    """
    Checks if the commit message body (or future PR title/body) contains an issue number.

    Args:
        commit_message_body: The body of the commit message.
        pr_title: The title of the Pull Request (currently unused).
        pr_body: The body of the Pull Request (currently unused).
        commit_sha: SHA of the commit for error reporting.
        policy: The RequireIssueNumberPolicy configuration.

    Returns:
        A list of violation messages. Empty if no violations.
    """
    violations: List[str] = []
    if not policy.enabled or not policy.pattern:
        return violations

    text_to_check: List[Tuple[str, str]] = []  # List of (text_source_name, text_content)

    if policy.in_commit_body:
        text_to_check.append(("commit message body", commit_message_body))
    # Future:
    # if policy.in_pr_title and pr_title:
    #     text_to_check.append(("PR title", pr_title))
    # if policy.in_pr_body and pr_body:
    #     text_to_check.append(("PR body", pr_body))

    found_in_any = False
    for source_name, text_content in text_to_check:
        if policy.pattern.search(text_content):
            found_in_any = True
            break

    if not text_to_check:  # No sources configured to check
        # This could be a warning if policy is enabled but no locations are selected.
        # For now, treat as no violation.
        pass
    elif not found_in_any:
        checked_sources = ", ".join([name for name, _ in text_to_check])
        violations.append(
            f"Commit {commit_sha[:7]}: No issue number matching pattern "
            f"'{policy.pattern.pattern}' found in {checked_sources}."
        )

    return violations


def check_commit_message_policies(
    commit_details: Dict,  # As returned by GitUtils.get_commit_details
    policy: CommitMessagePolicy,
    # pr_title: Optional[str] = None, # For future PR context
    # pr_body: Optional[str] = None   # For future PR context
) -> List[str]:
    """
    Runs all configured commit message policies for a single commit.
    """
    violations: List[str] = []
    if not policy.enabled:
        return violations

    commit_sha = commit_details.get("sha", "UnknownSHA")
    commit_subject = commit_details.get("message_subject", "")
    commit_body = commit_details.get("message_body", "")  # Full message body after subject

    # Conventional Commit Check
    if policy.conventional_commit.enabled:
        violations.extend(
            check_conventional_commit_format(commit_subject, commit_sha, policy.conventional_commit)
        )

    # Require Issue Number Check
    if policy.require_issue_number.enabled:
        violations.extend(
            check_commit_for_issue_number(
                commit_message_body=commit_body,  # commit_details.get("message", "") for full msg
                pr_title=None,  # Placeholder
                pr_body=None,  # Placeholder
                commit_sha=commit_sha,
                policy=policy.require_issue_number,
            )
        )

    return violations
