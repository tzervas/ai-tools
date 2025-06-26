import pytest

from src.mcp_tools.iac_doc_generator.models import (
    TerraformVariableDoc, TerraformOutputDoc, TerraformResourceDoc,
    TerraformModuleCallDoc, TerraformProviderDoc, TerraformFileDoc,
    TerraformModuleProcessedDoc
)
from src.mcp_tools.iac_doc_generator.markdown_renderer import MarkdownRenderer, format_value

# --- Test format_value helper ---
@pytest.mark.parametrize("input_val, expected_str", [
    ("string_val", "`string_val`"),
    (123, "`123`"),
    (True, "`True`"),
    (None, "`null`"),
    ([], "`[]`"),
    ({}, "`{}`"),
    ([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20], "`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,...`"), # Truncated list
    ({"a":1, "b":2, "longkeylongkeylongkeylongkeylongkey":3}, "`{'a': 1, 'b': 2, 'longkeylongkeylongkeylongkeylo...`"), # Truncated dict
    (1.23, "`1.23`")
])
def test_format_value(input_val, expected_str):
    assert format_value(input_val) == expected_str

# --- Test MarkdownRenderer ---

@pytest.fixture
def sample_module_doc_data() -> TerraformModuleProcessedDoc:
    var1 = TerraformVariableDoc(name="instance_count", type="number", description="Number of instances.", default=1)
    var2 = TerraformVariableDoc(name="image_id", type="string", description="AMI ID. Pipe | char test.", is_sensitive=True) # Required

    out1 = TerraformOutputDoc(name="instance_ips", description="Public IPs.", is_sensitive=False)
    out2 = TerraformOutputDoc(name="app_url", description="Application URL.", is_sensitive=True)

    res1 = TerraformResourceDoc(resource_type="aws_instance", resource_name="web_app", source_file="main.tf")
    res2 = TerraformResourceDoc(resource_type="aws_s3_bucket", resource_name="app_storage", source_file="s3.tf")

    modcall1 = TerraformModuleCallDoc(module_name="networking", source="./modules/vpc", source_file="main.tf")

    prov1 = TerraformProviderDoc(name="aws", alias="primary", source_file="main.tf")
    prov2 = TerraformProviderDoc(name="random", source_file="main.tf")

    file_main = TerraformFileDoc(
        file_path="main.tf",
        description="Main infrastructure setup.",
        providers=[prov1, prov2],
        resources=[res1],
        module_calls=[modcall1]
    )
    file_vars = TerraformFileDoc(file_path="variables.tf", variables=[var1, var2])
    file_outputs = TerraformFileDoc(file_path="outputs.tf", outputs=[out1, out2])
    file_s3 = TerraformFileDoc(file_path="s3.tf", resources=[res2]) # Resources in another file

    return TerraformModuleProcessedDoc(
        module_path="/test/module/path",
        description="A test Terraform module.",
        files=[file_main, file_vars, file_outputs, file_s3]
    )

def test_markdown_renderer_module_header(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "# Terraform Module: `path`" in md # Basename of module_path
    assert "**Path:** `/test/module/path`" in md
    assert "A test Terraform module." in md # Module description

def test_markdown_renderer_file_sections(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "## File: `main.tf`" in md
    assert "Main infrastructure setup." in md # File description
    assert "## File: `variables.tf`" in md
    assert "## File: `outputs.tf`" in md
    assert "## File: `s3.tf`" in md
    assert "---" in md # Separator

def test_markdown_renderer_providers_section(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "### Providers" in md
    assert "- `aws` (alias: `primary`)" in md
    assert "- `random`" in md

def test_markdown_renderer_variables_section(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "### Variables" in md
    assert "| Name | Description | Type | Default | Sensitive |" in md
    assert "| `image_id` | AMI ID. Pipe \\| char test. | `string` | *(Required)* | `True` |" in md
    assert "| `instance_count` | Number of instances. | `number` | `1` | `False` |" in md

def test_markdown_renderer_outputs_section(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "### Outputs" in md
    assert "| Name | Description | Sensitive |" in md
    assert "| `app_url` | Application URL. | `True` |" in md
    assert "| `instance_ips` | Public IPs. | `False` |" in md

def test_markdown_renderer_resources_section(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "### Managed Resources" in md
    # Check for resources from main.tf
    assert "- **`aws_instance.web_app`**" in md
    # Check for resources from s3.tf (should be under its own file section)
    assert "## File: `s3.tf`" in md # Ensure s3.tf section exists
    # Find "Managed Resources" header specifically under s3.tf section
    s3_tf_section_start = md.find("## File: `s3.tf`")
    s3_tf_section_end = md.find("---", s3_tf_section_start) if "---" in md[s3_tf_section_start:] else len(md)
    s3_tf_md = md[s3_tf_section_start:s3_tf_section_end]

    assert "### Managed Resources" in s3_tf_md
    assert "- **`aws_s3_bucket.app_storage`**" in s3_tf_md


def test_markdown_renderer_module_calls_section(sample_module_doc_data: TerraformModuleProcessedDoc):
    renderer = MarkdownRenderer(sample_module_doc_data)
    md = renderer.render_module_documentation()
    assert "### Module Calls" in md
    assert "- **`networking`** (Source: `./modules/vpc`)" in md

def test_markdown_renderer_empty_sections_not_rendered():
    file_empty = TerraformFileDoc(file_path="empty.tf")
    module_doc = TerraformModuleProcessedDoc(module_path="/empty/module", files=[file_empty])
    renderer = MarkdownRenderer(module_doc)
    md = renderer.render_module_documentation()

    assert "## File: `empty.tf`" in md
    assert "### Variables" not in md # Because file_empty.variables is empty
    assert "### Outputs" not in md
    assert "### Managed Resources" not in md
    assert "### Module Calls" not in md
    assert "### Providers" not in md

def test_markdown_renderer_no_files():
    module_doc = TerraformModuleProcessedDoc(module_path="/no_files/module", files=[])
    renderer = MarkdownRenderer(module_doc)
    md = renderer.render_module_documentation()
    assert "# Terraform Module: `module`" in md # Basename should still work
    assert "## File:" not in md # No file sections
    assert "---" not in md
