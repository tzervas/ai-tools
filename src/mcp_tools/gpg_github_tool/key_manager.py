import argparse
import gnupg
import httpx
import os
import sys
import tempfile

DEFAULT_GPG_HOME_RELATIVE = ".gnupg_mcp_tool" # Relative to user's home directory
DEFAULT_KEY_EXPIRY = "7d" # Default to 7 days for short-lived keys
GITHUB_API_URL = "https://api.github.com"

def generate_gpg_key(gpg_home: str, name: str, email: str, expiry: str, passphrase: str = None) -> tuple[str, str, str]:
    """
    Generates a new GPG key pair.

    Args:
        gpg_home: Path to the GPG home directory to use.
        name: Real name for the GPG key.
        email: Email for the GPG key.
        expiry: Expiration date for the GPG key (e.g., 0 for no expiry, 1y, 7d).
        passphrase: Optional passphrase for the key. If None, key will not be passphrase protected.

    Returns:
        A tuple containing (key_id, public_key_armored, private_key_armored).
        Returns (None, None, None) on failure.
    """
    gpg = gnupg.GPG(gnupghome=gpg_home)

    # GPG input parameters
    # Note: python-gnupg might abstract some of this, but direct input is often clearer for batch mode.
    # For python-gnupg, we can use gpg.gen_key_input and then gpg.gen_key()

    key_input_params = gpg.gen_key_input(
        name_real=name,
        name_email=email,
        expire_date=expiry,
        key_type="RSA",      # Default is RSA, can also be DSA, ELG, ECDSA
        key_length=4096,     # Standard strong key length
        subkey_type="RSA",   # For signing subkey
        subkey_length=4096,
        passphrase=passphrase # If None, key is not protected by passphrase
    )

    print("Generating GPG key... This may take a moment.", file=sys.stderr)
    key_data = gpg.gen_key(key_input_params)

    if not key_data or not key_data.fingerprint:
        print("Error: GPG key generation failed. No fingerprint returned.", file=sys.stderr)
        print(f"GPG status: {key_data.status if key_data else 'Unknown'}", file=sys.stderr)
        # Attempt to get more details if available from stderr of gpg process
        # This is tricky with python-gnupg as it captures stderr.
        # If you were using subprocess directly: print(result.stderr.decode())
        return None, None, None

    fingerprint = key_data.fingerprint
    key_id = fingerprint[-16:] # Typically, the last 16 chars of fingerprint are the short Key ID

    print(f"GPG Key generated successfully. Fingerprint: {fingerprint}, Key ID: {key_id}", file=sys.stderr)

    # Export the public key
    public_key_armored = gpg.export_keys(fingerprint, armor=True)
    if not public_key_armored:
        print(f"Error: Failed to export public key for fingerprint {fingerprint}.", file=sys.stderr)
        return None, None, None

    # Export the private key
    # IMPORTANT: Handle with extreme care.
    private_key_armored = gpg.export_keys(fingerprint, secret=True, armor=True)
    if not private_key_armored:
        print(f"Error: Failed to export private key for fingerprint {fingerprint}.", file=sys.stderr)
        # This could happen if the key is on a hardware token, but not for generated keys.
        return None, None, None

    return key_id, public_key_armored, private_key_armored

def add_gpg_key_to_github(public_key_armored: str, github_token: str) -> bool:
    """
    Adds the GPG public key to the authenticated user's GitHub account.

    Args:
        public_key_armored: The GPG public key in ASCII-armored format.
        github_token: GitHub Personal Access Token with 'write:gpg_key' scope.

    Returns:
        True if successful, False otherwise.
    """
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {
        "armored_public_key": public_key_armored
    }
    url = f"{GITHUB_API_URL}/user/gpg_keys"

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for 4XX/5XX responses
        print("GPG key successfully added to GitHub account.", file=sys.stderr)
        # print(f"GitHub API response: {response.json()}", file=sys.stderr) # For debugging
        return True
    except httpx.HTTPStatusError as e:
        print(f"Error adding GPG key to GitHub: {e.response.status_code} - {e.request.url!r}.", file=sys.stderr)
        try:
            error_details = e.response.json()
            print(f"GitHub Error: {error_details.get('message', 'No message')}", file=sys.stderr)
            if 'errors' in error_details:
                for err in error_details['errors']:
                    print(f"  - {err.get('resource', '')} {err.get('field', '')}: {err.get('code', '')}", file=sys.stderr)
        except Exception:
            print(f"Raw response: {e.response.text}", file=sys.stderr)
        return False
    except httpx.RequestError as e:
        print(f"An error occurred while requesting {e.request.url!r}: {str(e)}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate a GPG key and add it to GitHub.")
    parser.add_argument("--name", required=True, help="Real name for the GPG key (e.g., 'Tyler Zervas Agent').")
    parser.add_argument("--email", required=True, help="Email for the GPG key (e.g., 'tz-dev-agent@vectorwieght.com').")
    parser.add_argument("--expiry", default=DEFAULT_KEY_EXPIRY,
                        help=f"Expiration for the GPG key (e.g., 0, 1y, 30d). Default: {DEFAULT_KEY_EXPIRY}.")
    parser.add_argument("--passphrase", default=None, help="Optional passphrase for the GPG key. If not provided, key will have no passphrase (less secure).")
    parser.add_argument("--github-token", help="GitHub Personal Access Token with 'write:gpg_key' scope. Can also be set via GITHUB_TOKEN env var.")
    parser.add_argument("--gpg-home", default=None,
                        help=f"Custom GPG home directory. Default: ~/{DEFAULT_GPG_HOME_RELATIVE} (a new temporary one is used if this is not set).")
    parser.add_argument("--output-private-key-file", default=None,
                        help="If specified, saves the armored private key to this file. Otherwise, prints to stdout.")

    args = parser.parse_args()

    github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Error: GitHub token not provided. Set --github-token or GITHUB_TOKEN environment variable.", file=sys.stderr)
        sys.exit(1)

    # Determine GPG home. Using a temporary GPG home is safer for ephemeral keys.
    # If a specific gpg_home is not provided, create a temporary one.
    if args.gpg_home:
        gpg_home_path = os.path.expanduser(args.gpg_home)
        if not os.path.exists(gpg_home_path):
            os.makedirs(gpg_home_path, mode=0o700, exist_ok=True)
            print(f"Using specified GPG home: {gpg_home_path}", file=sys.stderr)
        temp_gpg_home_dir = None # Not using a temp dir if specified
    else:
        # Create a temporary directory for GPG home for this run
        temp_gpg_home_dir = tempfile.TemporaryDirectory(prefix="mcp_gpg_")
        gpg_home_path = temp_gpg_home_dir.name
        print(f"Using temporary GPG home: {gpg_home_path}", file=sys.stderr)


    key_id, public_key, private_key = generate_gpg_key(
        gpg_home=gpg_home_path,
        name=args.name,
        email=args.email,
        expiry=args.expiry,
        passphrase=args.passphrase
    )

    if not key_id:
        print("Failed to generate GPG key.", file=sys.stderr)
        if temp_gpg_home_dir:
            temp_gpg_home_dir.cleanup()
        sys.exit(1)

    print(f"\n--- Generated GPG Key Details ---", file=sys.stderr)
    print(f"Key ID: {key_id}", file=sys.stderr)
    # print(f"Public Key (Armored):\n{public_key}", file=sys.stderr) # Can be very verbose

    if not add_gpg_key_to_github(public_key, github_token):
        print("Failed to add GPG key to GitHub.", file=sys.stderr)
        # Optionally, decide if you want to delete the generated key from local GPG home if GitHub add fails
        # gpg = gnupg.GPG(gnupghome=gpg_home_path)
        # gpg.delete_keys(key_id, secret=True) # Be careful with this
        if temp_gpg_home_dir:
            temp_gpg_home_dir.cleanup()
        sys.exit(1)

    print("\n--- Private Key (Armored) ---", file=sys.stderr)
    print("SECURITY WARNING: The following is your GPG private key. Handle it with extreme care.", file=sys.stderr)
    print("It is recommended to import it into your primary GPG keyring or agent's environment immediately", file=sys.stderr)
    print("and ensure this output is not stored insecurely.\n", file=sys.stderr)

    if args.output_private_key_file:
        try:
            with open(args.output_private_key_file, 'w') as f:
                f.write(private_key)
            os.chmod(args.output_private_key_file, 0o600) # Set restrictive permissions
            print(f"Private key saved to: {args.output_private_key_file}", file=sys.stderr)
            print(f"Ensure you protect this file. Consider encrypting it or importing and then deleting it.", file=sys.stderr)
        except IOError as e:
            print(f"Error writing private key to file {args.output_private_key_file}: {e}", file=sys.stderr)
            print("Printing private key to STDOUT instead:", file=sys.stderr)
            print(private_key) # Fallback to stdout
    else:
        print(private_key) # Print to stdout

    print(f"\n--- Actions to take manually ---", file=sys.stderr)
    print(f"1. If you didn't save the private key to a file, copy the private key block above.", file=sys.stderr)
    print(f"2. Import the private key into your desired GPG environment:", file=sys.stderr)
    print(f"   gpg --import /path/to/private_key.asc  (or pipe it: ... | gpg --import)", file=sys.stderr)
    print(f"3. Configure git to use this key ID for signing commits (globally or per repo):", file=sys.stderr)
    print(f"   git config --global user.signingkey {key_id}", file=sys.stderr)
    print(f"   git config --global commit.gpgsign true", file=sys.stderr)
    print(f"4. (Optional) Trust the key if needed: gpg --edit-key {key_id} (then type 'trust', '5', 'y', 'quit')", file=sys.stderr)

    if temp_gpg_home_dir:
        print(f"Temporary GPG home {gpg_home_path} will be cleaned up.", file=sys.stderr)
        temp_gpg_home_dir.cleanup()

if __name__ == "__main__":
    main()
