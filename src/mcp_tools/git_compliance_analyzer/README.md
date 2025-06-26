# Git Compliance Analyzer

The Git Compliance Analyzer (`cli.py` in this directory) is a command-line tool that scans a local Git repository against a configurable set of compliance rules. It helps ensure that repository content, commit history, and potentially Infrastructure as Code (IaC) configurations adhere to defined standards and best practices.

This tool can be used by developers locally before committing/pushing changes or integrated into CI/CD pipelines for automated compliance checks.

## Current Features (Initial Version)

*   **Configurable Rules:** Define compliance policies in a YAML file (default: `.compliance-rules.yml` in the repository root). This allows for flexible and project-specific compliance definitions.
*   **Checks Performed:**
    *   **File Existence:**
        *   `must_exist`: Verify that specific files (e.g., `LICENSE`, `CONTRIBUTING.md`) are present in the repository at the target revision.
        *   `must_not_exist_patterns`: Check for the absence of files matching specified glob patterns (e.g., `*.pem`, `*.key`, `secrets/**/*.json`).
    *   **File Content:**
        *   Scan files (selected by a path regex) for required (`must_contain_pattern`) or forbidden (`must_not_contain_pattern`) regex patterns within their content.
        *   Useful for detecting hardcoded secrets (basic patterns), TODOs without ticket numbers, disallowed function calls, etc.
    *   **Commit History:**
        *   Analyze commit messages on the current branch (compared against a specified base branch) for compliance with Conventional Commit format and allowed types.
    *   **IaC Validation (Basic Wrapper):**
        *   Execute external IaC validation commands, currently supporting `terraform validate -no-color` in specified directories within the repository. (Requires the respective CLI tool, like `terraform`, to be installed and in the system PATH).
*   **CLI Interface:** Allows users to specify the repository path, the branch/revision to analyze, a base branch for commit history comparison, and a path to a custom rules file.
*   **Reporting:** Outputs a list of compliance findings, including severity, a descriptive message, and relevant context (e.g., file paths, line numbers, commit SHAs). Exits with a non-zero status code if violations are found.

## Usage

1.  **Ensure you have a local clone of the Git repository you wish to analyze.**
2.  **Optionally, create a `.compliance-rules.yml` file in the root of that repository** to define your specific compliance rules. If this file is not found, the tool will run with its default built-in rules (which are generally minimal, focusing on structure rather than specific content).
3.  **Run the tool from your project root** (or ensure `src` is in `PYTHONPATH` if running `python -m ...`):

    To analyze the current directory's repository, checking the `HEAD` revision, and comparing commit history on the current branch against `origin/main`:
    ```bash
    python -m src.mcp_tools.git_compliance_analyzer.cli . --branch HEAD --base-branch origin/main
    ```

    To analyze a specific repository path and branch, using a custom rules file:
    ```bash
    python -m src.mcp_tools.git_compliance_analyzer.cli /path/to/your/scanned-repo --branch my-feature-branch --base-branch develop --rules-file /path/to/your/custom-compliance.yml
    ```

### Command-Line Arguments

*   `repo_path` (Positional, Optional): Path to the local Git repository to analyze.
    *   Default: `.` (current directory).
*   `--branch <branch/tag/commit_sha>` (`-b`): The branch, tag, or specific commit SHA to analyze the state of. This is the revision against which file existence and content checks are performed. For commit history checks, this is the "head" of the range.
    *   Default: `HEAD`.
*   `--base-branch <branch/tag/commit_sha>`: The base branch for commit history comparison. Commits on `--branch` that are not on `--base-branch` will be analyzed.
    *   Default: `None` (if not provided, commit history checks that require a base for comparison are typically skipped or might default to comparing against a common ancestor with `main`/`master` if logic allows, though explicit is better). The current CLI skips if not provided.
*   `--rules-file <path>`: Optional path to the compliance rules YAML configuration file.
    *   Default: The tool searches for `.compliance-rules.yml` in the `repo_path` and its parent directories. If not found, default built-in rules are applied.

## Configuration (`.compliance-rules.yml`)

Define your compliance checks in a `.compliance-rules.yml` file.

**Example `.compliance-rules.yml`:**
```yaml
file_checks:
  enabled: true
  must_exist:
    - path: "LICENSE" # Path relative to repo root
      severity: "High"
      message: "A LICENSE file is required in the repository."
    - path: "README.md"
      severity: "Medium"
  must_not_exist_patterns:
    - pattern: "*.pem" # Glob pattern
      severity: "High"
      message: "Private key files (.pem) should not be committed."
    - pattern: "config/secrets.json" # Specific file
      severity: "High"
    - pattern: "**/*.bak" # All .bak files anywhere
      severity: "Low"

file_content_checks:
  enabled: true
  rules:
    - file_path_pattern: "\\.md$" # Regex for file paths (e.g., all Markdown files)
      enabled: true
      must_contain_pattern: # Check if these files contain...
        pattern: "## Contribution Guidelines" # Regex for content
        message: "Markdown files should link to or include Contribution Guidelines."
        severity: "Low"
    - file_path_pattern: "\\.(py|java|js|ts|go)$" # Common code files
      enabled: true
      must_not_contain_pattern: # Check if these files DO NOT contain...
        # Example: TODO/FIXME without a ticket reference like [JIRA-123] or #123
        pattern: "(TODO|FIXME)(?!\\s*:\\s*(\\[[A-Z]+-[0-9]+\\]|#\\d+))"
        message: "Found TODO/FIXME without a linked issue number (e.g., TODO: [JIRA-123] Description or FIXME: #123 Fix this)."
        severity: "Medium"
    - file_path_pattern: ".*" # Check all files
      enabled: true
      must_not_contain_pattern:
        pattern: "(password|secret|api_key)\\s*[:=]\\s*['\\\"]?[^\\s'\\\"]{8,}" # Basic secret detection (value at least 8 chars)
        message: "Potential hardcoded credential detected."
        severity: "High"

commit_history_checks:
  enabled: true # For all commit history checks
  conventional_commit_format: # Specific check type
    enabled: true
    # List of allowed conventional commit types
    types: ["feat", "fix", "chore", "docs", "style", "refactor", "test", "ci", "build", "perf", "revert"]
    severity: "Medium"
  # Future: Add more commit checks, e.g., require_issue_in_commit_message

iac_validation_checks:
  enabled: true # For all IaC validation checks
  rules:
    - type: "terraform_validate" # Type of IaC validation
      paths: ["terraform/environments/", "terraform/modules/"] # List of directories to run in (relative to repo root)
      enabled: true
      severity: "High"
    # - type: "terrascan_run" # Example for a future checker
    #   paths: ["./"]
    #   enabled: false
    #   severity: "High"
```

## Interpreting Output

*   The tool will print messages about the repository being analyzed and the rules file being used.
*   It will indicate which categories of checks are being performed.
*   If compliance findings (violations) are discovered:
    *   A summary line: "--- Compliance Analyzer Summary: X FINDING(S) ---".
    *   Each finding is detailed with:
        *   **Severity:** e.g., "High", "Medium", "Low", "Informational".
        *   **Rule ID:** An identifier for the specific rule that was violated (e.g., `FILE_MUST_EXIST_MISSING`, `COMMIT_CONVENTIONAL_TYPE_INVALID`).
        *   **Context:** File path, line number (for content issues), or commit SHA (for commit issues) where applicable.
        *   **Message:** A human-readable description of the finding.
        *   **Details:** (Optional) A dictionary with extra context-specific data about the finding.
*   If no findings are reported for the enabled checks: "--- Compliance Analyzer Summary: ALL CHECKS PASSED ---".
*   **Exit Code:**
    *   `0`: All enabled checks passed successfully (no findings).
    *   `1`: Compliance findings were reported.
    *   `2`: Error related to Git repository access or initialization.
    *   `3`: Error related to loading or parsing the compliance rules file.
    *   Other non-zero codes for unexpected operational errors.

## Current Limitations & Future Enhancements

*   **Local Execution Context:** The tool analyzes a local clone of a Git repository. It does not directly interact with remote Git platforms (like GitHub/GitLab APIs for PR details, branch protection rules, etc., though commit history from local refs is used).
*   **Basic IaC Validation:** The `iac_validation_checks` feature currently acts as a simple wrapper around external CLI tools like `terraform validate`. It doesn't parse the output of these tools in detail to extract specific issues; it primarily reports success/failure based on the exit code. More sophisticated integration with IaC static analysis tools (e.g., Checkov, Terrascan, tfsec) could provide richer, more granular feedback.
*   **Comment/Contextual Code Understanding:** For file content checks, the pattern matching is regex-based and does not have a deep semantic understanding of the code or comments. More advanced static analysis techniques could improve the accuracy and context-awareness of these checks.
*   **Remediation:** The tool currently only reports findings. Future versions could potentially suggest specific remediation commands or, with extreme caution and user approval, attempt automated fixes for certain types of violations.
*   **Performance:** For very large repositories or extensive commit histories, some checks might be slow. Performance optimization may be needed as more complex rules are added.

This tool aims to provide a flexible and configurable way to enforce coding standards, security best practices, and project-specific conventions within your Git repositories, helping to improve code quality and reduce risks.
```
