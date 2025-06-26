from typing import List, Optional, Dict

from ..models import ComplianceFinding
from ..config import CommitHistoryRules, ConventionalCommitFormatRule
from ...common.git_utils import GitUtils, GitRepoError  # Common GitUtils
import re  # For CONVENTIONAL_COMMIT_REGEX

# Re-use or adapt the conventional commit regex from pr_reviewer if suitable.
# For now, define it here or import if pr_reviewer.policies.commit is made common.
CONVENTIONAL_COMMIT_REGEX = re.compile(
    r"^(?P<type>[a-zA-Z_]+)(?:\((?P<scope>[^\)]+)\))?(?P<breaking>!)?: (?P<subject>.+)$"
)


def check_commit_conventional_format_single(
    commit_sha: str, commit_subject: str, rule: ConventionalCommitFormatRule
) -> List[ComplianceFinding]:
    """Checks a single commit subject against conventional commit format rule."""
    findings: List[ComplianceFinding] = []
    if not rule.enabled:
        return findings

    match = CONVENTIONAL_COMMIT_REGEX.match(commit_subject)
    if not match:
        findings.append(
            ComplianceFinding(
                rule_id="COMMIT_CONVENTIONAL_FORMAT_INVALID",
                severity=rule.severity,
                message=f"Commit subject line does not follow Conventional Commits format (e.g., 'feat(scope): description').",
                commit_sha=commit_sha,
                details={"subject": commit_subject},
            )
        )
        return findings

    commit_type = match.group("type")
    if rule.types and commit_type not in rule.types:
        findings.append(
            ComplianceFinding(
                rule_id="COMMIT_CONVENTIONAL_TYPE_INVALID",
                severity=rule.severity,
                message=f"Commit type '{commit_type}' is not one of the allowed types: {', '.join(rule.types)}.",
                commit_sha=commit_sha,
                details={
                    "subject": commit_subject,
                    "type": commit_type,
                    "allowed_types": rule.types,
                },
            )
        )
    return findings


def check_commit_history(
    git_utils: GitUtils,
    base_revision: str,  # e.g., 'main' or 'develop'
    head_revision: str,  # e.g., 'HEAD' or current feature branch
    rules: CommitHistoryRules,
) -> List[ComplianceFinding]:
    """
    Checks commit history on the current branch against configured rules.
    Analyzes commits present in `head_revision` but not in `base_revision`.
    """
    findings: List[ComplianceFinding] = []
    if not rules.enabled:
        return findings

    try:
        commits_to_check = git_utils.get_commits_between(base_revision, head_revision)
    except GitRepoError as e:
        findings.append(
            ComplianceFinding(
                rule_id="GIT_COMMIT_HISTORY_ERROR",
                severity="High",  # This is a significant error for this check
                message=f"Error retrieving commit history between '{base_revision}' and '{head_revision}': {e}",
            )
        )
        return findings

    if not commits_to_check:
        # No commits to check, so no violations from these rules.
        return findings

    # Conventional Commit Format Check
    if rules.conventional_commit_format and rules.conventional_commit_format.enabled:
        for commit_obj in commits_to_check:
            commit_details = git_utils.get_commit_details(commit_obj)
            findings.extend(
                check_commit_conventional_format_single(
                    commit_sha=commit_details["sha"],
                    commit_subject=commit_details["message_subject"],
                    rule=rules.conventional_commit_format,
                )
            )

    # Future: Add other commit history checks here, e.g., presence of issue numbers
    # if rules.require_issue_in_commit and rules.require_issue_in_commit.enabled:
    #     # ... logic similar to pr_reviewer's issue number check ...
    #     pass

    return findings


if __name__ == "__main__":
    # This block requires a live Git repo or extensive GitUtils mocking.
    # Unit tests in dedicated test files are preferred.
    print("Commit history checker logic. Run unit tests for detailed checks.")

    # Conceptual example:
    # try:
    #     # Assume GitUtils is initialized for a test repo
    #     # utils = GitUtils("path/to/test/repo/with/history")
    #     # mock_rules = CommitHistoryRules(
    #     #     conventional_commit_format=ConventionalCommitFormatRule(
    #     #         enabled=True,
    #     #         types=["feat", "fix"],
    #     #         severity="Medium"
    #     #     ),
    #     #     enabled=True
    #     # )
    #     # # Assume 'main' and 'feature-branch' exist in the test repo
    #     # findings = check_commit_history(utils, "main", "feature-branch", mock_rules)
    #     # print("\nCommit History Findings:")
    #     # for f in findings: print(f"  - {f}")
    # except Exception as e:
    #     print(f"Error in commit_checker example: {e}")
    pass
