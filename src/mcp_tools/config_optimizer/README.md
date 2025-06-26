# Configuration Optimization Recommender

The Configuration Optimization Recommender (`cli.py` in this directory) is a command-line tool that analyzes your Infrastructure as Code (IaC) configurations (initially focusing on Terraform state files) and provides recommendations for improvements in areas like cost, performance, security, and reliability.

## Current Features (Initial Version)

*   **IaC Support:**
    *   **Terraform:** Analyzes resources parsed from `.tfstate` files. This means it evaluates the *last known state* of your infrastructure as understood by Terraform.
*   **Focus Areas (AWS Cloud Provider):**
    *   **EC2 Instances:**
        *   **Newer Generations:** Suggests upgrading to newer instance generations if available and potentially more cost-effective or performant (e.g., T2 to T3, M4 to M5). This uses a configurable mapping.
        *   **Large Instance Types:** Flags usage of very large instance types (from a configurable list), prompting a review to ensure they are justified by workload requirements.
    *   **S3 Buckets:**
        *   **Server-Side Encryption (SSE):** Checks if SSE is enabled. Can be configured to specifically require SSE-KMS.
        *   **Object Versioning:** Checks if S3 bucket versioning is enabled to protect against accidental data loss.
        *   **Public Access Block:** Verifies if all S3 Public Access Block settings are enabled to prevent unintended public exposure.
*   **Configurable Rules:** Define and customize optimization rules and their parameters in a YAML file (default: `.config-optimizer-rules.yml`). This allows tailoring recommendations to your specific needs and standards.
*   **CLI Interface:** Allows specifying the IaC source file (e.g., `terraform.tfstate`) and a custom rules file.

## Usage

1.  **Prepare your IaC files:**
    *   For Terraform, ensure you have a relevant `.tfstate` file representing the last applied state of your infrastructure.
2.  **Optionally, create a custom rules file:**
    *   Create a `.config-optimizer-rules.yml` file in your repository root (or another location specified by `--rules-file`) if you wish to override default checks, parameters, or disable certain rules. If no file is found, built-in default rules are applied.
3.  **Run the tool from your project root** (or ensure `src` is in `PYTHONPATH`):

    To analyze a Terraform state file using default or auto-detected rules:
    ```bash
    python -m src.mcp_tools.config_optimizer.cli --tf-state-file /path/to/your/terraform.tfstate
    ```

    To use a custom rules file:
    ```bash
    python -m src.mcp_tools.config_optimizer.cli --tf-state-file /path/to/your/terraform.tfstate --rules-file /path/to/your/custom-rules.yml
    ```

### Command-Line Arguments

*   `--iac-type <type>`: The IaC tool source.
    *   Default: `terraform`
    *   Choices: `terraform` (currently only option)
*   `--tf-state-file <path>`: Path to the Terraform state file (`.tfstate`). **Required if `--iac-type` is `terraform`.**
*   `--rules-file <path>`: Optional path to the optimization rules YAML configuration file. If not provided, the tool searches for `.config-optimizer-rules.yml` in the current directory and its parents.

## Configuration (`.config-optimizer-rules.yml`)

Customize the optimization checks by creating a `.config-optimizer-rules.yml` file.

**Example `.config-optimizer-rules.yml`:**

```yaml
aws_ec2:
  enabled: true # Master switch for all EC2 checks
  instance_type_optimization:
    enabled: true
    suggest_newer_generations: true
    # generation_map can be used to override/extend default suggestions
    # e.g., to suggest specific AMD or Graviton alternatives
    generation_map:
      t2: t3a # Prefer t3a over t3 for t2 upgrades
      m4: m5a
    large_instance_types_to_flag: # Define which types are considered "large"
      - "m5.16xlarge"
      - "c5.12xlarge"
      - "r5.metal"
    # flag_large_types_without_tag: # Future enhancement for tag-based exemptions
    #   criticality!: ["high", "true"]

aws_s3:
  enabled: true # Master switch for all S3 checks
  encryption:
    enabled: true
    require_sse_kms: true # Be stricter: require KMS, not just any SSE (e.g. AES256)
  versioning:
    enabled: true # Ensure versioning is checked
  public_access_block:
    enabled: true
    require_all_blocks_true: true # Ensure all four PAB settings are true
```

### Rule Details:

*   **`aws_ec2` / `aws_s3` (etc.):** Top-level keys for each AWS service (or future provider).
    *   `enabled`: `true` or `false` to toggle all checks for that service.
*   **`instance_type_optimization` (under `aws_ec2`):**
    *   `enabled`: `true` or `false`.
    *   `suggest_newer_generations`: `true` or `false`.
    *   `generation_map`: A dictionary mapping old instance type prefixes to new ones (e.g., `"t2": "t3a"`).
    *   `large_instance_types_to_flag`: A list of specific, large instance types that should be flagged for review.
*   **`encryption` (under `aws_s3`):**
    *   `enabled`: `true` or `false`.
    *   `require_sse_kms`: `true` if SSE-KMS is mandatory, `false` if any SSE (like AES256) is acceptable.
*   **`versioning` (under `aws_s3`):**
    *   `enabled`: `true` or `false`.
*   **`public_access_block` (under `aws_s3`):**
    *   `enabled`: `true` or `false`.
    *   `require_all_blocks_true`: `true` if all four PAB settings must be active.

## Interpreting Output

*   The tool will print messages about loading IaC data and the rules being applied.
*   If recommendations are found:
    *   A summary line: "--- Result: X OPTIMIZATION RECOMMENDATION(S) FOUND ---".
    *   For each recommendation:
        *   **Severity:** e.g., "High", "Medium", "Low", "Informational".
        *   **Rule ID:** A unique identifier for the triggered rule (e.g., `AWS_EC2_NEWER_GENERATION_MAPPED`).
        *   **Resource:** The type, logical name, and cloud ID (if available) of the affected resource.
        *   **Message:** A human-readable description of the potential optimization.
        *   **Details:** (Optional) A dictionary with extra context (e.g., current vs. suggested instance type).
*   If no recommendations are generated based on the active rules and resources: "--- Result: NO OPTIMIZATION RECOMMENDATIONS FOUND ---".
*   **Exit Code:**
    *   `0`: No recommendations generated.
    *   `1`: Recommendations were found.
    *   Other non-zero codes for operational errors (e.g., file not found, rule parsing issues).

### Example of a Recommendation Output Snippet:

```
Recommendation 1/X: [Low|AWS_EC2_NEWER_GENERATION_MAPPED]
  Resource: aws_instance 'old_web_server' (ID: i-012345abcdef)
  Message:  Instance type 't2.medium' is an older generation. Consider upgrading to a newer generation like 't3a.medium' from the same family for potential cost/performance benefits. Verify compatibility and pricing.
  Details:  {'current_type': 't2.medium', 'suggested_type_example': 't3a.medium'}
```

## Current Limitations & Future Enhancements

*   **Terraform State File Focus:** The tool primarily analyzes `.tfstate` files. This reflects the *last applied state*, not necessarily the *current HCL definition* if there are unapplied changes. Future enhancements could include direct HCL parsing for a more "desired state" analysis.
*   **Limited AWS Service Coverage:** Initial checks are focused on AWS EC2 and S3. Support for more AWS services (RDS, ELB, IAM, etc.) and other cloud providers (GCP, Azure) is a key area for expansion.
*   **Basic Recommendation Logic:** Some recommendation logic (e.g., instance "right-sizing" beyond just flagging large types, or mapping newer generations) is currently based on simple heuristics or predefined maps. More advanced analysis, potentially integrating with:
    *   Cloud provider pricing APIs.
    *   Actual resource utilization metrics (e.g., from CloudWatch), would significantly improve recommendation quality but adds complexity.
*   **Static Rule Definitions:** While rules are configurable via YAML, the core logic for *how* a rule works is implemented in Python. More dynamic or user-defined rule engines could be explored.
*   **No Automated Remediation:** The tool only provides recommendations; it does not attempt to apply any changes.

This tool aims to help identify potential areas to optimize your cloud configurations for better cost efficiency, performance, security posture, and operational reliability by analyzing your IaC definitions.
```
