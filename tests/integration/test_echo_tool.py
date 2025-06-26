import pytest
import httpx  # <--- Import httpx
from fastapi.testclient import TestClient
from src.mcp_server.main import (
    app,
    CONTEXT_STORE,
)  # Import the FastAPI app and context store
from src.mcp_tools.echo_tool.client import call_echo_tool  # Import the client function

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_context_store_after_each_test():
    """
    Fixture to clear the CONTEXT_STORE after each test.
    """
    CONTEXT_STORE.clear()
    yield
    CONTEXT_STORE.clear()


def test_echo_endpoint_direct():
    """
    Test the /v1/tools/echo endpoint directly using TestClient.
    """
    test_message = "Hello, مباشر!"  # "Hello, direct!" in Arabic
    payload = {"message": test_message}
    response = client.post("/v1/tools/echo", json=payload)
    assert response.status_code == 200
    assert response.json() == {"echoed_message": test_message, "context_id": None}


def test_echo_endpoint_direct_with_context():
    """
    Test the /v1/tools/echo endpoint directly with a context_id.
    """
    test_message = "Hello, context!"
    context_id = "test-context-123"
    # Optionally create the context first if the tool logic requires it
    # client.post("/v1/contexts", json={"context_id": context_id})

    payload = {"message": test_message, "context_id": context_id}
    response = client.post("/v1/tools/echo", json=payload)
    assert response.status_code == 200
    assert response.json() == {"echoed_message": test_message, "context_id": context_id}
    # If the echo tool were to modify the context, we could assert that here:
    # assert CONTEXT_STORE[context_id]['echo_history'] == [test_message]


def test_echo_tool_client_function(monkeypatch):
    """
    Test the call_echo_tool client function against the TestClient.
    This is an integration test for the client utility.
    """
    test_message = "Hello, client function!"

    # The client function expects a full URL. TestClient doesn't run a live server on a port by default.
    # We can use the TestClient's base_url or mock httpx.post to direct to the TestClient.
    # For a true integration test of the client against the app, it's simpler to use TestClient as the server.

    # Method 1: Use TestClient as if it were a server (requires client to be adaptable or server to be live)
    # For this, call_echo_tool needs to be able to point to the TestClient.
    # We can use TestClient's `base_url` which is "http://testserver" by default.

    # Pass the FastAPI TestClient instance directly
    echo_response = call_echo_tool(
        server_url=client.base_url,  # Used by call_echo_tool to construct endpoint
        message=test_message,
        http_client=client,  # Pass the TestClient instance
    )
    assert echo_response == {"echoed_message": test_message, "context_id": None}


def test_echo_tool_client_function_with_context(monkeypatch):
    """
    Test the call_echo_tool client function with context_id against the TestClient.
    """
    test_message = "Client to context!"
    context_id = "client-context-456"

    # client.post(f"{client.base_url}/v1/contexts", json={"context_id": context_id}) # Create context if necessary for tool

    echo_response = call_echo_tool(
        server_url=client.base_url,
        message=test_message,
        context_id=context_id,
        http_client=client,  # Pass the TestClient instance
    )
    assert echo_response == {"echoed_message": test_message, "context_id": context_id}


# We could also add a test for the command-line interface of client.py,
# but that would involve subprocess calls and capturing stdout, which is more involved.
# For now, testing the core `call_echo_tool` function is a good step.
