from .models import (
    TerraformModuleProcessedDoc,
    TerraformFileDoc,
    TerraformVariableDoc,
    TerraformOutputDoc,
    TerraformResourceDoc,
    TerraformModuleCallDoc,
    TerraformProviderDoc,
)
from typing import List, Any  # Added Any


def format_value(value: Any) -> str:
    """Helper to format default values or other complex values for display."""
    if isinstance(value, (str, int, float, bool)):
        return f"`{value}`"
    if value is None:
        return "`null`"  # or "Not set" or ""
    # For lists or dicts, show a compact representation or placeholder
    if isinstance(value, list):
        if not value:
            return "`[]`"
        return f"`{str(value)[:50]}{'...' if len(str(value)) > 50 else ''}`"  # Truncate long lists
    if isinstance(value, dict):
        if not value:
            return "`{}`"
        return f"`{str(value)[:50]}{'...' if len(str(value)) > 50 else ''}`"  # Truncate long dicts
    return f"`{type(value).__name__}` (Complex Value)"


class MarkdownRenderer:
    def __init__(self, module_doc: TerraformModuleProcessedDoc):
        self.module_doc = module_doc
        self.lines: List[str] = []

    def _add_line(self, text: str = ""):
        self.lines.append(text)

    def _add_header(self, level: int, text: str):
        self.lines.append(f"{'#' * level} {text}")
        self._add_line()

    def _render_variables(self, variables: List[TerraformVariableDoc]):
        if not variables:
            return
        self._add_header(3, "Variables")
        self._add_line("| Name | Description | Type | Default | Sensitive |")
        self._add_line("|------|-------------|------|---------|-----------|")
        for var in sorted(variables, key=lambda v: v.name):
            desc = var.description or "N/A"
            # Escape pipe characters in description for table rendering
            desc = desc.replace("|", "\\|").replace("\n", " <br> ")

            default_val_str = (
                format_value(var.default) if var.default is not None else "*(Required)*"
            )

            self._add_line(
                f"| `{var.name}` | {desc} | `{var.type or 'any'}` | {default_val_str} | `{var.is_sensitive}` |"
            )
        self._add_line()

    def _render_outputs(self, outputs: List[TerraformOutputDoc]):
        if not outputs:
            return
        self._add_header(3, "Outputs")
        self._add_line("| Name | Description | Sensitive |")
        self._add_line("|------|-------------|-----------|")
        for out in sorted(outputs, key=lambda o: o.name):
            desc = out.description or "N/A"
            desc = desc.replace("|", "\\|").replace("\n", " <br> ")
            self._add_line(f"| `{out.name}` | {desc} | `{out.is_sensitive}` |")
        self._add_line()

    def _render_resources(self, resources: List[TerraformResourceDoc]):
        if not resources:
            return
        self._add_header(3, "Managed Resources")
        # Could group by type or just list
        for res in sorted(resources, key=lambda r: (r.resource_type, r.resource_name)):
            self._add_line(f"- **`{res.resource_type}.{res.resource_name}`**")
            # Future: Add more details like key attributes if extracted by parser
        self._add_line()

    def _render_module_calls(self, module_calls: List[TerraformModuleCallDoc]):
        if not module_calls:
            return
        self._add_header(3, "Module Calls")
        for mc in sorted(module_calls, key=lambda m: m.module_name):
            self._add_line(f"- **`{mc.module_name}`** (Source: `{mc.source}`)")
            # Future: List key arguments passed to the module
        self._add_line()

    def _render_providers(self, providers: List[TerraformProviderDoc]):
        if not providers:
            return
        self._add_header(3, "Providers")
        for p in sorted(providers, key=lambda x: (x.name, x.alias or "")):
            alias_str = f" (alias: `{p.alias}`)" if p.alias else ""
            self._add_line(f"- `{p.name}`{alias_str}")
        self._add_line()

    def render_file_doc(self, file_doc: TerraformFileDoc):
        self._add_header(2, f"File: `{file_doc.file_path}`")
        if file_doc.description:
            self._add_line(
                file_doc.description
            )  # Assuming it's already formatted or simple text
            self._add_line()

        # Aggregate and render for the file
        self._render_providers(file_doc.providers)
        self._render_variables(file_doc.variables)
        self._render_resources(file_doc.resources)
        self._render_module_calls(file_doc.module_calls)
        self._render_outputs(file_doc.outputs)
        # Add data sources later if needed

    def render_module_documentation(self) -> str:
        """
        Generates Markdown documentation for the entire Terraform module.
        """
        self.lines = []  # Reset for fresh render

        self._add_header(
            1,
            f"Terraform Module: `{os.path.basename(self.module_doc.module_path) or os.path.basename(os.path.dirname(self.module_doc.module_path))}`",
        )  # Use directory name
        self._add_line(f"**Path:** `{self.module_doc.module_path}`")
        self._add_line()

        if self.module_doc.description:
            self._add_line(self.module_doc.description)
            self._add_line()

        # Option 1: Render file by file
        for file_doc in sorted(self.module_doc.files, key=lambda f: f.file_path):
            self.render_file_doc(file_doc)
            self._add_line("---")  # Separator between files
            self._add_line()

        # Option 2: Aggregate all elements and render module-level sections
        # (This might be preferred for a typical module README)
        # For this, the TerraformModuleProcessedDoc would need aggregated lists,
        # or we aggregate them here.
        # Example for aggregated (if we choose this path later):
        # all_vars = sorted([var for fd in self.module_doc.files for var in fd.variables], key=lambda v: v.name)
        # self._render_variables(all_vars)
        # ... etc for outputs, resources ...

        return "\n".join(self.lines)


# Helper to get a basename for a module path
import os  # Already imported but good for clarity if this class moves

if __name__ == "__main__":
    # Example Usage (requires dummy models from a test or direct instantiation)
    print("--- Testing Markdown Renderer ---")

    # Create dummy TerraformModuleProcessedDoc data
    var1 = TerraformVariableDoc(
        name="instance_count",
        type="number",
        description="Number of instances to create.",
        default=1,
    )
    var2 = TerraformVariableDoc(
        name="image_id",
        type="string",
        description="AMI ID for instances. This description | has a pipe.",
    )
    out1 = TerraformOutputDoc(
        name="instance_ips", description="List of public IPs.", is_sensitive=False
    )
    res1 = TerraformResourceDoc(
        resource_type="aws_instance", resource_name="web", source_file="main.tf"
    )
    modcall1 = TerraformModuleCallDoc(
        module_name="my_vpc", source="./modules/vpc", source_file="main.tf"
    )
    prov1 = TerraformProviderDoc(name="aws", alias="primary", source_file="main.tf")

    file_doc_main = TerraformFileDoc(
        file_path="main.tf",
        description="Main configuration file for the web application.",
        variables=[],  # Typically variables are in their own file
        outputs=[],
        resources=[res1],
        module_calls=[modcall1],
        providers=[prov1],
    )
    file_doc_vars = TerraformFileDoc(
        file_path="variables.tf",
        variables=[var1, var2],
    )
    file_doc_outputs = TerraformFileDoc(file_path="outputs.tf", outputs=[out1])

    module_doc_data = TerraformModuleProcessedDoc(
        module_path="/path/to/my_terraform_module",
        description="This Terraform module sets up a basic web application infrastructure.",
        files=[file_doc_main, file_doc_vars, file_doc_outputs],
    )

    renderer = MarkdownRenderer(module_doc_data)
    markdown_output = renderer.render_module_documentation()

    print("\nGenerated Markdown Output:")
    print(markdown_output)

    # Basic assertions on output
    assert "# Terraform Module: `my_terraform_module`" in markdown_output
    assert "## File: `main.tf`" in markdown_output
    assert (
        "### Variables" in markdown_output
    )  # Variables section should exist due to variables.tf
    assert (
        "| `image_id` | AMI ID for instances. This description \\| has a pipe. | `string` | *(Required)* | `False` |"
        in markdown_output
    )
    assert (
        "| `instance_count` | Number of instances to create. | `number` | `1` | `False` |"
        in markdown_output
    )
    assert "### Outputs" in markdown_output  # Outputs section from outputs.tf
    assert "| `instance_ips` | List of public IPs. | `False` |" in markdown_output
    assert "### Managed Resources" in markdown_output
    assert "- **`aws_instance.web`**" in markdown_output
    assert "### Module Calls" in markdown_output
    assert "- **`my_vpc`** (Source: `./modules/vpc`)" in markdown_output
    assert "### Providers" in markdown_output
    assert "- `aws` (alias: `primary`)" in markdown_output

    print("\nMarkdown Renderer tests complete.")
