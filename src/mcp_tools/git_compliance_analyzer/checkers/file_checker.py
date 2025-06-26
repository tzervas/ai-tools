import os
import re
from pathlib import Path
from typing import List, Optional, Callable, Pattern

from ..models import ComplianceFinding
from ..config import FileExistenceRules, FileContentRules, FileExistenceRuleItem, FilePatternRuleItem, FileContentRuleItem
from ...common.git_utils import GitUtils # Assuming GitUtils is now common

# Type alias for a function that gets file content from GitUtils
GetFileContentCallable = Callable[[str, str], Optional[str]] # (filepath, revision) -> content


def check_file_existence(
    git_utils: GitUtils,
    target_revision: str,
    rules: FileExistenceRules
) -> List[ComplianceFinding]:
    """
    Checks for file existence (must_exist, must_not_exist_patterns) in the repo.
    """
    findings: List[ComplianceFinding] = []
    if not rules.enabled:
        return findings

    try:
        all_repo_files = set(git_utils.list_files_at_revision(revision=target_revision))
    except Exception as e:
        findings.append(ComplianceFinding(
            rule_id="GIT_LIST_FILES_ERROR",
            severity="High",
            message=f"Error listing files in repository at revision '{target_revision}': {e}",
        ))
        return findings

    # Must Exist Checks
    for rule_item in rules.must_exist:
        if rule_item.path not in all_repo_files:
            findings.append(ComplianceFinding(
                rule_id="FILE_MUST_EXIST_MISSING",
                severity=rule_item.severity,
                message=rule_item.message or f"Required file '{rule_item.path}' is missing.",
                file_path=rule_item.path
            ))

    # Must Not Exist Patterns Checks
    for rule_item in rules.must_not_exist_patterns:
        # Convert glob to regex-like for matching against list_files_at_revision output
        # For simplicity, we'll use Path.match which is good for globs
        # Or, if GitUtils.list_files_at_revision supports glob directly:
        # matching_files = git_utils.list_files_at_revision(target_revision, file_glob_patterns=[rule_item.pattern])
        # For now, iterate and match:
        for repo_file_path_str in all_repo_files:
            if Path(repo_file_path_str).match(rule_item.pattern):
                findings.append(ComplianceFinding(
                    rule_id="FILE_MUST_NOT_EXIST_PRESENT",
                    severity=rule_item.severity,
                    message=rule_item.message or f"File '{repo_file_path_str}' matches forbidden pattern '{rule_item.pattern}' and should not exist.",
                    file_path=repo_file_path_str
                ))
    return findings


def check_file_content(
    git_utils: GitUtils,
    target_revision: str,
    rules: FileContentRules
) -> List[ComplianceFinding]:
    """
    Checks file content for specified patterns.
    """
    findings: List[ComplianceFinding] = []
    if not rules.enabled or not rules.rules:
        return findings

    # Get content using the callable
    get_content_func: GetFileContentCallable = git_utils.get_file_content_at_revision

    # Iterate through each rule, then find matching files, then check content
    for rule_item in rules.rules:
        if not rule_item.enabled:
            continue

        # Find files matching the file_path_pattern for this rule
        # This requires listing all files first if not already done.
        try:
            # This could be optimized if all_repo_files is fetched once per run
            all_repo_files = git_utils.list_files_at_revision(revision=target_revision)
        except Exception as e:
            findings.append(ComplianceFinding(
                rule_id="GIT_LIST_FILES_ERROR_CONTENT_CHECK",
                severity="High",
                message=f"Error listing files for content check at revision '{target_revision}': {e}",
            ))
            continue # Skip this rule if we can't list files

        files_to_check_for_this_rule: List[str] = []
        for repo_file_path_str in all_repo_files:
            if rule_item.file_path_pattern.match(repo_file_path_str):
                files_to_check_for_this_rule.append(repo_file_path_str)

        for filepath_to_check in files_to_check_for_this_rule:
            content = get_content_func(filepath_to_check, target_revision)
            if content is None: # Binary, unreadable, or not found (shouldn't be not found if listed)
                # Optionally log a warning if content is None for a matched file
                # print(f"Warning: Could not read content for {filepath_to_check} for content pattern checks.", file=sys.stderr)
                continue

            # Must Contain Pattern
            if rule_item.must_contain_pattern and rule_item.must_contain_pattern.enabled:
                mc_rule = rule_item.must_contain_pattern
                if not mc_rule.pattern.search(content):
                    findings.append(ComplianceFinding(
                        rule_id="FILE_CONTENT_MUST_CONTAIN_MISSING",
                        severity=mc_rule.severity,
                        message=mc_rule.message or f"File '{filepath_to_check}' does not contain required pattern: '{mc_rule.pattern.pattern}'.",
                        file_path=filepath_to_check
                    ))

            # Must Not Contain Pattern
            if rule_item.must_not_contain_pattern and rule_item.must_not_contain_pattern.enabled:
                mnc_rule = rule_item.must_not_contain_pattern
                match = mnc_rule.pattern.search(content)
                if match:
                    # Try to find line number (basic)
                    line_num: Optional[int] = None
                    try:
                        # Find the line number of the first occurrence
                        start_index = match.start()
                        line_num = content.count('\n', 0, start_index) + 1
                    except Exception:
                        pass # Keep line_num as None if error

                    findings.append(ComplianceFinding(
                        rule_id="FILE_CONTENT_MUST_NOT_CONTAIN_PRESENT",
                        severity=mnc_rule.severity,
                        message=mnc_rule.message or f"File '{filepath_to_check}' contains forbidden pattern: '{mnc_rule.pattern.pattern}'. Matched: '{match.group(0)}'",
                        file_path=filepath_to_check,
                        line_number=line_num,
                        details={"matched_text": match.group(0)}
                    ))
    return findings


if __name__ == '__main__':
    # This block would require a more complex setup with a live Git repo
    # or extensive mocking of GitUtils. Unit tests for these checkers
    # will be more effective in their dedicated test files.
    print("File checker logic. Run unit tests for detailed checks.")

    # Example of how it might be called (conceptual)
    # try:
    #     # Assume we are in a git repo for this direct test
    #     git_utils_instance = GitUtils(".")
    #     mock_existence_rules = FileExistenceRules(
    #         must_exist=[FileExistenceRuleItem(path="README.md", severity="High")],
    #         must_not_exist_patterns=[FilePatternRuleItem(pattern="*.secret", severity="High")]
    #     )
    #     existence_findings = check_file_existence(git_utils_instance, "HEAD", mock_existence_rules)
    #     print("\nExistence Findings:")
    #     for f in existence_findings: print(f"  - {f}")

    #     mock_content_rules_config = FileContentRules(rules=[
    #         FileContentRuleItem(
    #             file_path_pattern=re.compile(r"README\.md"),
    #             must_contain_pattern={"pattern": r"## Usage", "message": "README needs Usage section", "severity": "Medium"}, # type: ignore
    #             enabled=True
    #         ),
    #         FileContentRuleItem(
    #             file_path_pattern=re.compile(r"\.py$"),
    #             must_not_contain_pattern={"pattern": r"REMOVE_BEFORE_COMMIT", "message": "Found placeholder", "severity": "High"}, # type: ignore
    #             enabled=True
    #         )
    #     ])
    #     content_findings = check_file_content(git_utils_instance, "HEAD", mock_content_rules_config)
    #     print("\nContent Findings:")
    #     for f in content_findings: print(f"  - {f}")

    # except Exception as e:
    #     print(f"Error in file_checker example: {e}")
    pass
