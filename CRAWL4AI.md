# Crawl4AI – Guida rapida utilizzo

## Endpoint del servizio

Il servizio Crawl4AI è esposto sulla tua VPS all'indirizzo:

- Base URL: `http://srv938822.hstgr.cloud:11235`
- Documentazione interattiva (Swagger UI): `http://srv938822.hstgr.cloud:11235/docs`
- Health check: `http://srv938822.hstgr.cloud:11235/health`

> Nota: il servizio è esposto in HTTP su porta 11235, non dietro Nginx.

---

## Verifica funzionamento

Per verificare che Crawl4AI sia up:

```bash
curl http://srv938822.hstgr.cloud:11235/health
```

Risposta attesa (simile):

```json
{"status":"ok","timestamp":1769150275.9093733,"version":"0.5.1-d1"}
```

---

## Endpoint principali

- `POST /crawl` – crawling sincrono (risposta immediata con i risultati)
- `POST /crawl/stream` – crawling con streaming dei risultati
- `POST /crawl/async` – avvia un task asincrono
- `GET  /task/{task_id}` – stato e risultato di un task asincrono

---

## Esempi di utilizzo con curl

### 1. Crawl sincrono di una pagina

```bash
curl -X POST "http://srv938822.hstgr.cloud:11235/crawl" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com"],
    "crawler_config": {
      "max_depth": 1,
      "max_pages": 5
    },
    "extract_config": {
      "mode": "markdown"
    }
  }'
```

### 2. Crawl asincrono (task)

```bash
curl -X POST "http://srv938822.hstgr.cloud:11235/crawl/async" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/blog"],
    "crawler_config": {
      "max_depth": 2,
      "max_pages": 20
    },
    "extract_config": {
      "mode": "markdown"
    }
  }'
```

Polling stato:

```bash
curl "http://srv938822.hstgr.cloud:11235/task/{task_id}"
```

---

## Sicurezza

Attualmente il servizio è esposto senza autenticazione.
Opzioni future: limitare accesso per IP, token di autenticazione, reverse proxy HTTPS.
