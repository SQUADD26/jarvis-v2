# Jarvis v2 — Proattivita e Multi-step Reasoning

## Data: 2026-02-14

## Obiettivo

Implementare 3 miglioramenti ad alto impatto per Jarvis v2:
1. Morning + Evening Briefing automatico
2. Email Monitoring con filtro smart
3. Multi-step Reasoning con self-correction

---

## 1. Morning + Evening Briefing

### Pattern: Task auto-schedulato (come `notion_proactive_check`)

**Nuovo task type:** `daily_briefing`

**Morning briefing (7:30):**
- Eventi del giorno da Google Calendar
- Email non lette importanti da Gmail
- Task in scadenza oggi/domani da Notion

**Evening briefing (20:00):**
- Riepilogo eventi della giornata
- Email ricevute oggi non ancora lette
- Preview agenda domani

**Flusso:**
1. Worker esegue task `daily_briefing`
2. Handler chiama direttamente Calendar API, Gmail API, Notion API (senza orchestrator)
3. LLM (Gemini 2.5 Flash) genera digest unificato in italiano
4. Notifica via TelegramNotifier
5. Auto-reschedule al prossimo slot (7:30 o 20:00)
6. Inizializzazione: il worker schedula il primo briefing al suo avvio

**File coinvolti:**
- `worker/executor.py` — nuovo handler `_handle_daily_briefing`
- `worker/main.py` — init del primo task al boot
- `config.py` — orari configurabili

---

## 2. Email Monitoring

### Pattern: Task auto-schedulato ogni 15 minuti

**Nuovo task type:** `email_monitor`

**Filtro smart (priorita):**
1. Mittente presente nel Knowledge Graph (persona nota) → urgenza ALTA
2. Keyword urgenti nel subject/body ("urgente", "scadenza", "deadline", "ASAP") → urgenza ALTA
3. Email con allegati da contatti noti → urgenza MEDIA
4. Tutto il resto → ignorato (non notificato)

**Anti-duplicati:** Redis key `email_monitor:last_check:{user_id}` con timestamp ultimo check

**Flusso:**
1. Worker esegue task `email_monitor`
2. Fetch email dal timestamp in Redis
3. Per ogni email: lookup mittente nel KG
4. Filtro urgenza
5. Se ci sono email urgenti: LLM genera riassunto, notifica Telegram
6. Aggiorna timestamp in Redis
7. Auto-reschedule tra 15 minuti

**File coinvolti:**
- `worker/executor.py` — nuovo handler `_handle_email_monitor`
- `worker/main.py` — init del primo task al boot
- `db/redis_client.py` — helper per timestamp (se necessario)

---

## 3. Multi-step Reasoning con Self-Correction

### Pattern: Loop LangGraph controllato

**Modifica al Planner:**
Il planner passa da output `{"agents": [...]}` a `{"steps": [{"agents": [...], "goal": "..."}]}`.
Backward-compatible: se un solo step, comportamento identico all'attuale.

**Nuovi nodi LangGraph:**
- `plan_steps` — wrapper che invoca il planner e prepara la sequenza
- `verify_result` — LLM verifica se il risultato di uno step soddisfa il goal
- `replan_step` — se verifica fallita, chiede al planner un approccio diverso

**Limiti di sicurezza:**
- Max 3 step per richiesta
- Max 2 retry per singolo step
- Timeout totale pipeline: 60 secondi

**Nuovo flusso orchestrator:**
```
analyze_intent → load_memory
  → [chitchat → direct response]
  → [action → plan_steps → step_loop]

step_loop:
  → enrich_query → check_freshness → execute_agents → verify_result
  → [OK + altri step → next step (con risultati precedenti come contesto)]
  → [OK + ultimo step → generate_response]
  → [FAIL + retry < 2 → replan_step → retry step]
  → [FAIL + retry >= 2 → generate_response (con errore)]

  → generate_response → extract_facts
```

**Passaggio contesto tra step:**
I risultati degli step precedenti vengono aggiunti allo state come `previous_step_results[]` e passati al prompt dell'agent successivo.

**File coinvolti:**
- `core/planner.py` — nuovo formato output con steps, nuovo PLANNER_PROMPT
- `core/orchestrator.py` — nuovi nodi, nuovo grafo con loop
- `core/state.py` — nuovi campi nello state (steps, current_step, step_results, retry_count)

---

## Ordine di implementazione

1. **Briefing** — piu semplice, usa pattern esistente, valore alto
2. **Email Monitor** — simile al briefing, aggiunge filtro smart
3. **Multi-step** — piu complesso, tocca il cuore dell'architettura
