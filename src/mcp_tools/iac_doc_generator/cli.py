import argparse
import os
import sys
from pathlib import Path

from .terraform_hcl_parser import parse_terraform_module_directory, TerraformModuleProcessedDoc
from .markdown_renderer import MarkdownRenderer

def main():
    parser = argparse.ArgumentParser(description="Automated IaC Documentation Generator for Terraform Modules.")
    parser.add_argument("input_dir", type=str,
                        help="Path to the directory containing the Terraform module (.tf files).")
    parser.add_argument("--output-file", "-o", type=str, default=None,
                        help="Path to the output Markdown file. If not specified, prints to STDOUT. "
                             "If a directory is specified, a README.md will be created in it.")
    # Future args:
    # parser.add_argument("--recursive", action="store_true", help="Recursively process submodules.")
    # parser.add_argument("--format", type=str, default="markdown", choices=["markdown"], help="Output format.")
    # parser.add_argument("--template-file", type=str, help="Path to a custom Markdown template file.")

    args = parser.parse_args()

    print(f"--- IaC Documentation Generator Initializing ---")
    input_path = Path(args.input_dir).resolve()

    if not input_path.is_dir():
        print(f"Error: Input path '{input_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing Terraform module at: {input_path}")

    # 1. Parse the Terraform module directory
    try:
        module_doc_data: TerraformModuleProcessedDoc = parse_terraform_module_directory(str(input_path))
    except ValueError as e: # Catch errors from parser like non-directory path
        print(f"Error during parsing: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"An unexpected error occurred during HCL parsing: {e}", file=sys.stderr)
        sys.exit(2)

    if not module_doc_data.files:
        print(f"No Terraform (.tf) files found or processed in directory: {input_path}")
        # Depending on desired behavior, could exit with 0 or an error/warning code
        sys.exit(0)

    print(f"Successfully parsed {len(module_doc_data.files)} .tf file(s).")

    # 2. Render the documentation to Markdown
    try:
        renderer = MarkdownRenderer(module_doc_data)
        markdown_output: str = renderer.render_module_documentation()
    except Exception as e:
        print(f"An unexpected error occurred during Markdown rendering: {e}", file=sys.stderr)
        sys.exit(3)

    # 3. Output the Markdown
    if args.output_file:
        output_path = Path(args.output_file).resolve()
        # If output_file is a directory, create README.md inside it
        if output_path.is_dir():
            output_path = output_path / "README.md"
        elif output_path.suffix.lower() != ".md" and not output_path.exists(): # if it's not ending in .md and doesn't exist, assume it's a dir
             # This logic might be too implicit. Better to require user to specify a file or make output_path a dir explicitly.
             # For now, if it doesn't end with .md and doesn't exist, it might be intended as a file without extension.
             # Let's ensure parent dir exists if it's a file path.
            output_path.parent.mkdir(parents=True, exist_ok=True)


        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_output)
            print(f"\nDocumentation successfully written to: {output_path}")
        except IOError as e:
            print(f"Error writing documentation to file {output_path}: {e}", file=sys.stderr)
            sys.exit(4)
    else:
        # Print to STDOUT
        print("\n--- Generated Markdown Documentation ---")
        sys.stdout.write(markdown_output)
        # Add a newline if stdout doesn't automatically add one from print
        if not markdown_output.endswith("\n"):
             sys.stdout.write("\n")


    print("\n--- IaC Documentation Generation Complete ---")
    sys.exit(0)

if __name__ == "__main__":
    # To test this CLI:
    # 1. Create a dummy Terraform module directory, e.g., 'my_test_module/'
    #    with some .tf files (main.tf, variables.tf, outputs.tf - can copy from
    #    terraform_hcl_parser.py example usage and place in 'my_test_module/').
    # 2. Run from the parent directory of 'my_test_module/':
    #    python -m src.mcp_tools.iac_doc_generator.cli my_test_module
    #    (This will print to STDOUT)
    # 3. To output to a file:
    #    python -m src.mcp_tools.iac_doc_generator.cli my_test_module -o my_test_module_doc.md
    #    Or to a directory (will create my_test_module_docs/README.md):
    #    mkdir my_test_module_docs
    #    python -m src.mcp_tools.iac_doc_generator.cli my_test_module -o my_test_module_docs
    main()
