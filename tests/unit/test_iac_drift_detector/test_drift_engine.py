import pytest
from typing import List, Dict, Any

from src.mcp_tools.iac_drift_detector.models import ParsedResource, DriftInfo, DriftType, AttributeDrift
from src.mcp_tools.iac_drift_detector.core_logic.drift_engine import compare_states, compare_attributes, DEFAULT_IGNORED_ATTRIBUTES

# --- Test compare_attributes ---

@pytest.mark.parametrize("iac_attrs, actual_attrs, resource_type, ignored_config, expected_drifts_count, expected_drift_details", [
    # No drift
    ({"size": "medium"}, {"size": "medium"}, "vm", None, 0, []),
    # Simple modification
    ({"size": "medium"}, {"size": "large"}, "vm", None, 1, [("size", "medium", "large")]),
    # Attribute added in actual
    ({"size": "medium"}, {"size": "medium", "new_attr": "val"}, "vm", None, 1, [("new_attr", None, "val")]),
    # Attribute removed in actual (present in IaC)
    ({"size": "medium", "old_attr": "val"}, {"size": "medium"}, "vm", None, 1, [("old_attr", "val", None)]),
    # Ignored attribute
    ({"size": "medium", "arn": "arn1"}, {"size": "medium", "arn": "arn2"}, "aws_instance", None, 0, []), # 'arn' is in DEFAULT_IGNORED_ATTRIBUTES for aws_instance
    # Custom ignored attribute
    ({"color": "blue", "shape": "round"}, {"color": "red", "shape": "round"}, "widget", {"widget": ["color"]}, 0, []),
    # Tags: Exact match
    ({"tags": {"env": "prod"}}, {"tags": {"env": "prod"}}, "vm", None, 0, []),
    # Tags: IaC tag value modified in actual
    ({"tags": {"env": "prod"}}, {"tags": {"env": "dev"}}, "vm", None, 1, [("tags.env", "prod", "dev")]),
    # Tags: IaC tag missing in actual
    ({"tags": {"env": "prod", "app": "A"}}, {"tags": {"env": "prod"}}, "vm", None, 1, [("tags.app", "A", None)]),
    # Tags: Extra tag in actual (should NOT be flagged by current logic)
    ({"tags": {"env": "prod"}}, {"tags": {"env": "prod", "extra": "B"}}, "vm", None, 0, []),
    # Tags: Both modified IaC tag and extra actual tag (only modified IaC tag should be flagged)
    ({"tags": {"env": "prod"}}, {"tags": {"env": "dev", "extra": "B"}}, "vm", None, 1, [("tags.env", "prod", "dev")]),
])
def test_compare_attributes(iac_attrs, actual_attrs, resource_type, ignored_config, expected_drifts_count, expected_drift_details):
    drifts = compare_attributes(iac_attrs, actual_attrs, resource_type, ignored_config)
    assert len(drifts) == expected_drifts_count
    for i, (attr_name, iac_val, act_val) in enumerate(expected_drift_details):
        found_drift = next((d for d in drifts if d.attribute_name == attr_name), None)
        assert found_drift is not None, f"Expected drift for attribute '{attr_name}' not found."
        assert found_drift.iac_value == iac_val
        assert found_drift.actual_value == act_val

# --- Test compare_states ---

def test_compare_states_modified_missing_unmanaged():
    iac_state: List[ParsedResource] = [
        ParsedResource(id="id-instance-01", type="vm", name="web_server_iac", provider_name="mock", attributes={"size": "medium", "image": "ubuntu-20.04", "tags": {"env": "prod"}}),
        ParsedResource(id="id-db-01", type="database", name="main_db_iac", provider_name="mock", attributes={"version": "12", "storage": "100GB"}), # Missing
    ]
    actual_state: List[ParsedResource] = [
        ParsedResource(id="id-instance-01", type="vm", name="web_server_actual", provider_name="mock", attributes={"size": "large", "image": "ubuntu-20.04", "tags": {"env": "prod", "extra_tag": "hello"}}), # Modified size
        ParsedResource(id="id-disk-unmanaged", type="disk", name="orphan_disk_actual", provider_name="mock", attributes={"size": "50GB"}), # Unmanaged
    ]

    drifts = compare_states(iac_state, actual_state)
    assert len(drifts) == 3

    modified_drift = next((d for d in drifts if d.drift_type == DriftType.MODIFIED and d.resource_id == "id-instance-01"), None)
    assert modified_drift is not None
    assert any(ad.attribute_name == "size" for ad in modified_drift.attribute_drifts)

    missing_drift = next((d for d in drifts if d.drift_type == DriftType.MISSING_IN_ACTUAL and d.resource_id == "id-db-01"), None)
    assert missing_drift is not None

    unmanaged_drift = next((d for d in drifts if d.drift_type == DriftType.UNMANAGED_IN_ACTUAL and d.resource_id == "id-disk-unmanaged"), None)
    assert unmanaged_drift is not None

def test_compare_states_no_drift():
    iac_state: List[ParsedResource] = [
        ParsedResource(id="id-vm-100", type="vm", name="app_server", provider_name="mock", attributes={"image": "centos8", "cpu": 2}),
    ]
    actual_state: List[ParsedResource] = [
        ParsedResource(id="id-vm-100", type="vm", name="app_server_live", provider_name="mock", attributes={"image": "centos8", "cpu": 2}),
    ]
    drifts = compare_states(iac_state, actual_state)
    assert not drifts, f"Expected no drift, but got: {drifts}"

def test_compare_states_ignored_attributes():
    custom_ignored = {"vm": ["last_updated_time", "dynamic_ip"]}
    iac_state: List[ParsedResource] = [
        ParsedResource(id="id-vm-200", type="vm", name="worker", provider_name="mock",
                    attributes={"image": "debian", "ram": "4GB", "last_updated_time": "ts1", "tags": {"managed_by": "iac"}}),
    ]
    actual_state: List[ParsedResource] = [
        ParsedResource(id="id-vm-200", type="vm", name="worker_live", provider_name="mock",
                       attributes={"image": "debian", "ram": "4GB", "last_updated_time": "ts2", "dynamic_ip": "1.2.3.4", "tags": {"managed_by": "iac", "status": "running"}}),
    ]
    drifts = compare_states(iac_state, actual_state, ignored_attributes_config=custom_ignored)
    assert not drifts, f"Expected no drift due to ignored attributes, but got: {drifts}"

def test_compare_states_tag_value_modified():
    iac_state: List[ParsedResource] = [
        ParsedResource(id="id-vm-300", type="vm", name="tagged_vm", provider_name="mock",
                    attributes={"tags": {"env": "staging", "owner": "team-a"}}),
    ]
    actual_state: List[ParsedResource] = [
        ParsedResource(id="id-vm-300", type="vm", name="tagged_vm_live", provider_name="mock",
                       attributes={"tags": {"env": "prod", "owner": "team-a", "new_tag": "val"}}),
    ]
    drifts = compare_states(iac_state, actual_state)
    assert len(drifts) == 1
    assert drifts[0].drift_type == DriftType.MODIFIED
    assert len(drifts[0].attribute_drifts) == 1
    assert drifts[0].attribute_drifts[0].attribute_name == "tags.env"
    assert drifts[0].attribute_drifts[0].iac_value == "staging"
    assert drifts[0].attribute_drifts[0].actual_value == "prod"

def test_compare_states_type_mismatch_on_same_id():
    """ Test scenario where same ID has different resource types (should be rare, but possible if IDs are not universally unique)."""
    iac_state: List[ParsedResource] = [
        ParsedResource(id="id-shared-01", type="vm", name="resource_a", provider_name="mock", attributes={})
    ]
    actual_state: List[ParsedResource] = [
        ParsedResource(id="id-shared-01", type="disk", name="resource_b_actual", provider_name="mock", attributes={})
    ]
    drifts = compare_states(iac_state, actual_state)
    assert len(drifts) == 1 # Should be one MODIFIED drift indicating type mismatch
    assert drifts[0].drift_type == DriftType.MODIFIED
    assert "Type mismatch" in drifts[0].message

def test_compare_states_empty_iac_all_unmanaged():
    iac_state: List[ParsedResource] = []
    actual_state: List[ParsedResource] = [
        ParsedResource(id="id-unmanaged-1", type="vm", name="vm1", provider_name="mock", attributes={}),
        ParsedResource(id="id-unmanaged-2", type="disk", name="disk1", provider_name="mock", attributes={}),
    ]
    drifts = compare_states(iac_state, actual_state)
    assert len(drifts) == 2
    assert all(d.drift_type == DriftType.UNMANAGED_IN_ACTUAL for d in drifts)

def test_compare_states_empty_actual_all_missing():
    iac_state: List[ParsedResource] = [
        ParsedResource(id="id-missing-1", type="vm", name="vm_iac_1", provider_name="mock", attributes={}),
        ParsedResource(id="id-missing-2", type="disk", name="disk_iac_1", provider_name="mock", attributes={}),
    ]
    actual_state: List[ParsedResource] = []
    drifts = compare_states(iac_state, actual_state)
    assert len(drifts) == 2
    assert all(d.drift_type == DriftType.MISSING_IN_ACTUAL for d in drifts)

def test_compare_states_no_ids_in_iac_resources():
    """ Test how it handles IaC resources that might be missing 'id' (e.g. malformed state). """
    iac_state: List[ParsedResource] = [
        ParsedResource(id=None, type="vm", name="vm_no_id", provider_name="mock", attributes={}) # type: ignore
    ]
    actual_state: List[ParsedResource] = [
         ParsedResource(id="id-actual-1", type="vm", name="vm_actual_1", provider_name="mock", attributes={})
    ]
    # Current implementation of compare_states uses `iac_by_id = {res.id: res for res in iac_resources if res.id}`
    # So, iac_resource without id will be skipped for MODIFIED/MISSING checks based on ID.
    # The actual resource will then be found as UNMANAGED.
    drifts = compare_states(iac_state, actual_state)
    assert len(drifts) == 1
    assert drifts[0].drift_type == DriftType.UNMANAGED_IN_ACTUAL
    assert drifts[0].resource_id == "id-actual-1"
