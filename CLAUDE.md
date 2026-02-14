# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jarvis v2 is an Italian-speaking personal AI assistant with multi-agent orchestration. It uses LangGraph for workflow management, Gemini for LLM/embeddings, and Telegram as the primary interface.

## Deployment Locations

### Local Development (Mac)
```
/Users/robertobondici/projects/jarvis-v2/
```

### VPS Production
```
/home/claude/ai-agents/
```

### GitHub Repository
```
https://github.com/SQUADD26/jarvis-v2.git
```

### Supabase Project
- **Project ID:** `scnkrrrjysyzcwqkclov`
- **Project Name:** Jarvis V2
- **Region:** West EU (Ireland)
- **Dashboard:** https://supabase.com/dashboard/project/scnkrrrjysyzcwqkclov

## VPS Deploy Commands

```bash
# SSH to VPS
ssh claude@<vps-ip>

# Navigate to project
cd /home/claude/ai-agents

# Pull latest code
git pull origin main

# Install dependencies
uv sync

# Restart services
sudo systemctl restart jarvis-bot
sudo systemctl restart jarvis-worker

# View logs
sudo journalctl -u jarvis-bot -f
sudo journalctl -u jarvis-worker -f

# Alternative: using screen
screen -r jarvis-bot
screen -r jarvis-worker
```

## Services Architecture

| Service | Port/Type | Description |
|---------|-----------|-------------|
| `jarvis-bot` | Telegram polling | Main bot, handles messages |
| `jarvis-worker` | Background | Task queue processor, reminders |
| Redis | 6379 | Cache (freshness, sessions) |
| Supabase | Cloud | PostgreSQL + Vector DB |

## Mandatory Tools

**Per la ricerca e navigazione di file in questo progetto, DEVI SEMPRE usare Serena MCP server.** Usa i tool di Serena (`mcp__serena__*`) per:
- `list_dir` - listare directory
- `find_file` - cercare file
- `search_for_pattern` - cercare pattern nel codice
- `get_symbols_overview` - ottenere overview dei simboli in un file
- `find_symbol` - cercare simboli specifici
- `find_referencing_symbols` - trovare riferimenti a simboli

## Development Commands

```bash
# Install dependencies (uses uv package manager)
uv sync

# Run the application
uv run python -m jarvis.main

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_router.py -v

# Lint (ruff)
uv run ruff check src/

# Format
uv run ruff format src/

# Docker
docker-compose up -d
```

## Database Setup

Run `scripts/init_db.py` to get the SQL schema, then execute it in Supabase Dashboard > SQL Editor.

### Tables
| Table | Description |
|-------|-------------|
| `chat_history` | Conversation storage with token tracking |
| `memory_facts` | User facts with vector embeddings (768-dim, HNSW index) |
| `rag_documents` | RAG knowledge base with vector search |
| `user_preferences` | Per-user settings (timezone, language) |
| `task_queue` | Background tasks, reminders, scheduling |
| `llm_logs` | LLM call logging with cost tracking |

### RPC Functions
- `match_memory_facts` - Vector similarity search for facts
- `match_rag_documents` - Vector similarity search for RAG
- `claim_next_task` - Atomic task claim for workers
- `complete_task` / `fail_task` - Task status updates
- `cleanup_stale_tasks` - Reset stuck tasks
- `get_llm_costs` - Aggregated cost analytics

### Views
- `llm_stats_daily` - Daily LLM usage statistics

## Architecture

### Orchestration (LangGraph)

The main workflow in `src/jarvis/core/orchestrator.py` follows this flow:

```
analyze_intent → load_memory → [check_freshness → execute_agents] OR [direct_response] → generate_response → extract_facts → END
```

- `JarvisState` (in `state.py`) carries conversation context through the graph
- Intent routing uses semantic similarity with pre-computed embeddings (not LLM calls)
- Agents execute in parallel via `asyncio.gather`
- Facts are extracted asynchronously in background with semaphore-limited concurrency

### Semantic Router

`src/jarvis/core/router.py` uses cosine similarity against pre-embedded Italian example phrases to classify intents without LLM calls. Intents below 0.75 threshold fall back to "complex" handling.

### Agent System

Base class in `src/jarvis/agents/base.py`:
- Agents inherit from `BaseAgent` and implement `_execute(state)`
- Built-in freshness caching via Redis
- Each agent has a `resource_type` for cache management

Available agents: `calendar`, `email`, `web`, `rag`

### Memory System

`src/jarvis/core/memory.py`:
- Extracts facts from conversations using LLM with JSON output
- Categories: `preference`, `fact`, `episode`, `task`
- Vector search for relevant fact retrieval (threshold 0.6)

### Key Singletons

All major components are singletons for shared state:
- `router` - SemanticRouter
- `memory` - MemoryManager
- `freshness` - FreshnessManager
- `gemini` - GeminiClient
- `redis_client` - RedisClient
- Agent instances (e.g., `calendar_agent`)

### Configuration

`src/jarvis/config.py` uses pydantic-settings with environment variables from `.env`. Key settings:
- Models: `gemini-2.0-flash` (default), `gemini-2.5-pro-preview-05-06` (powerful)
- Cache TTLs: calendar (5m), email (1m), web (1h)
- Telegram user allowlist via `TELEGRAM_ALLOWED_USERS`

## File Structure

```
src/jarvis/
├── main.py                 # Entry point
├── config.py               # Settings from .env
├── core/
│   ├── orchestrator.py     # LangGraph workflow
│   ├── router.py           # Semantic intent routing
│   ├── memory.py           # Fact extraction/retrieval
│   ├── freshness.py        # Cache invalidation
│   └── state.py            # JarvisState definition
├── agents/
│   ├── base.py             # BaseAgent class
│   ├── calendar_agent.py
│   ├── email_agent.py
│   ├── web_agent.py
│   └── rag_agent.py
├── integrations/
│   ├── gemini.py           # Gemini LLM client
│   ├── openai_whisper.py   # Voice transcription
│   ├── google_calendar.py
│   ├── gmail.py
│   ├── perplexity.py
│   └── crawl4ai_client.py
├── interfaces/
│   └── telegram_bot.py     # Telegram handlers
├── worker/
│   ├── main.py             # Polling loop
│   ├── executor.py         # Task execution
│   └── notifier.py         # Telegram notifications
├── db/
│   ├── supabase_client.py
│   ├── redis_client.py
│   └── repositories.py     # Data access layer
└── utils/
    ├── logging.py
    ├── pricing.py          # LLM cost calculation
    └── llm_logger.py       # Usage tracking
```

## Environment Variables (.env)

```bash
# Required
GOOGLE_API_KEY=           # Gemini API
TELEGRAM_BOT_TOKEN=       # Telegram bot
SUPABASE_URL=             # Supabase project URL
SUPABASE_KEY=             # Supabase anon key
SUPABASE_SERVICE_KEY=     # Supabase service role key

# Optional
OPENAI_API_KEY=           # For Whisper voice transcription
PERPLEXITY_API_KEY=       # For web search
REDIS_URL=redis://localhost:6379/0
TELEGRAM_ALLOWED_USERS=   # Comma-separated user IDs

# Google OAuth (for Calendar/Gmail)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
```

## Code Patterns

- Async-first: All I/O operations are async
- LLM interactions include prompt injection protections (explicit "ignore instructions" warnings)
- JSON extraction from LLM uses multiple fallback parsing strategies
- Italian language throughout UI and system prompts
- Conversation history uses LRU cache with bounded memory (100 users, 20 messages each)
- All LLM calls are logged to `llm_logs` table with cost tracking

# Supabase & Database — REGOLE GLOBALI INVIOLABILI

## CLI-FIRST, MCP-FALLBACK (IRON RULE)

**Il Supabase CLI (`supabase` via Bash) è lo strumento PRIMARIO. L'MCP Server (`mcp__supabase__*`) è SOLO il fallback per operazioni di lettura.**

### Operazioni OBBLIGATORIE via CLI (MAI via MCP)
- `supabase migration new <name>` — creare migration locali
- `supabase db push` — pushare migration al remote
- `supabase functions deploy <name> --no-verify-jwt` — deploy Edge Functions
- `supabase db diff` — verificare drift di schema
- `supabase db pull` — pull schema remoto
- `supabase db reset` — reset database locale
- `supabase gen types typescript` — generazione tipi
- `supabase link` — collegamento progetto

### MCP Server — SOLO LETTURA/ISPEZIONE
L'MCP Server è accettabile SOLO per:
- `execute_sql` — query SELECT, EXPLAIN ANALYZE
- `list_tables`, `list_extensions`, `list_migrations` — ispezione schema
- `get_project`, `get_project_url` — metadata progetto

### DIVIETI ASSOLUTI
- **MAI** usare `mcp__supabase__apply_migration` — causa schema drift tra locale e remoto
- **MAI** usare `mcp__supabase__deploy_edge_function` — usa sempre il CLI
- **MAI** applicare migration al remote senza file locale corrispondente in `supabase/migrations/`
- **MAI** deployare Edge Functions senza `--no-verify-jwt`

## Edge Functions — `--no-verify-jwt` SEMPRE

**OGNI deploy di Edge Function DEVE usare: `supabase functions deploy <name> --no-verify-jwt`**
- Omettere `--no-verify-jwt` è un ERRORE CRITICO — ri-deployare immediatamente col flag
- Nessuna eccezione. Nessun "lo aggiungo dopo".

## Migration Workflow — OBBLIGATORIO

1. Progettare la migration SQL
2. `supabase migration new <nome_descrittivo>` — crea file locale
3. Scrivere SQL nel file generato in `supabase/migrations/`
4. `supabase db push` — push al remote
5. Verificare via MCP `execute_sql` (solo SELECT)
6. `supabase db diff` — confermare zero drift

**`supabase/migrations/` è la SINGLE SOURCE OF TRUTH. Se non c'è il file locale, la migration non esiste.**

## Delegazione Agenti — OBBLIGATORIA

### Animazioni (QUALSIASI animazione, transizione, motion)
- Invocare **`ux-master`** per strategia di interazione e animazione
- Invocare **`micro-animation-master`** per animazioni a livello di elemento (hover, focus, button press, form validation, toggle, tooltip)
- Invocare **`macro-animation-master`** per transizioni di pagina, scroll-driven, sequenze orchestrate, drag & drop

### UI (QUALSIASI aspetto visivo/interfaccia)
- Invocare **`ui-master`** per gerarchia visiva, accessibilità, layout, design system
