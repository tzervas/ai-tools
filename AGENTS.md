# AGENTS.md - Instructions for AI Agents

This document provides guidelines for AI agents contributing to this project.

## General Guidelines

1.  **Project Goal:** This project aims to be a collection of MCP (Model Context Protocol) tools and servers useful for AI-assisted R&D, ML, AI, software, and IT engineering.
2.  **Modularity:** Design tools and server components to be modular and extensible.
3.  **Testing:** All new features and bug fixes must be accompanied by tests. Pytest is the preferred testing framework.
4.  **Dependencies:** Use `uv` for Python package management. All dependencies should be listed in `pyproject.toml` (or `requirements.txt` if `pyproject.toml` is not used for dependencies).
5.  **Docker & Devcontainers:** The project should be runnable and testable within a Docker container, and a devcontainer configuration should be provided for ease of development.
6.  **Commit Messages:** Follow conventional commit message formats.
7.  **Branching:**
    *   Use feature branches for new tools or significant enhancements (e.g., `feature/my-new-tool`).
    *   Use `fix/` for bug fixes (e.g., `fix/issue-with-parser`).
8.  **Code Style:** Follow PEP 8 guidelines for Python code. Use a formatter like Black or Ruff Formatter if possible.

## MCP Server

*   The core MCP server should be implemented in `src/mcp_server/main.py`.
*   It should adhere to the Anthropic Model Context Protocol specifications.
*   Prioritize clarity and maintainability in the server implementation.

## MCP Tools

*   Each distinct MCP tool should reside in its own subdirectory within `src/mcp_tools/`.
*   Tools should be designed to interact with the MCP server.

## Testing Specifics

*   Unit tests should be placed in the `tests/unit/` directory.
*   Integration tests (e.g., testing tool interaction with the server) should be placed in `tests/integration/`.
*   Ensure tests cover both success and failure cases.

## Environment Variables

*   If your component requires environment variables, document them clearly in the `README.md` and provide sensible defaults where possible.

By following these guidelines, we can ensure the project remains organized, maintainable, and easy for both humans and AI agents to contribute to.
