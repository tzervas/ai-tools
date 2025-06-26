from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ComplianceFinding(BaseModel):
    rule_id: str # A unique identifier for the rule that was violated (can be auto-generated or from config)
    severity: str # e.g., "High", "Medium", "Low", "Informational"
    message: str # Human-readable description of the finding/violation
    file_path: Optional[str] = None # File path related to the finding, if applicable
    line_number: Optional[int] = None # Line number, if applicable
    commit_sha: Optional[str] = None # Commit SHA, if related to commit history
    details: Dict[str, Any] = Field(default_factory=dict) # For any extra context-specific details

    def __str__(self) -> str:
        context = []
        if self.file_path:
            context.append(f"File: {self.file_path}")
            if self.line_number:
                context.append(f"Line: {self.line_number}")
        if self.commit_sha:
            context.append(f"Commit: {self.commit_sha[:7]}") # Short SHA

        context_str = f" ({', '.join(context)})" if context else ""
        return f"[{self.severity}|{self.rule_id}]{context_str}: {self.message}"
