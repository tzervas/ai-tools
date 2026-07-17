# CLAUDE.md — ai-tools

Guidance for Claude (and other coding assistants) working in this repository.

## Product

**ai-tools** is a Python package of MCP-related utilities and CLI tools for AI-assisted
engineering: PR policy checks, IaC drift/docs/compliance, config optimization, and a small
FastAPI MCP server scaffold.

Package name: `ai-tools` (not `app`). Layout lives under `src/mcp_server/` and `src/mcp_tools/`.

## Quick commands

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
# MCP server (dev)
uv run uvicorn src.mcp_server.main:app --host 0.0.0.0 --port 8000
```

## Where to put work

| Change | Location |
|--------|----------|
| New CLI tool | `src/mcp_tools/<tool_name>/` + tests under `tests/unit/` / `tests/integration/` |
| Shared git helpers | `src/mcp_tools/common/` |
| MCP HTTP server | `src/mcp_server/main.py` |
| Agent/human docs | `AGENTS.md`, this file, tool catalog in `README.md` |

## Conventions

- Conventional commits; feature branches `feature/…`, fixes `fix/…`.
- Prefer **ruff** for lint/format (`line-length = 100` in `pyproject.toml`).
- Pytest for all new behavior; keep tools modular (one directory per tool).
- Do not invent production claims — tools are 0.x utilities; document limitations honestly.
- Never touch **mycelium**.

## Tool catalog (summary)

See [README.md § Tool catalog](README.md#tool-catalog) for the full table. Tools include:
`echo_tool`, `pr_reviewer`, `iac_drift_detector`, `config_optimizer`, `iac_doc_generator`,
`git_compliance_analyzer`, `gpg_github_tool`.
