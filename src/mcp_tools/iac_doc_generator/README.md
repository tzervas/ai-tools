# Automated IaC Documentation Generator

The Automated Infrastructure as Code (IaC) Documentation Generator (`cli.py` in this directory) analyzes your Terraform HCL code (`.tf` files) and automatically generates Markdown documentation. This documentation details the resources, variables, outputs, providers, and module calls defined within a specified Terraform module directory.

This tool helps maintain up-to-date documentation for your Terraform modules, making them easier to understand, use, and maintain.

## Current Features (Initial Version)

*   **IaC Support:**
    *   **Terraform:** Parses HCL code directly from `.tf` files within a module directory using the `python-hcl2` library.
*   **Information Extracted and Documented (per file, then aggregated for the module):**
    *   **Providers:** Name and alias (e.g., `aws (alias: primary)`).
    *   **Variables:** Name, description (extracted from the `description` attribute in the `variable` block), type, default value, and sensitive status.
    *   **Outputs:** Name, description (from the `description` attribute), and sensitive status.
    *   **Managed Resources:** Type and logical name (e.g., `aws_instance.web_server`).
    *   **Module Calls:** Logical name given to the module instance (e.g., `my_vpc_module`) and its source path or URL.
*   **Output Format:**
    *   **Markdown (`.md`):** Documentation is generated in Markdown format.
    *   The output is structured with a main header for the module, followed by sections for each `.tf` file processed. Within each file section, tables or lists are used for providers, variables, outputs, resources, and module calls.
*   **CLI Interface:** Allows specifying the input directory (the Terraform module path) and an output destination (a specific file, a directory where `README.md` will be created, or STDOUT).

## Usage

1.  **Point to your Terraform module directory:**
    Ensure the directory you specify contains your Terraform HCL configuration files (`.tf` files).
2.  **Run the tool from your project root** (or ensure `src` is in `PYTHONPATH`):

    To generate documentation and print it to Standard Output:
    ```bash
    python -m src.mcp_tools.iac_doc_generator.cli /path/to/your/terraform_module_directory
    ```

    To output the documentation to a specific Markdown file:
    ```bash
    python -m src.mcp_tools.iac_doc_generator.cli /path/to/your/terraform_module_directory -o /path/to/output/module_documentation.md
    ```

    To output to a directory (which will result in `README.md` being created inside that directory):
    ```bash
    # First, create the output directory if it doesn't exist
    mkdir -p /path/to/output_docs_directory
    python -m src.mcp_tools.iac_doc_generator.cli /path/to/your/terraform_module_directory -o /path/to/output_docs_directory
    ```

### Command-Line Arguments

*   `input_dir` (Positional): The path to the directory containing the Terraform module files.
*   `--output-file` (`-o`) (Optional):
    *   Path to the output Markdown file.
    *   If a directory path is provided, a `README.md` file will be created within that directory.
    *   If this option is omitted, the generated Markdown will be printed to STDOUT.

## Example Output Structure (Snippet)

The generated Markdown documentation will typically look like this:

```markdown
# Terraform Module: `my_module_name`
**Path:** `/path/to/your/terraform_module_directory`

<!-- Optional overall module description could be added here if parsed -->

---
## File: `variables.tf`

<!-- Optional file-level description -->

### Variables
| Name             | Description                     | Type     | Default        | Sensitive |
|------------------|---------------------------------|----------|----------------|-----------|
| `instance_count` | Number of web instances         | `number` | `1`            | `False`   |
| `admin_user`     | Admin username                  | `string` | *(Required)*   | `True`    |
| ...              | ...                             | ...      | ...            | ...       |

---
## File: `main.tf`

<!-- Optional file-level description -->

### Providers
- `aws` (alias: `primary`)
- `random`

### Managed Resources
- **`aws_instance.web_server`**
- **`aws_db_instance.database`**

### Module Calls
- **`networking_module`** (Source: `./modules/vpc`)
- **`s3_backend_storage`** (Source: `git::https://example.com/tf-modules/s3.git?ref=v1.0.0`)

---
## File: `outputs.tf`

<!-- Optional file-level description -->

### Outputs
| Name              | Description                 | Sensitive |
|-------------------|-----------------------------|-----------|
| `web_instance_ip` | Public IP of the web instance | `False`   |
| `database_arn`    | ARN of the RDS instance     | `True`    |
| ...               | ...                         | ...       |
```

## Current Limitations & Future Enhancements

*   **Comment Parsing for Descriptions:** Extraction of descriptions for modules, files, resources, etc., primarily relies on explicit `description` attributes within `variable` and `output` blocks. Associating general HCL comments (e.g., `//` or `#` comments preceding a block, or `/* ... */` block comments) with specific HCL elements is a complex task and is currently very basic or not implemented.
*   **Terraform HCL Focus:** The initial version is specifically designed for Terraform HCL files. Support for other IaC languages (e.g., CloudFormation YAML/JSON, Pulumi, Ansible) would require different parsers.
*   **Fixed Markdown Structure:** The output Markdown structure is currently fixed by the `MarkdownRenderer`. Future enhancements could include using customizable templates (e.g., Jinja2 templates) to allow users to define their own documentation layouts.
*   **No Cross-File or Deep Module Resolution:** The tool currently documents elements as defined within each file of the specified module directory. It does not yet:
    *   Resolve complex variable interpolations or dependencies across files in-depth.
    *   Recursively parse and document sub-modules referenced in `module` blocks (it lists the call and source).
    *   Pull input variable descriptions for a module call from the sub-module's own variable definitions.
*   **Limited Detail for Resources/Modules:** For managed resources and module calls, it currently lists their type, logical name, and source (for modules). It could be expanded to extract and document key arguments/attributes passed to resources or modules.
*   **Error Handling:** While basic error handling for file operations and HCL parsing is included, it could be made more robust for complex or malformed HCL.

This tool aims to provide a solid baseline for automatically generating documentation from your Terraform modules, helping to keep documentation efforts synchronized with code changes and improving the overall maintainability and understandability of your IaC projects.
```
