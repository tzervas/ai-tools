from typing import List, Optional, Callable, AnyStr
from ..config import DisallowedPatternsPolicy, FileSizePolicy, DisallowedPatternItem
import os
import fnmatch # For wildcard path matching if needed for ignore_paths

# Type alias for a function that gets file content
GetFileContentCallable = Callable[[str], Optional[AnyStr]] # Takes path, returns content or None
GetFileSizeCallable = Callable[[str], Optional[int]] # Takes path, returns size or None


def check_content_disallowed_patterns(
    filepath: str,
    get_file_content: GetFileContentCallable, # Function to get content (e.g., from git_utils)
    policy: DisallowedPatternsPolicy
) -> List[str]:
    """
    Checks file content for disallowed patterns.

    Args:
        filepath: Path of the file being checked.
        get_file_content: A callable that takes filepath and returns its content as string or bytes.
                          If content is bytes, it will be decoded as UTF-8 (best effort).
                          Returns None if file is binary or cannot be read.
        policy: The DisallowedPatternsPolicy configuration object.

    Returns:
        A list of violation messages. Empty if no violations.
    """
    violations: List[str] = []
    if not policy.enabled or not policy.patterns:
        return violations

    file_content_any = get_file_content(filepath)

    if file_content_any is None:
        # Could be binary, or not found by the content getter.
        # For now, we skip checks on files we can't read as text.
        # A warning could be logged here if desired.
        # print(f"Warning: Content for '{filepath}' not available or binary. Skipping disallowed pattern check.", file=sys.stderr)
        return violations

    file_content_str: str
    if isinstance(file_content_any, bytes):
        try:
            file_content_str = file_content_any.decode('utf-8')
        except UnicodeDecodeError:
            # print(f"Warning: Could not decode '{filepath}' as UTF-8. Skipping disallowed pattern check.", file=sys.stderr)
            return violations # Skip if not valid UTF-8
    else: # Assume it's already a string
        file_content_str = file_content_any


    for item in policy.patterns:
        if not item.enabled:
            continue

        # item.pattern is already a compiled regex from Pydantic model
        # We search line by line to provide line numbers
        for line_num, line in enumerate(file_content_str.splitlines(), 1):
            match = item.pattern.search(line)
            if match:
                custom_message = item.message or f"Disallowed pattern '{item.pattern.pattern}' found."
                violations.append(
                    f"File '{filepath}', line {line_num}: {custom_message} (Matched: '{match.group(0)}')"
                )
    return violations


def check_file_size_policy(
    filepath: str,
    get_file_size: GetFileSizeCallable, # Function to get file size (e.g., from git_utils)
    policy: FileSizePolicy
) -> List[str]:
    """
    Checks if the file size exceeds the configured maximum.

    Args:
        filepath: Path of the file being checked.
        get_file_size: A callable that takes filepath and returns its size in bytes.
                       Returns None if file size cannot be determined.
        policy: The FileSizePolicy configuration object.

    Returns:
        A list of violation messages. Empty if no violations.
    """
    violations: List[str] = []
    if not policy.enabled:
        return violations

    # Check against ignore_extensions
    _, extension = os.path.splitext(filepath)
    if extension and extension.lower() in [ext.lower() for ext in policy.ignore_extensions]:
        return violations # Ignored by extension

    # Check against ignore_paths (simple wildcard matching)
    for ignore_pattern in policy.ignore_paths:
        if fnmatch.fnmatch(filepath, ignore_pattern):
            return violations # Ignored by path pattern

    file_size = get_file_size(filepath)

    if file_size is None:
        # Could not determine size. Maybe log a warning.
        # print(f"Warning: Could not determine size for '{filepath}'. Skipping file size check.", file=sys.stderr)
        return violations

    if file_size > policy.max_bytes:
        violations.append(
            f"File '{filepath}' (size: {file_size} bytes) exceeds maximum allowed size of {policy.max_bytes} bytes."
        )
    return violations


if __name__ == '__main__':
    # Example Usage
    from ..config import DisallowedPatternsPolicy, FileSizePolicy, DisallowedPatternItem
    import re

    # --- Test Disallowed Patterns ---
    print("--- Testing Disallowed Content Patterns ---")
    pattern_list = [
        DisallowedPatternItem(pattern="SECRET_KEY", message="Found hardcoded secret key.", enabled=True),
        DisallowedPatternItem(pattern="TODO: FIXME", enabled=True) # Default message
    ]
    disallowed_policy = DisallowedPatternsPolicy(patterns=pattern_list, enabled=True)

    mock_files_content = {
        "safe.py": "print('hello world')\n#This is fine",
        "secrets.txt": "API_TOKEN=123\nSECRET_KEY = 'abcdef'\nAnother line",
        "fixme.py": "# TODO: Fix this later\n# TODO: FIXME this critical bug",
        "binary_file.bin": b"\x00\x01\x02\x03SECRET_KEY", # Test binary content
        "utf8_error.txt": b"Hello \xff world" # Test bad utf-8
    }

    def mock_get_content(path: str) -> Optional[AnyStr]:
        return mock_files_content.get(path)

    for f_path in mock_files_content.keys():
        violations = check_content_disallowed_patterns(f_path, mock_get_content, disallowed_policy)
        if violations:
            print(f"Violations for '{f_path}':")
            for v in violations:
                print(f"  - {v}")
        else:
            print(f"No content violations for '{f_path}'.")

    # --- Test File Size ---
    print("\n--- Testing File Size Policy ---")
    size_policy = FileSizePolicy(max_bytes=100, ignore_extensions=[".log"], ignore_paths=["vendor/*", "*.tmp"], enabled=True)

    mock_files_sizes = {
        "small.txt": 50,
        "large.doc": 150,
        "ignored.log": 200,
        "temp.tmp": 300,
        "vendor/lib.js": 1000,
        "unknown_size_file.dat": None # Simulate file not found or size unavailable
    }

    def mock_get_size(path: str) -> Optional[int]:
        return mock_files_sizes.get(path)

    for f_path in mock_files_sizes.keys():
        violations = check_file_size_policy(f_path, mock_get_size, size_policy)
        if violations:
            print(f"Violations for '{f_path}':")
            for v in violations:
                print(f"  - {v}")
        else:
            print(f"No size violations for '{f_path}'.")

    # Test disabled policy
    disabled_size_policy = FileSizePolicy(max_bytes=10, enabled=False)
    violations_disabled = check_file_size_policy("large.doc", mock_get_size, disabled_size_policy)
    print(f"Violations for large.doc (policy disabled): {violations_disabled}") # Expected: []
