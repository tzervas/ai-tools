import argparse
import os
import sys
from typing import List

# Assuming ParsedResource is accessible from the iac_drift_detector tool
from ..iac_drift_detector.models import ParsedResource
from ..iac_drift_detector.parsers.terraform_parser import parse_terraform_state_file

from .config import load_optimizer_rules, OptimizerRuleConfig
from .models import Recommendation
from .aws import ec2_optimizer, s3_optimizer  # Import the AWS optimizer modules


def run_optimization_checks(
    iac_resources: List[ParsedResource], rules_config: OptimizerRuleConfig
) -> List[Recommendation]:
    """
    Runs all configured optimization checks on the provided IaC resources.
    """
    all_recommendations: List[Recommendation] = []

    print("\n--- Running Configuration Optimization Checks ---")

    for resource in iac_resources:
        provider = (
            resource.provider_name.lower()
        )  # Assuming provider_name is like "aws", "gcp"

        if provider == "aws":
            if resource.type == "aws_instance" and rules_config.aws_ec2.enabled:
                if rules_config.aws_ec2.instance_type_optimization.enabled:
                    all_recommendations.extend(
                        ec2_optimizer.check_ec2_instance_optimizations(
                            resource, rules_config.aws_ec2.instance_type_optimization
                        )
                    )
                # Add calls to other EC2 check groups from rules_config.aws_ec2 here

            elif resource.type == "aws_s3_bucket" and rules_config.aws_s3.enabled:
                # S3 Encryption
                if rules_config.aws_s3.encryption.enabled:
                    all_recommendations.extend(
                        s3_optimizer.check_s3_bucket_optimizations(  # This function checks all its sub-rules
                            resource,
                            rules_config.aws_s3,  # Pass the parent AWSS3Rules object
                        )
                    )
                # Note: s3_optimizer.check_s3_bucket_optimizations internally checks sub-rules like versioning, pab
                # So, we call it once per S3 bucket if aws_s3 rules are enabled.
                # The structure above for EC2 is slightly different (calling specific check if sub-rule enabled).
                # For consistency, s3_optimizer.check_s3_bucket_optimizations should ideally take the specific sub-rule config.
                # Let's adjust s3_optimizer to be called once, and it handles its sub-rules.
                # The current s3_optimizer.check_s3_bucket_optimizations(resource, rules_config.aws_s3) is fine.

            # Add other AWS resource type checks here
            # elif resource.type == "aws_rds_instance" and rules_config.aws_rds.enabled:
            #     ...

        # elif provider == "gcp":
        # Add GCP checks here
        # ...

    return all_recommendations


def main():
    parser = argparse.ArgumentParser(
        description="Configuration Optimization Recommendations Tool."
    )
    parser.add_argument(
        "--iac-type",
        type=str,
        default="terraform",
        choices=["terraform"],
        help="Type of Infrastructure as Code tool source (default: terraform).",
    )

    tf_group = parser.add_argument_group(
        "Terraform Options (if --iac-type is terraform)"
    )
    tf_group.add_argument(
        "--tf-state-file",
        type=str,
        help="Path to the Terraform state file (.tfstate) for IaC data.",
    )

    parser.add_argument(
        "--rules-file",
        default=None,
        help="Path to the optimization rules configuration YAML file. Defaults to searching for '.config-optimizer-rules.yml'.",
    )
    # parser.add_argument("--repo-path", default=None, # If needed for context, not used currently
    #                     help="Path to the Git repository. Defaults to current working directory.")

    args = parser.parse_args()
    print("--- Configuration Optimizer Initializing ---")

    # 1. Load IaC Resources
    iac_resources: List[ParsedResource] = []
    if args.iac_type == "terraform":
        if args.tf_state_file:
            print(f"Loading IaC data from Terraform state file: {args.tf_state_file}")
            if not os.path.exists(args.tf_state_file):
                print(
                    f"Error: Terraform state file {args.tf_state_file} not found.",
                    file=sys.stderr,
                )
                sys.exit(2)
            iac_resources = parse_terraform_state_file(
                args.tf_state_file
            )  # From iac_drift_detector
            if not iac_resources and os.path.exists(
                args.tf_state_file
            ):  # File exists but no resources parsed
                print(
                    f"Warning: No managed resources found or parsed from {args.tf_state_file}."
                )
        else:
            print(
                "Error: For Terraform, --tf-state-file must be provided.",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        print(
            f"Error: IaC type '{args.iac_type}' is not yet supported.", file=sys.stderr
        )
        sys.exit(2)

    if not iac_resources:
        print("No IaC resources loaded. No optimizations to check. Exiting.")
        sys.exit(0)

    print(f"Loaded {len(iac_resources)} resources from IaC source.")

    # 2. Load Optimizer Rules
    print(
        f"Loading optimization rules (file: {args.rules_file or 'auto-detect .config-optimizer-rules.yml'})..."
    )
    try:
        rules_config = load_optimizer_rules(config_path=args.rules_file)
    except (
        FileNotFoundError,
        ValueError,
    ) as e:  # Catch errors from load_optimizer_rules
        print(f"Error loading rules configuration: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"An unexpected error occurred while loading rules: {e}", file=sys.stderr)
        sys.exit(3)

    # 3. Run Optimization Checks
    recommendations = run_optimization_checks(iac_resources, rules_config)

    # 4. Report Recommendations
    if not recommendations:
        print(
            "\n--- Result: NO OPTIMIZATION RECOMMENDATIONS FOUND (based on current rules) ---"
        )
        sys.exit(0)

    print(
        f"\n--- Result: {len(recommendations)} OPTIMIZATION RECOMMENDATION(S) FOUND ---"
    )
    # Group recommendations by rule or severity? For now, just list them.
    for i, rec in enumerate(recommendations, 1):
        print(
            f"\nRecommendation {i}/{len(recommendations)}: [{rec.severity}|{rec.rule_id}]"
        )
        print(
            f"  Resource: {rec.resource_type} '{rec.resource_name}' (ID: {rec.resource_id or 'N/A'})"
        )
        print(f"  Message:  {rec.message}")
        if rec.details:
            print(f"  Details:  {rec.details}")

    sys.exit(1)  # Exit with non-zero code if recommendations are found


if __name__ == "__main__":
    # To test this CLI:
    # 1. Create a dummy Terraform state file (e.g., copy from iac_drift_detector's terraform_parser.py example)
    #    as 'test_optimizer.tfstate' in the current directory.
    #    Ensure it has some aws_instance and aws_s3_bucket resources.
    # 2. Optionally, create a .config-optimizer-rules.yml file to customize rules.
    # 3. Run: python -m src.mcp_tools.config_optimizer.cli --tf-state-file test_optimizer.tfstate
    main()
