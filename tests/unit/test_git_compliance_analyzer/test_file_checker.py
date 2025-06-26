import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import re

from src.mcp_tools.git_compliance_analyzer.models import ComplianceFinding
from src.mcp_tools.git_compliance_analyzer.config import (
    FileExistenceRules,
    FileExistenceRuleItem,
    FilePatternRuleItem,
    FileContentRules,
    FileContentRuleItem,
    ContentPatternRule,
)
from src.mcp_tools.git_compliance_analyzer.checkers import file_checker
from src.mcp_tools.common.git_utils import GitUtils, GitRepoError


@pytest.fixture
def mock_git_utils():
    """Fixture to create a MagicMock for GitUtils."""
    mock = MagicMock(spec=GitUtils)
    # Setup default return values for methods that might be called
    mock.list_files_at_revision.return_value = []
    mock.get_file_content_at_revision.return_value = None
    return mock


# --- Tests for check_file_existence ---


def test_file_existence_must_exist_present(mock_git_utils: MagicMock):
    mock_git_utils.list_files_at_revision.return_value = ["README.md", "LICENSE"]
    rules = FileExistenceRules(
        must_exist=[FileExistenceRuleItem(path="LICENSE", severity="High")]
    )
    findings = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert not findings


def test_file_existence_must_exist_missing(mock_git_utils: MagicMock):
    mock_git_utils.list_files_at_revision.return_value = ["README.md"]
    rules = FileExistenceRules(
        must_exist=[FileExistenceRuleItem(path="LICENSE", severity="High")]
    )
    findings = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert len(findings) == 1
    assert findings[0].rule_id == "FILE_MUST_EXIST_MISSING"
    assert findings[0].file_path == "LICENSE"
    assert findings[0].severity == "High"


def test_file_existence_must_not_exist_absent(mock_git_utils: MagicMock):
    mock_git_utils.list_files_at_revision.return_value = ["config.json"]
    rules = FileExistenceRules(
        must_not_exist_patterns=[
            FilePatternRuleItem(pattern="*.secret", severity="High")
        ]
    )
    findings = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert not findings


def test_file_existence_must_not_exist_present(mock_git_utils: MagicMock):
    mock_git_utils.list_files_at_revision.return_value = [
        "config.json",
        "id_rsa.pem",
        "another.pem.backup",
    ]
    rules = FileExistenceRules(
        must_not_exist_patterns=[
            FilePatternRuleItem(
                pattern="*.pem", severity="High", message="PEM file found"
            )
        ]
    )
    findings = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert (
        len(findings) == 1
    )  # Path.match matches full name, so "*.pem" will only match "id_rsa.pem"
    # To match "another.pem.backup", pattern would need to be different or logic more complex.
    # Current test setup for *.pem will match id_rsa.pem.
    # If we wanted to match both, we'd need two rules or more complex pattern.

    # Let's refine the test to be more specific or test multiple patterns
    mock_git_utils.list_files_at_revision.return_value = ["id_rsa.pem"]
    findings_one = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert len(findings_one) == 1
    assert findings_one[0].rule_id == "FILE_MUST_NOT_EXIST_PRESENT"
    assert findings_one[0].file_path == "id_rsa.pem"
    assert "PEM file found" in findings_one[0].message


def test_file_existence_rules_disabled(mock_git_utils: MagicMock):
    rules = FileExistenceRules(
        enabled=False, must_exist=[FileExistenceRuleItem(path="IMPORTANT.txt")]
    )
    findings = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert not findings


def test_file_existence_git_list_error(mock_git_utils: MagicMock):
    mock_git_utils.list_files_at_revision.side_effect = GitRepoError("Test Git error")
    rules = FileExistenceRules(must_exist=[FileExistenceRuleItem(path="file.txt")])
    findings = file_checker.check_file_existence(mock_git_utils, "HEAD", rules)
    assert len(findings) == 1
    assert findings[0].rule_id == "GIT_LIST_FILES_ERROR"


# --- Tests for check_file_content ---


@pytest.fixture
def content_rule_must_contain() -> FileContentRuleItem:
    return FileContentRuleItem(
        file_path_pattern=re.compile(r"README\.md"),
        must_contain_pattern=ContentPatternRule(
            pattern="## Usage", message="Missing Usage section", severity="Medium"
        ),
        enabled=True,
    )


@pytest.fixture
def content_rule_must_not_contain() -> FileContentRuleItem:
    return FileContentRuleItem(
        file_path_pattern=re.compile(r"\.py$"),
        must_not_contain_pattern=ContentPatternRule(
            pattern="REMOVE_THIS_DEBUG_CODE",
            message="Debug code found",
            severity="High",
        ),
        enabled=True,
    )


def test_file_content_must_contain_present(
    mock_git_utils: MagicMock, content_rule_must_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.return_value = ["README.md", "src/main.py"]
    mock_git_utils.get_file_content_at_revision.return_value = (
        "Some content\n## Usage\nMore content"
    )

    rules = FileContentRules(rules=[content_rule_must_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert not findings
    mock_git_utils.get_file_content_at_revision.assert_called_with("README.md", "HEAD")


def test_file_content_must_contain_missing(
    mock_git_utils: MagicMock, content_rule_must_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.return_value = ["README.md"]
    mock_git_utils.get_file_content_at_revision.return_value = (
        "Some content\nNo usage section here."
    )

    rules = FileContentRules(rules=[content_rule_must_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert len(findings) == 1
    assert findings[0].rule_id == "FILE_CONTENT_MUST_CONTAIN_MISSING"
    assert findings[0].file_path == "README.md"
    assert "Missing Usage section" in findings[0].message


def test_file_content_must_not_contain_absent(
    mock_git_utils: MagicMock, content_rule_must_not_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.return_value = ["src/app.py"]
    mock_git_utils.get_file_content_at_revision.return_value = (
        "def main():\n  print('Hello')"
    )

    rules = FileContentRules(rules=[content_rule_must_not_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert not findings


def test_file_content_must_not_contain_present(
    mock_git_utils: MagicMock, content_rule_must_not_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.return_value = ["src/debug_me.py"]
    file_content_with_debug = "line1\nline2\nREMOVE_THIS_DEBUG_CODE\nline4"
    mock_git_utils.get_file_content_at_revision.return_value = file_content_with_debug

    rules = FileContentRules(rules=[content_rule_must_not_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert len(findings) == 1
    assert findings[0].rule_id == "FILE_CONTENT_MUST_NOT_CONTAIN_PRESENT"
    assert findings[0].file_path == "src/debug_me.py"
    assert "Debug code found" in findings[0].message
    assert "Matched: 'REMOVE_THIS_DEBUG_CODE'" in findings[0].message  # Check details
    assert findings[0].line_number == 3


def test_file_content_rules_disabled(
    mock_git_utils: MagicMock, content_rule_must_contain: FileContentRuleItem
):
    rules = FileContentRules(
        rules=[content_rule_must_contain], enabled=False
    )  # Parent rule disabled
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert not findings

    content_rule_must_contain.enabled = False  # Sub-rule disabled
    rules_parent_enabled = FileContentRules(
        rules=[content_rule_must_contain], enabled=True
    )
    findings_sub_disabled = file_checker.check_file_content(
        mock_git_utils, "HEAD", rules_parent_enabled
    )
    assert not findings_sub_disabled


def test_file_content_no_matching_files(
    mock_git_utils: MagicMock, content_rule_must_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.return_value = [
        "src/other.py",
        "docs/index.html",
    ]  # No README.md
    rules = FileContentRules(rules=[content_rule_must_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert not findings


def test_file_content_unreadable_file(
    mock_git_utils: MagicMock, content_rule_must_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.return_value = ["README.md"]
    mock_git_utils.get_file_content_at_revision.return_value = (
        None  # Simulate binary or unreadable
    )
    rules = FileContentRules(rules=[content_rule_must_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert not findings  # Should skip checks for this file


def test_file_content_git_list_error(
    mock_git_utils: MagicMock, content_rule_must_contain: FileContentRuleItem
):
    mock_git_utils.list_files_at_revision.side_effect = GitRepoError(
        "Test Git list error for content"
    )
    rules = FileContentRules(rules=[content_rule_must_contain])
    findings = file_checker.check_file_content(mock_git_utils, "HEAD", rules)
    assert len(findings) == 1
    assert findings[0].rule_id == "GIT_LIST_FILES_ERROR_CONTENT_CHECK"
