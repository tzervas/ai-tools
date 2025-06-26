import pytest
from src.mcp_tools.iac_drift_detector.models import DriftInfo, DriftType, AttributeDrift, ParsedResource
from src.mcp_tools.iac_drift_detector.core_logic.remediation import suggest_remediation

# --- Test suggest_remediation ---

def test_suggest_remediation_missing_in_actual_terraform():
    drift = DriftInfo(
        drift_type=DriftType.MISSING_IN_ACTUAL,
        resource_type="aws_instance",
        resource_name="web_server_01",
        iac_resource=ParsedResource(id="i-expected123", type="aws_instance", name="web_server_01", provider_name="aws", attributes={})
    )
    suggestions = suggest_remediation(drift, iac_tool="terraform")
    assert len(suggestions) >= 2
    assert f"Resource aws_instance.web_server_01 (Expected IaC ID: i-expected123) is defined in IaC but MISSING" in suggestions[0]
    assert "Run 'terraform apply' to create the resource." in suggestions[1]

def test_suggest_remediation_missing_in_actual_with_module_terraform():
    drift = DriftInfo(
        drift_type=DriftType.MISSING_IN_ACTUAL,
        resource_type="aws_instance",
        resource_name="web_server_module",
        iac_resource=ParsedResource(id="i-expected456", type="aws_instance", name="web_server_module", provider_name="aws", module="module.my_module", attributes={})
    )
    suggestions = suggest_remediation(drift, iac_tool="terraform")
    assert len(suggestions) >= 3
    assert "(Resource is in module: module.my_module)" in suggestions[2]


def test_suggest_remediation_unmanaged_in_actual_terraform():
    drift = DriftInfo(
        drift_type=DriftType.UNMANAGED_IN_ACTUAL,
        resource_type="aws_s3_bucket",
        resource_name="manual-bucket-007",
        resource_id="manual-bucket-007-id",
        actual_resource=ParsedResource(id="manual-bucket-007-id", type="aws_s3_bucket", name="manual-bucket-007", provider_name="aws", attributes={})
    )
    suggestions = suggest_remediation(drift, iac_tool="terraform")
    assert len(suggestions) >= 4 # Main message + 3 suggestions
    assert "Resource aws_s3_bucket.manual-bucket-007 (ID: manual-bucket-007-id) exists in the actual state but is UNMANAGED by IaC." in suggestions[0]
    assert "Suggestion 1: Import the resource into Terraform state using 'terraform import aws_s3_bucket.manual-bucket-007 manual-bucket-007-id'" in suggestions[2]
    assert "Suggestion 2: If the resource is not needed" in suggestions[3]


def test_suggest_remediation_modified_terraform():
    attr_drifts = [
        AttributeDrift(attribute_name="instance_type", iac_value="t2.micro", actual_value="t3.small"),
        AttributeDrift(attribute_name="monitoring", iac_value=None, actual_value=True)
    ]
    drift = DriftInfo(
        drift_type=DriftType.MODIFIED,
        resource_type="aws_instance",
        resource_name="app_server_main",
        resource_id="i-actual456",
        iac_resource=ParsedResource(id="i-actual456", type="aws_instance", name="app_server_main", provider_name="aws", attributes={"instance_type": "t2.micro"}),
        actual_resource=ParsedResource(id="i-actual456", type="aws_instance", name="app_server_main_live", provider_name="aws", attributes={"instance_type": "t3.small", "monitoring": True}),
        attribute_drifts=attr_drifts
    )
    suggestions = suggest_remediation(drift, iac_tool="terraform")

    full_suggestion_text = "\n".join(suggestions)
    # print(full_suggestion_text) # For debugging

    assert "Resource aws_instance.app_server_main (ID: i-actual456) is MODIFIED." in suggestions[0]
    assert "Attribute 'instance_type':" in full_suggestion_text
    assert "IaC expects: 't2.micro'" in full_suggestion_text
    assert "Actual is:   't3.small'" in full_suggestion_text
    assert "Attribute 'monitoring':" in full_suggestion_text
    assert "IaC expects: not set (None)" in full_suggestion_text
    assert "Actual is:   'True'" in full_suggestion_text
    assert "Suggestion: Review the differences. If IaC is the source of truth, run 'terraform apply' to align the actual state." in full_suggestion_text

def test_suggest_remediation_unknown_drift_type():
    # Create a dummy DriftType or mock it if Enum doesn't allow easy extension for tests
    class MockUnknownDriftType:
        value = "very_unknown_drift"

    drift = DriftInfo(
        drift_type=MockUnknownDriftType(), # type: ignore
        resource_type="some_type",
        resource_name="some_name",
        resource_id="some_id"
    )
    suggestions = suggest_remediation(drift)
    assert len(suggestions) == 1
    assert "Unknown drift type 'very_unknown_drift' for resource some_type.some_name (ID: some_id)." in suggestions[0]

def test_suggest_remediation_generic_iac_tool():
    drift_missing = DriftInfo(
        drift_type=DriftType.MISSING_IN_ACTUAL,
        resource_type="generic_resource",
        resource_name="test_res",
        iac_resource=ParsedResource(id="gen-id-123", type="generic_resource", name="test_res", provider_name="any", attributes={})
    )
    suggestions = suggest_remediation(drift_missing, iac_tool="pulumi") # Example other tool
    assert len(suggestions) >= 2
    assert "Use your IaC tool to apply the configuration and create the resource." in suggestions[1]

    drift_unmanaged = DriftInfo(
        drift_type=DriftType.UNMANAGED_IN_ACTUAL,
        resource_type="another_resource",
        resource_name="unmanaged_res",
        resource_id="unmanaged-id-456",
        actual_resource=ParsedResource(id="unmanaged-id-456", type="another_resource", name="unmanaged_res", provider_name="any", attributes={})
    )
    suggestions_unmanaged = suggest_remediation(drift_unmanaged, iac_tool="cloudformation")
    assert any("Consider importing it into your IaC" in s for s in suggestions_unmanaged)

    drift_modified = DriftInfo(
        drift_type=DriftType.MODIFIED,
        resource_type="yet_another_resource",
        resource_name="modified_res",
        resource_id="mod-id-789",
        attribute_drifts=[AttributeDrift(attribute_name="color", iac_value="blue", actual_value="red")]
    )
    suggestions_modified = suggest_remediation(drift_modified, iac_tool="ansible")
    assert any("Review differences. Align actual state by applying IaC" in s for s in suggestions_modified)
