<div align="center">

<img src="./frontend/apps/main/public/favicon.svg" alt="Numina" width="80" />

# Numina

**Privacy-first, self-hosted family financial management platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

[简体中文](./README.md) | English

</div>

## Overview

Numina is a fully self-hosted family asset visualization and management system. It helps family members collaboratively track, manage, and visualize assets and liabilities. The core design principle is **privacy** — all financial data stays entirely under your control, deployable on a home LAN or private cloud server.

### Key Features

**Asset Management**
- **Full Asset Coverage** — Physical assets (real estate, vehicles, electronics) + financial assets (deposits, funds, stocks) with multi-currency support; multi-format intelligent import (PDF statements / screenshots / Excel with AI classification)
- **Liability Management** — Mortgages, car loans, credit cards with 4 repayment methods (equal principal, equal installment, etc.) and historical retroactive entry, automatic net worth calculation
- **Rental Contracts** — Landlord/tenant views, deposit tracking, due date reminders
- **Trip Planning** — Multi-day itinerary timeline + day-by-day scheduling, cross-day items (hotels, rentals) auto-expanded, multi-currency expense tracking / bill-splitting / receipt AI parsing, cost sync to itinerary
- **Wish Linking** — Fulfilled wishes auto-link to realized assets with bidirectional navigation
- **Data Visualization** — Financial dashboard, net worth trends, asset allocation charts, daily cost analysis

**AI Capabilities**
- **Conversational Finance Assistant** — DeerFlow-powered multi-provider AI chat (OpenAI / Anthropic / Gemini / Ollama) with web search and MCP tools
- **Finance Coach** — AI-driven personalized financial advice
- **Asset Reports** — AI-generated asset analysis reports
- **Wish Advice** — Smart wish evaluation and suggestions
- **Dashboard Narrative** — AI-generated monthly financial summary in natural language explaining data changes
- **PDF / Image Import** — AI-powered document scanning with batch asset import
- **Task Resilience** — AI tasks continue server-side after disconnect; frontend auto-replays events on reconnect — closing the browser doesn't lose progress
- **AI Learning Tutor** — Knowledge graph-powered AI tutoring with Chinese dialogue, interactive teaching, and adaptive assessment

**Family & Children**
- **Multi-User Family** — Individual records with family-level aggregation and complete data isolation
- **Child Incentive System** — Chores for star coins, wish redemption, blind box draws, three-tier currency; personal avatars (image / 3D icons / emoji)
- **Financial Literacy** — Scenario learning, badge system, AI literacy weekly reports (behavioral evidence + family activity suggestions)
- **AI Learning OS** — Children's learning system built on the os-taxonomy knowledge graph, covering 1,590 topics across 8 subjects (math, science, English, etc.)
  - **Knowledge Map** — Subject and domain-organized knowledge graph with prerequisite/dependent relationships
  - **AI Tutoring** — DeerFlow-powered streaming AI tutor with Chinese-first dialogue, interactive assessment, and safety-filtered output
  - **Mastery Tracking** — 7-level state machine (locked → available → learning → assessing → mastered → review) with spaced repetition
  - **Learning Paths & Growth** — Parent-assigned tasks auto-sorted by prerequisites, XP/level system (🌱 Seed → 🌟 Master) with milestone rewards; children can also explore freely with age-difficulty warnings
  - **Bilingual Support** — English originals + on-demand LLM Chinese translation with technical terms preserved
  - **Parent Dashboard** — Children's learning overview, task assignment, review queue, study duration tracking
  - **Failure Streak Alerts** — Auto-notifies parents after 3 consecutive failed assessments on the same topic
- **Family Manifesto** — Signable family financial goals and commitments with calligraphy signatures, family crest, and signing ceremony visualization

**Security & Experience**
- **Privacy & Security** — Fully self-hosted, JWT auth, bcrypt hashing, encrypted file storage
- **Mobile-First** — Responsive H5 design for mobile browsers
- **Dark Mode** — Auto-follows system theme
- **One-Click Deploy** — Docker Compose quick setup with GHCR pre-built images
- **PWA** — Installable to desktop, offline dashboard & asset viewing, push notifications

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts + Pinia |
| Backend | Python 3.12+ · FastAPI · SQLAlchemy 2.0 · Alembic |
| AI Agent | Python 3.12+ · DeerFlow · LangChain · Multi-provider (OpenAI / Anthropic / Gemini / Ollama) |
| Streaming | Redis Streams + unified cache layer (cross-process event dispatch & sharing, Last-Event-ID reconnection) |
| Database | SQLite (default) · PostgreSQL · MySQL |
| Deploy | Docker Compose · Nginx · GHCR images |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.12+, Node.js 18+, and [uv](https://docs.astral.sh/uv/) for local development

### Docker Deployment (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. Initialize (auto-generate secrets + .env + data directories + invitation codes)
make setup

# 3. Start services
make deploy

# 4. Access the application — open http://localhost in your browser
```

> **Pre-built images:** Run `make deploy-images` to pull the latest GHCR images — no compilation needed.

### Environment Variables

`make setup` already generates them. Full reference: [docs/configuration.md](docs/configuration.md)

```env
PORT=8080                                    # Nginx port
SECRET_KEY=your-secret-key-here              # JWT signing key (must set in production)
DATABASE_URL=sqlite:////app/.numina/data/numina.db   # Database path
SNOWFLAKE_MACHINE_ID=1                       # Snowflake ID machine id (0-1023)
```

### Updating

```bash
git pull origin main
make deploy           # local build
# or
make deploy-images    # pull pre-built images
```

### Data Backup

The SQLite database is at `./.numina/data/db/numina.db`. Back up this file regularly.

> **Path note:** The `DATABASE_URL` env variable uses the container path (`/app/.numina/data/...`), which maps via Docker volume to the host's `.numina/data/`. The actual database file on the host is at `.numina/data/db/numina.db`.

```bash
cp ./.numina/data/db/numina.db ./backups/numina-$(date +%Y%m%d).db
```

### Local Development

```bash
make install          # Install all dependencies (uv + pnpm)
make dev-all          # Start all 5 dev servers (backend/agent/worker/frontend/child)
make stop-dev-all     # Stop all dev servers
```

Module-specific dev guides: [Backend](./server/apps/backend/README.md) · [Frontend](./frontend/apps/main/README.md) · [Agent](./server/apps/agent/README.md)

## Project Structure

```
numina/
├── server/                     # Python server monorepo (uv workspace)
│   ├── apps/
│   │   ├── backend/            # FastAPI core backend (:8000)
│   │   ├── agent/              # AI analysis microservice (DeerFlow, :8001)
│   │   └── scheduler_worker/   # Scheduled task executor (:8002)
│   ├── packages/               # Shared Python packages
│   │   ├── core/               # Infrastructure (config, Snowflake ID, circuit breaker, cache)
│   │   ├── db/                 # SQLAlchemy models & database sessions
│   │   ├── domain/             # Domain logic & computations
│   │   ├── security/           # Auth, encryption, JWT
│   │   ├── storage/            # File storage & encryption
│   │   ├── stream_bridge/      # DeerFlow cross-process event dispatch (Redis Streams)
│   │   └── os_taxonomy/        # Open-source taxonomy data (knowledge graph, learning topics)
│   ├── scripts/                # Data seed scripts (knowledge graph import, badge definitions)
│   ├── tests/                  # Unified test suite
│   └── pyproject.toml
├── frontend/                   # Vue 3 frontend monorepo (pnpm workspace)
│   ├── apps/
│   │   ├── main/               # Adult-facing H5 app (:5173)
│   │   └── child/              # Child-facing H5 app (:5174)
│   └── packages/
│       ├── auth/               # @numina/auth — shared auth package
│       ├── math/               # @numina/math — business computation functions
│       └── shared/             # @numina/shared — SSE parsing and shared utilities
├── tests/                      # E2E / visual regression tests
├── docs/                       # Project documentation
├── docker-compose.yml          # Development / default deployment
├── docker-compose.production.yml  # Production deployment (GHCR images)
└── Makefile                    # Unified command entry point
```

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](./docs/ARCHITECTURE.md) | System architecture, module breakdown, data flow |
| [Data Models](./docs/DATA_MODELS.md) | Entity relationships, field definitions, computation logic |
| [API Spec](./docs/API_SPEC.md) | Endpoint list, request/response formats |
| [Configuration](./docs/configuration.md) | Environment variables, database setup |
| [Deployment](./docs/deployment.md) | Production deployment, image management |

Auto-generated API docs after starting the backend: Swagger UI `http://localhost:8000/docs` · ReDoc `http://localhost:8000/redoc`

---

<div align="center">

**Record attentively, decide wisely**

Made with ❤️ by Numina Team

</div>
