import pytest
import subprocess
import os
from pathlib import Path
import shutil

CLI_MODULE_PATH = "src.mcp_tools.iac_doc_generator.cli"

# Sample Terraform HCL content for various files
MAIN_TF_CONTENT = """
provider "aws" {
  region = "us-east-1"
}
resource "aws_instance" "web" {
  instance_type = "t2.micro"
  ami           = "ami-123"
}
module "vpc" {
  source = "./modules/custom_vpc"
  cidr   = "10.0.0.0/16"
}
"""

VARIABLES_TF_CONTENT = """
variable "instance_count" {
  description = "Number of web instances"
  type        = number
  default     = 1
}
variable "admin_user" {
  description = "Admin username"
  type        = string
  sensitive   = true
}
"""

OUTPUTS_TF_CONTENT = """
output "web_instance_ip" {
  description = "Public IP of the web instance"
  value       = aws_instance.web.public_ip
}
output "vpc_id_out" {
  description = "ID of the VPC"
  value       = module.vpc.id
  sensitive   = true
}
"""

@pytest.fixture
def temp_tf_module_for_cli(tmp_path: Path) -> Path:
    """Fixture to create a temporary Terraform module directory with sample .tf files."""
    module_dir = tmp_path / "sample_tf_module"
    module_dir.mkdir()

    (module_dir / "main.tf").write_text(MAIN_TF_CONTENT)
    (module_dir / "variables.tf").write_text(VARIABLES_TF_CONTENT)
    (module_dir / "outputs.tf").write_text(OUTPUTS_TF_CONTENT)

    # Create a dummy submodule directory as referenced by main.tf
    # (module_dir / "modules" / "custom_vpc").mkdir(parents=True, exist_ok=True)
    # (module_dir / "modules" / "custom_vpc" / "main.tf").write_text("# Dummy VPC module")

    yield module_dir
    # Cleanup handled by tmp_path

def run_iac_doc_cli(cwd_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Helper function to run the IaC Doc Generator CLI tool."""
    cmd = ["python", "-m", CLI_MODULE_PATH] + args
    # When running module with python -m, CWD should be project root or have src in PYTHONPATH
    # For these tests, CWD will be tmp_path where module_dir is, which might not be ideal for python -m if it can't find src.
    # It's often better to run from project root and pass full paths to input_dir.
    # However, subprocess.run(cwd=...) sets the CWD for the command.
    # Let's assume tests are run from project root.

    # If CLI needs to be run from project root:
    # current_project_root = Path(__file__).parent.parent.parent.parent # Adjust based on actual test file depth
    # return subprocess.run(cmd, capture_output=True, text=True, cwd=current_project_root)

    # For now, assume simple execution with cwd_path if python -m works relative to it
    # This might fail if src is not in PYTHONPATH relative to cwd_path.
    # A safer bet for `python -m` is to run from a CWD where `src` is a subdir, or `src` is in PYTHONPATH.
    # Let's try running from the parent of tmp_path (which is usually a pytest temp area)
    # or pass absolute path to input_dir.

    # The command will be `python -m src.mcp_tools.iac_doc_generator.cli <input_dir_abs_path> ...`
    # So CWD for subprocess doesn't matter as much as for finding the module.
    # Let's run from a neutral CWD like tmp_path itself.

    return subprocess.run(cmd, capture_output=True, text=True, cwd=tmp_path)


# --- CLI Tests ---

def test_cli_iac_doc_help_message():
    result = subprocess.run(["python", "-m", CLI_MODULE_PATH, "--help"], capture_output=True, text=True)
    assert "usage: cli.py" in result.stdout
    assert "Path to the directory containing the Terraform module" in result.stdout
    assert "--output-file" in result.stdout
    assert result.returncode == 0

def test_cli_iac_doc_invalid_input_dir(tmp_path: Path):
    result = run_iac_doc_cli(tmp_path, ["non_existent_dir"])
    assert result.returncode != 0
    assert "Error: Input path" in result.stderr
    assert "is not a valid directory." in result.stderr

def test_cli_iac_doc_generate_to_stdout(temp_tf_module_for_cli: Path, tmp_path: Path):
    input_dir_abs = str(temp_tf_module_for_cli.resolve())
    result = run_iac_doc_cli(tmp_path, [input_dir_abs]) # Output to STDOUT by default

    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)

    assert result.returncode == 0
    assert "--- Generated Markdown Documentation ---" in result.stdout
    assert "# Terraform Module: `sample_tf_module`" in result.stdout
    assert "## File: `main.tf`" in result.stdout
    assert "### Providers" in result.stdout
    assert "- `aws` (alias: `primary`)" in result.stdout
    assert "### Managed Resources" in result.stdout
    assert "- **`aws_instance.web`**" in result.stdout
    assert "### Module Calls" in result.stdout
    assert "- **`vpc`** (Source: `./modules/custom_vpc`)" in result.stdout

    assert "## File: `variables.tf`" in result.stdout
    assert "### Variables" in result.stdout
    assert "| `instance_count` | Number of web instances | `number` | `1` | `False` |" in result.stdout
    assert "| `admin_user` | Admin username | `string` | *(Required)* | `True` |" in result.stdout

    assert "## File: `outputs.tf`" in result.stdout
    assert "### Outputs" in result.stdout
    assert "| `web_instance_ip` | Public IP of the web instance | `False` |" in result.stdout
    assert "| `vpc_id_out` | ID of the VPC | `True` |" in result.stdout
    assert "--- IaC Documentation Generation Complete ---" in result.stdout


def test_cli_iac_doc_generate_to_output_file(temp_tf_module_for_cli: Path, tmp_path: Path):
    input_dir_abs = str(temp_tf_module_for_cli.resolve())
    output_file = tmp_path / "generated_doc.md"
    output_file_abs = str(output_file.resolve())

    result = run_iac_doc_cli(tmp_path, [input_dir_abs, "--output-file", output_file_abs])

    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)

    assert result.returncode == 0
    assert f"Documentation successfully written to: {output_file_abs}" in result.stdout
    assert output_file.exists()

    content = output_file.read_text()
    assert "# Terraform Module: `sample_tf_module`" in content
    assert "## File: `variables.tf`" in content
    assert "| `instance_count`" in content

def test_cli_iac_doc_generate_to_output_directory(temp_tf_module_for_cli: Path, tmp_path: Path):
    input_dir_abs = str(temp_tf_module_for_cli.resolve())
    output_dir = tmp_path / "docs_output"
    # CLI should create README.md inside this if it's a dir
    # The CLI creates parent dirs for output_file, but if output_file IS a dir, it appends README.md.
    # So, output_dir itself doesn't need to be created by this test beforehand if logic is robust.
    # However, current CLI logic: output_path.parent.mkdir(). If output_path is a dir, parent is its parent.
    # If output_path is docs_output/, then output_path.is_dir() is true, path becomes docs_output/README.md.
    # Then output_path.parent (docs_output/) is created. This is fine.

    output_dir_abs = str(output_dir.resolve())

    result = run_iac_doc_cli(tmp_path, [input_dir_abs, "--output-file", output_dir_abs])

    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)

    assert result.returncode == 0
    expected_output_readme = output_dir / "README.md"
    assert f"Documentation successfully written to: {str(expected_output_readme.resolve())}" in result.stdout
    assert expected_output_readme.exists()

    content = expected_output_readme.read_text()
    assert "# Terraform Module: `sample_tf_module`" in content

def test_cli_iac_doc_empty_module_dir(tmp_path: Path):
    empty_module_dir = tmp_path / "empty_tf_module"
    empty_module_dir.mkdir()
    input_dir_abs = str(empty_module_dir.resolve())

    result = run_iac_doc_cli(tmp_path, [input_dir_abs])
    # print("STDOUT:", result.stdout)
    # print("STDERR:", result.stderr)
    assert result.returncode == 0 # Exits 0 if no .tf files found
    assert f"No Terraform (.tf) files found or processed in directory: {input_dir_abs}" in result.stdout
    assert "--- Generated Markdown Documentation ---" not in result.stdout # Should not attempt to print if no files

# Future tests:
# - Invalid HCL content in one of the .tf files (check stderr for warnings from parser)
# - Recursive processing (when implemented)
# - Different output formats (when implemented)
# - Custom templates (when implemented)
# - File I/O errors for output file (e.g., permission denied - harder to test reliably)
# - Very large HCL files or many files (performance, stability)
# - Special characters in file paths, HCL content (ensure proper handling)
