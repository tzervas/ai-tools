import pytest
from typing import List, Dict, Any, Optional  # Added Optional

from src.mcp_tools.iac_drift_detector.models import ParsedResource  # Reusing
from src.mcp_tools.config_optimizer.models import Recommendation
from src.mcp_tools.config_optimizer.config import EC2InstanceTypeRule
from src.mcp_tools.config_optimizer.aws.ec2_optimizer import (
    check_ec2_instance_optimizations,
)

# --- Test Data ---


def create_ec2_resource(
    id: str, name: str, instance_type: str, tags: Optional[Dict[str, str]] = None
) -> ParsedResource:
    return ParsedResource(
        id=id,
        type="aws_instance",
        name=name,
        provider_name="aws",
        attributes={"instance_type": instance_type, "tags": tags or {}},
    )


# --- Tests for check_ec2_instance_optimizations ---


def test_ec2_newer_generation_suggestion_from_map():
    res = create_ec2_resource("i-t2", "test-t2", "t2.medium")
    rules = EC2InstanceTypeRule(
        suggest_newer_generations=True, generation_map={"t2": "t3"}
    )
    recs = check_ec2_instance_optimizations(res, rules)
    assert len(recs) == 1
    assert recs[0].rule_id == "AWS_EC2_NEWER_GENERATION_MAPPED"
    assert "'t2.medium'" in recs[0].message
    assert "'t3.medium'" in recs[0].message


def test_ec2_newer_generation_suggestion_generic_family():
    res = create_ec2_resource(
        "i-c3", "test-c3", "c3.large"
    )  # Assume c3 is older, c4/c5/c6/c7 in default map
    # Use default generation_map which doesn't have 'c3' explicitly, so it falls to generic family check
    rules = EC2InstanceTypeRule(suggest_newer_generations=True)
    # Ensure INSTANCE_FAMILY_GENERATION in ec2_optimizer.py has 'c3' or a similar setup for this test to be meaningful
    # For this test, let's assume 'c3' is not in INSTANCE_FAMILY_GENERATION, so no generic suggestion for 'c' family
    # If 'c3' *was* in INSTANCE_FAMILY_GENERATION and older than 'c4'/'c5', it would trigger.
    # The current INSTANCE_FAMILY_GENERATION starts at gen 4 for 'c' family. So 'c3' would not match a family to find newer.

    # Let's test with "m3.large" if m4/m5/m6/m7 are in map.
    # Assuming "m3" is not in INSTANCE_FAMILY_GENERATION, but "m" family exists with newer.
    # This test is a bit tricky without directly mocking INSTANCE_FAMILY_GENERATION.
    # The current logic: if current_type_prefix is not in INSTANCE_FAMILY_GENERATION, no generic suggestion.
    # So, to test generic, the prefix MUST be in INSTANCE_FAMILY_GENERATION.

    res_m4 = create_ec2_resource(
        "i-m4", "test-m4", "m4.xlarge"
    )  # m4 is in map, m5/m6/m7 are newer
    rules_m4 = EC2InstanceTypeRule(
        suggest_newer_generations=True, generation_map={}
    )  # Empty map to force generic

    recs_m4 = check_ec2_instance_optimizations(res_m4, rules_m4)
    assert len(recs_m4) >= 1  # Should find at least one newer generation in 'm' family
    assert any(r.rule_id == "AWS_EC2_NEWER_GENERATION_GENERIC" for r in recs_m4)
    assert any(
        "m4.xlarge" in r.message
        and ("m5" in r.message or "m6" in r.message or "m7" in r.message)
        for r in recs_m4
    )


def test_ec2_newer_generation_already_newest_or_unmapped():
    res = create_ec2_resource(
        "i-m7g", "test-m7g", "m7g.large"
    )  # m7g is latest in default map
    rules = EC2InstanceTypeRule(suggest_newer_generations=True)
    recs = check_ec2_instance_optimizations(res, rules)
    assert not any("NEWER_GENERATION" in r.rule_id for r in recs)

    res_unknown = create_ec2_resource(
        "i-custom", "test-custom", "custom.type"
    )  # Not in map
    recs_unknown = check_ec2_instance_optimizations(res_unknown, rules)
    assert not any("NEWER_GENERATION" in r.rule_id for r in recs_unknown)


def test_ec2_flag_large_instance_type():
    res_large = create_ec2_resource(
        "i-large", "test-large", "m5.24xlarge"
    )  # In default large_instance_types_to_flag
    rules = EC2InstanceTypeRule(
        large_instance_types_to_flag=["m5.24xlarge"],  # Explicitly list it for clarity
        # flag_large_types_without_tag logic is simplified in current implementation
    )
    recs = check_ec2_instance_optimizations(res_large, rules)
    assert len(recs) == 1
    assert recs[0].rule_id == "AWS_EC2_LARGE_INSTANCE_TYPE"
    assert "'m5.24xlarge' is a large instance" in recs[0].message


def test_ec2_flag_large_instance_type_not_in_list():
    res_medium = create_ec2_resource("i-medium", "test-medium", "m5.large")
    rules = EC2InstanceTypeRule(
        large_instance_types_to_flag=["c5.18xlarge"]
    )  # m5.large not in this list
    recs = check_ec2_instance_optimizations(res_medium, rules)
    assert not any(r.rule_id == "AWS_EC2_LARGE_INSTANCE_TYPE" for r in recs)


def test_ec2_no_instance_type_attribute():
    res_no_type = ParsedResource(
        id="i-no-type",
        type="aws_instance",
        name="no-type-test",
        provider_name="aws",
        attributes={},
    )
    rules = EC2InstanceTypeRule()
    recs = check_ec2_instance_optimizations(res_no_type, rules)
    assert not recs  # Should not generate recommendations if instance_type is missing


def test_ec2_rules_disabled():
    res = create_ec2_resource("i-t2", "test-t2", "t2.medium")
    rules = EC2InstanceTypeRule(
        enabled=False, suggest_newer_generations=True
    )  # Main rule disabled
    recs = check_ec2_instance_optimizations(res, rules)
    assert not recs


def test_ec2_suggest_newer_generations_disabled_in_rule():
    res = create_ec2_resource("i-t2", "test-t2", "t2.medium")
    rules = EC2InstanceTypeRule(
        enabled=True, suggest_newer_generations=False
    )  # Sub-rule disabled
    recs = check_ec2_instance_optimizations(res, rules)
    assert not any("NEWER_GENERATION" in r.rule_id for r in recs)


# Note: The 'flag_large_types_without_tag' logic in ec2_optimizer.py was simplified.
# The current test 'test_ec2_flag_large_instance_type' reflects this simplified behavior
# (flags if type is in list, message advises to check justification/tagging).
# More complex tests for tag-based exemption would require updating the config model
# and the implementation in ec2_optimizer.py for `flag_large_types_without_tag`.
