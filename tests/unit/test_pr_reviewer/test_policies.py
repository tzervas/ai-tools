import pytest
import re
from typing import Optional, AnyStr, List, Pattern

# Adjust import paths based on test execution context
from src.mcp_tools.pr_reviewer.config import (
    BranchNamingPolicy,
    CommitMessagePolicy,
    ConventionalCommitPolicy,
    RequireIssueNumberPolicy,
    DisallowedPatternsPolicy,
    DisallowedPatternItem,
    FileSizePolicy,
)
from src.mcp_tools.pr_reviewer.policies import branch as branch_policies
from src.mcp_tools.pr_reviewer.policies import commit as commit_policies
from src.mcp_tools.pr_reviewer.policies import file as file_policies

# --- Tests for branch policies ---


def test_check_branch_name_policy_valid():
    policy = BranchNamingPolicy(pattern="^(feat|fix)/[a-z0-9-]+$", enabled=True)
    assert branch_policies.check_branch_name_policy("feat/new-stuff-123", policy) == []


def test_check_branch_name_policy_invalid():
    pattern_str = "^(feat|fix)/[a-z0-9-]+$"
    policy = BranchNamingPolicy(pattern=pattern_str, enabled=True)
    violations = branch_policies.check_branch_name_policy("Feature/InvalidName", policy)
    assert len(violations) == 1
    assert f"does not match the required pattern: '{pattern_str}'" in violations[0]


def test_check_branch_name_policy_disabled():
    policy = BranchNamingPolicy(pattern="^valid/.+$", enabled=False)
    assert branch_policies.check_branch_name_policy("anything/goes", policy) == []


def test_check_branch_name_policy_detached_head():
    policy = BranchNamingPolicy(pattern="^valid/.+$", enabled=True)
    violations = branch_policies.check_branch_name_policy(None, policy)
    assert len(violations) == 1
    assert "Branch name could not be determined" in violations[0]


# --- Tests for commit policies ---


@pytest.mark.parametrize(
    "subject, types, is_valid",
    [
        ("feat: add new feature", ["feat", "fix"], True),
        ("fix(scope): resolve bug", ["feat", "fix"], True),
        ("docs!: update README with breaking change", ["docs", "feat"], True),
        ("Chore: update dependencies", ["chore"], False),  # Case-sensitive type
        ("chore: update dependencies", ["chore"], True),
        ("unknown: some work", ["feat", "fix"], False),  # Unknown type
        ("feat resolve bug without colon", ["feat"], False),  # Missing colon and space
        ("feat(scope) missing colon space", ["feat"], False),
        ("feat: ", ["feat"], False),  # Empty subject
    ],
)
def test_check_conventional_commit_format(subject, types, is_valid):
    policy = ConventionalCommitPolicy(enabled=True, types=types)
    violations = commit_policies.check_conventional_commit_format(
        subject, "sha123", policy
    )
    if is_valid:
        assert (
            not violations
        ), f"Expected no violations for '{subject}' with types {types}"
    else:
        assert violations, f"Expected violations for '{subject}' with types {types}"


def test_check_conventional_commit_format_disabled():
    policy = ConventionalCommitPolicy(enabled=False, types=["feat"])
    violations = commit_policies.check_conventional_commit_format(
        "anything goes", "sha123", policy
    )
    assert not violations


@pytest.mark.parametrize(
    "body, pattern_str, pr_title, pr_body, in_commit_body, expected_violations_count",
    [
        ("Fixes TICKET-123", r"TICKET-\d+", None, None, True, 0),
        ("Related to task [PROJ-001]", r"\[PROJ-\d+\]", None, None, True, 0),
        ("No ticket here.", r"TICKET-\d+", None, None, True, 1),
        (
            "Body has TICKET-123",
            r"TICKET-\d+",
            None,
            None,
            False,
            0,
        ),  # Policy check for body disabled
        # Future tests for PR title/body would go here
    ],
)
def test_check_commit_for_issue_number(
    body, pattern_str, pr_title, pr_body, in_commit_body, expected_violations_count
):
    policy = RequireIssueNumberPolicy(
        pattern=pattern_str, in_commit_body=in_commit_body, enabled=True
    )
    violations = commit_policies.check_commit_for_issue_number(
        body, pr_title, pr_body, "sha123", policy
    )
    assert len(violations) == expected_violations_count


def test_check_commit_for_issue_number_disabled():
    policy = RequireIssueNumberPolicy(pattern=r"TICKET-\d+", enabled=False)
    violations = commit_policies.check_commit_for_issue_number(
        "No ticket needed", None, None, "sha123", policy
    )
    assert not violations


def test_check_commit_message_policies_orchestration():
    commit_details = {
        "sha": "testsha",
        "message_subject": "badtype: this is a test",
        "message_body": "This commit has no ticket reference.",
    }
    policy = CommitMessagePolicy(
        conventional_commit=ConventionalCommitPolicy(
            enabled=True, types=["feat", "fix"]
        ),
        require_issue_number=RequireIssueNumberPolicy(
            pattern=r"TICKET-\d+", in_commit_body=True, enabled=True
        ),
        enabled=True,
    )
    violations = commit_policies.check_commit_message_policies(commit_details, policy)
    assert len(violations) == 2  # One for bad type, one for missing ticket
    assert any(
        "Type 'badtype' is not one of the allowed types" in v for v in violations
    )
    assert any("No issue number matching pattern" in v for v in violations)


# --- Tests for file policies ---

# Mock file content getter for content tests
mock_file_contents = {
    "secrets.py": "API_KEY = '12345'\nPASSWORD = \"secret\"\nOTHER_VAR='ok'",
    "clean.txt": "This file is clean.",
    "binary.data": b"\x00\x01\x02SECRET_KEY",  # Will be skipped by content check
    "utf8_error.txt": b"Invalid \xff UTF-8",  # Will be skipped
}


def mock_get_file_content(filepath: str) -> Optional[AnyStr]:
    return mock_file_contents.get(filepath)


@pytest.mark.parametrize(
    "filepath, patterns_config, expected_violations_count, expected_messages_contain",
    [
        (
            "secrets.py",
            [DisallowedPatternItem(pattern="API_KEY\\s*=", enabled=True)],
            1,
            ["API_KEY"],
        ),
        (
            "secrets.py",
            [DisallowedPatternItem(pattern="PASSWORD\\s*=", enabled=True)],
            1,
            ["PASSWORD"],
        ),
        (
            "secrets.py",
            [
                DisallowedPatternItem(pattern="API_KEY\\s*=", enabled=True),
                DisallowedPatternItem(pattern="PASSWORD\\s*=", enabled=True),
            ],
            2,
            ["API_KEY", "PASSWORD"],
        ),
        ("clean.txt", [DisallowedPatternItem(pattern="SECRET", enabled=True)], 0, []),
        (
            "secrets.py",
            [DisallowedPatternItem(pattern="API_KEY", enabled=False)],
            0,
            [],
        ),  # Disabled pattern
        (
            "binary.data",
            [DisallowedPatternItem(pattern="SECRET_KEY", enabled=True)],
            0,
            [],
        ),  # Binary skipped
        (
            "utf8_error.txt",
            [DisallowedPatternItem(pattern="Invalid", enabled=True)],
            0,
            [],
        ),  # UTF-8 error skipped
    ],
)
def test_check_content_disallowed_patterns(
    filepath, patterns_config, expected_violations_count, expected_messages_contain
):
    policy = DisallowedPatternsPolicy(patterns=patterns_config, enabled=True)
    violations = file_policies.check_content_disallowed_patterns(
        filepath, mock_get_file_content, policy
    )
    assert len(violations) == expected_violations_count
    for msg_part in expected_messages_contain:
        assert any(
            msg_part in v for v in violations
        ), f"Expected part '{msg_part}' not in violations: {violations}"


def test_check_content_disallowed_patterns_disabled():
    policy = DisallowedPatternsPolicy(
        patterns=[DisallowedPatternItem(pattern="SECRET", enabled=True)], enabled=False
    )
    violations = file_policies.check_content_disallowed_patterns(
        "secrets.py", mock_get_file_content, policy
    )
    assert not violations


# Mock file size getter for size tests
mock_file_sizes = {
    "small.txt": 100,
    "large.exe": 2000000,
    "ignored.log": 5000000,
    "vendor/big_lib.js": 3000000,
    "docs/image.png": 1024,  # 1KB
    "not_found.txt": None,
}


def mock_get_file_size(filepath: str) -> Optional[int]:
    return mock_file_sizes.get(filepath)


@pytest.mark.parametrize(
    "filepath, max_bytes, ignore_ext, ignore_paths, expected_violations_count",
    [
        ("small.txt", 1000, [], [], 0),
        ("large.exe", 1000000, [], [], 1),  # Exceeds 1MB
        ("ignored.log", 100, [".log"], [], 0),  # Ignored by extension
        ("vendor/big_lib.js", 1000, [], ["vendor/*"], 0),  # Ignored by path
        ("docs/image.png", 1000, [], [], 1),  # Exceeds 1000 bytes (not 1KB)
        ("not_found.txt", 1000, [], [], 0),  # Size unknown, skipped
    ],
)
def test_check_file_size_policy(
    filepath, max_bytes, ignore_ext, ignore_paths, expected_violations_count
):
    policy = FileSizePolicy(
        max_bytes=max_bytes,
        ignore_extensions=ignore_ext,
        ignore_paths=ignore_paths,
        enabled=True,
    )
    violations = file_policies.check_file_size_policy(
        filepath, mock_get_file_size, policy
    )
    assert len(violations) == expected_violations_count


def test_check_file_size_policy_disabled():
    policy = FileSizePolicy(max_bytes=10, enabled=False)
    violations = file_policies.check_file_size_policy(
        "large.exe", mock_get_file_size, policy
    )
    assert not violations
