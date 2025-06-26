from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# Re-using ParsedResource from the iac_drift_detector for consistency if needed
# from ...iac_drift_detector.models import ParsedResource
# For now, recommendations will refer to resource by its identifiers.

class Recommendation(BaseModel):
    """Represents a single optimization recommendation."""
    rule_id: str  # Identifier for the rule that triggered this recommendation
    severity: str # e.g., "High", "Medium", "Low", "Informational"
    resource_type: str
    resource_name: str # Logical name from IaC
    resource_id: Optional[str] = None # Actual cloud ID, if available from parsed data
    message: str # Human-readable description of the issue and recommendation
    # Optional: Add fields for suggested_action_command, documentation_url, etc.
    details: Dict[str, Any] = Field(default_factory=dict) # For any extra context

    def __str__(self) -> str:
        return f"[{self.severity}|{self.rule_id}] {self.resource_type} '{self.resource_name}' (ID: {self.resource_id or 'N/A'}): {self.message}"
