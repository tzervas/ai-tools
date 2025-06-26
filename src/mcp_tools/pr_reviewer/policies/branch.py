from typing import List, Pattern, Optional
from ..config import (
    BranchNamingPolicy,
)  # Using relative import for sibling module in package


def check_branch_name_policy(
    branch_name: Optional[str], policy: BranchNamingPolicy
) -> List[str]:
    """
    Checks if the branch name conforms to the configured pattern.

    Args:
        branch_name: The name of the branch to check. Can be None (e.g. detached HEAD).
        policy: The BranchNamingPolicy configuration object.

    Returns:
        A list of violation messages. Empty if no violations.
    """
    violations: List[str] = []
    if not policy.enabled:
        return violations

    if not branch_name:
        violations.append(
            "Branch name could not be determined (possibly detached HEAD). Cannot check naming policy."
        )
        return violations

    if policy.pattern:
        # Assuming pattern is already compiled by Pydantic model
        if not policy.pattern.match(branch_name):
            violations.append(
                f"Branch name '{branch_name}' does not match the required pattern: '{policy.pattern.pattern}'."
            )
    else:
        # This case should ideally not happen if config validation is good and enabled is true
        violations.append(
            "Branch naming policy is enabled, but no pattern is configured."
        )

    return violations


if __name__ == "__main__":
    # Example Usage
    import re

    # Test case 1: Valid branch name
    policy1 = BranchNamingPolicy(pattern="^(feature|fix)/[a-z0-9-]+$", enabled=True)
    violations1 = check_branch_name_policy("feature/new-login", policy1)
    print(
        f"Test 1 (feature/new-login vs {policy1.pattern.pattern}): Violations: {violations1}"
    )  # Expected: []

    # Test case 2: Invalid branch name
    violations2 = check_branch_name_policy("Feature/NewLogin", policy1)
    print(
        f"Test 2 (Feature/NewLogin vs {policy1.pattern.pattern}): Violations: {violations2}"
    )  # Expected: [violation message]

    # Test case 3: Policy disabled
    policy3 = BranchNamingPolicy(pattern="^(feature|fix)/[a-z0-9-]+$", enabled=False)
    violations3 = check_branch_name_policy("anything", policy3)
    print(f"Test 3 (policy disabled): Violations: {violations3}")  # Expected: []

    # Test case 4: Detached HEAD
    violations4 = check_branch_name_policy(None, policy1)
    print(
        f"Test 4 (detached HEAD): Violations: {violations4}"
    )  # Expected: [violation message]

    # Test case 5: Pattern is None but enabled (should ideally be caught by config validation earlier)
    # Manually create a policy where pattern regex object is None
    policy5_config_data = {"enabled": True, "pattern": None}

    # policy5 = BranchNamingPolicy(**policy5_config_data) # Pydantic validator will likely convert None to default or fail if always=True
    # For this test, let's assume the pattern object itself is None on the policy object after loading
    class MockBranchNamingPolicy:
        def __init__(self, pattern_obj, enabled):
            self.pattern = pattern_obj
            self.enabled = enabled

    policy5_manual = MockBranchNamingPolicy(pattern_obj=None, enabled=True)
    violations5 = check_branch_name_policy("some-branch", policy5_manual)  # type: ignore
    print(f"Test 5 (pattern is None but enabled): Violations: {violations5}")

    # Test with default pattern
    default_policy = BranchNamingPolicy()  # Uses default pattern
    print(
        f"Default pattern: {default_policy.pattern.pattern if default_policy.pattern else 'None'}"
    )
    violations6 = check_branch_name_policy("feature/valid-branch_123", default_policy)
    print(f"Test 6 (valid default): Violations: {violations6}")
    violations7 = check_branch_name_policy("invalidBranch", default_policy)
    print(f"Test 7 (invalid default): Violations: {violations7}")
