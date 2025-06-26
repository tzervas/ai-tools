from ..models import DriftInfo, DriftType, AttributeDrift
from typing import List


def suggest_remediation(
    drift_info: DriftInfo, iac_tool: str = "terraform"
) -> List[str]:
    """
    Generates human-readable remediation suggestions for a given drift.

    Args:
        drift_info: A DriftInfo object describing the detected drift.
        iac_tool: The IaC tool in use (e.g., "terraform", "pulumi"). This helps tailor
                  suggestions to specific commands.

    Returns:
        A list of strings, where each string is a suggested remediation action or comment.
    """
    suggestions: List[str] = []

    res_identifier = f"{drift_info.resource_type}.{drift_info.resource_name}"
    if drift_info.resource_id:
        res_identifier += f" (ID: {drift_info.resource_id})"
    else:  # E.g. for missing resource where ID might be from IaC but not confirmed actual
        if drift_info.iac_resource and drift_info.iac_resource.id:
            res_identifier += f" (Expected IaC ID: {drift_info.iac_resource.id})"

    if drift_info.drift_type == DriftType.MISSING_IN_ACTUAL:
        suggestions.append(
            f"Resource {res_identifier} is defined in IaC but MISSING in the actual state."
        )
        if iac_tool == "terraform":
            suggestions.append(
                f"  - Suggestion: Run 'terraform apply' to create the resource."
            )
            if drift_info.iac_resource and drift_info.iac_resource.module:
                suggestions.append(
                    f"    (Resource is in module: {drift_info.iac_resource.module})"
                )
        else:
            suggestions.append(
                f"  - Suggestion: Use your IaC tool to apply the configuration and create the resource."
            )

    elif drift_info.drift_type == DriftType.UNMANAGED_IN_ACTUAL:
        suggestions.append(
            f"Resource {res_identifier} exists in the actual state but is UNMANAGED by IaC."
        )
        suggestions.append(
            f"  - This resource may have been created manually or outside of the current IaC configuration."
        )
        if iac_tool == "terraform":
            suggestions.append(
                f"  - Suggestion 1: Import the resource into Terraform state using 'terraform import {drift_info.actual_resource.type}.{drift_info.actual_resource.name} {drift_info.resource_id}' (adjust logical name as needed) and then define it in your Terraform code."
            )
            suggestions.append(
                f"  - Suggestion 2: If the resource is not needed or should be managed by a different IaC setup, consider removing it manually from the cloud environment (with caution)."
            )
            suggestions.append(
                f"  - Suggestion 3: If it should be ignored by this drift detection, update ignore configurations."
            )
        else:
            suggestions.append(
                f"  - Suggestion: Consider importing it into your IaC, defining it in code, or removing it manually if not needed."
            )

    elif drift_info.drift_type == DriftType.MODIFIED:
        suggestions.append(
            f"Resource {res_identifier} is MODIFIED. Differences found between IaC and actual state:"
        )
        for attr_drift in drift_info.attribute_drifts:
            iac_val_str = (
                f"'{attr_drift.iac_value}'"
                if attr_drift.iac_value is not None
                else "not set (None)"
            )
            actual_val_str = (
                f"'{attr_drift.actual_value}'"
                if attr_drift.actual_value is not None
                else "not set (None)"
            )
            suggestions.append(f"  - Attribute '{attr_drift.attribute_name}':")
            suggestions.append(f"    - IaC expects: {iac_val_str}")
            suggestions.append(f"    - Actual is:   {actual_val_str}")

        if iac_tool == "terraform":
            suggestions.append(
                f"  - Suggestion: Review the differences. If IaC is the source of truth, run 'terraform apply' to align the actual state."
            )
            suggestions.append(
                f"    If changes in actual state are intentional and desired, update your Terraform code to match, then plan and apply."
            )
        else:
            suggestions.append(
                f"  - Suggestion: Review differences. Align actual state by applying IaC, or update IaC to match actual state if changes are desired."
            )

    else:
        suggestions.append(
            f"Unknown drift type '{drift_info.drift_type.value}' for resource {res_identifier}."
        )

    return suggestions


if __name__ == "__main__":
    # Example Usage
    from ..models import ParsedResource  # For creating mock DriftInfo

    print("--- Testing Remediation Suggester ---")

    # Scenario 1: Missing Resource
    drift_missing = DriftInfo(
        drift_type=DriftType.MISSING_IN_ACTUAL,
        resource_type="aws_instance",
        resource_name="web_server_01",
        iac_resource=ParsedResource(
            id="i-expected123",
            type="aws_instance",
            name="web_server_01",
            provider_name="aws",
            attributes={},
        ),
    )
    suggestions_missing = suggest_remediation(drift_missing, iac_tool="terraform")
    print("\nDrift: MISSING_IN_ACTUAL")
    for s in suggestions_missing:
        print(s)
    assert any("Run 'terraform apply'" in s for s in suggestions_missing)

    # Scenario 2: Unmanaged Resource
    drift_unmanaged = DriftInfo(
        drift_type=DriftType.UNMANAGED_IN_ACTUAL,
        resource_type="aws_s3_bucket",
        resource_name="manual-bucket-007",  # This name comes from the actual resource
        resource_id="manual-bucket-007-id",
        actual_resource=ParsedResource(
            id="manual-bucket-007-id",
            type="aws_s3_bucket",
            name="manual-bucket-007",
            provider_name="aws",
            attributes={},
        ),
    )
    suggestions_unmanaged = suggest_remediation(drift_unmanaged, iac_tool="terraform")
    print("\nDrift: UNMANAGED_IN_ACTUAL")
    for s in suggestions_unmanaged:
        print(s)
    assert any(
        "terraform import aws_s3_bucket.manual-bucket-007 manual-bucket-007-id" in s
        for s in suggestions_unmanaged
    )

    # Scenario 3: Modified Resource
    attr_drifts_modified = [
        AttributeDrift(
            attribute_name="instance_type",
            iac_value="t2.micro",
            actual_value="t3.small",
        ),
        AttributeDrift(
            attribute_name="tags.Environment",
            iac_value="staging",
            actual_value="production",
        ),
        AttributeDrift(
            attribute_name="ebs_optimized", iac_value=False, actual_value=True
        ),
        AttributeDrift(
            attribute_name="monitoring", iac_value=None, actual_value=True
        ),  # IaC doesn't specify, actual has it
    ]
    drift_modified = DriftInfo(
        drift_type=DriftType.MODIFIED,
        resource_type="aws_instance",
        resource_name="app_server_main",
        resource_id="i-actual456",
        iac_resource=ParsedResource(
            id="i-actual456",
            type="aws_instance",
            name="app_server_main",
            provider_name="aws",
            attributes={
                "instance_type": "t2.micro",
                "tags": {"Environment": "staging"},
                "ebs_optimized": False,
            },
        ),
        actual_resource=ParsedResource(
            id="i-actual456",
            type="aws_instance",
            name="app_server_main_live",
            provider_name="aws",
            attributes={
                "instance_type": "t3.small",
                "tags": {"Environment": "production"},
                "ebs_optimized": True,
                "monitoring": True,
            },
        ),
        attribute_drifts=attr_drifts_modified,
    )
    suggestions_modified = suggest_remediation(drift_modified, iac_tool="terraform")
    print("\nDrift: MODIFIED")
    for s in suggestions_modified:
        print(s)
    assert any("Attribute 'instance_type'" in s for s in suggestions_modified)
    assert any("IaC expects: 't2.micro'" in s for s in suggestions_modified)
    assert any("Actual is:   't3.small'" in s for s in suggestions_modified)
    assert any("Attribute 'monitoring'" in s for s in suggestions_modified)
    assert any(
        "IaC expects: not set (None)" in s for s in suggestions_modified
    )  # Testing None display
    assert any("Actual is:   'True'" in s for s in suggestions_modified)
    assert any("run 'terraform apply' to align" in s for s in suggestions_modified)

    print("\nRemediation Suggester tests complete.")
