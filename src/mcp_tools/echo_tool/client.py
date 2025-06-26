import httpx
import argparse
import sys

DEFAULT_SERVER_URL = "http://localhost:8000"


def call_echo_tool(
    server_url: str,
    message: str,
    context_id: str = None,
    http_client: httpx.Client = None,
) -> dict:
    """
    Calls the echo tool endpoint on the MCP server.

    Args:
        server_url: The base URL of the MCP server.
        message: The message to echo.
        context_id: Optional context ID to pass to the tool.
        http_client: Optional httpx.Client instance to use for the request.
                     If None, a default client is used for a single request.

    Returns:
        The JSON response from the server.

    Raises:
        httpx.HTTPStatusError: If the server returns an error status code.
        httpx.RequestError: For other request issues (e.g., connection error).
    """
    endpoint = f"{server_url}/v1/tools/echo"
    payload = {"message": message}
    if context_id:
        payload["context_id"] = context_id

    client_to_use = http_client if http_client else httpx

    try:
        response = client_to_use.post(endpoint, json=payload)
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        return response.json()
    except httpx.HTTPStatusError as e:
        print(
            f"Error response {e.response.status_code} while requesting {e.request.url!r}.",
            file=sys.stderr,
        )
        print(f"Details: {e.response.text}", file=sys.stderr)
        raise
    except httpx.RequestError as e:
        print(f"An error occurred while requesting {e.request.url!r}.", file=sys.stderr)
        print(f"Details: {str(e)}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description="MCP Echo Tool Client")
    parser.add_argument(
        "message", type=str, help="The message to send to the echo tool."
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default=DEFAULT_SERVER_URL,
        help=f"The base URL of the MCP server (default: {DEFAULT_SERVER_URL}).",
    )
    parser.add_argument(
        "--context-id",
        type=str,
        help="Optional context ID to associate with the echo request.",
    )

    args = parser.parse_args()

    try:
        result = call_echo_tool(args.server_url, args.message, args.context_id)
        print("Server response:")
        print(result)
    except Exception:
        # Error messages are already printed by call_echo_tool
        print("Echo tool call failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
