from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ParsedResource(BaseModel):
    """Standardized representation of an IaC resource or an actual cloud resource."""
    id: str # The primary identifier of the resource within its provider
    type: str # e.g., "aws_instance", "aws_s3_bucket" (Terraform type or equivalent)
    name: str # The logical name (from IaC) or a descriptive name (if actual)
    provider_name: str # e.g., "aws", "google", "mock"
    module: Optional[str] = None # Module path if from IaC
    attributes: Dict[str, Any] = Field(default_factory=dict) # Key-value pairs of resource attributes
    # Additional field to distinguish source, could be useful
    # source: str # e.g., "terraform_state", "actual_cloud", "terraform_plan"

    # Make it hashable based on a unique key for easier comparison in sets
    # For drift detection, a composite key of type, name (logical from IaC), and provider might be better
    # Or type and ID for actual resources. This needs careful consideration for matching.
    # For now, basic Pydantic model. Hashability will be handled by the drift engine if needed.

    class Config:
        # Pydantic v2 config
        # from_attributes = True # if you were creating from ORM models, not relevant here.
        # frozen = True # If you want instances to be hashable by default for sets/dicts
        pass


from enum import Enum

class DriftType(str, Enum):
    MISSING_IN_ACTUAL = "missing_in_actual"      # Defined in IaC, not found in actual state
    UNMANAGED_IN_ACTUAL = "unmanaged_in_actual"  # Found in actual state, not defined in IaC
    MODIFIED = "modified"                      # Resource exists in both, but attributes differ
    # NO_DRIFT = "no_drift" # Could be used for explicit non-drift reporting

class AttributeDrift(BaseModel):
    attribute_name: str
    iac_value: Any
    actual_value: Any

class DriftInfo(BaseModel):
    drift_type: DriftType
    resource_type: str
    resource_name: str # Logical name from IaC if available, or a descriptive name
    resource_id: Optional[str] = None # Actual ID if available
    iac_resource: Optional[ParsedResource] = None # The resource as defined in IaC
    actual_resource: Optional[ParsedResource] = None # The resource as found in actual state
    attribute_drifts: List[AttributeDrift] = Field(default_factory=list) # For MODIFIED type
    message: Optional[str] = None # General message about the drift

    # Custom validator or logic could generate the message based on other fields.
