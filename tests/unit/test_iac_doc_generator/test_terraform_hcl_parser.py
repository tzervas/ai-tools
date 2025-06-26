import pytest
from pathlib import Path
import shutil  # For cleaning up test dirs if needed (though tmp_path is better)

from src.mcp_tools.iac_doc_generator.models import (
    TerraformVariableDoc,
    TerraformOutputDoc,
    TerraformResourceDoc,
    TerraformModuleCallDoc,
    TerraformProviderDoc,
    TerraformFileDoc,
    TerraformModuleProcessedDoc,
)
from src.mcp_tools.iac_doc_generator.terraform_hcl_parser import (
    parse_hcl_file_content,
    parse_terraform_module_directory,
    _extract_description_from_block_body,  # Test helper if needed
    _extract_string_or_first_from_list,  # Test helper if needed
)

# --- Test Helper Functions (if complex enough) ---


def test_extract_string_or_first_from_list():
    assert _extract_string_or_first_from_list(["hello"]) == "hello"
    assert _extract_string_or_first_from_list("world") == "world"
    assert _extract_string_or_first_from_list(123) == "123"
    assert _extract_string_or_first_from_list(True) == "True"
    assert _extract_string_or_first_from_list(None) is None
    assert (
        _extract_string_or_first_from_list(["hello", "world"]) == "['hello', 'world']"
    )  # Default str conversion for >1 item list


def test_extract_description_from_block_body():
    assert (
        _extract_description_from_block_body({"description": "Test desc"})
        == "Test desc"
    )
    assert (
        _extract_description_from_block_body({"description": ["Test desc list"]})
        == "Test desc list"
    )
    assert _extract_description_from_block_body({}) is None
    assert (
        _extract_description_from_block_body({"description": ["Item1", "Item2"]})
        is None
    )  # Expects single item list


# --- Tests for parse_hcl_file_content ---


@pytest.fixture
def sample_hcl_content_main() -> str:
    return """
provider "aws" {
  region = "us-west-2"
  alias  = "west"
}

resource "aws_instance" "my_server" {
  ami           = "ami-abcdef12"
  instance_type = "t3.micro"
  tags = { Name = "MyServer" }
}

module "my_vpc" {
  source      = "./modules/vpc"
  cidr_block  = "10.0.0.0/16"
}
"""


@pytest.fixture
def sample_hcl_content_variables() -> str:
    return """
variable "instance_name" {
  description = "Name for the EC2 instance"
  type        = string
  default     = "DefaultServerName"
}
variable "is_prod" {
  type        = bool
  default     = false
  sensitive   = true
}
variable "no_desc_no_type" {}
"""


@pytest.fixture
def sample_hcl_content_outputs() -> str:
    return """
output "server_ip" {
  description = "Public IP of the server"
  value       = aws_instance.my_server.public_ip
}
output "vpc_id" {
  value       = module.my_vpc.vpc_id
  sensitive   = true
}
"""


def test_parse_hcl_main_tf_content(sample_hcl_content_main):
    file_doc = parse_hcl_file_content(sample_hcl_content_main, "main.tf")

    assert len(file_doc.providers) == 1
    assert file_doc.providers[0].name == "aws"
    assert file_doc.providers[0].alias == "west"

    assert len(file_doc.resources) == 1
    assert file_doc.resources[0].resource_type == "aws_instance"
    assert file_doc.resources[0].resource_name == "my_server"
    assert file_doc.resources[0].source_file == "main.tf"

    assert len(file_doc.module_calls) == 1
    assert file_doc.module_calls[0].module_name == "my_vpc"
    assert file_doc.module_calls[0].source == "./modules/vpc"
    assert file_doc.module_calls[0].source_file == "main.tf"


def test_parse_hcl_variables_tf_content(sample_hcl_content_variables):
    file_doc = parse_hcl_file_content(sample_hcl_content_variables, "variables.tf")

    assert len(file_doc.variables) == 3

    var_instance_name = next(v for v in file_doc.variables if v.name == "instance_name")
    assert var_instance_name.description == "Name for the EC2 instance"
    assert var_instance_name.type == "string"
    assert var_instance_name.default == "DefaultServerName"
    assert var_instance_name.is_sensitive is False

    var_is_prod = next(v for v in file_doc.variables if v.name == "is_prod")
    assert var_is_prod.type == "bool"
    assert var_is_prod.default is False
    assert var_is_prod.is_sensitive is True

    var_no_desc = next(v for v in file_doc.variables if v.name == "no_desc_no_type")
    assert var_no_desc.description is None
    assert var_no_desc.type is None  # hcl2 will parse type as None if not specified


def test_parse_hcl_outputs_tf_content(sample_hcl_content_outputs):
    file_doc = parse_hcl_file_content(sample_hcl_content_outputs, "outputs.tf")

    assert len(file_doc.outputs) == 2

    out_server_ip = next(o for o in file_doc.outputs if o.name == "server_ip")
    assert out_server_ip.description == "Public IP of the server"
    assert out_server_ip.is_sensitive is False

    out_vpc_id = next(o for o in file_doc.outputs if o.name == "vpc_id")
    assert out_vpc_id.description is None
    assert out_vpc_id.is_sensitive is True


def test_parse_hcl_empty_content():
    file_doc = parse_hcl_file_content("", "empty.tf")
    assert not file_doc.variables
    assert not file_doc.outputs
    assert not file_doc.resources
    assert not file_doc.module_calls
    assert not file_doc.providers


def test_parse_hcl_invalid_syntax(capsys):
    file_doc = parse_hcl_file_content(
        "resource 'invalid' {}", "invalid.tf"
    )  # Missing "
    captured = capsys.readouterr()
    assert "Warning: Could not parse HCL file invalid.tf" in captured.err
    # File_doc will still be created but empty of parsed elements
    assert file_doc.file_path == "invalid.tf"
    assert not file_doc.resources


# --- Tests for parse_terraform_module_directory ---


@pytest.fixture
def temp_tf_module(
    tmp_path: Path,
    sample_hcl_content_main,
    sample_hcl_content_variables,
    sample_hcl_content_outputs,
):
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()
    (module_dir / "main.tf").write_text(sample_hcl_content_main)
    (module_dir / "variables.tf").write_text(sample_hcl_content_variables)
    (module_dir / "outputs.tf").write_text(sample_hcl_content_outputs)
    (module_dir / "other.txt").write_text("This is not a tf file.")  # Should be ignored
    return module_dir


def test_parse_terraform_module_directory_valid(temp_tf_module: Path):
    module_doc = parse_terraform_module_directory(str(temp_tf_module))

    assert module_doc.module_path == str(temp_tf_module.resolve())
    assert len(module_doc.files) == 3  # main.tf, variables.tf, outputs.tf

    main_tf_file_doc = next(
        (f for f in module_doc.files if f.file_path == "main.tf"), None
    )
    assert main_tf_file_doc is not None
    assert len(main_tf_file_doc.resources) == 1
    assert len(main_tf_file_doc.module_calls) == 1
    assert len(main_tf_file_doc.providers) == 1

    variables_tf_file_doc = next(
        (f for f in module_doc.files if f.file_path == "variables.tf"), None
    )
    assert variables_tf_file_doc is not None
    assert len(variables_tf_file_doc.variables) == 3

    outputs_tf_file_doc = next(
        (f for f in module_doc.files if f.file_path == "outputs.tf"), None
    )
    assert outputs_tf_file_doc is not None
    assert len(outputs_tf_file_doc.outputs) == 2


def test_parse_terraform_module_directory_empty(tmp_path: Path):
    empty_module_dir = tmp_path / "empty_module"
    empty_module_dir.mkdir()
    module_doc = parse_terraform_module_directory(str(empty_module_dir))
    assert len(module_doc.files) == 0


def test_parse_terraform_module_directory_not_a_directory(tmp_path: Path):
    not_a_dir = tmp_path / "not_a_dir.txt"
    not_a_dir.write_text("hello")
    with pytest.raises(ValueError, match="Provided path is not a directory"):
        parse_terraform_module_directory(str(not_a_dir))


def test_parse_terraform_module_directory_file_with_parsing_error(
    tmp_path: Path, capsys
):
    module_dir_with_error = tmp_path / "module_with_error"
    module_dir_with_error.mkdir()
    (module_dir_with_error / "good.tf").write_text('resource "null_resource" "good" {}')
    (module_dir_with_error / "bad.tf").write_text(
        'resource "invalid_syntax {}'
    )  # Missing quote

    module_doc = parse_terraform_module_directory(str(module_dir_with_error))
    assert len(module_doc.files) == 2  # Both files attempted, one will be mostly empty

    good_file_doc = next(
        (f for f in module_doc.files if f.file_path == "good.tf"), None
    )
    assert good_file_doc is not None
    assert len(good_file_doc.resources) == 1

    bad_file_doc = next((f for f in module_doc.files if f.file_path == "bad.tf"), None)
    assert bad_file_doc is not None
    assert not bad_file_doc.resources  # Should be empty due to parse error

    captured = capsys.readouterr()
    assert "Warning: Could not parse HCL file bad.tf" in captured.err
