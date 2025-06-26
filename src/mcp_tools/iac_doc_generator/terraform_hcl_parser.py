import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hcl2  # Changed import

# from hcl2.parser import hcl2_parse # type: ignore # HCL2 library might not have perfect stubs

from .models import (
    TerraformVariableDoc,
    TerraformOutputDoc,
    TerraformResourceDoc,
    TerraformModuleCallDoc,
    TerraformProviderDoc,
    TerraformFileDoc,
    TerraformModuleProcessedDoc,
)

# Comment parsing is notoriously difficult with HCL parsers as comments are often
# not part of the AST in a structured way. We might need to do some line-based heuristics
# or rely on specific comment formats if this becomes a strong requirement.
# For now, we'll focus on extracting defined attributes like 'description'.


def _extract_description_from_block_body(block_body: Dict[str, Any]) -> Optional[str]:
    """Tries to extract 'description' if it's a direct string attribute."""
    desc = block_body.get("description")
    if isinstance(desc, list) and len(desc) == 1 and isinstance(desc[0], str):
        return desc[0]
    if isinstance(desc, str):  # Sometimes it's just a string
        return desc
    return None


def _extract_string_or_first_from_list(value: Any) -> Optional[str]:
    """Helper to get a string value, even if it's wrapped in a list by the parser."""
    if isinstance(value, list) and len(value) == 1:
        return str(value[0])
    if isinstance(value, (str, int, bool)):  # Allow basic types to be stringified
        return str(value)
    return None


def parse_hcl_file_content(hcl_content: str, file_path_str: str) -> TerraformFileDoc:
    """
    Parses the content of a single HCL (.tf) file.
    """
    file_doc = TerraformFileDoc(file_path=file_path_str)

    try:
        # Use hcl2.loads() for parsing a string
        parsed_data = hcl2.loads(hcl_content)  # type: ignore
        if not parsed_data:
            return file_doc  # Empty or unparsable content
    except Exception as e:
        print(
            f"Warning: Could not parse HCL file {file_path_str}: {e}", file=sys.stderr
        )
        return file_doc  # Return with what we have, which is just the path

    # Top-level comments for file description (heuristic, not robust)
    # This part is very basic. Real comment parsing would need more advanced logic.
    # if hcl_content.startswith("#") or hcl_content.startswith("/*"):
    #    first_lines = hcl_content.split('\n', 5)
    #    potential_desc_lines = []
    #    for line in first_lines:
    #        if line.strip().startswith("#"):
    #            potential_desc_lines.append(line.strip().lstrip('#').strip())
    #        elif line.strip().startswith("/*") and "*/" in line: # Simple single line block
    #            potential_desc_lines.append(line.split("/*")[1].split("*/")[0].strip())
    #            break
    #        elif line.strip().startswith("/*"): # Start of multi-line
    #             # This simple check doesn't handle multi-line block comments well.
    #            break
    #        else: # First non-comment line
    #            break
    #    if potential_desc_lines:
    #        file_doc.description = "\n".join(potential_desc_lines)

    for block_type, blocks_of_that_type in parsed_data.items():
        if not isinstance(blocks_of_that_type, list):
            continue  # Should always be a list of blocks

        for block_instance_data in blocks_of_that_type:
            if not isinstance(block_instance_data, dict):
                continue

            if block_type == "variable":
                for var_name, var_body_list in block_instance_data.items():
                    if not isinstance(var_body_list, list) or not var_body_list:
                        continue
                    var_body = var_body_list[0]  # Variable block has one body
                    file_doc.variables.append(
                        TerraformVariableDoc(
                            name=var_name,
                            type=_extract_string_or_first_from_list(
                                var_body.get("type")
                            ),
                            description=_extract_description_from_block_body(var_body),
                            default=var_body.get("default"),  # Default can be complex
                            is_sensitive=var_body.get("sensitive", False),
                        )
                    )
            elif block_type == "output":
                for output_name, output_body_list in block_instance_data.items():
                    if not isinstance(output_body_list, list) or not output_body_list:
                        continue
                    output_body = output_body_list[0]
                    file_doc.outputs.append(
                        TerraformOutputDoc(
                            name=output_name,
                            description=_extract_description_from_block_body(
                                output_body
                            ),
                            is_sensitive=output_body.get("sensitive", False),
                        )
                    )
            elif block_type == "resource":
                for resource_tf_type, resource_name_map in block_instance_data.items():
                    for (
                        resource_name,
                        _,
                    ) in resource_name_map.items():  # body not used for now
                        file_doc.resources.append(
                            TerraformResourceDoc(
                                resource_type=resource_tf_type,
                                resource_name=resource_name,
                                source_file=file_path_str,
                            )
                        )
            elif block_type == "module":
                for module_name, module_body_list in block_instance_data.items():
                    if not isinstance(module_body_list, list) or not module_body_list:
                        continue
                    module_body = module_body_list[0]
                    file_doc.module_calls.append(
                        TerraformModuleCallDoc(
                            module_name=module_name,
                            source=_extract_string_or_first_from_list(
                                module_body.get("source", "Unknown Source")
                            ),
                            source_file=file_path_str,
                        )
                    )
            elif block_type == "provider":
                for provider_name, provider_body_list in block_instance_data.items():
                    if (
                        not isinstance(provider_body_list, list)
                        or not provider_body_list
                    ):
                        continue
                    provider_body = provider_body_list[
                        0
                    ]  # Can have multiple provider blocks for aliases
                    file_doc.providers.append(
                        TerraformProviderDoc(
                            name=provider_name,
                            alias=_extract_string_or_first_from_list(
                                provider_body.get("alias")
                            ),
                            source_file=file_path_str,
                        )
                    )
            # Could add "data" sources here as well

    return file_doc


def parse_terraform_module_directory(
    module_dir_path: str,
) -> TerraformModuleProcessedDoc:
    """
    Parses all .tf files in a given directory (Terraform module) and aggregates results.
    """
    module_path_obj = Path(module_dir_path)
    if not module_path_obj.is_dir():
        raise ValueError(f"Provided path is not a directory: {module_dir_path}")

    module_doc = TerraformModuleProcessedDoc(module_path=str(module_path_obj.resolve()))

    # Try to find a module description (e.g. from a main.tf comment or a dedicated README in the module)
    # This is a placeholder for more advanced description extraction.
    # For now, if a 'main.tf' has a leading comment, we might use it.
    # Or if a 'README.md' (or similar) exists in the module_dir_path.

    for tf_file_path_obj in module_path_obj.glob("*.tf"):
        try:
            with open(tf_file_path_obj, "r", encoding="utf-8") as f:
                content = f.read()
            file_doc = parse_hcl_file_content(
                content, str(tf_file_path_obj.name)
            )  # Pass relative name
            module_doc.files.append(file_doc)
        except Exception as e:
            print(f"Error processing file {tf_file_path_obj}: {e}", file=sys.stderr)

    return module_doc


if __name__ == "__main__":
    # Example Usage:
    # Create a dummy Terraform module directory structure for testing

    dummy_module_path = Path("temp_tf_module_for_parser_test")
    dummy_module_path.mkdir(exist_ok=True)

    # main.tf
    main_tf_content = """
# This is the main configuration for our webapp.
# It sets up an EC2 instance and an S3 bucket.

provider "aws" {
  region = "us-east-1"
  alias  = "primary"
}

resource "aws_instance" "web" {
  ami           = "ami-12345"
  instance_type = "t2.micro"
  tags = {
    Name = "WebAppServer"
  }
  # A resource comment
}

module "s3_bucket" {
  source = "./modules/s3"
  bucket_name = "my-app-data-${var.environment}"
}
"""
    (dummy_module_path / "main.tf").write_text(main_tf_content)

    # variables.tf
    variables_tf_content = """
variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "admin_email" {
  description = "Admin email for notifications."
  type        = string
  # No default, so it's required
}

variable "sensitive_data" {
  description = "A sensitive variable."
  type        = string
  sensitive   = true
}
"""
    (dummy_module_path / "variables.tf").write_text(variables_tf_content)

    # outputs.tf
    outputs_tf_content = """
output "instance_ip" {
  description = "Public IP address of the web instance."
  value       = aws_instance.web.public_ip
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket created by the module."
  value       = module.s3_bucket.bucket_name
  sensitive   = true # Example
}
"""
    (dummy_module_path / "outputs.tf").write_text(outputs_tf_content)

    # A subdirectory for a module (optional for this simple test)
    # (dummy_module_path / "modules" / "s3").mkdir(parents=True, exist_ok=True)
    # (dummy_module_path / "modules" / "s3" / "main.tf").write_text("resource \"aws_s3_bucket\" \"this\" { bucket = var.bucket_name }")
    # (dummy_module_path / "modules" / "s3" / "variables.tf").write_text("variable \"bucket_name\" {}")
    # (dummy_module_path / "modules" / "s3" / "outputs.tf").write_text("output \"bucket_name\" { value = aws_s3_bucket.this.id }")

    print(f"--- Parsing Terraform Module at: {dummy_module_path.resolve()} ---")
    try:
        module_documentation = parse_terraform_module_directory(str(dummy_module_path))

        print(f"\nModule Path: {module_documentation.module_path}")
        # print(f"Module Description: {module_documentation.description or 'N/A'}")

        for file_doc in module_documentation.files:
            print(f"\n-- File: {file_doc.file_path} --")
            # print(f"  File Description: {file_doc.description or 'N/A'}")
            if file_doc.providers:
                print("  Providers:")
                for p in file_doc.providers:
                    print(f"    - {p.name} (alias: {p.alias or 'none'})")
            if file_doc.variables:
                print("  Variables:")
                for v in file_doc.variables:
                    print(
                        f"    - {v.name} (Type: {v.type or 'any'}, Desc: {v.description or 'N/A'}, Sensitive: {v.is_sensitive})"
                    )
            if file_doc.outputs:
                print("  Outputs:")
                for o in file_doc.outputs:
                    print(
                        f"    - {o.name} (Desc: {o.description or 'N/A'}, Sensitive: {o.is_sensitive})"
                    )
            if file_doc.resources:
                print("  Resources:")
                for r in file_doc.resources:
                    print(f"    - {r.resource_type}.{r.resource_name}")
            if file_doc.module_calls:
                print("  Module Calls:")
                for m in file_doc.module_calls:
                    print(f"    - {m.module_name} (Source: {m.source})")

        # Example Assertions (very basic)
        main_tf_doc = next(
            f for f in module_documentation.files if f.file_path == "main.tf"
        )
        assert any(
            r.resource_type == "aws_instance" and r.resource_name == "web"
            for r in main_tf_doc.resources
        )
        variables_tf_doc = next(
            f for f in module_documentation.files if f.file_path == "variables.tf"
        )
        assert any(
            v.name == "environment" and "deployment environment" in v.description
            for v in variables_tf_doc.variables
        )
        assert any(
            v.name == "sensitive_data" and v.is_sensitive
            for v in variables_tf_doc.variables
        )
        outputs_tf_doc = next(
            f for f in module_documentation.files if f.file_path == "outputs.tf"
        )
        assert any(o.name == "instance_ip" for o in outputs_tf_doc.outputs)
        assert any(
            o.name == "s3_bucket_name" and o.is_sensitive
            for o in outputs_tf_doc.outputs
        )

    except Exception as e:
        print(f"Error during parser example: {e}", file=sys.stderr)
    finally:
        # Cleanup dummy directory
        import shutil

        shutil.rmtree(dummy_module_path, ignore_errors=True)
        print(f"\nCleaned up {dummy_module_path}")

    print("\nTerraform HCL Parser example complete.")
