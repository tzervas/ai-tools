# IaC Drift Detector

The Infrastructure as Code (IaC) Drift Detector (`cli.py` in this directory) is a command-line tool designed to identify differences (drift) between your infrastructure's desired state (as defined in IaC files) and its actual state in the cloud or other managed environments. It also provides suggestions for remediation.

This tool helps you maintain consistency, prevent unexpected configurations, and ensure your live infrastructure aligns with its version-controlled definitions.

## Current Features (Initial Version)

*   **IaC Support:**
    *   **Terraform:** Parses the desired state from Terraform state files (`.tfstate`).
*   **Actual State Source:**
    *   **Mock Connector:** Includes a built-in mock data source (`MockActualStateConnector`) to simulate actual cloud resources. This is primarily for testing the tool's logic without requiring live cloud access or credentials.
    *   *(Future: Connectors for AWS, GCP, Azure, etc.)*
*   **Drift Detection Capabilities:**
    *   **Missing Resources:** Identifies resources defined in your IaC state but not found in the actual (mocked) environment.
    *   **Unmanaged Resources:** Identifies resources found in the actual (mocked) environment that are not defined or tracked in your IaC state.
    *   **Modified Resources:** Compares attributes of resources that exist in both states and flags differences.
        *   Includes basic support for ignoring common noisy or dynamic attributes (e.g., ARNs, dynamic IPs for certain resource types – currently managed by a default internal dictionary).
        *   Provides special handling for `tags` to check if IaC-defined tags are present and correctly valued in the actual resource (extra tags in the actual resource are not currently flagged as drift).
*   **Remediation Suggestions:** For each detected drift, it provides human-readable suggestions, tailored for the specified IaC tool (currently Terraform, e.g., `terraform apply`, `terraform import`, or manual review).
*   **CLI Interface:** Allows specifying the IaC type, path to the state file, and the source for the actual state (currently only "mock").

## Usage

1.  **Prepare your IaC files:**
    *   For Terraform, ensure you have a relevant `.tfstate` file that represents the desired state of your infrastructure.
2.  **Run the tool from your project root** (or ensure `src` is in `PYTHONPATH`):

    ```bash
    python -m src.mcp_tools.iac_drift_detector.cli --iac-type terraform --tf-state-file /path/to/your/terraform.tfstate --actual-state-source mock
    ```

### Command-Line Arguments

*   `--iac-type <type>`: The IaC tool being used.
    *   Default: `terraform`
    *   Choices: `terraform` (currently only option)
*   `--tf-state-file <path>`: Path to the Terraform state file (`.tfstate`). **Required if `--iac-type` is `terraform`.**
*   `--actual-state-source <source>`: Source to fetch the actual infrastructure state from.
    *   Default: `mock`
    *   Choices: `mock` (currently only option)
    *   *(Future: `--aws-profile <profile>`, `--aws-region <region>` for an AWS connector; similar for GCP, Azure.)*

## Interpreting Output

The tool will provide output in the following stages:
1.  **Initialization:** Messages indicating the IaC type, state file being loaded, and the actual state source being used.
2.  **Comparison Summary:** A message indicating that state comparison and drift detection is in progress.
3.  **Drift Report:**
    *   If no drifts are detected: A message like "--- Result: NO DRIFT DETECTED ---".
    *   If drifts are detected:
        *   A header: "--- Result: X DRIFT(S) DETECTED ---".
        *   For each detected drift:
            *   **Drift Type:** e.g., `MODIFIED`, `MISSING_IN_ACTUAL`, `UNMANAGED_IN_ACTUAL`.
            *   **Resource Details:** Type, logical name (from IaC if available), and cloud ID.
            *   **Specific Differences (for `MODIFIED`):** A list of attributes that differ, showing the IaC expected value and the actual value.
            *   **General Message (for other types):** A summary of why the resource is considered drifted.
            *   **Suggested Remediation:** Actionable steps to resolve the drift (e.g., "Run 'terraform apply'", "Consider 'terraform import ...'").
4.  **Exit Code:**
    *   `0`: No drift detected.
    *   `1`: Drifts were detected.
    *   `2`: Error related to IaC file input (e.g., file not found, parsing error).
    *   `3`: Error related to the actual state source (e.g., connector not implemented).
    *   Other non-zero codes for unexpected errors.

### Example of a `MODIFIED` Drift Output Snippet:

```
Drift 1/X: MODIFIED
  Resource Type: aws_instance
  Resource Name: my_web_server_iac  (Name from IaC)
  Resource ID:   i-012345abcdef
  Attribute Differences:
    - 'tags.Environment': IaC = 'dev', Actual = 'staging'
    - 'instance_type': IaC = 't2.micro', Actual = 't3.small'
  Suggested Remediation:
    - Resource aws_instance.my_web_server_iac (ID: i-012345abcdef) has modified attributes.
    -   - Attribute 'tags.Environment':
    -     - IaC expects: 'dev'
    -     - Actual is:   'staging'
    -   - Attribute 'instance_type':
    -     - IaC expects: 't2.micro'
    -     - Actual is:   't3.small'
    -   - Suggestion: Review the differences. If IaC is the source of truth, run 'terraform apply' to align the actual state.
    -     If changes in actual state are intentional and desired, update your Terraform code to match, then plan and apply.
```

## Current Limitations & Future Enhancements

*   **Mock Actual State Only:** The initial version relies entirely on a `MockActualStateConnector`. Real cloud provider connectors (AWS, GCP, Azure) are necessary for practical use and are planned future enhancements.
*   **Terraform State File Focus:** Currently analyzes desired state from `.tfstate` files. Future versions could:
    *   Parse Terraform HCL code directly for a richer understanding of desired state and to operate without needing a state file (e.g., for dry runs on new code).
    *   Utilize Terraform plan files (`terraform show -json plan.out`) more effectively to predict drift or validate planned changes against actual state *before* applying.
*   **Basic Attribute Comparison:** The logic for comparing resource attributes in the `drift_engine.py` is currently basic. It may require refinement for:
    *   Handling complex nested attributes and data structures more intelligently.
    *   More sophisticated type coercion or normalization before comparison.
    *   More configurable and granular rules for ignoring specific attributes or attribute patterns (currently uses a hardcoded default dictionary with basic ignores).
*   **Limited IaC Tool Support:** Only Terraform is supported in this initial version. Support for other IaC tools like CloudFormation, Pulumi, Ansible, or Kubernetes manifests could be added.
*   **No Configuration File for Drift Rules:** Unlike some other tools in this project, the drift detector itself doesn't yet have its own configuration file for defining what constitutes "significant" drift or detailed ignore rules (beyond the internal attribute ignore list).

This tool aims to be a foundational piece in maintaining IaC hygiene and ensuring that your deployed infrastructure accurately reflects its intended, version-controlled configuration.
```
