from typing import List, Dict, Any
from ..models import ParsedResource  # Import from shared models


class MockActualStateConnector:
    """
    Simulates fetching actual infrastructure state.
    """

    def __init__(self, mock_data: Optional[List[Dict[str, Any]]] = None):
        """
        Initializes the mock connector.

        Args:
            mock_data: A list of dictionaries, where each dictionary represents
                       an actual resource's properties. If None, default mock data is used.
        """
        if mock_data is not None:
            self.mock_resources_data = mock_data
        else:
            self.mock_resources_data = self._get_default_mock_data()

    def _get_default_mock_data(self) -> List[Dict[str, Any]]:
        """Provides a default set of mock resources."""
        return [
            {
                "id": "i-12345abcdef",  # Matches dummy_tfstate_content
                "type": "aws_instance",
                "name": "actual-example-ec2",  # Name might differ from IaC name
                "provider_name": "aws",
                "attributes": {
                    "id": "i-12345abcdef",
                    "ami": "ami-0c55b31ad29f52962",
                    "instance_type": "t2.micro",  # Same as tfstate
                    "tags": {
                        "Name": "example-instance",
                        "Environment": "prod_actual",
                    },  # Tag differs
                },
            },
            {
                # This resource matches one in tfstate but will have different attributes
                "id": "my-unique-bucket-name",
                "type": "aws_s3_bucket",
                "name": "actual-s3-bucket",
                "provider_name": "aws",
                "attributes": {
                    "id": "my-unique-bucket-name",
                    "bucket": "my-unique-bucket-name",
                    "acl": "public-read",  # Different from tfstate's "private"
                    "versioning": {"enabled": True},  # Extra attribute not in tfstate
                },
            },
            {
                # This resource is only in the "actual" state (unmanaged)
                "id": "vol-09876fedcba",
                "type": "aws_ebs_volume",
                "name": "unmanaged-data-volume",
                "provider_name": "aws",
                "attributes": {
                    "id": "vol-09876fedcba",
                    "size": 100,
                    "type": "gp3",
                    "availability_zone": "us-east-1a",
                },
            },
        ]

    def fetch_actual_state(
        self, environment_params: Optional[Dict[str, Any]] = None
    ) -> List[ParsedResource]:
        """
        Fetches the (mocked) actual state of resources.

        Args:
            environment_params: Parameters specific to the environment being queried
                               (e.g., region, account_id). Not used by mock connector
                               but important for real connectors.

        Returns:
            A list of ParsedResource objects representing the actual state.
        """
        print(
            f"MockConnector: Fetching actual state (using {len(self.mock_resources_data)} mock data entries)."
        )
        if environment_params:
            print(
                f"MockConnector: Received environment params: {environment_params} (currently unused by mock)."
            )

        actual_resources: List[ParsedResource] = []
        for res_data in self.mock_resources_data:
            try:
                # Directly create ParsedResource from the dictionary structure
                # This assumes the dictionary keys match ParsedResource fields.
                actual_resources.append(ParsedResource(**res_data))
            except Exception as e:  # Catch Pydantic validation errors or others
                print(
                    f"Warning: Could not parse mock resource data into ParsedResource: {res_data}. Error: {e}",
                    file=sys.stderr,
                )

        return actual_resources


if __name__ == "__main__":
    # Example Usage
    print("--- Testing MockActualStateConnector with default data ---")
    connector_default = MockActualStateConnector()
    default_state = connector_default.fetch_actual_state({"region": "us-east-1"})

    if default_state:
        print(f"Fetched {len(default_state)} resources from default mock state:")
        for res in default_state:
            print(
                f"  ID: {res.id}, Type: {res.type}, Name: {res.name}, Provider: {res.provider_name}"
            )
            if res.type == "aws_instance":
                assert res.attributes.get("instance_type") == "t2.micro"
                assert (
                    res.attributes.get("tags", {}).get("Environment") == "prod_actual"
                )
            elif res.type == "aws_s3_bucket":
                assert res.attributes.get("acl") == "public-read"

    custom_mock_data = [
        {
            "id": "custom-vm-01",
            "type": "gcp_compute_instance",
            "name": "my-custom-vm",
            "provider_name": "gcp",
            "attributes": {"machine_type": "n1-standard-1", "zone": "us-central1-a"},
        }
    ]
    print("\n--- Testing MockActualStateConnector with custom data ---")
    connector_custom = MockActualStateConnector(mock_data=custom_mock_data)
    custom_state = connector_custom.fetch_actual_state()
    if custom_state:
        print(f"Fetched {len(custom_state)} resources from custom mock state:")
        for res in custom_state:
            print(
                f"  ID: {res.id}, Type: {res.type}, Name: {res.name}, Provider: {res.provider_name}"
            )
            if res.type == "gcp_compute_instance":
                assert res.attributes.get("machine_type") == "n1-standard-1"
    else:
        print("No resources fetched from custom mock state.")
