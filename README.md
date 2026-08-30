# Talk-to-my-Data (GenAI BI) — The Gadget Store
**Artefact Capstone 2026 | Case #1: Building a real-world Generative AI application**

**Team:** Raed Ali Ba Fadhl (Lead), Fares Al-humaikani, Amir Safi, Muhammed Dulger
**Client contacts:** mark.rademaker@artefact.com · quinten.tulp@artefact.com

---

## 1. What we're building

A natural-language business intelligence assistant for The Gadget Store's sales team. A non-technical user asks a question in plain English (e.g. *"What were total headphone sales in the Netherlands over the last 3 months?"*), and the system:

1. Interprets the question using knowledge of our database schema
2. Generates and validates a safe, read-only SQL query
3. Executes it against our data warehouse
4. Returns results as a table, a chart, and a plain-English summary

**Client requirements (non-negotiable):**
- Enhance the user's question with schema knowledge
- Compute at least 2 KPIs
- Execute SQL returning aggregated results (over time, store, country, etc.)

---

## 2. Dataset

**Global Electronics Retailer** (Maven Analytics / Microsoft, public domain — also mirrored on Kaggle)

A fictional global electronics retailer operating across North America, Europe, and Australia — structurally close to The Gadget Store. Five relational tables:

| Table | Key columns |
|---|---|
| **Sales** | Order Date, Order Number, Line Item, Product Key, Quantity, Customer Key, Store Key, Currency Code, Delivery Date |
| **Products** | Product Key, Product Name, Brand, Color, Unit Cost, Unit Price, Category, Subcategory |
| **Customers** | Customer Key, Name, Gender, City, State, Zip Code, Country, Continent, Birthday |
| **Stores** | Store Key, Country, State, City, Store Name, Square Meters, Open Date |
| **Exchange Rates** | Date, Currency, Exchange Rate to USD |

## 3. KPIs

1. **Revenue over time** — by month/quarter, by store or country
2. **Top-performing products/categories** — by revenue or units sold
3. **Average Order Value (AOV)** — overall and by segment
4. **Category sales share** — % of revenue by product category

---

## 4. System architecture — 4 pillars

```
User question (plain English)
        │
        ▼
[Pillar 2] LLM + dynamic schema injection + few-shot examples
        │
        ▼
Generated SQL ── ambiguity? → clarification question back to user
        │
        ▼
[Pillar 3] SQL validation & safety guardrails (read-only SELECT only)
        │
        ▼
[Pillar 1] BigQuery execution (partitioned, indexed warehouse)
        │
        ▼
[Pillar 3] KPI computation + multi-modal response formatting
        │
        ▼
[Pillar 4] Streamlit UI — table + chart + narrative summary
```

### Pillar 1 — Cloud & Data Platform
1.1 Retail Data Cleaning & ETL — ingest & transform the dataset into clean tabular form
1.2 BigQuery Data Warehouse Setup — schema, partitioning, indexing
1.3 IAM & Security Configuration — least-privilege access, service accounts
1.4 Docker & Cloud Run Deployment — containerize, CI/CD to GCP Cloud Run

### Pillar 2 — GenAI & Text-to-SQL
2.1 Dynamic Schema Injection — feed table structures/metadata into prompt context
2.2 Few-Shot Prompting & Domain Lexicon — map retail terms (revenue, units, returns) to SQL
2.3 Self-Healing Query Feedback Loop — intercept SQL errors, let LLM self-correct
2.4 Ambiguity Resolution & Clarification — ask before hallucinating schema entities

### Pillar 3 — Backend & Analytics Engine
3.1 FastAPI Core Service Layer — async REST API coordinating UI ↔ LLM ↔ BigQuery
3.2 SQL Validation & Safety Guardrails — enforce read-only `SELECT`, block injection
3.3 Retail KPI Computation Engine — revenue growth, AOV, category share
3.4 Multi-Modal Response Formatter — raw SQL → narrative + table + chart schema

### Pillar 4 — Frontend UI, Benchmark & Delivery
4.1 Streamlit Conversational Interface — clean chat UI for business stakeholders
4.2 Dynamic Data Visualizations — Plotly time-series, distribution, breakdown charts
4.3 Golden Benchmark Evaluation Suite — 30+ validated reference questions testing accuracy
4.4 Excalidraw Architecture & Client Deck — living architecture sketch + final pitch deck

---

## 5. Responsibility matrix

| Role (Owner) | Focus Area | Core Stack | Milestone Deliverable |
|---|---|---|---|
| **Member 1 — Cloud & Data Engineer** | Data pipelines, BigQuery modeling, Cloud Run infra | GCP, BigQuery, Docker, SQL | Clean DB tables & live Cloud environment |
| **Member 2 — LLM & Text-to-SQL Engineer** | Prompt architecture, SQL generation, self-healing loop | Vertex AI, LangChain, Few-Shot | High-accuracy Text-to-SQL pipeline |
| **Member 3 — Backend & Analytics Dev** | API orchestration, KPI calculations, SQL safety layer | FastAPI, Python, Pydantic | Secure API & automated KPI engine |
| **Member 4 — Frontend & Delivery Lead** | Streamlit UI, visualization, benchmark & deck | Streamlit, Plotly, Excalidraw | Interactive UI & evaluation report |

*(As team lead, decide with your team who takes which seat — align to individual strengths from your intro round.)*

---

## 6. Working in stages

We work through the project in gated stages. Early stages are short and everyone contributes to a different slice at once; Stage 2 is the whole team working the same pillar together, one pillar at a time, before moving to the next. Full detail in `PROJECT_ORGANIZATION.md`.

| Stage | Focus | Who |
|---|---|---|
| **0 — Prerequisites** | Cloud, Environment, Design, Data & BI — 4 categories, 4 people, in parallel | Everyone, own category |
| **1 — Contracts & skeleton** | `schema.md`, `api.md`, repo folder structure | Everyone, together |
| **2A — Pillar 1** | Cloud & Data Platform (1.1–1.4) | Everyone, one sub-task each |
| **2B — Pillar 2** | LLM & Text-to-SQL (2.1–2.4) | Everyone, one sub-task each |
| **2C — Pillar 3** | Backend & Analytics Engine (3.1–3.4) | Everyone, one sub-task each |
| **2D — Pillar 4** | Frontend UI, Benchmark & Delivery (4.1–4.4) | Everyone, one sub-task each |
| **3 — Integration** | Wire all four pillars into one working pipeline | Everyone, together |
| **4 — Dry run** | Deck + rehearsal, presented to Mark + Quinten | Everyone, together |
| **5 — Final** | Cloud deployment, final deck, live demo | Everyone, together |

**Backlog = GitHub Issues, labeled by stage (`stage-0` through `stage-5`).**
**Board = GitHub Projects** (Backlog → In Progress → Review → Done).
**Daily standup** on WhatsApp during active stages: yesterday / today / blockers.

---


