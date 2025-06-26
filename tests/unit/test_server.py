import pytest
from fastapi.testclient import TestClient
from src.mcp_server.main import app  # Import the FastAPI app

# Create a TestClient instance for making requests to the app
client = TestClient(app)


def test_health_check():
    """
    Test the /health endpoint.
    It should return a 200 OK status and a JSON response with {"status": "ok"}.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_context_success():
    """
    Test successful context creation.
    """
    context_id = "test_context_01"
    response = client.post("/v1/contexts", json={"context_id": context_id})
    assert response.status_code == 201
    assert response.json() == {
        "message": "Context created successfully",
        "context_id": context_id,
    }

    # Verify it's in the store (optional, depends on how much you want to test internal state)
    # This requires access to CONTEXT_STORE or a way to inspect it.
    # For now, we trust the response. A get request could also verify.
    get_response = client.get(f"/v1/contexts/{context_id}")
    assert get_response.status_code == 200
    assert get_response.json() == {"context_id": context_id, "data": {}}


def test_create_context_conflict():
    """
    Test creating a context that already exists.
    """
    context_id = "test_context_conflict"
    # Create it once
    client.post("/v1/contexts", json={"context_id": context_id})
    # Try to create it again
    response = client.post("/v1/contexts", json={"context_id": context_id})
    assert response.status_code == 409
    assert response.json() == {"detail": "Context already exists"}


def test_get_context_not_found():
    """
    Test retrieving a context that does not exist.
    """
    response = client.get("/v1/contexts/non_existent_context")
    assert response.status_code == 404
    assert response.json() == {"detail": "Context not found"}


# Clean up contexts created during tests to ensure test isolation if needed
# For simple in-memory store, this might not be strictly necessary if TestClient re-initializes state,
# but good practice for more complex scenarios.
# However, TestClient(app) uses the same app instance.
# We can clear the store manually for now after certain tests or globally.


@pytest.fixture(autouse=True)
def clear_context_store_after_each_test():
    """
    Fixture to clear the CONTEXT_STORE after each test that might modify it.
    """
    # Setup:
    # Could backup CONTEXT_STORE here if needed

    yield  # This is where the test runs

    # Teardown: Clear the CONTEXT_STORE
    from src.mcp_server.main import CONTEXT_STORE

    CONTEXT_STORE.clear()
