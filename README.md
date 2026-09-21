<div align="center">

# GJALLARHORN

### **Asgard Cybersecurity Suite — Hub di Alerting Centralizzato**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![CI Pipeline](https://github.com/Fioru12/Gjallarhorn/actions/workflows/pytest.yml/badge.svg?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)

</div>

> **Perché ho costruito Gjallarhorn?**
> Nella mitologia norrena Gjallarhorn è il corno che Heimdall suona per dare l'allarme all'arrivo del Ragnarok — un solo segnale che tutti sentono, invece di ogni guardiano che grida a modo suo. Nella suite Asgard stava succedendo l'esatto contrario: **Heimdall** ha una `TelegramNotifier` scritta in casa (`core/notifier.py`), e ogni nuovo modulo (Sleipnir, Bifrost, ...) che aveva bisogno di avvisare qualcuno finiva per reimplementare la stessa manciata di righe di `urllib` verso l'API Telegram, spesso con piccoli bug diversi (ad esempio Heimdall passava `parse_mode: "TEXT"`, che Telegram non riconosce come valore valido). Gjallarhorn esiste per eliminare questa duplicazione: **un solo hub HTTP** che centralizza l'invio (Telegram, webhook Slack/Discord-compatible, email SMTP), la deduplica degli allarmi ripetuti e l'audit trail, con un client Python di poche righe che qualsiasi modulo Asgard può importare al posto della propria logica di notifica.

---

## Come Funziona

```
   Heimdall / Sleipnir / Bifrost / ...
              |
              |  gjallarhorn_client.notify(...)
              v
   POST /api/v1/notify  (X-API-Key)
              |
              v
      NotificationHub
        |         |
        |         +--> Dedup/Throttling (finestra configurabile, default 5 min)
        |                    |
        |                    +--> entro la finestra: SOPPRESSA (solo audit trail, contatore++)
        |                    +--> fuori dalla finestra: procede all'invio
        v
   Canali (skip silenzioso se non configurati)
        +--> TelegramChannel (Bot API)
        +--> WebhookChannel  (Slack/Discord JSON generico)
        +--> TeamsChannel    (Microsoft Teams MessageCard)
        +--> JiraChannel     (apre un ticket su Jira Cloud)
        +--> ServiceNowChannel (apre un incident su ServiceNow)
        +--> SMTPChannel     (email)
              |
              v
   SQLite: notification_log (audit trail, GET /api/v1/history)
```

---

## Architettura & Design Pragmatico

- **Un'unica interfaccia per i canali** (`core/channels/base.py`): ogni canale implementa `is_configured()` e `send(title, message, severity) -> bool`. Un canale non configurato viene semplicemente saltato con un log — mai un crash, mai un'eccezione che si propaga.
- **Dedup/throttling persistente**: la finestra di deduplica (default 300s, configurabile) è calcolata sull'ultimo invio effettivo salvato su SQLite, quindi sopravvive ai riavvii dell'hub. Le occorrenze soppresse non spariscono: vengono comunque registrate nell'audit trail con un contatore `suppressed_count` incrementale.
- **Autenticazione uniforme con il resto della suite**: stesso pattern di Heimdall — header `X-API-Key`, chiave letta da `GJALLARHORN_API_KEY`, generata casualmente e stampata a schermo se assente.
- **Nessuna funzionalità aspirazionale**: tutto ciò che è descritto in questo README corrisponde a codice presente in `core/`, `api/` e `tests/` — niente canali "in roadmap", niente endpoint non implementati.

---

## Chi lo usa già nella suite

Gjallarhorn non è più solo teorico: è integrato, in modo opzionale e non-breaking, in due moduli della suite Asgard, ciascuno con la propria copia di `gjallarhorn_client.py`:

- **Heimdall** (`Heimdall/core/notifier.py`, funzione `send_alert_via_gjallarhorn`): se `GJALLARHORN_HUB_URL` è impostata, gli alert HIDS vengono inoltrati all'hub (`source="Heimdall"`) invece che al `TelegramNotifier` diretto, che resta il fallback automatico se l'hub non è configurato o non è raggiungibile.
- **Sleipnir** (`Sleipnir/core/engine.py`, funzione `notify_gjallarhorn_outcome`): se `GJALLARHORN_HUB_URL` è impostata, ogni playbook che raggiunge `CONTAINED` o `FAILED` notifica l'hub (`source="Sleipnir"`); altrimenti nessuna chiamata di rete viene effettuata.

In entrambi i casi l'integrazione è puramente additiva: senza `GJALLARHORN_HUB_URL` impostata nell'ambiente, i due moduli si comportano esattamente come prima dell'integrazione.

## Come lo userebbe un altro modulo Asgard

Invece di reimplementare `TelegramNotifier` come fa oggi Heimdall, un modulo Asgard copia `gjallarhorn_client.py` (un file singolo, senza dipendenze dal resto di Gjallarhorn) e lo importa così:

```python
from gjallarhorn_client import notify

ok = notify(
    hub_url="http://localhost:8090",
    api_key=os.environ["GJALLARHORN_API_KEY"],
    source="heimdall",
    severity="high",
    title="SSH Brute-Force Attack Detected",
    message="203.0.113.50 ha tentato 12 login falliti come 'root' in 60s.",
)
if not ok:
    # notify() non solleva mai eccezioni: logga un warning e ritorna False.
    # Il chiamante decide se ritentare, loggare in locale, ecc.
    ...
```

---

## Canali Supportati

Ogni canale è configurabile via variabili d'ambiente (vedi `.env.example`) o via `config.yaml` (vedi `config.yaml.example`). Le variabili d'ambiente hanno sempre la precedenza su `config.yaml`.

| Canale     | Config richiesta                                              | Variabili d'ambiente                                              |
|------------|-----------------------------------------------------------------|---------------------------------------------------------------------|
| Telegram   | `bot_token`, `chat_id`                                          | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`                            |
| Webhook    | `url` (Slack/Discord incoming webhook)                          | `WEBHOOK_URL`                                                       |
| Teams      | `url` (Microsoft Teams Incoming Webhook)                        | `TEAMS_WEBHOOK_URL`                                                 |
| Jira       | `base_url`, `email`, `api_token`, `project_key` (+ `issue_type`) | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`, `JIRA_ISSUE_TYPE` |
| ServiceNow | `instance`, `username`, `password`, `table` (default `incident`)  | `SERVICENOW_INSTANCE`, `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD`, `SERVICENOW_TABLE` |
| Email SMTP | `host`, `from_addr`, `to_addrs` (+ opzionali `username`/`password`) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`, `SMTP_USE_TLS` |

Un canale senza configurazione viene saltato in fase di invio (log informativo), non blocca gli altri canali.

---

## Quick Start

```bash
# Clona e installa
cd Gjallarhorn
pip install -r requirements.txt

# Copia i template di configurazione
cp .env.example .env          # imposta almeno GJALLARHORN_API_KEY
cp config.yaml.example config.yaml   # opzionale: credenziali dei canali

# Avvia l'hub HTTP (porta 8090 di default)
python main.py serve --port 8090

# In un altro terminale: invia una notifica di prova per validare la config
# senza scrivere codice (dispaccio locale sui canali configurati)
python main.py test-notify --source test --severity high --title "Test" --message "Hello"

# Oppure, verso un hub già in esecuzione:
python main.py test-notify --source test --severity high --title "Test" --message "Hello" \
    --hub-url http://localhost:8090 --api-key <la-tua-chiave>
```

### API

```bash
# Invia una notifica (autenticato)
curl -X POST http://localhost:8090/api/v1/notify \
    -H "X-API-Key: <chiave>" -H "Content-Type: application/json" \
    -d '{"source":"heimdall","severity":"critical","title":"Ransomware detected","message":"..."}'

# Storico paginato (autenticato)
curl "http://localhost:8090/api/v1/history?limit=20&offset=0" -H "X-API-Key: <chiave>"
```

Il campo opzionale `channels` nel payload di `/api/v1/notify` permette di scegliere esplicitamente i canali per quella singola notifica (es. `"channels": ["telegram"]`); se omesso, viene usato l'elenco `default_channels` configurato.

---

## Test

```bash
pytest -v
```

La suite (63 test) copre: dedup/throttling della finestra temporale, ognuno dei sei canali mockato (nessuna vera chiamata Telegram/SMTP/webhook/Teams/Jira/ServiceNow), l'endpoint `/api/v1/notify` con `TestClient` (401 senza chiave, 200 con chiave corretta, 422 su payload malformato) e `gjallarhorn_client.notify()` con hub irraggiungibile.

---

<div align="center">

**Sviluppato da [Fioru12](https://github.com/Fioru12)** — Parte della Suite Asgard.

</div>
