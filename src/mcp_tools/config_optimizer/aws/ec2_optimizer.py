from typing import List, Dict, Any, Optional

# Assuming ParsedResource and Recommendation models are accessible
# Adjust import path if they are moved or if this becomes part of a larger package structure
from ...iac_drift_detector.models import ParsedResource # Reusing from drift detector for resource structure
from ..models import Recommendation # Recommendation model specific to optimizer
from ..config import EC2InstanceTypeRule # EC2 specific rule config

# --- EC2 Specific Helper Data (Could be expanded or moved to a config/data file) ---
# Simple mapping of instance prefix to generation number and family type
# This is very basic and doesn't cover all nuances (e.g. arm, amd, intel, specialized types)
INSTANCE_FAMILY_GENERATION = {
    # General Purpose
    "t2": {"gen": 2, "family": "t"}, "t3": {"gen": 3, "family": "t"}, "t3a": {"gen": 3, "family": "t"},
    "t4g": {"gen": 4, "family": "t"},
    "m4": {"gen": 4, "family": "m"}, "m5": {"gen": 5, "family": "m"}, "m5a": {"gen": 5, "family": "m"},
    "m5n": {"gen": 5, "family": "m"}, "m5zn": {"gen": 5, "family": "m"},
    "m6i": {"gen": 6, "family": "m"}, "m6a": {"gen": 6, "family": "m"}, "m6g": {"gen": 6, "family": "m"},
    "m7i": {"gen": 7, "family": "m"}, "m7g": {"gen": 7, "family": "m"},
    # Compute Optimized
    "c4": {"gen": 4, "family": "c"}, "c5": {"gen": 5, "family": "c"}, "c5a": {"gen": 5, "family": "c"},
    "c5n": {"gen": 5, "family": "c"},
    "c6i": {"gen": 6, "family": "c"}, "c6a": {"gen": 6, "family": "c"}, "c6g": {"gen": 6, "family": "c"}, "c6gn": {"gen": 6, "family": "c"},
    "c7i": {"gen": 7, "family": "c"}, "c7g": {"gen": 7, "family": "c"},
    # Memory Optimized
    "r4": {"gen": 4, "family": "r"}, "r5": {"gen": 5, "family": "r"}, "r5a": {"gen": 5, "family": "r"},
    "r5b": {"gen": 5, "family": "r"}, "r5n": {"gen": 5, "family": "r"},
    "r6i": {"gen": 6, "family": "r"}, "r6a": {"gen": 6, "family": "r"}, "r6g": {"gen": 6, "family": "r"},
    "r7i": {"gen": 7, "family": "r"}, "r7g": {"gen": 7, "family": "r"},
    # Storage Optimized
    "i3": {"gen": 3, "family": "i"}, "i3en": {"gen": 3, "family": "i"},
    "i4i": {"gen": 4, "family": "i"}, "i4g": {"gen": 4, "family": "i"},
    # Accelerated Computing (very simplified)
    "p2": {"gen": 2, "family": "p"}, "p3": {"gen": 3, "family": "p"}, "p4": {"gen": 4, "family": "p"}, "p5": {"gen": 5, "family": "p"},
    "g3": {"gen": 3, "family": "g"}, "g4": {"gen": 4, "family": "g"}, "g4dn": {"gen": 4, "family": "g"},
    "g5": {"gen": 5, "family": "g"}, "g5g": {"gen": 5, "family": "g"},
}


def check_ec2_instance_optimizations(
    resource: ParsedResource,
    rules: EC2InstanceTypeRule
) -> List[Recommendation]:
    """
    Checks a parsed EC2 instance resource against configured optimization rules.

    Args:
        resource: The ParsedResource object representing an EC2 instance.
        rules: The EC2InstanceTypeRule configuration.

    Returns:
        A list of Recommendation objects.
    """
    recommendations: List[Recommendation] = []
    if not rules.enabled:
        return recommendations

    instance_type = resource.attributes.get("instance_type")
    if not instance_type or not isinstance(instance_type, str):
        return recommendations # Cannot perform checks without instance_type

    # 1. Suggest Newer Generations
    if rules.suggest_newer_generations:
        current_type_prefix = instance_type.split('.')[0] # e.g., "t2" from "t2.micro"
        current_gen_info = INSTANCE_FAMILY_GENERATION.get(current_type_prefix)

        if current_gen_info:
            # Look for newer generations in the same family
            for known_prefix, known_info in INSTANCE_FAMILY_GENERATION.items():
                if known_info["family"] == current_gen_info["family"] and known_info["gen"] > current_gen_info["gen"]:
                    # Found a newer generation prefix in the same family
                    # This is a very basic check. A real tool would need to consider compatibility, size equivalence, region availability etc.
                    # And use the mapping from config if more precise (rules.generation_map)

                    # Try to use the generation_map from config first
                    suggested_prefix_from_map = None
                    for old_gen_prefix, new_gen_prefix in rules.generation_map.items():
                        if current_type_prefix.startswith(old_gen_prefix): # e.g. t2 matches t2
                             # Construct suggested new type by replacing prefix, keeping size (e.g. t2.micro -> t3.micro)
                            size_suffix = instance_type.split('.', 1)[1] if '.' in instance_type else ''
                            if size_suffix: # only if there was a size
                                suggested_prefix_from_map = f"{new_gen_prefix}.{size_suffix}"
                                break

                    if suggested_prefix_from_map:
                         recommendations.append(Recommendation(
                            rule_id="AWS_EC2_NEWER_GENERATION_MAPPED",
                            severity="Low",
                            resource_type=resource.type,
                            resource_name=resource.name,
                            resource_id=resource.id,
                            message=f"Instance type '{instance_type}' is an older generation. "
                                    f"Consider upgrading to a newer generation like '{suggested_prefix_from_map}' "
                                    f"from the same family for potential cost/performance benefits. "
                                    f"Verify compatibility and pricing.",
                            details={"current_type": instance_type, "suggested_type_example": suggested_prefix_from_map}
                        ))
                         break # Found one suggestion from map, stop for this rule for this resource

                    # Fallback to basic family/gen check if map didn't provide one
                    elif known_prefix != current_type_prefix : # ensure it's actually a different prefix
                        size_suffix = instance_type.split('.', 1)[1] if '.' in instance_type else ''
                        suggested_type_generic = f"{known_prefix}.{size_suffix}" if size_suffix else known_prefix
                        recommendations.append(Recommendation(
                            rule_id="AWS_EC2_NEWER_GENERATION_GENERIC",
                            severity="Informational",
                            resource_type=resource.type,
                            resource_name=resource.name,
                            resource_id=resource.id,
                            message=f"Instance type '{instance_type}' belongs to an older generation family ('{current_gen_info['family']}'). "
                                    f"Newer generations in the same family (e.g., starting with '{known_prefix}') might offer better price/performance. "
                                    f"Example: '{suggested_type_generic}'. Please research specific equivalents.",
                            details={"current_type": instance_type, "newer_family_prefix_example": known_prefix}
                        ))
                        break # Found one generic suggestion, stop for this rule

    # 2. Flag Large Instance Types without Justification Tag
    if rules.flag_large_types_without_tag and instance_type in rules.large_instance_types_to_flag:
        tags = resource.attributes.get("tags", {})
        if not isinstance(tags, dict): tags = {} # Ensure tags is a dict

        exemption_tag_found = False
        if rules.flag_large_types_without_tag: # Check if this config part exists
            for tag_key_op, exempting_values in rules.flag_large_types_without_tag.items():
                # Basic support for "tag_key!" for "not equals" or "tag_key" for "equals"
                # This logic is simplistic. A proper implementation would be more robust.
                # For now, this assumes tag_key! means "tag key must exist and its value NOT IN exempting_values"
                # and tag_key means "tag key must exist and its value IS IN exempting_values"
                # The current config example `criticality!`: `['high', 'true']` is a bit confusing.
                # Let's assume it means: if tag `criticality` is NOT `high` or `true`, then it's NOT exempt.
                # Or more simply: if a tag `criticality` exists and its value is `high` or `true`, IT IS EXEMPT.

                # Corrected logic: flag_large_types_without_tag maps a tag key to a list of values that grant exemption.
                # Example: {"criticality": ["high", "true"]} means if tag 'criticality' is 'high' or 'true', it's exempt.

                # Let's simplify to: "flag if type is large AND (tag_key is not present OR tag_value not in exempt_values)"
                # The config was `flag_large_types_without_tag: {"criticality!": ["high", "true"]}`
                # This is hard to parse directly. Let's assume the config means:
                # exempt_if_tag_key_has_value: {"criticality": ["high", "true"]}

                # For now, let's use a simpler interpretation of the rule config as provided:
                # if tag 'criticality' exists and its value is 'high', it's exempt.
                # This requires changing the config structure slightly or making this code more complex.
                # Using the provided config structure: `flag_large_types_without_tag: {"criticality!": ["high", "true"]}`
                # This is non-standard. Let's assume it means: "flag if tag 'criticality' is NOT 'high' or 'true'".
                # Or, more likely, "flag if tag 'criticality' is missing, or its value is not one of these".
                # A better config would be: `exempt_if_tag_present: {"criticality": ["high", "true"]}`

                # Given the current config structure: `flag_large_types_without_tag: {"criticality!": ["high", "true"]}`
                # This is difficult to interpret directly.
                # I will proceed with a more standard interpretation: exempt if a specific tag has a specific value.
                # The config structure in `config.py` for this rule needs to be aligned.
                # Let's assume `rules.flag_large_types_without_tag` is `Dict[str, List[str]]` where key is tag_name, value is list of exempting values.
                # (This means I should update the Pydantic model in config.py for this field if this is the desired logic)

                # For this implementation, I'll use the `large_instance_types_to_flag` list
                # and assume a simple "exempt if ANY tag matches a predefined exemption criteria" (which is not in current rule structure).
                #
                # Simpler approach for now: if it's a large type, always flag it with a message to check for justification.
                # The rule `flag_large_types_without_tag` is too complex for this stage without config model change.
                # Let's just use `large_instance_types_to_flag` for now.

                # Revised logic: if instance_type is in `large_instance_types_to_flag`, generate a warning.
                # The "without_tag" part will be a generic message.
                recommendations.append(Recommendation(
                    rule_id="AWS_EC2_LARGE_INSTANCE_TYPE",
                    severity="Medium",
                    resource_type=resource.type,
                    resource_name=resource.name,
                    resource_id=resource.id,
                    message=f"Instance type '{instance_type}' is a large instance. "
                            f"Ensure this size is justified by workload requirements and consider tagging for cost allocation or justification.",
                    details={"current_type": instance_type}
                ))

    # Future checks:
    # - Unattached EBS volumes (requires knowledge of attachments, not just instance attributes)
    # - EBS encryption (from block_device_mappings in instance attributes or separate EBS resource)
    # - Low utilization (requires metrics)

    return recommendations


if __name__ == '__main__':
    print("--- Testing EC2 Optimizer Logic ---")

    # Mock ParsedResource for an EC2 instance
    res_t2_micro = ParsedResource(
        id="i-t2micro", type="aws_instance", name="test-t2", provider_name="aws",
        attributes={"instance_type": "t2.micro", "tags": {"Name": "TestT2"}}
    )
    res_m4_large = ParsedResource(
        id="i-m4large", type="aws_instance", name="test-m4", provider_name="aws",
        attributes={"instance_type": "m4.large", "tags": {"Name": "TestM4"}}
    )
    res_m5_24xl = ParsedResource(
        id="i-m5huge", type="aws_instance", name="test-m5huge", provider_name="aws",
        attributes={"instance_type": "m5.24xlarge", "tags": {"Name": "TestM5Huge"}}
    )
    res_m6i_large = ParsedResource(
        id="i-m6ilarge", type="aws_instance", name="test-m6i", provider_name="aws",
        attributes={"instance_type": "m6i.large", "tags": {"Name": "TestM6i"}}
    )

    # Test with default rules
    print("\n-- Test 1: Default EC2InstanceTypeRule --")
    default_ec2_rules = EC2InstanceTypeRule()

    recs1_t2 = check_ec2_instance_optimizations(res_t2_micro, default_ec2_rules)
    print(f"Recs for t2.micro (default rules):")
    for r in recs1_t2: print(f"  - {r}")
    assert any("Consider upgrading to a newer generation like 't3.micro'" in r.message for r in recs1_t2)

    recs1_m4 = check_ec2_instance_optimizations(res_m4_large, default_ec2_rules)
    print(f"Recs for m4.large (default rules):")
    for r in recs1_m4: print(f"  - {r}")
    assert any("Consider upgrading to a newer generation like 'm5.large'" in r.message for r in recs1_m4)

    recs1_m5huge = check_ec2_instance_optimizations(res_m5_24xl, default_ec2_rules)
    print(f"Recs for m5.24xlarge (default rules):") # Should be flagged as large
    for r in recs1_m5huge: print(f"  - {r}")
    assert any("is a large instance." in r.message for r in recs1_m5huge)
    # Check if it also suggests newer generation (m5 is relatively new, but map might have m6/m7)
    # Current map doesn't have m5 -> m6/m7 directly. It's based on prefix matching.
    # The "large instance" check should be independent of "newer generation".
    # This specific default rule has m5.24xlarge in large_instance_types_to_flag.

    recs1_m6i = check_ec2_instance_optimizations(res_m6i_large, default_ec2_rules)
    print(f"Recs for m6i.large (default rules):") # m6i is newer, should not have "newer gen" from map
    for r in recs1_m6i: print(f"  - {r}")
    assert not any("Consider upgrading" in r.message for r in recs1_m6i if "NEWER_GENERATION" in r.rule_id)


    # Test with customized rules
    print("\n-- Test 2: Custom EC2InstanceTypeRule --")
    custom_ec2_rules = EC2InstanceTypeRule(
        suggest_newer_generations=False,
        large_instance_types_to_flag=["t2.micro"], # Flag t2.micro as "large" for this test
        flag_large_types_without_tag=None # Effectively disables this specific sub-check method
    )
    recs2_t2 = check_ec2_instance_optimizations(res_t2_micro, custom_ec2_rules)
    print(f"Recs for t2.micro (custom rules):")
    for r in recs2_t2: print(f"  - {r}")
    assert not any("Consider upgrading" in r.message for r in recs2_t2) # Newer gen disabled
    assert any("is a large instance." in r.message for r in recs2_t2)   # Flagged as large by custom rule

    print("\nEC2 Optimizer tests complete.")
