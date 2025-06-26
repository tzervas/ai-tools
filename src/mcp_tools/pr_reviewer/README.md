# Automated PR Review Helper

The Automated PR Review Helper (`cli.py` in this directory) is a command-line tool designed to
check your current Git branch's changes against a defined set of policies before you create a Pull
Request or push your changes. This helps ensure code quality, consistency, and adherence to project
standards.

It's intended for local use by developers or for integration into CI/CD pipelines as an automated
check.

## Features

- **Configurable Policies:** Define policies in a `.pr-policy.yml` file (by default, searched in the
  repository root and parent directories). This allows customization of checks per repository.
- **Checks Performed:**
  - **Branch Naming:** Verifies if the current branch name (or specified head branch) matches a
    configured regex pattern.
  - **Commit Messages (for commits in the PR/branch range):**
    - Checks for Conventional Commit format (e.g., `feat: ...`, `fix(scope): ...`).
    - Ensures commit messages include an issue/ticket number if required by policy (configurable
      pattern, checks commit body).
  - **Disallowed Content:** Scans changed files (in the PR/branch range, at their state in the head
    branch) for disallowed regex patterns (e.g., `TODO FIXME` without an associated issue, basic
    common secret patterns like "API_KEY = ...").
  - **File Size:** Checks if any changed files (at their state in the head branch) exceed a maximum
    size limit.
- **Local Execution:** Designed to be run locally on your feature branch before pushing.
- **CI Integration:** Can be incorporated into CI/CD pipelines to automate these checks on Pull
  Requests or proposed changes.

## Usage

1. **Ensure you are on your feature branch** or specify the head branch for analysis.
2. **Run the tool from the root of your repository** (or use `--repo-path`):

   To check the current branch against `main`:

   ```bash
   python -m src.mcp_tools.pr_reviewer.cli --base-branch main --head-branch HEAD
   ```

   To check a specific feature branch `my-feature` against `develop`:

   ```bash
   python -m src.mcp_tools.pr_reviewer.cli --base-branch develop --head-branch my-feature
   ```

### Command-Line Arguments

- `--base-branch <branch>`: The base branch to compare against (e.g., `main`, `develop`).
  Default: `main`.
- `--head-branch <branch_or_rev>`: The head branch or revision to check (e.g., your feature branch
  name, `HEAD`). Default: `HEAD`.
- `--config-file <path>`: Path to the policy configuration YAML file. If not provided, the tool
  searches for `.pr-policy.yml` in the current directory and its parents.
- `--repo-path <path>`: Path to the Git repository. Defaults to the current working directory.

## Configuration (`.pr-policy.yml`)

Create a `.pr-policy.yml` file in the root of your repository (or a custom path specified with
`--config-file`) to customize policies. If no configuration file is found, default policies (defined
in `src/mcp_tools/pr_reviewer/config.py`) will be applied.

**Example `.pr-policy.yml`:**

```yaml
# .pr-policy.yml
branch_naming:
  pattern: "^(feature|fix|chore|docs|refactor|test)/[a-zA-Z0-9_.-]+$" # Example: feat/my-cool-thing
  enabled: true

commit_messages:
  enabled: true
  conventional_commit:
    enabled: true
    # Allowed conventional commit types
    types: ["feat", "fix", "docs", "style", "refactor", "test", "chore", "ci", "build", "perf", "revert"]
  require_issue_number:
    enabled: true
    # Regex pattern for issue numbers (e.g., [PROJ-123], #123)
    pattern: "\\[([A-Z]+-[0-9]+|#[0-9]+)\\]"
    in_commit_body: true # Check in commit message body

disallowed_patterns:
  enabled: true
  patterns:
    - pattern: "console\\.log" # Disallow console.log statements (example for JS/TS)
      message: "Found 'console.log'. Please remove debug statements."
      enabled: true
    - pattern: "(SECRET|PASSWORD|API_KEY|PRIVATE_KEY)\\s*[:=]\\s*['\\\"]?[^\\s'\\\"]{5,}" # Basic secret detection (at least 5 chars value)
      message: "Potential hardcoded secret detected. Ensure this is intentional and secure."
      enabled: true
    - pattern: "TODO(?!\\s*:\\s*\\[([A-Z]+-[0-9]+|#[0-9]+)\\])" # TODO without a linked issue
      message: "Found 'TODO' without a linked issue (e.g., TODO: [PROJ-123] Description or TODO: #123 Description)."
      enabled: true
    - pattern: "FIXME(?!\\s*:\\s*\\[([A-Z]+-[0-9]+|#[0-9]+)\\])" # FIXME without a linked issue
      message: "Found 'FIXME' without a linked issue."
      enabled: true

file_size:
  enabled: true
  max_bytes: 2097152 # 2MB
  ignore_extensions: [".lock", ".mp4", ".zip", ".gz", ".tar", ".jar", ".exe", ".dll", ".pdb"]
  ignore_paths: ["vendor/*", "dist/*", "build/*", "*.log", "node_modules/*", "target/*"] # Wildcards supported
```

### Policy Details

- **`branch_naming`**:
  - `pattern`: Regex string for valid branch names.
  - `enabled`: `true` or `false`.
- **`commit_messages`**:
  - `enabled`: `true` or `false` for all commit message checks.
  - `conventional_commit`:
    - `enabled`: `true` or `false`.
    - `types`: List of allowed conventional commit types (e.g., "feat", "fix").
  - `require_issue_number`:
    - `enabled`: `true` or `false`.
    - `pattern`: Regex string for matching issue numbers.
    - `in_commit_body`: (Currently only `true` is supported) If `true`, checks the commit message
      body.
- **`disallowed_patterns`**:
  - `enabled`: `true` or `false` for all disallowed pattern checks.
  - `patterns`: A list of pattern items:
    - `pattern`: Regex string for the content to disallow.
    - `message`: Custom message for this violation.
    - `enabled`: `true` or `false` for this specific pattern.
- **`file_size`**:
  - `enabled`: `true` or `false`.
  - `max_bytes`: Maximum allowed file size in bytes.
  - `ignore_extensions`: List of file extensions (e.g., `[".log", ".tmp"]`) to exclude from size
    checks.
  - `ignore_paths`: List of glob patterns (e.g., `["vendor/*", "testdata/*.bin"]`) for paths to
    exclude from size checks.

## Interpreting Output

- The tool will print messages indicating which policies are being checked.
- If violations are found, they will be listed with details, including:
  - The specific rule violated.
  - The file path (for file content/size violations).
  - The line number (for content violations, if determinable).
  - The commit SHA (for commit message violations).
  - A descriptive message about the violation.
- The tool will exit with:
  - Status code `0` if all enabled checks pass.
  - Status code `1` if any violations are found.
  - Other non-zero codes for operational errors (e.g., Git repository issues, configuration file
    problems).

This tool aims to catch common issues early in the development cycle, promoting cleaner code, more
consistent commit histories, and adherence to project standards before code reviews or merges.
