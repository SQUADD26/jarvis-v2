# Repository Guidelines

## Project Structure & Module Organization
Core code lives under `src/jarvis/`. Keep domain logic in:
- `core/` (orchestration, memory, planning, knowledge graph)
- `agents/` (feature agents such as calendar, email, web, RAG, tasks)
- `integrations/` (external APIs and providers)
- `db/`, `interfaces/`, `worker/`, `api/`, `voice/`, `utils/`

Tests are in `tests/` at repository root (for example `tests/test_router.py`). Operational scripts and SQL migrations are in `scripts/`. Runtime config is loaded from `.env` via `src/jarvis/config.py`.

## Build, Test, and Development Commands
Run these from repository root (`/home/ubuntu/ai-agents`):
- `uv sync`: install runtime and dev dependencies.
- `uv run python -m jarvis.main`: start Telegram bot flow.
- `uv run python -m jarvis.api`: run FastAPI server on port `8000`.
- `uv run python -m jarvis.worker`: start background task worker.
- `uv run pytest`: run full test suite.
- `uv run pytest tests/test_router.py -v`: run one test module.
- `uv run ruff check src/ tests/`: lint.
- `uv run ruff format src/ tests/`: format code.

## Coding Style & Naming Conventions
Use Python 3.12, 4-space indentation, and type hints for public interfaces. Ruff is the style authority (`line-length = 100` in `pyproject.toml`). Use `snake_case` for modules/functions/variables, `PascalCase` for classes, and descriptive async names for coroutines (`async def` + verb-first function names).

## Testing Guidelines
Use `pytest` with `pytest-asyncio` (`asyncio_mode = auto`). Name files `test_*.py` and tests `test_<behavior>()`. For new features, cover both happy path and failure handling, especially for agent orchestration and integration boundaries. `pytest-cov` is available; no fixed threshold is configured, so maintain or improve coverage on touched modules.

## Commit & Pull Request Guidelines
This workspace snapshot does not include `.git` history, so follow Conventional Commit style by default (example: `feat(core): add planner fallback`). Keep commits small and scoped. PRs should include:
- clear problem/solution summary,
- linked issue/task,
- test evidence (`uv run pytest` / lint output),
- API or behavior notes (and screenshots/log snippets when UI or bot output changes).

## Security & Configuration Tips
Never commit secrets from `.env` (API keys, tokens, service keys). Use `.env` locally and rotate credentials if exposed. Validate external API calls in `integrations/` with timeouts and explicit error handling.
