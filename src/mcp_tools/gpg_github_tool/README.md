# GPG Key Management and Agentic GitHub Operations Helper

This tool (`key_manager.py`) assists in generating GPG keys and adding them to a GitHub account. It's particularly useful for setting up environments where AI agents or automated processes need to make GPG-signed commits.

## Tool: GPG Key Generation and GitHub Addition (`key_manager.py`)

The script `key_manager.py` (located in this directory) helps automate:
1.  **Generation of a new GPG key pair:**
    *   Supports RSA 4096-bit keys.
    *   Allows specifying user name, email, and an expiration date (e.g., "7d" for 7 days, "1y" for 1 year, "0" for no expiry). Short-lived keys are recommended for agentic use.
    *   Optionally, a passphrase can be set for the key. For fully automated agentic use, passphrase-less keys (combined with short expiry) are often more practical but require careful handling of the private key.
2.  **Addition of the public GPG key to your GitHub account:**
    *   Uses a GitHub Personal Access Token (PAT) with the `write:gpg_key` scope.
3.  **Secure output of the private GPG key:**
    *   The armored private key can be outputted to STDOUT or saved to a specified file.
    *   Strong warnings are provided regarding the secure handling of this private key.

### Prerequisites

*   Python 3.x
*   `gnupg` CLI installed and in PATH.
*   Required Python packages: `python-gnupg`, `httpx` (installable via project's `pyproject.toml` or `requirements.txt`).
*   A GitHub Personal Access Token (Classic) with the `write:gpg_key` scope.

### Usage

The script is run as a Python module:
```bash
python -m src.mcp_tools.gpg_github_tool.key_manager [OPTIONS]
```

**Key Options:**
*   `--name TEXT`: Real name for the GPG key (e.g., "My Agent Bot"). (Required)
*   `--email TEXT`: Email for the GPG key. (Required)
*   `--expiry TEXT`: Expiration for the GPG key (e.g., 0, 1y, 30d). Default: "7d".
*   `--passphrase TEXT`: Optional passphrase for the GPG key.
*   `--github-token TEXT`: GitHub PAT. Can also be set via `GITHUB_TOKEN` environment variable. (Required)
*   `--gpg-home TEXT`: Custom GPG home directory. Defaults to a temporary directory for the run.
*   `--output-private-key-file FILE`: If specified, saves the armored private key to this file. Otherwise, prints to STDOUT.

**Example:**
To generate a key for "Agent X" expiring in 7 days, without a passphrase, and add it to GitHub:
```bash
# Ensure GITHUB_TOKEN environment variable is set, or use --github-token
export GITHUB_TOKEN="your_github_pat_with_write:gpg_key_scope"

python -m src.mcp_tools.gpg_github_tool.key_manager \
    --name "Agent X" \
    --email "agent-x@example.com" \
    --expiry "7d"
    # The private key will be printed to STDOUT.
```

To save the private key to a file and set a passphrase:
```bash
python -m src.mcp_tools.gpg_github_tool.key_manager \
    --name "Secure Agent Key" \
    --email "secure-agent@example.com" \
    --expiry "30d" \
    --passphrase "mySuperSecretPassphrase" \
    --github-token "your_pat_here" \
    --output-private-key-file ./secure_agent_private.key
```

**Output:**
The script will output:
*   The Key ID of the generated GPG key.
*   The full armored private key (either to STDOUT or the specified file).
*   Instructions for manually importing the private key into a GPG keyring and configuring Git to use it.

### Security Considerations for `key_manager.py`
*   **GitHub Token:** Handle your GitHub PAT securely. Avoid hardcoding it or committing it to repositories. Using environment variables is recommended.
*   **Private Key:** The generated private key is extremely sensitive.
    *   If outputted to STDOUT, ensure it's captured securely and not logged inadvertently.
    *   If saved to a file, ensure the file has restrictive permissions (the script attempts to set `600`) and is stored securely (e.g., encrypted volume, hardware token, or imported into a GPG agent and then deleted).
    *   For passphrase-less keys, the private key file itself is unprotected. These are best suited for short-lived keys in controlled environments.
*   **GPG Home:** By default, the script uses a temporary GPG home directory for key generation, which is cleaned up afterwards. This means the generated key is not automatically added to your user's default GPG keyring unless you explicitly import the outputted private key. This is generally safer for ephemeral/agent keys.

## Workflow for Agentic Signed Commits

Once a GPG key is generated (e.g., using `key_manager.py`), its private key imported into the agent's GPG environment, and Git configured, an agent can make GPG-signed commits.

### 1. Configure Git (One-Time Setup)

The `key_manager.py` script provides these instructions upon successful key generation. This setup needs to be done in the environment where the agent will run `git commit`.

*   **Set the GPG Signing Key for Git:**
    ```bash
    git config --global user.signingkey <YOUR_KEY_ID>
    ```
    (Replace `<YOUR_KEY_ID>` with the GPG Key ID outputted by `key_manager.py`. Use `--local` instead of `--global` to configure for a single repository.)

*   **Tell Git to Sign All Commits Automatically:**
    ```bash
    git config --global commit.gpgsign true
    ```

*   **Ensure Git User Name and Email Match the GPG Key Identity:**
    ```bash
    git config --global user.name "Your Agent Name"
    git config --global user.email "your-agent-email@example.com"
    ```
    (These should match the `--name` and `--email` used when generating the key.)

### 2. Agent's Commit Workflow

With Git configured as above, the agent's workflow for making signed commits is standard:

*   **Make code changes:** The agent modifies files in the repository.
*   **Stage changes:**
    ```bash
    git add <file1> <file2> ...
    # or
    git add .
    ```
*   **Commit changes:**
    ```bash
    git commit -m "Automated commit message describing changes"
    ```
    If `commit.gpgsign true` is set, Git will automatically attempt to sign this commit using the key specified by `user.signingkey`.
    *   If the GPG key has a passphrase, `gpg-agent` (or a similar mechanism) must be configured to provide it (e.g., by caching it after first use). This can be complex for full automation.
    *   For passphrase-less keys (recommended for short-lived agent keys generated by `key_manager.py`), this step should proceed without interactive prompts.

*   **Push changes (to a feature branch):**
    ```bash
    git push origin <feature-branch-name>
    ```

### Security Best Practices for Agentic Commits

*   **Short-Lived GPG Keys:** Use keys with a defined, short expiration date (e.g., 1-7 days) for agents. Regenerate and replace them regularly using `key_manager.py`.
*   **Passphrase-Less Keys:** For fully automated agents, passphrase-less GPG keys are often necessary. This makes the secure storage and handling of the exported private key paramount.
*   **Scoped GitHub Tokens:** The GitHub Personal Access Token used by `key_manager.py` requires the `write:gpg_key` scope. Tokens used by agents for pushing code should only have `repo` scope and ideally be GitHub Fine-Grained Personal Access Tokens restricted to specific repositories and permissions.
*   **Branch Protection Rules:** Configure branch protection rules on GitHub for your `main` (or other important) branches to prevent direct pushes by agents. Agents should push to feature branches, and Pull Requests should be reviewed by humans before merging.
*   **Secure Agent Environment:** The environment where the agent runs and has access to the GPG private key must be secured.
```
