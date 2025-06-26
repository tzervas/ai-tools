from typing import List, Dict, Any, Optional

from ...iac_drift_detector.models import ParsedResource  # Reusing
from ..models import Recommendation
from ..config import AWSS3Rules  # S3 specific rule config bundle


def check_s3_bucket_optimizations(
    resource: ParsedResource, rules: AWSS3Rules
) -> List[Recommendation]:
    """
    Checks a parsed S3 bucket resource against configured optimization rules.

    Args:
        resource: The ParsedResource object representing an S3 bucket.
        rules: The AWSS3Rules configuration object.

    Returns:
        A list of Recommendation objects.
    """
    recommendations: List[Recommendation] = []
    if not rules.enabled:
        return recommendations

    attributes = resource.attributes

    # 1. Encryption Check
    if rules.encryption.enabled:
        sse_config = attributes.get("server_side_encryption_configuration")
        # SSE config structure:
        # "server_side_encryption_configuration": {
        #   "rule": {
        #     "apply_server_side_encryption_by_default": {
        #       "sse_algorithm": "aws:kms" OR "AES256",
        #       "kms_master_key_id": "arn:aws:kms:..." (if aws:kms)
        #     },
        #     "bucket_key_enabled": true (optional)
        #   }
        # }
        encryption_found = False
        if sse_config and isinstance(sse_config, dict):
            rule = sse_config.get("rule")
            if rule and isinstance(rule, dict):
                apply_sse = rule.get("apply_server_side_encryption_by_default")
                if apply_sse and isinstance(apply_sse, dict):
                    sse_algorithm = apply_sse.get("sse_algorithm")
                    if sse_algorithm:
                        if rules.encryption.require_sse_kms:
                            if sse_algorithm == "aws:kms":
                                encryption_found = True
                            # Could also check for kms_master_key_id if require_sse_kms is very strict
                        else:  # Any sse_algorithm is fine
                            encryption_found = True

        if not encryption_found:
            recommendations.append(
                Recommendation(
                    rule_id="AWS_S3_ENCRYPTION_DISABLED",
                    severity="Medium",
                    resource_type=resource.type,
                    resource_name=resource.name,
                    resource_id=resource.id,
                    message=f"Server-side encryption is not enabled or not configured as per policy "
                    f"(require_sse_kms: {rules.encryption.require_sse_kms}). "
                    f"Consider enabling SSE for data at rest.",
                    details={"current_sse_config": sse_config},
                )
            )

    # 2. Versioning Check
    if rules.versioning.enabled:
        versioning_config = attributes.get("versioning")
        # Versioning config structure:
        # "versioning": {
        #   "enabled": true/false, (sometimes "status": "Enabled"/"Suspended")
        #   "mfa_delete": true/false
        # }
        # Terraform state often shows it as: "versioning": [{"enabled": true, "mfa_delete": false}] (a list with one dict)

        versioning_status_enabled = False
        if isinstance(versioning_config, list) and versioning_config:  # TF state style
            versioning_dict = versioning_config[0]
            if (
                isinstance(versioning_dict, dict)
                and versioning_dict.get("enabled") is True
            ):
                versioning_status_enabled = True
        elif isinstance(
            versioning_config, dict
        ):  # More direct API style or simplified state
            if (
                versioning_config.get("enabled") is True
                or versioning_config.get("status") == "Enabled"
            ):
                versioning_status_enabled = True

        if not versioning_status_enabled:
            recommendations.append(
                Recommendation(
                    rule_id="AWS_S3_VERSIONING_DISABLED",
                    severity="Medium",
                    resource_type=resource.type,
                    resource_name=resource.name,
                    resource_id=resource.id,
                    message="Object versioning is not enabled. Consider enabling versioning to protect against accidental deletions and to preserve object history.",
                    details={"current_versioning_config": versioning_config},
                )
            )

    # 3. Public Access Block Check
    if rules.public_access_block.enabled:
        pab_config = attributes.get("public_access_block")
        # PAB config structure (example from TF state):
        # "public_access_block": [{
        #   "block_public_acls": true,
        #   "block_public_policy": true,
        #   "ignore_public_acls": true,
        #   "restrict_public_buckets": true
        # }]
        # Or sometimes directly a dict from actual state.

        all_blocks_true = False
        expected_true_blocks = {
            "block_public_acls",
            "block_public_policy",
            "ignore_public_acls",
            "restrict_public_buckets",
        }

        pab_settings_to_check = {}
        if isinstance(pab_config, list) and pab_config:
            pab_settings_to_check = (
                pab_config[0] if isinstance(pab_config[0], dict) else {}
            )
        elif isinstance(pab_config, dict):
            pab_settings_to_check = pab_config

        if rules.public_access_block.require_all_blocks_true:
            # Check if all expected block settings are present and True
            all_blocks_true = all(
                pab_settings_to_check.get(block_name) is True
                for block_name in expected_true_blocks
            )

            if not all_blocks_true:
                missing_or_false_blocks = {
                    block: pab_settings_to_check.get(block, "Not Set")
                    for block in expected_true_blocks
                    if pab_settings_to_check.get(block) is not True
                }
                recommendations.append(
                    Recommendation(
                        rule_id="AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE",
                        severity="High",
                        resource_type=resource.type,
                        resource_name=resource.name,
                        resource_id=resource.id,
                        message="Public Access Block is not configured to block all public access. "
                        "It's highly recommended to enable all four public access block settings.",
                        details={
                            "current_public_access_block_config": pab_settings_to_check,
                            "blocks_not_fully_enabled": missing_or_false_blocks,
                        },
                    )
                )
        # Else (if require_all_blocks_true is false), policy might define specific blocks to check.
        # For now, only implementing the "all true" case.

    # Future checks:
    # - Lifecycle policies (e.g., suggest transitioning old data to Glacier)
    # - Intelligent tiering usage
    # - Logging configuration
    # - Replication setup for DR

    return recommendations


if __name__ == "__main__":
    print("--- Testing S3 Optimizer Logic ---")

    # Mock ParsedResource for S3 Buckets
    s3_no_sse = ParsedResource(
        id="bucket-no-sse",
        type="aws_s3_bucket",
        name="no-sse-bucket",
        provider_name="aws",
        attributes={"bucket": "bucket-no-sse", "acl": "private"},
    )
    s3_with_aes256 = ParsedResource(
        id="bucket-aes256",
        type="aws_s3_bucket",
        name="aes256-bucket",
        provider_name="aws",
        attributes={
            "bucket": "bucket-aes256",
            "acl": "private",
            "server_side_encryption_configuration": {
                "rule": {
                    "apply_server_side_encryption_by_default": {
                        "sse_algorithm": "AES256"
                    }
                }
            },
        },
    )
    s3_with_kms = ParsedResource(
        id="bucket-kms",
        type="aws_s3_bucket",
        name="kms-bucket",
        provider_name="aws",
        attributes={
            "bucket": "bucket-kms",
            "acl": "private",
            "server_side_encryption_configuration": {
                "rule": {
                    "apply_server_side_encryption_by_default": {
                        "sse_algorithm": "aws:kms",
                        "kms_master_key_id": "alias/aws/s3",
                    }
                }
            },
        },
    )
    s3_no_versioning = ParsedResource(
        id="bucket-no-versioning",
        type="aws_s3_bucket",
        name="no-versioning",
        provider_name="aws",
        attributes={"bucket": "no-versioning"},
    )
    s3_versioning_enabled_tf_style = ParsedResource(  # Terraform state list style
        id="bucket-versioned-tf",
        type="aws_s3_bucket",
        name="versioned-tf",
        provider_name="aws",
        attributes={
            "bucket": "versioned-tf",
            "versioning": [{"enabled": True, "mfa_delete": False}],
        },
    )
    s3_pab_incomplete = ParsedResource(
        id="bucket-pab-bad",
        type="aws_s3_bucket",
        name="pab-bad",
        provider_name="aws",
        attributes={
            "bucket": "pab-bad",
            "public_access_block": {  # Direct dict style
                "block_public_acls": True,
                "block_public_policy": False,  # This one is False
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
        },
    )
    s3_pab_good_tf_style = ParsedResource(  # TF state list style
        id="bucket-pab-good",
        type="aws_s3_bucket",
        name="pab-good",
        provider_name="aws",
        attributes={
            "bucket": "pab-good",
            "public_access_block": [
                {
                    "block_public_acls": True,
                    "block_public_policy": True,
                    "ignore_public_acls": True,
                    "restrict_public_buckets": True,
                }
            ],
        },
    )

    # Test with default rules
    print("\n-- Test 1: Default AWSS3Rules --")
    default_s3_rules = AWSS3Rules()  # All checks enabled by default

    recs_no_sse = check_s3_bucket_optimizations(s3_no_sse, default_s3_rules)
    print(f"Recs for s3_no_sse: {len(recs_no_sse)}")  # Expect SSE, Versioning, PAB
    assert any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs_no_sse)
    assert any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs_no_sse)
    assert any(
        r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs_no_sse
    )

    recs_aes256 = check_s3_bucket_optimizations(s3_with_aes256, default_s3_rules)
    print(
        f"Recs for s3_with_aes256 (default require_sse_kms=False): {len(recs_aes256)}"
    )  # No SSE violation
    assert not any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs_aes256)
    assert any(
        r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs_aes256
    )  # Still needs versioning & PAB

    # Test require_sse_kms = True
    custom_s3_rules_kms = AWSS3Rules()
    custom_s3_rules_kms.encryption.require_sse_kms = True
    recs_aes256_kms_req = check_s3_bucket_optimizations(
        s3_with_aes256, custom_s3_rules_kms
    )
    print(
        f"Recs for s3_with_aes256 (require_sse_kms=True): {len(recs_aes256_kms_req)}"
    )  # SSE violation now
    assert any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs_aes256_kms_req)

    recs_kms = check_s3_bucket_optimizations(s3_with_kms, custom_s3_rules_kms)
    print(
        f"Recs for s3_with_kms (require_sse_kms=True): {len(recs_kms)}"
    )  # No SSE violation
    assert not any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs_kms)

    recs_versioned_tf = check_s3_bucket_optimizations(
        s3_versioning_enabled_tf_style, default_s3_rules
    )
    print(f"Recs for s3_versioning_enabled_tf_style: {len(recs_versioned_tf)}")
    assert not any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs_versioned_tf)

    recs_pab_incomplete = check_s3_bucket_optimizations(
        s3_pab_incomplete, default_s3_rules
    )
    print(f"Recs for s3_pab_incomplete: {len(recs_pab_incomplete)}")
    assert any(
        r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE"
        for r in recs_pab_incomplete
    )
    assert "block_public_policy" in recs_pab_incomplete[-1].details.get(
        "blocks_not_fully_enabled", {}
    )  # Assuming PAB is last check

    recs_pab_good = check_s3_bucket_optimizations(
        s3_pab_good_tf_style, default_s3_rules
    )
    print(f"Recs for s3_pab_good_tf_style: {len(recs_pab_good)}")
    assert not any(
        r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs_pab_good
    )

    # Test with all S3 rules disabled
    disabled_s3_rules = AWSS3Rules(enabled=False)
    recs_disabled_all = check_s3_bucket_optimizations(s3_no_sse, disabled_s3_rules)
    print(f"Recs for s3_no_sse (all S3 rules disabled): {len(recs_disabled_all)}")
    assert not recs_disabled_all

    # Test with only one sub-rule disabled
    one_disabled_s3_rules = AWSS3Rules()
    one_disabled_s3_rules.versioning.enabled = False
    recs_one_disabled = check_s3_bucket_optimizations(s3_no_sse, one_disabled_s3_rules)
    print(f"Recs for s3_no_sse (versioning rule disabled): {len(recs_one_disabled)}")
    assert not any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs_one_disabled)
    assert any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs_one_disabled)

    print("\nS3 Optimizer tests complete.")
