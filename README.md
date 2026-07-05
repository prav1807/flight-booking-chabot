# ✈️ Flight Booking Chatbot

An AI-powered flight booking assistant built with **Rasa Pro** and **Ollama**, integrated with the **Duffel** flights API and **Supabase** for booking storage.

---

## Prerequisites

Make sure the following are installed before getting started:

- [Python 3.11](https://www.python.org/downloads/release/python-3119/)
- [Ollama](https://ollama.com/download)
- A **Rasa Pro license key** — get one at [rasa.com](https://rasa.com)

---

## 1. Clone the repository

```bash
git clone https://github.com/prav1807/flight-booking-chabot.git
cd flight-booking-chabot
```

---

## 2. Set up environment variables

Copy the example env file and fill in your credentials:

```bash
cp .env_example .env
```

Edit `.env` with your values:

```env
DUFFEL_ACCESS_TOKEN=your_duffel_token
DUFFEL_BASE_URL=https://api.duffel.com

SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_key

RASA_PRO_LICENSE=your_rasa_pro_license_key
```

---

## 3. Pull Ollama models

Make sure Ollama is running, then pull the required models:

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

---

## 4. Create virtual environments

This project uses **two separate virtual environments** to avoid dependency conflicts between Rasa Pro and the action server.

```bash
python -m venv .venv
python -m venv .venv-actions
```

---

## 5. Install dependencies

### Rasa Pro venv

**Windows:**
```powershell
.\.venv\Scripts\activate
pip install rasa-pro
```

**Mac/Linux:**
```bash
source .venv/bin/activate
pip install rasa-pro
```

### Action server venv

**Windows:**
```powershell
.\.venv-actions\Scripts\activate
pip install rasa-sdk duffel-api supabase python-dotenv python-dateutil
```

**Mac/Linux:**
```bash
source .venv-actions/bin/activate
pip install rasa-sdk duffel-api supabase python-dotenv python-dateutil
```

---

## 6. Train the model

**Windows:**
```powershell
.\.venv\Scripts\activate
$env:RASA_PRO_LICENSE = (Get-Content .\.env | Select-String "RASA_PRO_LICENSE" | ForEach-Object { ($_ -replace "RASA_PRO_LICENSE=","").Trim() })
cd rasa-chatbot
rasa train
```

**Mac/Linux:**
```bash
source .venv/bin/activate
export RASA_PRO_LICENSE=$(grep RASA_PRO_LICENSE .env | cut -d= -f2)
cd rasa-chatbot
rasa train
```

---

## 7. Run the bot

You need **two terminals** running simultaneously.

### Terminal 1 — Action Server

**Windows:**
```powershell
.\.venv-actions\Scripts\activate
cd rasa-chatbot
python -m rasa_sdk --actions actions
```

**Mac/Linux:**
```bash
source .venv-actions/bin/activate
cd rasa-chatbot
python -m rasa_sdk --actions actions
```

You should see:
```
Action endpoint is up and running on http://0.0.0.0:5055
```

### Terminal 2 — Rasa Shell

**Windows:**
```powershell
.\.venv\Scripts\activate
$env:RASA_PRO_LICENSE = (Get-Content .\.env | Select-String "RASA_PRO_LICENSE" | ForEach-Object { ($_ -replace "RASA_PRO_LICENSE=","").Trim() })
cd rasa-chatbot
rasa shell
```

**Mac/Linux:**
```bash
source .venv/bin/activate
export RASA_PRO_LICENSE=$(grep RASA_PRO_LICENSE .env | cut -d= -f2)
cd rasa-chatbot
rasa shell
```

---

## Project structure

```
flight-booking-chabot/
├── .env                   # Your secrets (never commit this)
├── .env_example           # Template for environment variables
├── rasa-chatbot/
│   ├── actions/           # Custom action server code
│   ├── data/
│   │   ├── flows/         # Conversation flows
│   │   └── nlu/           # NLU training data
│   ├── domain/            # Slots, responses, and actions definitions
│   ├── config.yml         # Rasa pipeline & policies (uses Ollama)
│   └── endpoints.yml      # Action server & model group config
├── .venv/                 # Rasa Pro virtual environment
└── .venv-actions/         # Action server virtual environment
```

---

## Notes

- **Two venvs are required** because `supabase` requires `websockets>=11` while `rasa-pro` requires `websockets<11`.
- The `think: false` flag in `endpoints.yml` disables qwen3's slow reasoning mode for faster responses.
- `.env` is excluded from git via `.gitignore` — never commit your secrets.
