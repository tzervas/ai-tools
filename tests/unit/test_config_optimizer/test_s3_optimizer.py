import pytest
from typing import List, Dict, Any, Optional

from src.mcp_tools.iac_drift_detector.models import ParsedResource # Reusing
from src.mcp_tools.config_optimizer.models import Recommendation
from src.mcp_tools.config_optimizer.config import AWSS3Rules, S3BucketEncryptionRule, S3BucketVersioningRule, S3BucketPublicAccessBlockRule
from src.mcp_tools.config_optimizer.aws.s3_optimizer import check_s3_bucket_optimizations

# --- Test Data ---

def create_s3_resource(id: str, name: str, attributes: Dict[str, Any]) -> ParsedResource:
    return ParsedResource(
        id=id, type="aws_s3_bucket", name=name, provider_name="aws", attributes=attributes
    )

# --- Tests for check_s3_bucket_optimizations ---

# 1. Encryption Tests
def test_s3_encryption_not_configured():
    res = create_s3_resource("bucket-no-sse", "no-sse", {"bucket": "bucket-no-sse"})
    rules = AWSS3Rules(encryption=S3BucketEncryptionRule(enabled=True, require_sse_kms=False))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs)

def test_s3_encryption_aes256_ok_when_kms_not_required():
    res_attrs = {"server_side_encryption_configuration": {"rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}}}}
    res = create_s3_resource("bucket-aes", "aes-bucket", res_attrs)
    rules = AWSS3Rules(encryption=S3BucketEncryptionRule(enabled=True, require_sse_kms=False))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs)

def test_s3_encryption_aes256_fail_when_kms_required():
    res_attrs = {"server_side_encryption_configuration": {"rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}}}}
    res = create_s3_resource("bucket-aes-kms-fail", "aes-kms-fail", res_attrs)
    rules = AWSS3Rules(encryption=S3BucketEncryptionRule(enabled=True, require_sse_kms=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs)

def test_s3_encryption_kms_ok_when_kms_required():
    res_attrs = {"server_side_encryption_configuration": {"rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": "aws:kms", "kms_master_key_id": "alias/aws/s3"}}}}
    res = create_s3_resource("bucket-kms-ok", "kms-ok", res_attrs)
    rules = AWSS3Rules(encryption=S3BucketEncryptionRule(enabled=True, require_sse_kms=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs)

def test_s3_encryption_rule_disabled():
    res = create_s3_resource("bucket-no-sse-rule-off", "no-sse-rule-off", {})
    rules = AWSS3Rules(encryption=S3BucketEncryptionRule(enabled=False))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_ENCRYPTION_DISABLED" for r in recs)


# 2. Versioning Tests
def test_s3_versioning_not_configured():
    res = create_s3_resource("bucket-no-ver", "no-ver", {"bucket": "bucket-no-ver"})
    rules = AWSS3Rules(versioning=S3BucketVersioningRule(enabled=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs)

def test_s3_versioning_explicitly_disabled_tf_style(): # TF state: list of dicts
    res_attrs = {"versioning": [{"enabled": False, "mfa_delete": False}]}
    res = create_s3_resource("bucket-ver-off-tf", "ver-off-tf", res_attrs)
    rules = AWSS3Rules(versioning=S3BucketVersioningRule(enabled=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs)

def test_s3_versioning_enabled_tf_style():
    res_attrs = {"versioning": [{"enabled": True, "mfa_delete": False}]}
    res = create_s3_resource("bucket-ver-on-tf", "ver-on-tf", res_attrs)
    rules = AWSS3Rules(versioning=S3BucketVersioningRule(enabled=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs)

def test_s3_versioning_enabled_api_style(): # API response: direct dict
    res_attrs = {"versioning": {"status": "Enabled"}} # or "enabled": True
    res = create_s3_resource("bucket-ver-on-api", "ver-on-api", res_attrs)
    rules = AWSS3Rules(versioning=S3BucketVersioningRule(enabled=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs)

    res_attrs_enabled_true = {"versioning": {"enabled": True}}
    res_enabled_true = create_s3_resource("bucket-ver-on-api2", "ver-on-api2", res_attrs_enabled_true)
    recs2 = check_s3_bucket_optimizations(res_enabled_true, rules)
    assert not any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs2)


def test_s3_versioning_rule_disabled():
    res = create_s3_resource("bucket-no-ver-rule-off", "no-ver-rule-off", {})
    rules = AWSS3Rules(versioning=S3BucketVersioningRule(enabled=False))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_VERSIONING_DISABLED" for r in recs)

# 3. Public Access Block Tests
def test_s3_pab_not_configured():
    res = create_s3_resource("bucket-no-pab", "no-pab", {"bucket": "bucket-no-pab"})
    rules = AWSS3Rules(public_access_block=S3BucketPublicAccessBlockRule(enabled=True, require_all_blocks_true=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs)

def test_s3_pab_partially_configured_false(): # TF style list of dicts
    res_attrs = {"public_access_block": [{
        "block_public_acls": True, "block_public_policy": False, # This one is False
        "ignore_public_acls": True, "restrict_public_buckets": True
    }]}
    res = create_s3_resource("bucket-pab-partial", "pab-partial", res_attrs)
    rules = AWSS3Rules(public_access_block=S3BucketPublicAccessBlockRule(enabled=True, require_all_blocks_true=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs)
    assert "block_public_policy" in recs[-1].details.get("blocks_not_fully_enabled", {}) # Assuming it's the last rec

def test_s3_pab_partially_configured_missing(): # Direct dict style
    res_attrs = {"public_access_block": {
        "block_public_acls": True, # block_public_policy is missing
        "ignore_public_acls": True, "restrict_public_buckets": True
    }}
    res = create_s3_resource("bucket-pab-missing", "pab-missing", res_attrs)
    rules = AWSS3Rules(public_access_block=S3BucketPublicAccessBlockRule(enabled=True, require_all_blocks_true=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert any(r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs)
    assert "block_public_policy" in recs[-1].details.get("blocks_not_fully_enabled", {})


def test_s3_pab_all_true_tf_style():
    res_attrs = {"public_access_block": [{
        "block_public_acls": True, "block_public_policy": True,
        "ignore_public_acls": True, "restrict_public_buckets": True
    }]}
    res = create_s3_resource("bucket-pab-good-tf", "pab-good-tf", res_attrs)
    rules = AWSS3Rules(public_access_block=S3BucketPublicAccessBlockRule(enabled=True, require_all_blocks_true=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs)

def test_s3_pab_all_true_direct_dict_style():
    res_attrs = {"public_access_block": {
        "block_public_acls": True, "block_public_policy": True,
        "ignore_public_acls": True, "restrict_public_buckets": True
    }}
    res = create_s3_resource("bucket-pab-good-dict", "pab-good-dict", res_attrs)
    rules = AWSS3Rules(public_access_block=S3BucketPublicAccessBlockRule(enabled=True, require_all_blocks_true=True))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs)


def test_s3_pab_rule_disabled():
    res = create_s3_resource("bucket-no-pab-rule-off", "no-pab-rule-off", {})
    rules = AWSS3Rules(public_access_block=S3BucketPublicAccessBlockRule(enabled=False))
    recs = check_s3_bucket_optimizations(res, rules)
    assert not any(r.rule_id == "AWS_S3_PUBLIC_ACCESS_BLOCK_INCOMPLETE" for r in recs)

def test_s3_all_aws_s3_rules_disabled():
    res = create_s3_resource("bucket-all-s3-off", "all-s3-off", {}) # Will fail all checks if enabled
    rules = AWSS3Rules(enabled=False) # Disable all S3 checks at parent level
    recs = check_s3_bucket_optimizations(res, rules)
    assert not recs
