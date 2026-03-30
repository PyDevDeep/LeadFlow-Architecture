# LeadFlow Architecture 🚀

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**LeadFlow Architecture** is a professional lead generation tool that automates the full pipeline — from data scraping to CRM integration via Webhooks and Make.com.

Built for developers and marketing teams who need to streamline lead collection and outreach workflows at scale.

---

## ✨ Features

- **Automated Scraping** — Extract leads from Google Maps, Google Search, or custom URL lists.
- **4 Scraping Modes** — Surface search, deep scrape, hybrid, and file-based pipelines.
- **Data Management** — Local SQLite storage for efficient processing and queue tracking.
- **Webhook Integration** — Push validated leads to Make.com, Zapier, or any HTTP endpoint.
- **Outreach Pipeline** — Native integration with Airtable, OpenAI, Hunter.io, and Instantly.
- **Reliability & Error Handling** — Break directives with automatic retry on API failures.
- **Lead Deduplication** — Built-in filters prevent duplicate records and skip leads without emails.
- **Configurable Logging** — Flexible log levels: `DEBUG`, `INFO`, `ERROR`.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | [Python 3.8+](https://www.python.org/) |
| Database | SQLite |
| Testing | [Pytest](https://docs.pytest.org/) |
| Automation | [Make.com](https://www.make.com/) |
| Integrations | Airtable · OpenAI · Hunter.io · Instantly |

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/PyDevDeep/LeadFlow-Architecture.git
cd LeadFlow-Architecture
```

### 2. Set Up the Environment

```bash
pip install -r requirements.txt
cp .env.example .env
```

> Edit `.env` with your credentials before proceeding.

### 3. Initialize the Database

```bash
python main.py init
```

---

## 🖥 CLI Usage Guide

All commands are executed from the project root directory.

### Database Initialization

Must be run once before any scraping pipeline.

```bash
python main.py init
```

---

### Scraping Pipelines

#### Scenario 1 — Google Maps Scraper

Extracts local business data from Google Maps based on a search query.

```bash
python main.py maps -q "<your_query>"

# Example
python main.py maps -q "dental clinics in Kyiv"
```

#### Scenario 2 — Google Search (Surface Level)

Extracts basic snippets and URLs from Google organic search results.

```bash
python main.py search -q "<your_query>"

# Example
python main.py search -q "top digital marketing agencies"
```

#### Scenario 3 — Hybrid (Search + Deep Scrape)

Runs an organic search, then performs multi-threaded deep scraping on each discovered domain to extract contact details and metadata.

```bash
python main.py hybrid -q "<your_query>"

# Example
python main.py hybrid -q "software development outsourcing ukraine"
```

#### Scenario 4 — File-Based Deep Scrape

Reads URLs from a `.txt` file and runs a multi-threaded deep scrape on each target.

```bash
python main.py file -f <filepath>

# Example
python main.py file -f urls_list.txt
```

---

### Push Leads to Webhook

Processes the pending queue and pushes validated leads to the configured Webhook endpoint.

```bash
python main.py send
```

---

### 🧪 Run Tests

```bash
pytest
```

---

## ⚙️ Configuration

All settings are managed via the `.env` file. Copy `.env.example` and fill in the values:

| Variable | Description |
|---|---|
| `DATABASE_PATH` | Path to the SQLite database file |
| `SCRAPER_TIMEOUT` | HTTP request timeout (seconds) |
| `WEBHOOK_URL` | Destination endpoint for lead delivery |
| `WEBHOOK_BATCH_SIZE` | Number of leads sent per batch |
| `LOG_LEVEL` | Logging verbosity (`DEBUG` / `INFO` / `ERROR`) |

---

## 🤖 Make.com Automation

A ready-to-use blueprint is available in the `/automation` directory.

### Quick Setup

1. Download `Make.json` or `outreach_pipeline.json` from `/automation`
2. In Make.com — create a new scenario → **Import Blueprint**
3. Connect each module marked with a red `!`:
   - **Airtable** (Production)
   - **Hunter.io** (Domain Search)
   - **OpenAI** (GPT-4o-mini)
   - **Instantly** (Lead Import)
4. Replace all `YOUR_...` placeholders with your actual IDs (see table below)
5. Copy the generated Webhook URL from Module 1 → paste it into your `.env` as `WEBHOOK_URL`

---

### 🔑 Service Identifiers

| Variable | Description | Where to Find |
|---|---|---|
| `YOUR_BASE_ID` | Unique ID of your Airtable Base | Airtable URL / API docs |
| `YOUR_TABLE_ID` | Name or ID of the target table | Airtable table URL |
| `YOUR_INSTANTLY_CAMPAIGN_ID` | ID of your outreach campaign | Instantly.ai dashboard |

---

### 🗂 Airtable Field Mapping

For **Module 11 (Create a Record)** to function correctly, your Airtable table must include columns matching these identifiers:

| Placeholder | Field Description |
|---|---|
| `YOUR_FIELD_ID_DOMAIN` | Company domain (e.g. `example.com`) |
| `YOUR_FIELD_ID_EMAIL` | Primary contact email found by Hunter |
| `YOUR_FIELD_ID_COMPANY_NAME` | Organization name |
| `YOUR_FIELD_ID_URL` | Full website URL |
| `YOUR_FIELD_ID_DB_ID` | Original ID from the lead source / webhook |
| `YOUR_FIELD_ID_PHONE` | Contact phone number |
| `YOUR_FIELD_ID_DESCRIPTION` | Company description used for AI context |
| `YOUR_FIELD_ID_SOURCE_METHOD` | Label indicating lead origin |
| `YOUR_FIELD_ID_AI_RESPONSE` | GPT-generated personalized opening line |
| `YOUR_FIELD_ID_STATUS` | Lead status (`Ready` / `Done`) |

---

### 🛡️ Reliability Features

- **Error Handling** — Break directives on OpenAI, Hunter, and Instantly modules; Make.com auto-retries on service failures.
- **Lead Filtering** — Skips leads already present in Airtable and leads without a valid email, reducing unnecessary API token usage.

---

### 🔐 Security Audit

| Check | Status |
|---|---|
| API keys / passwords in JSON | ✅ None found |
| `__IMTCONN__` connection fields | ✅ All set to `null` |
| Sensitive placeholders | ✅ Correctly masked |

---

## 🖼 Pipeline Overview

![Pipeline Overview](automation/Scenario_IMG.jpg)

---

## 📂 Project Structure

```text
.
├── app/
│   ├── scraper/          # Scraping modules (client, parser, logic)
│   ├── sender/           # Webhook sending logic
│   ├── utils/            # Utilities and logging
│   ├── config.py         # Environment configuration
│   └── database.py       # Database interaction layer
├── automation/           # Make.com blueprints and assets
│   ├── Make.json
│   ├── outreach_pipeline.json
│   └── Scenario_IMG.jpg
├── main.py               # CLI entry point
├── requirements.txt      # Project dependencies
└── .env.example          # Environment variable template
```

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).