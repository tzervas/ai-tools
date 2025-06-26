import pytest
from unittest.mock import MagicMock

from src.mcp_tools.git_compliance_analyzer.models import ComplianceFinding
from src.mcp_tools.git_compliance_analyzer.config import (
    CommitHistoryRules,
    ConventionalCommitFormatRule,
)
from src.mcp_tools.git_compliance_analyzer.checkers import commit_checker
from src.mcp_tools.common.git_utils import GitUtils, GitRepoError  # Common GitUtils
from git import Commit as GitPythonCommit  # For mocking commit objects


@pytest.fixture
def mock_git_utils_commit_checker():
    mock = MagicMock(spec=GitUtils)
    mock.get_commits_between.return_value = []
    mock.get_commit_details.return_value = {}  # Default empty details
    return mock


@pytest.fixture
def conventional_commit_rule_default() -> ConventionalCommitFormatRule:
    return ConventionalCommitFormatRule(
        enabled=True, severity="Medium"
    )  # Uses default types


@pytest.fixture
def commit_history_rules_default(
    conventional_commit_rule_default: ConventionalCommitFormatRule,
) -> CommitHistoryRules:
    return CommitHistoryRules(
        conventional_commit_format=conventional_commit_rule_default, enabled=True
    )


# --- Tests for check_commit_conventional_format_single ---
@pytest.mark.parametrize(
    "subject, allowed_types, expected_violations, expected_rule_id",
    [
        ("feat: new stuff", ["feat", "fix"], 0, None),
        ("fix(scope): bug resolved", ["feat", "fix"], 0, None),
        ("docs!: breaking change in docs", ["docs", "feat"], 0, None),
        (
            "UnknownType: some work",
            ["feat", "fix"],
            1,
            "COMMIT_CONVENTIONAL_TYPE_INVALID",
        ),
        ("badformat no colon", ["feat"], 1, "COMMIT_CONVENTIONAL_FORMAT_INVALID"),
        (
            "feat: ",
            ["feat"],
            1,
            "COMMIT_CONVENTIONAL_FORMAT_INVALID",
        ),  # Empty subject after type
    ],
)
def test_check_commit_conventional_format_single(
    subject,
    allowed_types,
    expected_violations,
    expected_rule_id,
    conventional_commit_rule_default: ConventionalCommitFormatRule,
):
    rule = (
        conventional_commit_rule_default.copy(update={"types": allowed_types})
        if allowed_types
        else conventional_commit_rule_default
    )
    findings = commit_checker.check_commit_conventional_format_single(
        "sha123", subject, rule
    )
    assert len(findings) == expected_violations
    if expected_violations > 0:
        assert findings[0].rule_id == expected_rule_id
        assert findings[0].commit_sha == "sha123"


def test_check_commit_conventional_format_single_disabled(
    conventional_commit_rule_default: ConventionalCommitFormatRule,
):
    rule = conventional_commit_rule_default.copy(update={"enabled": False})
    findings = commit_checker.check_commit_conventional_format_single(
        "sha123", "anything goes", rule
    )
    assert not findings


# --- Tests for check_commit_history ---
def test_check_commit_history_no_commits(
    mock_git_utils_commit_checker: MagicMock,
    commit_history_rules_default: CommitHistoryRules,
):
    mock_git_utils_commit_checker.get_commits_between.return_value = (
        []
    )  # No commits in range
    findings = commit_checker.check_commit_history(
        mock_git_utils_commit_checker, "main", "HEAD", commit_history_rules_default
    )
    assert not findings


def test_check_commit_history_all_compliant(
    mock_git_utils_commit_checker: MagicMock,
    commit_history_rules_default: CommitHistoryRules,
):
    # Mock GitPython Commit objects (only need 'hexsha' for get_commit_details to be called with it)
    mock_commit1 = MagicMock(spec=GitPythonCommit)
    mock_commit1.hexsha = "commit1sha"
    mock_commit2 = MagicMock(spec=GitPythonCommit)
    mock_commit2.hexsha = "commit2sha"

    mock_git_utils_commit_checker.get_commits_between.return_value = [
        mock_commit1,
        mock_commit2,
    ]
    mock_git_utils_commit_checker.get_commit_details.side_effect = [
        {"sha": "commit1sha", "message_subject": "feat: first valid commit"},
        {"sha": "commit2sha", "message_subject": "fix(scope): second valid commit"},
    ]
    findings = commit_checker.check_commit_history(
        mock_git_utils_commit_checker, "main", "HEAD", commit_history_rules_default
    )
    assert not findings


def test_check_commit_history_some_non_compliant(
    mock_git_utils_commit_checker: MagicMock,
    commit_history_rules_default: CommitHistoryRules,
):
    mock_commit1 = MagicMock(spec=GitPythonCommit)
    mock_commit1.hexsha = "c1"
    mock_commit2 = MagicMock(spec=GitPythonCommit)
    mock_commit2.hexsha = "c2"
    mock_commit3 = MagicMock(spec=GitPythonCommit)
    mock_commit3.hexsha = "c3"

    mock_git_utils_commit_checker.get_commits_between.return_value = [
        mock_commit1,
        mock_commit2,
        mock_commit3,
    ]
    mock_git_utils_commit_checker.get_commit_details.side_effect = [
        {"sha": "c1", "message_subject": "feat: valid commit"},
        {"sha": "c2", "message_subject": "INVALID subject line"},  # Non-compliant
        {"sha": "c3", "message_subject": "chore(sub): also valid"},
    ]
    findings = commit_checker.check_commit_history(
        mock_git_utils_commit_checker, "main", "HEAD", commit_history_rules_default
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "COMMIT_CONVENTIONAL_FORMAT_INVALID"
    assert findings[0].commit_sha == "c2"


def test_check_commit_history_rules_disabled(
    mock_git_utils_commit_checker: MagicMock,
    commit_history_rules_default: CommitHistoryRules,
):
    rules_disabled = commit_history_rules_default.copy(update={"enabled": False})
    # Setup some commits that would normally fail
    mock_commit1 = MagicMock(spec=GitPythonCommit)
    mock_commit1.hexsha = "c1"
    mock_git_utils_commit_checker.get_commits_between.return_value = [mock_commit1]
    mock_git_utils_commit_checker.get_commit_details.return_value = {
        "sha": "c1",
        "message_subject": "bad commit",
    }

    findings = commit_checker.check_commit_history(
        mock_git_utils_commit_checker, "main", "HEAD", rules_disabled
    )
    assert not findings


def test_check_commit_history_conventional_commit_rule_disabled(
    mock_git_utils_commit_checker: MagicMock,
    commit_history_rules_default: CommitHistoryRules,
):
    # Disable just the conventional_commit_format sub-rule
    rules_sub_disabled = commit_history_rules_default.copy(deep=True)
    rules_sub_disabled.conventional_commit_format.enabled = False  # type: ignore

    mock_commit1 = MagicMock(spec=GitPythonCommit)
    mock_commit1.hexsha = "c1"
    mock_git_utils_commit_checker.get_commits_between.return_value = [mock_commit1]
    mock_git_utils_commit_checker.get_commit_details.return_value = {
        "sha": "c1",
        "message_subject": "bad commit",
    }

    findings = commit_checker.check_commit_history(
        mock_git_utils_commit_checker, "main", "HEAD", rules_sub_disabled
    )
    assert not findings


def test_check_commit_history_git_error(
    mock_git_utils_commit_checker: MagicMock,
    commit_history_rules_default: CommitHistoryRules,
):
    mock_git_utils_commit_checker.get_commits_between.side_effect = GitRepoError(
        "Failed to get commits"
    )
    findings = commit_checker.check_commit_history(
        mock_git_utils_commit_checker, "main", "HEAD", commit_history_rules_default
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "GIT_COMMIT_HISTORY_ERROR"
    assert "Error retrieving commit history" in findings[0].message
