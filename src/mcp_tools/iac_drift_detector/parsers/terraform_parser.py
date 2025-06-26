import json
from typing import List, Dict, Any, Optional, Union

# No longer need BaseModel, Field, validator directly here if ParsedResource is self-contained
from ..models import ParsedResource  # Import from shared models

# --- Terraform State Parser ---


def parse_terraform_state_file(file_path: str) -> List[ParsedResource]:
    """
    Parses a Terraform state file (.tfstate) and extracts resources.

    Args:
        file_path: Path to the .tfstate file.

    Returns:
        A list of ParsedResource objects.
        Returns an empty list if parsing fails or no resources are found.
    """
    try:
        with open(file_path, "r") as f:
            state_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Terraform state file not found at {file_path}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(
            f"Error: Invalid JSON in Terraform state file {file_path}: {e}",
            file=sys.stderr,
        )
        return []
    except Exception as e:
        print(f"Error reading Terraform state file {file_path}: {e}", file=sys.stderr)
        return []

    parsed_resources: List[ParsedResource] = []

    # Terraform state structure can vary slightly (e.g., version 3 vs 4 format)
    # We are interested in the 'resources' array.
    # In TF versions >= 0.12, resources are typically under a top-level 'resources' key.
    # For older versions or complex states with modules, traversal might be needed.
    # This parser assumes a common structure where 'resources' contains a list of resource objects.

    resources_in_state = state_data.get("resources", [])

    for res_data in resources_in_state:
        # Skip data sources, focus on managed resources
        if res_data.get("mode", "managed") != "managed":
            continue

        res_type = res_data.get("type")
        res_name = res_data.get("name")
        res_provider_full = res_data.get(
            "provider", ""
        )  # e.g., "provider[\"registry.terraform.io/hashicorp/aws\"]"

        # Extract provider name (e.g., "aws")
        provider_name_short = "unknown"
        if "hashicorp/" in res_provider_full:
            provider_name_short = res_provider_full.split("hashicorp/")[-1].split('"]')[
                0
            ]
        elif "providers/" in res_provider_full:  # For some community providers
            provider_name_short = res_provider_full.split("providers/")[-1].split('"]')[
                0
            ]

        # Each resource can have multiple instances (e.g., if using count or for_each)
        for instance_data in res_data.get("instances", []):
            instance_attributes = instance_data.get("attributes", {})
            instance_id = instance_attributes.get("id")  # Common 'id' attribute

            if not instance_id or not res_type or not res_name:
                # print(f"Warning: Skipping resource instance due to missing id, type, or name: {instance_data}", file=sys.stderr)
                continue

            # Module path if present
            module_path = res_data.get("module")

            parsed_resources.append(
                ParsedResource(
                    id=str(instance_id),  # Ensure ID is string
                    type=res_type,
                    name=res_name,
                    provider_name=provider_name_short,
                    module=module_path,
                    attributes=instance_attributes,  # Store all attributes from the instance
                )
            )

    return parsed_resources


# --- Terraform Plan Parser ---


def parse_terraform_plan_json_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses a Terraform plan file (JSON output from `terraform show -json <planfile>`)
    and extracts planned changes. This is more about *changes* than current state.
    For drift detection, we are usually more interested in the state file for "desired state".
    However, a plan can show what *would* change if applied, which can indicate drift
    if the plan is generated against an out-of-sync state.

    This function will extract a list of resource changes for now.
    A more sophisticated drift tool might use this to predict drift resolution.

    Args:
        file_path: Path to the JSON plan file.

    Returns:
        A list of dictionaries, where each dictionary represents a planned resource change.
        Returns an empty list if parsing fails.
    """
    try:
        with open(file_path, "r") as f:
            plan_data = json.load(f)
    except FileNotFoundError:
        print(
            f"Error: Terraform plan JSON file not found at {file_path}", file=sys.stderr
        )
        return []
    except json.JSONDecodeError as e:
        print(
            f"Error: Invalid JSON in Terraform plan file {file_path}: {e}",
            file=sys.stderr,
        )
        return []
    except Exception as e:
        print(f"Error reading Terraform plan file {file_path}: {e}", file=sys.stderr)
        return []

    # The structure of plan JSON is complex. We are interested in 'resource_changes'.
    resource_changes = plan_data.get("resource_changes", [])

    # We could transform these into ParsedResource or a new `PlannedChange` model.
    # For now, just returning the raw change objects for further processing.
    # Each change object has "address", "type", "name", "change" (with "actions", "before", "after").

    # Example: Filter for changes that are not "no-op"
    # actual_changes = [rc for rc in resource_changes if rc.get("change", {}).get("actions", ["no-op"]) != ["no-op"]]
    # return actual_changes

    return resource_changes  # Return all resource change objects for now


if __name__ == "__main__":
    # Example Usage:
    # Create dummy tfstate and tfplan files for testing this module directly.

    # Dummy tfstate content
    dummy_tfstate_content = {
        "version": 4,
        "terraform_version": "1.0.0",
        "serial": 1,
        "lineage": "some-uuid",
        "outputs": {},
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "example_ec2",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "i-12345abcdef",
                            "ami": "ami-0c55b31ad29f52962",
                            "instance_type": "t2.micro",
                            "tags": {"Name": "example-instance"},
                        },
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "my_bucket",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {
                        "schema_version": 0,
                        "attributes": {
                            "id": "my-unique-bucket-name",
                            "bucket": "my-unique-bucket-name",
                            "acl": "private",
                        },
                    }
                ],
            },
            {
                "mode": "data",  # This should be skipped
                "type": "aws_ami",
                "name": "ubuntu",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [{"attributes": {"id": "ami-0c55b31ad29f52962"}}],
            },
        ],
    }

    # Dummy tfplan JSON content (simplified)
    dummy_tfplan_json_content = {
        "format_version": "1.0",
        "terraform_version": "1.0.0",
        "resource_changes": [
            {
                "address": "aws_instance.example_ec2_new",
                "module_address": "",
                "mode": "managed",
                "type": "aws_instance",
                "name": "example_ec2_new",
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {"instance_type": "t3.small"},
                    "after_unknown": {"id": True},
                },
            },
            {
                "address": "aws_s3_bucket.my_bucket",
                "module_address": "",
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "my_bucket",
                "change": {
                    "actions": ["update"],
                    "before": {"acl": "private"},
                    "after": {"acl": "public-read"},
                },
            },
            {
                "address": "aws_instance.no_op_instance",
                "module_address": "",
                "mode": "managed",
                "type": "aws_instance",
                "name": "no_op_instance",
                "change": {
                    "actions": [
                        "no-op"
                    ],  # Should ideally be filtered out by caller if only interested in actual changes
                    "before": {"instance_type": "t2.micro"},
                    "after": {"instance_type": "t2.micro"},
                },
            },
        ],
    }

    # Create temporary files
    temp_dir = "temp_test_tf_files"
    os.makedirs(temp_dir, exist_ok=True)
    tfstate_path = os.path.join(temp_dir, "test.tfstate")
    tfplan_path = os.path.join(temp_dir, "test_plan.json")

    with open(tfstate_path, "w") as f:
        json.dump(dummy_tfstate_content, f)
    with open(tfplan_path, "w") as f:
        json.dump(dummy_tfplan_json_content, f)

    print("--- Testing Terraform State Parser ---")
    parsed_state_resources = parse_terraform_state_file(tfstate_path)
    if parsed_state_resources:
        print(f"Found {len(parsed_state_resources)} managed resources in state:")
        for res in parsed_state_resources:
            print(
                f"  ID: {res.id}, Type: {res.type}, Name: {res.name}, Provider: {res.provider_name}, Attrs count: {len(res.attributes)}"
            )
            if res.type == "aws_instance":
                assert res.attributes.get("instance_type") == "t2.micro"
    else:
        print("No resources parsed from state or error occurred.")

    print("\n--- Testing Terraform Plan JSON Parser ---")
    parsed_plan_changes = parse_terraform_plan_json_file(tfplan_path)
    if parsed_plan_changes:
        print(f"Found {len(parsed_plan_changes)} resource changes in plan:")
        for change in parsed_plan_changes:
            print(
                f"  Address: {change['address']}, Actions: {change['change']['actions']}"
            )
            if change["change"]["actions"] == ["create"]:
                assert change["change"]["after"].get("instance_type") == "t3.small"
    else:
        print("No changes parsed from plan or error occurred.")

    # Cleanup
    os.remove(tfstate_path)
    os.remove(tfplan_path)
    os.rmdir(temp_dir)
    print("\nCleanup complete.")
