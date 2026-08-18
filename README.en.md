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
- **Full Asset Coverage** — Physical assets (real estate, vehicles, electronics) + financial assets (deposits, funds, stocks) with multi-currency support
- **Liability Management** — Mortgages, car loans, credit cards with automatic net worth calculation
- **Rental Contracts** — Landlord/tenant views, deposit tracking, due date reminders
- **Data Visualization** — Financial dashboard, net worth trends, asset allocation charts, daily cost analysis

**AI Capabilities**
- **Conversational Finance Assistant** — DeerFlow-powered multi-provider AI chat with web search and MCP tools
- **Finance Coach** — AI-driven personalized financial advice
- **Asset Reports** — AI-generated asset analysis reports
- **Wish Advice** — Smart wish evaluation and suggestions
- **Dashboard Narrative** — AI-driven financial summaries and insights
- **PDF / Image Import** — AI-powered document scanning with batch asset import

**Family & Children**
- **Multi-User Family** — Individual records with family-level aggregation and complete data isolation
- **Child Incentive System** — Chores for star coins, wish redemption, blind box draws, three-tier currency
- **Financial Literacy** — Learning scenarios, badge system, AI weekly reports
- **Family Manifesto** — Signable family financial goals and commitments

**Security & Experience**
- **Privacy & Security** — Fully self-hosted, JWT auth, bcrypt hashing, encrypted file storage
- **Mobile-First** — Responsive H5 design for mobile browsers
- **Dark Mode** — Auto-follows system theme
- **One-Click Deploy** — Docker Compose quick setup with GHCR pre-built images

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts + Pinia |
| Backend | Python 3.12+ · FastAPI · SQLAlchemy 2.0 · Alembic |
| AI Agent | Python 3.12+ · DeerFlow · LangChain · Multi-provider (OpenAI / Anthropic / Ollama) |
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
│   │   ├── core/               # Infrastructure (config, Snowflake ID, circuit breaker)
│   │   ├── db/                 # SQLAlchemy models & database sessions
│   │   ├── domain/             # Domain logic & computations
│   │   ├── security/           # Auth, encryption, JWT
│   │   └── storage/            # File storage & encryption
│   ├── tests/                  # Unified test suite
│   └── pyproject.toml
├── frontend/                   # Vue 3 frontend monorepo (pnpm workspace)
│   ├── apps/
│   │   ├── main/               # Adult-facing H5 app (:5173)
│   │   └── child/              # Child-facing H5 app (:5174)
│   └── packages/
│       ├── auth/               # @numina/auth — shared auth package
│       └── math/               # @numina/math — business logic functions
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
| [Data Models](./docs/DATA_MODELS.md) | Entity relationships, field definitions, computed fields |
| [API Spec](./docs/API_SPEC.md) | Endpoint list, request/response formats |
| [Configuration](./docs/configuration.md) | Environment variables, database setup |
| [Deployment](./docs/deployment.md) | Production deployment, image management |

Auto-generated API docs after starting the backend: Swagger UI `http://localhost:8000/docs` · ReDoc `http://localhost:8000/redoc`

---

<div align="center">

**Track wisely, decide smartly**

Made with ❤️ by Numina Team

</div>
