# Data Flow Architecture

## Pipeline Overview

This diagram illustrates the complete lifecycle of a lead, from the initial search query to the execution of a cold outreach campaign.
```mermaid
flowchart TD
    %% Source Layer
    CLI([CLI Input / URL File]) --> Orchestrator

    %% Orchestration & Scraping
    subgraph Python Worker Layer
        Orchestrator[ScrapeManager] -->|Search / Maps / Scrape| SerperAPI((Serper.dev API))
        SerperAPI -->|JSON / Markdown| Validator[Pydantic Validator & Regex]
        Validator -->|Clean Domain & Phone| DB[(SQLite: leads_queue)]
    end

    %% Delivery Layer
    subgraph Delivery Layer
        DB -->|SELECT pending| Consumer[Consumer Worker]
        Consumer -->|HTTP POST Batch| Webhook((Make.com Webhook))
        Consumer -.->|UPDATE status| DB
    end

    %% Cloud Integration Layer
    subgraph Make.com (SSOT & Enrichment)
        Webhook --> Iterator[Iterator]
        Iterator --> Filter{Domain valid?}
        Filter -- Yes --> Airtable[(Airtable SSOT)]
        Airtable --> Hunter((Hunter.io API))
        Hunter --> OpenAI((OpenAI: First Line))
        OpenAI --> Instantly((Instantly.ai))
    end
```

---

## 🧩 Component Breakdown

### 1. ScrapeManager
The central orchestrator. Determines the appropriate Serper API endpoint (`Maps`, `Search`, or `Scrape`) based on the selected CLI execution mode and dispatches work accordingly.

### 2. Pydantic Validator & Regex
Stateless validation layer that normalizes raw API responses into clean, typed records — stripping noise, extracting domains, and formatting phone numbers before any data touches the database.

### 3. SQLite — Persistent Queue
Acts as a local buffer between the scraping and delivery layers. Ensures no leads are lost in the event of network failures, application crashes, or Make.com rate limiting. All records persist with a `status` field (`pending` / `sent` / `failed`).

### 4. Consumer Worker
Reads the `pending` queue in configurable batches and delivers payloads to the cloud webhook. Implements **Exponential Backoff** for resilient error handling on transient failures.

### 5. Make.com — SSOT & Enrichment
Serves as the business logic orchestrator in the cloud:
- **Deduplication** — filters leads already present in Airtable.
- **Email Enrichment** — queries Hunter.io by domain to retrieve verified contact emails.
- **AI Personalization** — passes company context to OpenAI to generate a tailored cold outreach opening line.
- **Campaign Injection** — pushes the enriched, personalized lead into Instantly.ai for outreach execution.

---

## 📦 Layer Summary

| Layer | Technology | Responsibility |
|---|---|---|
| Input | CLI / `.txt` file | Query or URL list ingestion |
| Orchestration | ScrapeManager (Python) | Mode routing, API dispatch |
| Validation | Pydantic + Regex | Data normalization & typing |
| Storage | SQLite | Persistent lead queue |
| Delivery | Consumer Worker | Batched webhook dispatch |
| Enrichment | Make.com + Hunter.io | Deduplication, email lookup |
| Personalization | OpenAI (GPT-4o-mini) | AI-generated opening lines |
| Outreach | Instantly.ai | Cold email campaign execution |