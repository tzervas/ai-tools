from typing import List, Dict, Any, Optional, Set
from ..models import ParsedResource, DriftInfo, DriftType, AttributeDrift
import sys

# Attributes to ignore during comparison by default for common Terraform resource types.
# This is a simplistic approach; a more advanced system might load these from config
# or have more sophisticated per-resource-type logic.
# Format: {"resource_type": ["attribute_to_ignore", "another_attribute_to_ignore"]}
DEFAULT_IGNORED_ATTRIBUTES: Dict[str, List[str]] = {
    "aws_instance": [
        "arn",
        "private_dns",
        "public_dns",
        "public_ip",
        "ipv6_addresses",
        "tags_all",
        "ebs_block_device",
        "root_block_device",
        "timeouts",
    ],
    "aws_s3_bucket": [
        "arn",
        "bucket_domain_name",
        "bucket_regional_domain_name",
        "tags_all",
        "timeouts",
    ],
    # Add more resource types and their commonly noisy/dynamic attributes
}


def compare_attributes(
    iac_attrs: Dict[str, Any],
    actual_attrs: Dict[str, Any],
    resource_type: str,  # For type-specific ignore rules
    ignored_attributes_config: Optional[Dict[str, List[str]]] = None,
) -> List[AttributeDrift]:
    """
    Compares attributes of two resource states (IaC vs Actual).

    Args:
        iac_attrs: Attributes from the IaC definition.
        actual_attrs: Attributes from the actual cloud resource.
        resource_type: The type of the resource, for applying type-specific ignore rules.
        ignored_attributes_config: Configuration for attributes to ignore during comparison.
                                   If None, uses DEFAULT_IGNORED_ATTRIBUTES.

    Returns:
        A list of AttributeDrift objects representing differing attributes.
    """
    drifts: List[AttributeDrift] = []

    current_ignored_attributes = (
        ignored_attributes_config or DEFAULT_IGNORED_ATTRIBUTES
    ).get(resource_type, [])
    # Add 'id' to ignored attributes as it's used for matching, not for diffing content.
    # Also, some attributes in TF state are computed/internal and start with '_' or are complex objects not meant for direct diff.
    # This simple diff won't handle nested structures well without more logic.

    all_keys = set(iac_attrs.keys()) | set(actual_attrs.keys())

    for key in all_keys:
        if key in current_ignored_attributes or key.startswith("_"):  # Basic ignore
            continue

        iac_value = iac_attrs.get(key)
        actual_value = actual_attrs.get(key)

        # Rudimentary handling for common "tags" pattern where actual might have more tags
        if (
            key == "tags"
            and isinstance(iac_value, dict)
            and isinstance(actual_value, dict)
        ):
            # Check if all IaC tags are present in actual tags with same values
            # This doesn't flag extra tags in actual_value as drift, only missing/different IaC tags.
            tag_drift_found = False
            for tag_key, tag_iac_val in iac_value.items():
                tag_actual_val = actual_value.get(tag_key)
                if tag_actual_val != tag_iac_val:
                    drifts.append(
                        AttributeDrift(
                            attribute_name=f"tags.{tag_key}",
                            iac_value=tag_iac_val,
                            actual_value=tag_actual_val,
                        )
                    )
                    tag_drift_found = True
            if tag_drift_found:
                # We've reported individual tag drifts, so skip generic 'tags' comparison
                continue
            # If no specific tag drifts, it implies all IaC tags are matched.
            # We are not considering extra actual tags as drift here.

        elif iac_value != actual_value:
            # This is a very basic comparison. It won't handle:
            # - Nested objects well (e.g. list of blocks, complex maps)
            # - Type differences (e.g. "1" vs 1) if not normalized by parser
            # - Computed values that are expected to be different
            # - Order in lists if order doesn't matter
            drifts.append(
                AttributeDrift(
                    attribute_name=key, iac_value=iac_value, actual_value=actual_value
                )
            )

    return drifts


def compare_states(
    iac_resources: List[ParsedResource],
    actual_resources: List[ParsedResource],
    ignored_attributes_config: Optional[Dict[str, List[str]]] = None,
) -> List[DriftInfo]:
    """
    Compares the desired state (from IaC) with the actual state (from cloud).

    Args:
        iac_resources: List of resources defined in IaC.
        actual_resources: List of resources found in the actual environment.
        ignored_attributes_config: Configuration for attributes to ignore during comparison.

    Returns:
        A list of DriftInfo objects detailing any detected drifts.
    """
    drift_results: List[DriftInfo] = []

    # Create dictionaries for quick lookup by resource ID (actual cloud ID)
    # This assumes `res.id` from iac_resources is the *actual cloud ID* stored in tfstate.
    iac_by_id: Dict[str, ParsedResource] = {
        res.id: res for res in iac_resources if res.id
    }
    actual_by_id: Dict[str, ParsedResource] = {
        res.id: res for res in actual_resources if res.id
    }

    # --- Check for MODIFIED and MISSING_IN_ACTUAL resources ---
    for iac_res_id, iac_res in iac_by_id.items():
        actual_res = actual_by_id.get(iac_res_id)

        if actual_res:
            # Resource exists in both IaC and Actual state, check for modifications
            if (
                iac_res.type != actual_res.type
            ):  # Should ideally not happen if ID is unique across types
                drift_results.append(
                    DriftInfo(
                        drift_type=DriftType.MODIFIED,
                        resource_type=iac_res.type,
                        resource_name=iac_res.name,
                        resource_id=iac_res_id,
                        iac_resource=iac_res,
                        actual_resource=actual_res,
                        message=f"Type mismatch: IaC type '{iac_res.type}', Actual type '{actual_res.type}' for ID '{iac_res_id}'.",
                    )
                )
                continue  # Skip further attribute comparison for this one

            attribute_drifts = compare_attributes(
                iac_res.attributes,
                actual_res.attributes,
                iac_res.type,
                ignored_attributes_config,
            )
            if attribute_drifts:
                drift_results.append(
                    DriftInfo(
                        drift_type=DriftType.MODIFIED,
                        resource_type=iac_res.type,
                        resource_name=iac_res.name,  # Logical name from IaC
                        resource_id=iac_res_id,
                        iac_resource=iac_res,
                        actual_resource=actual_res,
                        attribute_drifts=attribute_drifts,
                        message=f"Resource '{iac_res.type}.{iac_res.name}' (ID: {iac_res_id}) has modified attributes.",
                    )
                )
        else:
            # Resource in IaC but not found in actual state
            drift_results.append(
                DriftInfo(
                    drift_type=DriftType.MISSING_IN_ACTUAL,
                    resource_type=iac_res.type,
                    resource_name=iac_res.name,
                    resource_id=iac_res_id,  # This ID was expected from IaC state
                    iac_resource=iac_res,
                    actual_resource=None,
                    message=f"Resource '{iac_res.type}.{iac_res.name}' (Expected ID: {iac_res_id}) defined in IaC is missing in actual state.",
                )
            )

    # --- Check for UNMANAGED_IN_ACTUAL resources ---
    # Resources in actual state but not tracked by (or missing from) IaC state
    actual_ids_processed: Set[str] = set(
        iac_by_id.keys()
    )  # IDs that were matched or found missing

    for actual_res_id, actual_res in actual_by_id.items():
        if actual_res_id not in actual_ids_processed:
            drift_results.append(
                DriftInfo(
                    drift_type=DriftType.UNMANAGED_IN_ACTUAL,
                    resource_type=actual_res.type,
                    resource_name=actual_res.name,  # Name from actual resource (e.g. a tag or descriptive name)
                    resource_id=actual_res_id,
                    iac_resource=None,
                    actual_resource=actual_res,
                    message=f"Resource ID '{actual_res_id}' (Type: {actual_res.type}, Name: {actual_res.name}) found in actual state is not managed by (or tracked in) current IaC state.",
                )
            )

    return drift_results


if __name__ == "__main__":
    # Example Usage
    from ..parsers.terraform_parser import ParsedResource as IaCResource  # For clarity
    from ..connectors.mock_connector import (
        ParsedResource as ActualResource,
    )  # For clarity

    print("--- Testing Drift Engine ---")

    # Scenario 1: Basic - one modified, one missing, one unmanaged
    iac_state: List[IaCResource] = [
        IaCResource(
            id="id-instance-01",
            type="vm",
            name="web_server_iac",
            provider_name="mock",
            attributes={
                "size": "medium",
                "image": "ubuntu-20.04",
                "tags": {"env": "prod"},
            },
        ),
        IaCResource(
            id="id-db-01",
            type="database",
            name="main_db_iac",
            provider_name="mock",
            attributes={"version": "12", "storage": "100GB"},
        ),  # This will be missing
    ]
    actual_state: List[ActualResource] = [
        ActualResource(
            id="id-instance-01",
            type="vm",
            name="web_server_actual",
            provider_name="mock",
            attributes={
                "size": "large",
                "image": "ubuntu-20.04",
                "tags": {"env": "prod", "extra_tag": "hello"},
            },
        ),  # Modified size
        ActualResource(
            id="id-disk-unmanaged",
            type="disk",
            name="orphan_disk_actual",
            provider_name="mock",
            attributes={"size": "50GB"},
        ),  # Unmanaged
    ]

    print("\nScenario 1: Modified, Missing, Unmanaged")
    drifts1 = compare_states(iac_state, actual_state)
    for drift in drifts1:
        print(
            f"  Drift Type: {drift.drift_type.value}, Resource: {drift.resource_type}.{drift.resource_name}, ID: {drift.resource_id}"
        )
        if drift.attribute_drifts:
            for attr_drift in drift.attribute_drifts:
                print(
                    f"    - Attr '{attr_drift.attribute_name}': IaC='{attr_drift.iac_value}', Actual='{attr_drift.actual_value}'"
                )
        if drift.message:
            print(f"    Msg: {drift.message}")

    assert len(drifts1) == 3
    assert any(
        d.drift_type == DriftType.MODIFIED and d.resource_id == "id-instance-01"
        for d in drifts1
    )
    assert any(
        d.drift_type == DriftType.MISSING_IN_ACTUAL and d.resource_id == "id-db-01"
        for d in drifts1
    )
    assert any(
        d.drift_type == DriftType.UNMANAGED_IN_ACTUAL
        and d.resource_id == "id-disk-unmanaged"
        for d in drifts1
    )

    # Scenario 2: No drift
    iac_state_no_drift: List[IaCResource] = [
        IaCResource(
            id="id-vm-100",
            type="vm",
            name="app_server",
            provider_name="mock",
            attributes={"image": "centos8", "cpu": 2},
        ),
    ]
    actual_state_no_drift: List[ActualResource] = [
        ActualResource(
            id="id-vm-100",
            type="vm",
            name="app_server_live",
            provider_name="mock",
            attributes={"image": "centos8", "cpu": 2},
        ),
    ]
    print("\nScenario 2: No Drift")
    drifts2 = compare_states(iac_state_no_drift, actual_state_no_drift)
    if not drifts2:
        print("  No drift detected. OK.")
    else:
        for drift in drifts2:
            print(
                f"  Unexpected Drift: {drift.drift_type.value} for {drift.resource_name}"
            )
    assert not drifts2

    # Scenario 3: Ignored attributes and tags
    # DEFAULT_IGNORED_ATTRIBUTES = {"vm": ["last_updated_time"]}
    custom_ignored = {"vm": ["last_updated_time", "dynamic_ip"]}
    iac_state_ignore: List[IaCResource] = [
        IaCResource(
            id="id-vm-200",
            type="vm",
            name="worker",
            provider_name="mock",
            attributes={
                "image": "debian",
                "ram": "4GB",
                "last_updated_time": "ts1",
                "tags": {"managed_by": "iac"},
            },
        ),
    ]
    actual_state_ignore: List[ActualResource] = [
        ActualResource(
            id="id-vm-200",
            type="vm",
            name="worker_live",
            provider_name="mock",
            attributes={
                "image": "debian",
                "ram": "4GB",
                "last_updated_time": "ts2",
                "dynamic_ip": "1.2.3.4",
                "tags": {"managed_by": "iac", "status": "running"},
            },
        ),
    ]
    print("\nScenario 3: Ignored attributes and tags")
    # Note: compare_attributes has its own DEFAULT_IGNORED_ATTRIBUTES. We pass our custom one here.
    drifts3 = compare_states(
        iac_state_ignore, actual_state_ignore, ignored_attributes_config=custom_ignored
    )
    if (
        not drifts3
    ):  # Expect no drift due to ignore rules for attributes and tags handling (extra actual tags are ignored)
        print(
            "  No drift detected (attributes ignored, extra actual tags ignored). OK."
        )
    else:
        for drift in drifts3:
            print(
                f"  Unexpected Drift: {drift.drift_type.value} for {drift.resource_name}"
            )
            if drift.attribute_drifts:
                for ad in drift.attribute_drifts:
                    print(f"    Attr: {ad.attribute_name}")
    assert not drifts3, f"Expected no drift, but got: {drifts3}"

    # Scenario 4: Attribute modified (tags specifically, one tag value changed)
    iac_state_tag_mod: List[IaCResource] = [
        IaCResource(
            id="id-vm-300",
            type="vm",
            name="tagged_vm",
            provider_name="mock",
            attributes={"tags": {"env": "staging", "owner": "team-a"}},
        ),
    ]
    actual_state_tag_mod: List[ActualResource] = [
        ActualResource(
            id="id-vm-300",
            type="vm",
            name="tagged_vm_live",
            provider_name="mock",
            attributes={"tags": {"env": "prod", "owner": "team-a", "new_tag": "val"}},
        ),  # env tag changed
    ]
    print("\nScenario 4: Tag value modified")
    drifts4 = compare_states(iac_state_tag_mod, actual_state_tag_mod)
    assert len(drifts4) == 1
    assert drifts4[0].drift_type == DriftType.MODIFIED
    assert len(drifts4[0].attribute_drifts) == 1
    assert drifts4[0].attribute_drifts[0].attribute_name == "tags.env"
    assert drifts4[0].attribute_drifts[0].iac_value == "staging"
    assert drifts4[0].attribute_drifts[0].actual_value == "prod"
    print("  Tag modification detected correctly. OK.")

    print("\nDrift Engine tests complete.")
