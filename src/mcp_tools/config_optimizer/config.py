import yaml
import os
from typing import List, Optional, Dict, Pattern
from pydantic import BaseModel, Field, field_validator, ValidationError

DEFAULT_OPTIMIZER_RULES_FILENAME = ".config-optimizer-rules.yml"

# --- Individual Rule Component Models ---

class EC2InstanceTypeRule(BaseModel):
    enabled: bool = True
    # Example: Warn if these types are used without a 'criticality: high' tag
    flag_large_types_without_tag: Optional[Dict[str, List[str]]] = Field(
        default_factory=lambda: {"criticality!": ["high", "true"]} # tag_key!: [list_of_values_that_exempt]
    )
    large_instance_types_to_flag: List[str] = Field(
        default_factory=lambda: ["m5.24xlarge", "c5.18xlarge", "r5.24xlarge", "p3.16xlarge"] # Example list
    )
    suggest_newer_generations: bool = True
    # Simple mapping, could be more complex (e.g. considering families, regions)
    generation_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "t2": "t3", "m4": "m5", "c4": "c5", "r4": "r5", "p2": "p3", "g3":"g4"
            # Add more mappings based on common upgrades
        }
    )

class S3BucketEncryptionRule(BaseModel):
    enabled: bool = True
    require_sse_kms: bool = False # If true, specifically look for 'aws:kms'
    # If false, any server_side_encryption_configuration block is fine.

class S3BucketVersioningRule(BaseModel):
    enabled: bool = True
    # No specific params needed, just checks if versioning is "Enabled" or "Suspended" vs not set.

class S3BucketPublicAccessBlockRule(BaseModel):
    enabled: bool = True
    require_all_blocks_true: bool = True # Check if all four public access block settings are true

# --- Provider-Specific Rule Groups ---

class AWSEC2Rules(BaseModel):
    instance_type_optimization: EC2InstanceTypeRule = Field(default_factory=EC2InstanceTypeRule)
    # Add other EC2 rules here, e.g., unattached_ebs, ebs_encryption
    enabled: bool = True

class AWSS3Rules(BaseModel):
    encryption: S3BucketEncryptionRule = Field(default_factory=S3BucketEncryptionRule)
    versioning: S3BucketVersioningRule = Field(default_factory=S3BucketVersioningRule)
    public_access_block: S3BucketPublicAccessBlockRule = Field(default_factory=S3BucketPublicAccessBlockRule)
    # Add other S3 rules here, e.g., lifecycle_policies, storage_class analysis
    enabled: bool = True

# --- Main Optimizer Configuration Model ---

class OptimizerRuleConfig(BaseModel):
    aws_ec2: AWSEC2Rules = Field(default_factory=AWSEC2Rules)
    aws_s3: AWSS3Rules = Field(default_factory=AWSS3Rules)
    # Add other providers or global rules here
    # e.g., global_tags_policy: Optional[SomeTagPolicy] = None

# --- Loading Function ---

def load_optimizer_rules(config_path: Optional[str] = None) -> OptimizerRuleConfig:
    """
    Loads optimization rules from a YAML file.
    If config_path is None, tries to load from '.config-optimizer-rules.yml'.
    If no file is found or path is invalid, returns default rule configuration.
    """
    actual_config_path = config_path
    if not actual_config_path:
        # Search for default config file in current and parent directories
        current_dir = os.getcwd()
        while True:
            default_path_try = os.path.join(current_dir, DEFAULT_OPTIMIZER_RULES_FILENAME)
            if os.path.exists(default_path_try):
                actual_config_path = default_path_try
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir: # Reached root directory
                break
            current_dir = parent_dir

    if actual_config_path and os.path.exists(actual_config_path):
        print(f"Loading optimizer rules from: {actual_config_path}")
        try:
            with open(actual_config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            if config_data is None: # Empty YAML file
                print(f"Warning: Optimizer rules file '{actual_config_path}' is empty. Using default rules.")
                return OptimizerRuleConfig()
            return OptimizerRuleConfig(**config_data)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML optimizer rules file {actual_config_path}: {e}")
        except ValidationError as e:
            raise ValueError(f"Optimizer rules validation error in {actual_config_path}:\n{e}")
        except Exception as e:
            raise ValueError(f"Unexpected error loading optimizer rules from {actual_config_path}: {e}")
    else:
        if config_path: # User specified a path but it wasn't found
             print(f"Warning: Optimizer rules file '{config_path}' not found. Using default rules.")
        else: # No specific path given and default wasn't found
            print(f"No optimizer rules file '{DEFAULT_OPTIMIZER_RULES_FILENAME}' found. Using default rules.")
        return OptimizerRuleConfig()


if __name__ == '__main__':
    # Example usage and simple test
    try:
        # Test with default rules (no file present)
        print("--- Testing with default optimizer rules (no file) ---")
        default_rules = load_optimizer_rules()
        print(f"Default EC2 instance type optimization enabled: {default_rules.aws_ec2.instance_type_optimization.enabled}")
        print(f"Default S3 encryption enabled: {default_rules.aws_s3.encryption.enabled}")
        assert default_rules.aws_ec2.instance_type_optimization.suggest_newer_generations is True

        # Create a dummy .config-optimizer-rules.yml for testing
        dummy_rules_content = {
            "aws_ec2": {
                "instance_type_optimization": {
                    "enabled": True,
                    "suggest_newer_generations": False, # Override default
                    "large_instance_types_to_flag": ["c5.2xlarge"]
                },
                "enabled": True
            },
            "aws_s3": {
                "encryption": {"enabled": False}, # Disable S3 encryption check
                "versioning": {"enabled": True},
                "enabled": True # aws_s3 rules are enabled
            }
        }
        with open(DEFAULT_OPTIMIZER_RULES_FILENAME, 'w') as f:
            yaml.dump(dummy_rules_content, f)

        print(f"\n--- Testing with dummy {DEFAULT_OPTIMIZER_RULES_FILENAME} ---")
        loaded_rules = load_optimizer_rules() # Should auto-detect
        print(f"Loaded EC2 suggest_newer_generations: {loaded_rules.aws_ec2.instance_type_optimization.suggest_newer_generations}")
        assert loaded_rules.aws_ec2.instance_type_optimization.suggest_newer_generations is False
        assert loaded_rules.aws_ec2.instance_type_optimization.large_instance_types_to_flag == ["c5.2xlarge"]
        assert loaded_rules.aws_s3.encryption.enabled is False
        assert loaded_rules.aws_s3.versioning.enabled is True
        assert loaded_rules.aws_s3.public_access_block.enabled is True # Default as not specified

    except Exception as e:
        print(f"Error during example usage: {e}", file=sys.stderr)
    finally:
        if os.path.exists(DEFAULT_OPTIMIZER_RULES_FILENAME):
            os.remove(DEFAULT_OPTIMIZER_RULES_FILENAME)
        pass
