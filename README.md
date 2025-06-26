# MCP Tools Project

## Overview

This project is a collection of tools and servers related to the Anthropic Model Context Protocol (MCP). It aims to provide useful utilities for AI-assisted Research & Development, Machine Learning, AI, Software, and IT engineering tasks.

The project includes:

- An MCP Server implementation.
- Various MCP client tools.
- Development environment setup using Docker and Devcontainers.
- Testing framework using Pytest.

## Project Structure

```text
.  
├── .devcontainer/        # VS Code Devcontainer configuration
│   └── devcontainer.json
├── AGENTS.md             # Instructions for AI agents working on this repo
├── Dockerfile            # Docker configuration for the application
├── LICENSE               # Project License
├── pyproject.toml        # Python project metadata and dependencies (for UV tool)
├── README.md             # This file
├── scripts/              # Utility scripts
│   └── git-amend-author-and-sign.sh # Script for amending commit authors and signing
├── src/                  # Source code
│   ├── mcp_server/       # MCP Server implementation
│   │   └── main.py
│   └── mcp_tools/        # Client tools interacting with MCP
│       ├── echo_tool/
│       │   └── client.py
│       ├── pr_reviewer/  # Automated PR Review Helper tool
│       │   ├── cli.py
│       │   ├── config.py
│       │   ├── git_utils.py
│       │   └── policies/
│       │       ├── branch.py
│       │       ├── commit.py
│       │       └── file.py
│       └── iac_drift_detector/ # IaC Drift Detector tool
│           ├── cli.py
│           ├── models.py
│           ├── parsers/
│           │   └── terraform_parser.py
│           ├── connectors/
│           │   └── mock_connector.py
│           └── core_logic/
│               ├── drift_engine.py
│               └── remediation.py
│       └── config_optimizer/ # Configuration Optimization Recommender tool
│           ├── cli.py
│           ├── models.py
│           ├── config.py
│           └── aws/
│               ├── ec2_optimizer.py
│               └── s3_optimizer.py
│       └── iac_doc_generator/ # Automated IaC Documentation Generator
│           ├── cli.py
│           ├── models.py
│           ├── terraform_hcl_parser.py
│           └── markdown_renderer.py
│       └── git_compliance_analyzer/ # Git Compliance Analyzer tool
│           ├── cli.py
│           ├── models.py
│           ├── config.py
│           └── checkers/
│               ├── file_checker.py
│               ├── commit_checker.py
│               └── iac_checker.py
└── tests/                # Tests
    ├── integration/      # Integration tests
    │   ├── test_echo_tool.py
    │   ├── test_pr_reviewer/
    │   │   └── test_pr_reviewer_cli.py
    │   └── test_iac_drift_detector/
    │       └── test_iac_drift_cli.py
    └── unit/             # Unit tests
        ├── test_server.py
        ├── test_pr_reviewer/
        │   ├── test_config.py
        │   └── test_policies.py
        └── test_iac_drift_detector/
            ├── test_terraform_parser.py
            ├── test_drift_engine.py
            └── test_remediation.py
        └── test_config_optimizer/
            ├── test_optimizer_config.py
            ├── test_ec2_optimizer.py
            └── test_s3_optimizer.py
        └── test_iac_doc_generator/
            ├── test_terraform_hcl_parser.py
            └── test_markdown_renderer.py
        └── test_git_compliance_analyzer/
            ├── test_config.py
            ├── test_file_checker.py
            ├── test_commit_checker.py
            └── test_iac_checker.py
```

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [VS Code](https://code.visualstudio.com/)
- [Remote - Containers extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- `uv` (Python packaging tool - will be installed in devcontainer, but useful locally too: `pip install uv`)
- `git`

### Setup with Devcontainer (Recommended)

1. **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2. **Open in VS Code:**
    Open the cloned repository folder in VS Code.

3. **Reopen in Container:**
    VS Code should prompt you to "Reopen in Container". Click it. This will build the Docker image defined in `Dockerfile` and configure the development environment as specified in `.devcontainer/devcontainer.json`. Dependencies listed in `pyproject.toml` will be installed automatically.

### Manual Setup (without Devcontainer)

1. **Clone the repository (if not already done).**
2. **Create and activate a virtual environment:**

    ```bash
    uv venv .venv
    source .venv/bin/activate
    ```

    (On Windows: `.venv\Scripts\activate`)
3. **Install dependencies:**

    ```bash
    uv pip install -e .[dev]
    ```

## Running the MCP Server

- **Inside Devcontainer or Manual Setup (with venv activated):**

    The MCP server is a FastAPI application. You can run it using Uvicorn:

    ```bash
    uvicorn src.mcp_server.main:app --reload --host 0.0.0.0 --port 8000
    ```

    The server will be available at `http://localhost:8000`.
    The API documentation (Swagger UI) will be at `http://localhost:8000/docs`.

## Running Tests

Tests are written using `pytest`.

- **Inside Devcontainer or Manual Setup (with venv activated):**

    To run all tests:

    ```bash
    uv run pytest
    ```

    Or simply:

    ```bash
    pytest
    ```

    Pytest is configured in `pyproject.toml` to automatically find tests and the `src` directory.

## Using Tools

### Echo Tool

The Echo Tool is a simple client that sends a message to the MCP server's echo endpoint and prints the response.

- **Usage (assuming server is running and venv is active or in devcontainer):**

    ```bash
    python src/mcp_tools/echo_tool/client.py "Your message here"
    ```

    Optional arguments:
  - `--server-url`: Specify the server URL (default: `http://localhost:8000`).
  - `--context-id`: Specify an optional context ID.

    Example:

    ```bash
    python src/mcp_tools/echo_tool/client.py "Hello MCP" --server-url http://localhost:8000
    ```

## Commit Author Amendment and Signing Script

A utility script `scripts/git-amend-author-and-sign.sh` is provided to help amend the author of a series of commits on a branch and prepare them for GPG signing. This is useful for ensuring commits adhere to specific authorship requirements and are properly signed.

### Purpose

When contributing code, especially if changes were initially made by an AI agent or under a different Git configuration, this script helps to:

1. Standardize the commit author to a designated name and email.
2. Guide the user through an interactive rebase to sign each commit individually with their GPG key.

### Prerequisites for the Script

- `git` installed and configured.
- A GPG key configured with Git for signing commits. See [GitHub's guide on signing commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).
- The script should be run from the root of the repository.

### Usage

```bash
./scripts/git-amend-author-and-sign.sh <branch-name> <base-branch>
```

- `<branch-name>`: The local feature branch whose commits you want to amend and sign.
- `<base-branch>`: The base branch (e.g., `main`, `develop`) against which to find the commits to process.

**Example:**
If you have a branch named `feature/new-tool` that was based off `main`:

```bash
chmod +x scripts/git-amend-author-and-sign.sh # Make it executable first
./scripts/git-amend-author-and-sign.sh feature/new-tool main
```

### Workflow of the Script

1. **Validation:** Checks if the branches exist and if the working directory is clean.
2. **Confirmation:** Asks for confirmation before starting the interactive rebase.
3. **Interactive Rebase:**
    - The script automatically starts an interactive rebase (`git rebase -i <base-branch>`).
    - It sets `GIT_SEQUENCE_EDITOR` to mark all commits in the rebase list for `edit`.
4. **User Actions During Rebase:**
    - Git will stop at each commit marked for `edit`.
    - The script provides instructions printed to the console:
        - **Amend Author:** Run `git commit --amend --author="Tyler Zervas <tz-dev@vectorwieght.com>" --no-edit` (the script pre-fills the configured author).
        - **Sign Commit:** Run `git commit --amend -S`. This will use your GPG key. You can combine this with the author amend: `git commit --amend --author="Tyler Zervas <tz-dev@vectorwieght.com>" -S --no-edit`.
        - **Continue Rebase:** After amending and/or signing, run `git rebase --continue`.
    - Repeat these steps for each commit.
5. **Completion:**
    - After the rebase is successfully completed, the commits on `<branch-name>` will have the new author and will be signed.
    - The script will remind you to force-push the changes: `git push --force-with-lease origin <branch-name>`. **Always verify your changes locally before force-pushing.**

**Important Notes for the Script:**

- If any conflicts occur during the rebase, you will need to resolve them manually, then `git add <resolved-files>`, and `git rebase --continue`.
- To abort the entire rebase process at any time, use `git rebase --abort`.
- The target author (`Tyler Zervas <tz-dev@vectorwieght.com>`) is currently hardcoded in the script. This can be modified if needed.

## Contributing

Please refer to `AGENTS.md` for guidelines on contributing to this project, especially if you are an AI agent.
Key points:

- Follow PEP 8 for Python code.
- Write tests for all new features and bug fixes using Pytest.
- Use feature branches for development.
- Ensure commits are signed (see script above if needed).

## Agentic GPG Key Management and Signed Commits

This project provides tools and guidance for enabling AI agents (or automated processes) to manage GPG keys and make GPG-signed commits.

### Tool: GPG Key Generation and GitHub Addition (`key_manager.py`)

The script `src/mcp_tools/gpg_github_tool/key_manager.py` helps automate:

1. Generation of a new GPG key pair (optionally with a short expiry and no passphrase, suitable for agentic use).
2. Addition of the public GPG key to your GitHub account using a Personal Access Token.
3. Secure output of the private GPG key for import into the agent's GPG environment.

**Usage Example:**

```bash
# Ensure GITHUB_TOKEN environment variable is set
export GITHUB_TOKEN="your_github_pat_with_write:gpg_key_scope"

python src/mcp_tools/gpg_github_tool/key_manager.py \
    --name "My Agent Bot" \
    --email "agent@example.com" \
    --expiry "7d" # Key valid for 7 days
    # --passphrase "optional-passphrase-if-needed"
    # --output-private-key-file ./agent_private.key
```

Follow the script's output for instructions on importing the private key.

### Workflow for Agentic Signed Commits

Once a GPG key is generated (e.g., using `key_manager.py`) and imported into the agent's GPG environment, and Git is configured, an agent can make signed commits as follows:

1. **Configure Git (one-time setup per environment, or per repository):**
    The `key_manager.py` script provides these instructions upon successful key generation.
    - Set the GPG signing key for Git:

        ```bash
        git config user.signingkey <YOUR_KEY_ID>
        ```

    - Tell Git to sign all commits automatically:

        ```bash
        git config commit.gpgsign true
        ```

    - Ensure Git user name and email match the GPG key identity:

        ```bash
        git config user.name "Your Agent Name"
        git config user.email "your-agent-email@example.com"
        ```

    These can be set globally (`--global`) or per repository.

2. **Agent's Commit Workflow:**
    - **Make code changes:** The agent modifies files in the repository.
    - **Stage changes:**

        ```bash
        git add <file1> <file2> ...
        # or
        git add .
        ```

    - **Commit changes:**

        ```bash
        git commit -m "Automated commit message describing changes"
        ```

        If Git is configured as above, this commit will be automatically GPG-signed. If the GPG key has a passphrase, `gpg-agent` must be configured to provide it, or the key should be passphrase-less (recommended for short-lived agent keys).
    - **Push changes (to a feature branch):**

        ```bash
        git push origin <feature-branch-name>
        ```

**Security for Agentic Commits:**

- **Short-lived GPG keys:** Use keys with a defined, short expiration date (e.g., 1-7 days) for agents. Regenerate and replace them regularly using `key_manager.py`.
- **Passphrase-less keys:** For fully automated agents, passphrase-less GPG keys are often necessary. This makes secure storage and handling of the private key even more critical.
- **Scoped GitHub Tokens:** The GitHub Personal Access Token used by `key_manager.py` needs `write:gpg_key`. Tokens used by agents for pushing code should only have `repo` scope and ideally be fine-grained tokens restricted to specific repositories.
- **Branch Protection:** Protect your `main` (or other important) branches on GitHub to prevent direct pushes by agents. Agents should push to feature branches and create Pull Requests. Merging PRs should remain a human-supervised process.

## Tool: Automated PR Review Helper

The Automated PR Review Helper (`src/mcp_tools/pr_reviewer/cli.py`) is a command-line tool designed to check your current branch's changes against a defined set of policies before you create a Pull Request or push your changes. This helps ensure code quality, consistency, and adherence to project standards.

### Features

- **Configurable Policies:** Define policies in a `.pr-policy.yml` file in your repository root.
- **Checks Performed:**
  - **Branch Naming:** Verifies if the current branch name matches a specified regex pattern.
  - **Commit Messages:**
    - Checks for Conventional Commit format (e.g., `feat: ...`, `fix(scope): ...`).
    - Ensures commit messages include an issue/ticket number (configurable pattern).
  - **Disallowed Content:** Scans changed files for disallowed regex patterns (e.g., `TODO FIXME` without issue, basic secret detection).
  - **File Size:** Checks if any changed files exceed a maximum size limit.
- **Local Execution:** Run it locally on your feature branch before pushing.
- **CI Integration:** Can be incorporated into CI/CD pipelines to automate checks on Pull Requests.

### APRH Usage

1. **Ensure you are on your feature branch.**
2. **Run the tool from the root of your repository:**

    ```bash
    python -m src.mcp_tools.pr_reviewer.cli --base-branch <your_main_branch> --head-branch HEAD
    ```

    Or, if your feature branch is named `my-feature-branch` and base is `develop`:

    ```bash
    python -m src.mcp_tools.pr_reviewer.cli --base-branch develop --head-branch my-feature-branch
    ```

    **Arguments:**
    - `--base-branch <branch>`: The base branch to compare against (default: `main`).
    - `--head-branch <branch_or_rev>`: The head branch or revision to check (default: `HEAD`).
    - `--config-file <path>`: Path to the policy configuration YAML file (default: searches for `.pr-policy.yml` in repo root and parent directories).
    - `--repo-path <path>`: Path to the Git repository (default: current directory).

### Configuration (`.pr-policy.yml`)

Create a `.pr-policy.yml` file in the root of your repository to customize policies. If not found, default policies will be applied.

**Example `.pr-policy.yml`:**

```yaml
branch_naming:
  pattern: "^(feature|fix|chore|docs|refactor|test)/[a-zA-Z0-9_.-]+$" # Stricter: only lowercase after slash
  enabled: true

commit_messages:
  conventional_commit:
    enabled: true
    types: ["feat", "fix", "docs", "style", "refactor", "test", "chore", "ci", "build", "perf"] # Extended list
  require_issue_number:
    pattern: "\\[(JIRA|TASK|ISSUE)-[0-9]+\\]" # e.g., [JIRA-123]
    in_commit_body: true # Check in commit message body
    enabled: true
  enabled: true

disallowed_patterns:
  patterns:
    - pattern: "console\\.log"
      message: "Found 'console.log'. Please remove debug statements."
      enabled: true
    - pattern: "(SECRET|PASSWORD|API_KEY)\\s*[:=]\\s*['\\\"]?[^\\s'\\\"]+"
      message: "Potential hardcoded secret detected. Ensure this is intentional and secure."
      enabled: true
    - pattern: "TODO(?!\\s*:\\s*\\[(JIRA|TASK|ISSUE)-[0-9]+\\])" # TODO without a linked issue
      message: "Found 'TODO' without a linked issue (e.g., TODO: [JIRA-123] Description)."
      enabled: true
  enabled: true

file_size:
  max_bytes: 2097152 # 2MB
  ignore_extensions: [".lock", ".mp4", ".zip"]
  ignore_paths: ["vendor/*", "dist/*", "build/*", "*.log"] # Wildcards supported
  enabled: true
```

### Interpreting Output

- The tool will print the policies being checked and the results.
- If violations are found, they will be listed with details (e.g., file path, line number, commit SHA).
- The tool will exit with status code `0` if all checks pass, `1` if violations are found, and other non-zero codes for errors (e.g., Git issues, configuration problems).

This tool helps maintain code quality and consistency across your project by automating common pre-PR checks.

## Tool: IaC Drift Detector

The IaC (Infrastructure as Code) Drift Detector (`src/mcp_tools/iac_drift_detector/cli.py`) is a command-line tool to identify differences (drift) between your infrastructure's desired state (defined in IaC files) and its actual state in the cloud or other environments. It also provides suggestions for remediation.

### Current Features (Initial Version) - IaC Drift Detector

- **IaC Support:**
  - **Terraform:** Parses desired state from `.tfstate` files.

- **Actual State Source:**
  - **Mock Connector:** Uses a built-in mock data source to simulate actual cloud resources. This is useful for testing the tool's logic without live cloud access. (Future: AWS, GCP, Azure connectors).

- **Drift Detection:**
  - **Missing Resources:** Identifies resources defined in IaC but not found in the actual state.
  - **Unmanaged Resources:** Identifies resources found in the actual state but not defined (tracked) in the IaC state.
  - **Modified Resources:** Compares attributes of resources that exist in both states and flags differences. Includes basic support for ignoring common noisy attributes (e.g., ARNs, dynamic IPs for certain resource types) and special handling for `tags`.

- **Remediation Suggestions:** Provides human-readable suggestions for each detected drift (e.g., `terraform apply`, `terraform import`, or manual review).
- **CLI Interface:** Allows specifying IaC type, state file, and actual state source.

### Usage - IaC Drift Detector

1. **Prepare your IaC files:**
    - For Terraform, ensure you have a relevant `.tfstate` file representing the desired state of your infrastructure.

2. **Run the tool from the root of your repository (or provide paths):**

    ```bash
    python -m src.mcp_tools.iac_drift_detector.cli --iac-type terraform --tf-state-file /path/to/your/terraform.tfstate --actual-state-source mock
    ```

    **Arguments:**
    - `--iac-type <type>`: The IaC tool used (default/currently only: `terraform`).
    - `--tf-state-file <path>`: Path to the Terraform state file. **Required for Terraform.**
    - `--actual-state-source <source>`: Source for actual state (default/currently only: `mock`).
        - *(Future: `--aws-profile`, `--aws-region` for an AWS connector, etc.)*

### Example Output Interpretation - IaC Drift Detector

The tool will output:

1. Initialization messages (loading state, connector type).
2. A summary of the comparison process.
3. If drifts are detected:
    - A header indicating the number of drifts.
    - For each drift:
        - Drift type (e.g., `MODIFIED`, `MISSING_IN_ACTUAL`, `UNMANAGED_IN_ACTUAL`).
        - Resource type, logical name, and ID.
        - For `MODIFIED` drifts, a list of differing attributes with their IaC and actual values.
        - Suggested remediation actions.
4. An exit code:
    - `0`: No drift detected.
    - `1`: Drifts detected.
    - Other non-zero codes for errors (e.g., file not found, parsing issues).

**Example of a `MODIFIED` drift output:**

```text
Drift 1/X: MODIFIED
  Resource Type: aws_instance
  Resource Name: my_web_server
  Resource ID:   i-012345abcdef
  Attribute Differences:
    - 'instance_type': IaC = 't2.micro', Actual = 't3.small'
    - 'tags.Environment': IaC = 'dev', Actual = 'staging'
  Suggested Remediation:
    - Resource aws_instance.my_web_server (ID: i-012345abcdef) has modified attributes.
    -   - Attribute 'instance_type':
    -     - IaC expects: 't2.micro'
    -     - Actual is:   't3.small'
    -   - Attribute 'tags.Environment':
    -     - IaC expects: 'dev'
    -     - Actual is:   'staging'
    -   - Suggestion: Review the differences. If IaC is the source of truth, run 'terraform apply' to align the actual state.
    -     If changes in actual state are intentional and desired, update your Terraform code to match, then plan and apply.
```

### Current Limitations & Future Enhancements - IaC Drift Detector

- **Mock Only:** The initial version only supports a mock connector for the actual state. Real cloud provider connectors (AWS, GCP, Azure) are planned.
- **Terraform State Only:** Currently focuses on `.tfstate` for desired state. Parsing HCL directly or using plan files more extensively for drift could be added.
- **Basic Attribute Comparison:** The attribute diffing logic is basic and may need refinement for complex nested attributes or specific resource types. Configuration for ignored attributes is currently via a default dictionary in code.
- **Limited IaC Tool Support:** Only Terraform is supported.

---

This tool aims to help you keep your infrastructure aligned with its definition in code, reducing unexpected changes and improving stability.

## Tool: Configuration Optimization Recommender

The Configuration Optimization Recommender (`src/mcp_tools/config_optimizer/cli.py`) is a command-line tool that analyzes your Infrastructure as Code (IaC) configurations (initially Terraform state files) and provides recommendations for cost, performance, security, and reliability improvements.

### Current Features (Initial Version) - Configuration Optimization Recommender

- **IaC Support:**
  - **Terraform:** Analyzes resources parsed from `.tfstate` files.
- **Focus Areas (AWS):**
  - **EC2 Instances:**
    - Suggests upgrading to newer instance generations (e.g., T2 to T3, M4 to M5) based on a configurable map.
    - Flags usage of very large instance types, prompting for justification.
  - **S3 Buckets:**
    - Checks if server-side encryption (SSE) is enabled (optionally requiring SSE-KMS).
    - Checks if object versioning is enabled.
    - Verifies if all S3 Public Access Block settings are enabled.
- **Configurable Rules:** Define optimization rules and their parameters in a `.config-optimizer-rules.yml` file.
- **CLI Interface:** Allows specifying the IaC source file and a custom rules file.

### Usage: Configuration Optimization Recommender

1. **Prepare your IaC files:**
    - For Terraform, have a relevant `.tfstate` file.
2. **Optionally, create a custom rules file:**
    - Create a `.config-optimizer-rules.yml` in your repository root or specify a path to a custom rules YAML file if you want to override default checks or parameters.
3. **Run the tool from the root of your repository (or provide paths):**

    ```bash
    python -m src.mcp_tools.config_optimizer.cli --tf-state-file /path/to/your/terraform.tfstate
    ```

    To use a custom rules file:

    ```bash
    python -m src.mcp_tools.config_optimizer.cli --tf-state-file /path/to/your/terraform.tfstate --rules-file /path/to/custom-rules.yml
    ```

    **Arguments:**
    - `--iac-type <type>`: The IaC tool source (default/currently only: `terraform`).
    - `--tf-state-file <path>`: Path to the Terraform state file. **Required for Terraform.**
    - `--rules-file <path>`: Optional path to the optimization rules YAML file (default: searches for `.config-optimizer-rules.yml`).

### Interpreting Output: Configuration Optimization Recommender

- The tool will print messages about loading IaC data and rules.
- If recommendations are found:
  - A summary indicating the number of recommendations.
  - For each recommendation:
    - Severity (e.g., "High", "Medium", "Low").
    - A unique rule ID.
    - The affected resource (type, name, ID).
    - A descriptive message explaining the potential optimization.
    - Any relevant details (e.g., current vs. suggested instance type).
- An exit code:
  - `0`: No recommendations generated (all checks passed or no relevant resources/rules).
  - `1`: Recommendations found.
  - Other non-zero codes for errors.

### Configuration File Example: Configuration Optimization Recommender

```yaml
aws_ec2:
  enabled: true # Enable/disable all EC2 checks
  instance_type_optimization:
    enabled: true
    suggest_newer_generations: true
    generation_map: # Override or extend default map
      t2: t3 # Example: ensure t2 maps to t3 specifically
      # m3: m5 # Add custom mappings
    large_instance_types_to_flag: # Override default list
      - "m5.16xlarge"
      - "c5.12xlarge"
    # flag_large_types_without_tag: # Future: more complex tag-based exemption
    #   criticality!: ["high"]

aws_s3:
  enabled: true # Enable/disable all S3 checks
  encryption:
    enabled: true
    require_sse_kms: true # Stricter: require KMS, not just any SSE
  versioning:
    enabled: true # Ensure versioning is checked
  public_access_block:
    enabled: true
    require_all_blocks_true: true # Ensure all PAB settings are true
```

## Tool: Automated IaC Documentation Generator

The Automated IaC Documentation Generator (`src/mcp_tools/iac_doc_generator/cli.py`) analyzes your Terraform HCL code (`.tf` files) and generates Markdown documentation detailing the resources, variables, outputs, and modules defined within a Terraform module.

### Current Features (Initial Version) - Automated IaC Documentation Generator

- **IaC Support:**
  - **Terraform:** Parses HCL code from `.tf` files directly using `python-hcl2`.
- **Information Extracted:**
  - **Providers:** Name and alias.
  - **Variables:** Name, description (if provided in the variable block), type, default value, and sensitive status.
  - **Outputs:** Name, description, and sensitive status.
  - **Managed Resources:** Type and logical name (e.g., `aws_instance.web_server`).
  - **Module Calls:** Logical name of the module instance and its source path/URL.
- **Output Format:** Markdown (`.md`). Documentation is structured per file within the module.
- **CLI Interface:** Allows specifying the input directory (Terraform module path) and an output file or directory.

### Usage: Automated IaC Documentation Generator

1. **Point to your Terraform module directory:**
    Ensure the directory contains your `.tf` files.
2. **Run the tool from your project root (or ensure `src` is in `PYTHONPATH`):**

    To print to Standard Output:

    ```bash
    python -m src.mcp_tools.iac_doc_generator.cli /path/to/your/terraform_module_directory
    ```

    To output to a specific Markdown file:

    ```bash
    python -m src.mcp_tools.iac_doc_generator.cli /path/to/your/terraform_module_directory -o /path/to/output/documentation.md
    ```

    To output to a directory (will create `README.md` inside it):

    ```bash
    python -m src.mcp_tools.iac_doc_generator.cli /path/to/your/terraform_module_directory -o /path/to/output_docs_directory
    ```

    **Arguments:**
    - `input_dir`: (Positional) Path to the directory containing the Terraform module.
    - `--output-file` (`-o`): Optional path for the output Markdown file. If a directory is given, `README.md` is created inside. If omitted, output goes to STDOUT.

### Example Output Structure (Snippet)

The generated Markdown will typically include:

- A main header for the module.
- Sections for each `.tf` file found.
- Within each file section, tables or lists for:
  - Providers
  - Variables (Name, Description, Type, Default, Sensitive)
  - Outputs (Name, Description, Sensitive)
  - Managed Resources (Type.Name)
  - Module Calls (Name (Source))

```markdown
# Terraform Module: `my_module_name`
**Path:** `/path/to/your/terraform_module_directory`

<!-- Optional module description here -->

---
## File: `variables.tf`

### Variables
| Name             | Description                     | Type     | Default        | Sensitive |
|------------------|---------------------------------|----------|----------------|-----------|
| `instance_count` | Number of web instances         | `number` | `1`            | `False`   |
| `admin_user`     | Admin username                  | `string` | *(Required)*   | `True`    |

---
## File: `main.tf`

### Providers
- `aws` (alias: `primary`)

### Managed Resources
- **`aws_instance.web`**

### Module Calls
- **`vpc`** (Source: `./modules/custom_vpc`)

---
## File: `outputs.tf`

### Outputs
| Name              | Description                 | Sensitive |
|-------------------|-----------------------------|-----------|
| `web_instance_ip` | Public IP of the web instance | `False`   |
| `vpc_id_out`      | ID of the VPC               | `True`    |
```

### Current Limitations & Future Enhancements - Automated IaC Documentation Generator

- **Comment Parsing:** Extraction of descriptions primarily relies on `description` attributes within `variable` and `output` blocks. Associating arbitrary HCL comments with specific blocks is complex and currently very basic.
- **Terraform HCL Only:** Initial version focuses on Terraform.
- **Basic Structure:** The Markdown output structure is currently fixed. Template-based rendering could be added for customization.
- **No Cross-File Resolution:** Does not yet resolve dependencies or references between files or modules in-depth (e.g., to pull descriptions for module inputs from the module's own variables).
- **Limited Detail for Resources/Modules:** Currently lists resources and module calls by name/type and source. Could be expanded to include key arguments or attributes.

---

This tool helps automate the creation of baseline documentation for your Terraform modules, making it easier to understand their components and usage.

## Tool: Git Compliance Analyzer

The Git Compliance Analyzer (`src/mcp_tools/git_compliance_analyzer/cli.py`) is a command-line tool that scans a local Git repository against a configurable set of compliance rules. It helps ensure that repository content, commit history, and potentially IaC configurations adhere to defined standards.

### Current Features (Initial Version) - Git Compliance Analyzer

- **Configurable Rules:** Define compliance policies in a `.compliance-rules.yml` file.
- **Checks Performed:**
  - **File Existence:** Verify that specific files must exist (e.g., `LICENSE`) or must *not* exist based on glob patterns (e.g., `*.pem`).
  - **File Content:** Scan files (matching a path regex) for required or forbidden regex patterns within their content.
  - **Commit History:**
    - Analyze commit messages (on the current branch compared to a base branch) for Conventional Commit format compliance.
  - **IaC Validation (Basic):**
    - Wrapper to run `terraform validate` in specified directories within the repository. (Requires `terraform` CLI in PATH).
- **CLI Interface:** Specify repository path, branch to analyze, base branch for commit history, and a custom rules file.
- **Reporting:** Outputs a list of compliance findings with severity, messages, and relevant context (file paths, commit SHAs).

### Usage: Git Compliance Analyzer

1. **Ensure you have a local clone of the Git repository you want to analyze.**
2. **Optionally, create a `.compliance-rules.yml` file in the repository root** to define your specific compliance rules. If not found, default checks (which are minimal) will apply.
3. **Run the tool from your project root (or ensure `src` is in `PYTHONPATH`):**

    ```bash
    # Analyze the current directory's repo, HEAD revision, comparing history against 'origin/main'
    python -m src.mcp_tools.git_compliance_analyzer.cli . --branch HEAD --base-branch origin/main

    # Analyze a specific repository path and branch, using a custom rules file
    python -m src.mcp_tools.git_compliance_analyzer.cli /path/to/your/repo --branch my-feature-branch --base-branch develop --rules-file /path/to/custom-compliance.yml
    ```

    **Arguments:**
    - `repo_path`: (Positional, Optional) Path to the Git repository (default: current directory).
    - `--branch <branch/rev>` (`-b`): Branch, tag, or commit SHA to analyze the state of (default: `HEAD`).
    - `--base-branch <branch>`: Base branch for commit history comparison (default: `None`, skips history checks that need a base).
    - `--rules-file <path>`: Optional path to the compliance rules YAML file (default: searches for `.compliance-rules.yml`).

### Interpreting Output: Git Compliance Analyzer

- The tool prints messages about the repository and rules being used.
- It lists different checks being performed.
- If compliance findings (violations) are discovered:
  - A summary indicates the total number of findings.
  - Each finding is detailed with its severity, rule ID, a descriptive message, and context (e.g., file path, line number, commit SHA).
- An exit code:
  - `0`: All checks passed (or no relevant rules triggered findings).
  - `1`: Compliance findings were reported.
  - Other non-zero codes for operational errors (e.g., invalid repo path, rules file issues).

### Current Limitations & Future Enhancements - Git Compliance Analyzer

- **Local Execution Only:** Currently analyzes local Git repository clones.
- **Limited IaC Tooling:** `iac_validation_checks` is basic (e.g., `terraform validate`). Could be expanded for more tools (Terrascan, Checkov) and richer output parsing.
- **Comment/Contextual Understanding:** Deeper understanding of comments or code context for more intelligent pattern matching is a future goal.
- **Remediation:** Currently only reports findings. Future versions could suggest or (with caution) attempt automated remediation for some issues.

---

This tool helps enforce coding standards, security practices, and project conventions within your Git repositories.
