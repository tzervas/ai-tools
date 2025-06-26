import argparse
import os
import sys
from typing import List

from .parsers.terraform_parser import (
    parse_terraform_state_file,
    parse_terraform_plan_json_file,
    ParsedResource as IaCResource,
)
from .connectors.mock_connector import MockActualStateConnector  # For now, only mock

# from .connectors.aws_connector import AwsActualStateConnector # Future
from .core_logic.drift_engine import compare_states, DriftInfo
from .core_logic.remediation import suggest_remediation

# No direct import of PolicyConfig here, this tool doesn't use .pr-policy.yml structure


def main():
    parser = argparse.ArgumentParser(
        description="IaC Drift Detection and Remediation Suggestion Tool."
    )
    parser.add_argument(
        "--iac-type",
        type=str,
        default="terraform",
        choices=["terraform"],
        help="Type of Infrastructure as Code tool being used (default: terraform).",
    )

    # Terraform specific arguments
    tf_group = parser.add_argument_group("Terraform Options")
    tf_group.add_argument(
        "--tf-state-file",
        type=str,
        help="Path to the Terraform state file (.tfstate) for desired state.",
    )
    # tf_group.add_argument("--tf-plan-file", type=str, # For future use with plan-based drift
    #                       help="Path to a Terraform plan JSON file (from 'terraform show -json plan.out').")

    # Actual state source arguments
    actual_state_group = parser.add_argument_group("Actual State Source Options")
    actual_state_group.add_argument(
        "--actual-state-source",
        type=str,
        default="mock",
        choices=["mock"],  # Add "aws", "gcp" later
        help="Source to fetch the actual infrastructure state from (default: mock).",
    )
    # Mock connector specific (optional, could be more)
    # actual_state_group.add_argument("--mock-data-file", type=str, help="Path to a JSON file with custom mock data for the mock connector.")

    # Future cloud provider args:
    # aws_group = parser.add_argument_group('AWS Options (if actual-state-source is aws)')
    # aws_group.add_argument("--aws-profile", type=str, help="AWS profile to use.")
    # aws_group.add_argument("--aws-region", type=str, help="AWS region to scan.")

    args = parser.parse_args()

    print("--- IaC Drift Detector Initializing ---")

    # 1. Load Desired State (from IaC)
    desired_state_resources: List[IaCResource] = []
    if args.iac_type == "terraform":
        if args.tf_state_file:
            print(
                f"Loading desired state from Terraform state file: {args.tf_state_file}"
            )
            desired_state_resources = parse_terraform_state_file(args.tf_state_file)
            if not desired_state_resources and os.path.exists(args.tf_state_file):
                print(
                    f"Warning: No managed resources found or parsed from {args.tf_state_file}."
                )
            elif not os.path.exists(args.tf_state_file):
                print(f"Error: Terraform state file {args.tf_state_file} not found.")
                sys.exit(2)

        # elif args.tf_plan_file:
        # print(f"Loading desired state/changes from Terraform plan file: {args.tf_plan_file}")
        # For true "desired state", state file is better. Plan shows *changes*.
        # plan_changes = parse_terraform_plan_json_file(args.tf_plan_file)
        # This would require different logic in drift engine or a pre-processor for plan data.
        # For now, focusing on state file for desired state.
        # print("Note: Plan file parsing is for future enhancements, focusing on state file for current desired state.")
        else:
            print(
                "Error: For Terraform, either --tf-state-file must be provided.",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        print(
            f"Error: IaC type '{args.iac_type}' is not yet supported.", file=sys.stderr
        )
        sys.exit(2)

    if (
        not desired_state_resources
        and args.tf_state_file
        and os.path.exists(args.tf_state_file)
    ):
        print(f"No desired state resources loaded from {args.tf_state_file}. Exiting.")
        # Exiting because if state file is empty or has no resources, drift detection is trivial (everything actual is unmanaged)
        # but usually implies an issue or an empty setup.
        # sys.exit(0) # Or continue to show all actual as unmanaged

    # 2. Load Actual State
    actual_state_resources: List[IaCResource] = (
        []
    )  # Using IaCResource type for consistency from models.py
    if args.actual_state_source == "mock":
        print("Loading actual state using MockConnector...")
        # custom_mock_data = None
        # if args.mock_data_file:
        #     try:
        #         with open(args.mock_data_file, 'r') as f:
        #             custom_mock_data = json.load(f) # Assuming JSON list of dicts
        #         print(f"Using custom mock data from {args.mock_data_file}")
        #     except Exception as e:
        #         print(f"Warning: Could not load custom mock data from {args.mock_data_file}: {e}. Using default mock data.")
        # connector = MockActualStateConnector(mock_data=custom_mock_data)
        connector = MockActualStateConnector()  # Using default mock data for now
        actual_state_resources = connector.fetch_actual_state()
    # elif args.actual_state_source == "aws":
    #     print("Loading actual state from AWS...")
    #     # connector = AwsActualStateConnector(profile=args.aws_profile, region=args.aws_region)
    #     # actual_state_resources = connector.fetch_actual_state() # This would involve boto3 calls
    #     print("AWS connector not yet implemented.", file=sys.stderr)
    #     sys.exit(3)
    else:
        print(
            f"Error: Actual state source '{args.actual_state_source}' is not yet supported.",
            file=sys.stderr,
        )
        sys.exit(3)

    # 3. Compare States and Detect Drift
    print("\n--- Comparing States and Detecting Drift ---")
    # TODO: Allow passing ignored_attributes_config from a config file or CLI
    detected_drifts = compare_states(desired_state_resources, actual_state_resources)

    # 4. Report Drifts and Suggest Remediation
    if not detected_drifts:
        print("\n--- Result: NO DRIFT DETECTED ---")
        sys.exit(0)

    print(f"\n--- Result: {len(detected_drifts)} DRIFT(S) DETECTED ---")
    for i, drift_info in enumerate(detected_drifts, 1):
        print(
            f"\nDrift {i}/{len(detected_drifts)}: {drift_info.drift_type.value.upper()}"
        )
        print(f"  Resource Type: {drift_info.resource_type}")
        print(f"  Resource Name: {drift_info.resource_name}")
        if drift_info.resource_id:
            print(f"  Resource ID:   {drift_info.resource_id}")

        if (
            drift_info.message and drift_info.drift_type != DriftType.MODIFIED
        ):  # MODIFIED has detailed attr reporting
            print(f"  Details: {drift_info.message}")

        if drift_info.drift_type == DriftType.MODIFIED and drift_info.attribute_drifts:
            print("  Attribute Differences:")
            for attr_drift in drift_info.attribute_drifts:
                iac_val_str = (
                    f"'{attr_drift.iac_value}'"
                    if attr_drift.iac_value is not None
                    else "not set (None)"
                )
                act_val_str = (
                    f"'{attr_drift.actual_value}'"
                    if attr_drift.actual_value is not None
                    else "not set (None)"
                )
                print(
                    f"    - '{attr_drift.attribute_name}': IaC = {iac_val_str}, Actual = {act_val_str}"
                )

        suggestions = suggest_remediation(drift_info, iac_tool=args.iac_type)
        if suggestions:
            print("  Suggested Remediation:")
            for suggestion_line in suggestions:
                print(f"    {suggestion_line}")

    sys.exit(1)  # Exit with non-zero code if drifts are found


if __name__ == "__main__":
    # To test this CLI:
    # 1. Create a dummy Terraform state file (e.g., copy from terraform_parser.py example usage)
    #    as 'test.tfstate' in the current directory.
    # 2. Run: python -m src.mcp_tools.iac_drift_detector.cli --tf-state-file test.tfstate
    #    This will use the default mock actual state.
    main()
