# Numina - Family Asset Visualization & Management

<div align="center">

**Privacy-first, self-hosted family financial management platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

[简体中文](./README.md) | English

</div>

## 📖 Overview

Numina is a fully self-hosted family asset visualization and management system. It helps family members collaboratively track, manage, and visualize assets and liabilities. The core design principle is **privacy** — all financial data stays entirely under your control, deployable on a home LAN or private cloud server.

### ✨ Key Features

- 🏠 **Full Asset Coverage** — Physical assets (real estate, vehicles, electronics) + financial assets (deposits, funds, stocks)
- 💳 **Liability Management** — Mortgages, car loans, credit cards with automatic net worth calculation
- 👨‍👩‍👧‍👦 **Multi-User Family** — Individual records with family-level aggregation and complete data isolation
- 📊 **Data Visualization** — Financial dashboard, net worth trends, asset allocation charts
- 💰 **Smart Analytics** — Daily cost calculation, low-usage alerts, investment return rankings
- 🤖 **AI Assistant** — Conversational finance assistant, finance coach, wish advice, asset reports, PDF import (DeerFlow/LangChain multi-provider)
- ⭐ **Child Incentive System** — Chores for star coins, wish redemption, three-tier currency to build financial awareness
- 🔐 **Privacy & Security** — Fully self-hosted, JWT auth, bcrypt hashing
- 📱 **Mobile-First** — Responsive design for mobile browsers
- 🐳 **One-Click Deploy** — Docker Compose quick setup

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Backend | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Agent | Python 3.12+ + FastAPI + DeerFlow/LangChain |
| Database | SQLite |
| Deploy | Docker + docker-compose + Nginx |

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.12+, Node.js 18+, and [uv](https://docs.astral.sh/uv/) for local development

### Docker Deployment (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. Initialize (auto-generate secrets + .env + data directories)
make setup

# 3. Start services
make deploy

# 4. Generate family invitation codes (required for registration)
make setup-invitation-codes

# 5. Access the application — open http://localhost in your browser
```

> **Pre-built images:** Run `make deploy-images` to pull the latest GHCR images — no compilation needed.

**Environment Variables** (optional, `make setup` already generates them):

```env
PORT=8080                                    # Nginx port
SECRET_KEY=your-secret-key-here              # JWT signing key (must set in production)
DATABASE_URL=sqlite:////app/.numina/data/numina.db   # Database path
SNOWFLAKE_MACHINE_ID=1                       # Snowflake ID machine id (0-1023)
```

Full configuration reference: [docs/configuration.md](docs/configuration.md)

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

Module-specific dev guides: [Backend](./server/apps/backend/README.md) · [Frontend](./frontend/apps/main/README.md) · [Agent](./server/apps/agent/README.md)

## 🗂️ Project Structure

```
numina/
├── server/                     # Python server monorepo (uv)
│   ├── apps/
│   │   ├── backend/            # FastAPI core backend
│   │   ├── agent/              # AI analysis microservice
│   │   └── scheduler_worker/   # Scheduled task executor
│   ├── packages/               # Shared packages (core/db/domain/security/storage)
│   ├── tests/                  # Unified test suite
│   └── pyproject.toml
├── frontend/                   # Vue 3 frontend monorepo (pnpm)
│   ├── apps/
│   │   ├── main/               # Adult-facing app
│   │   └── child/              # Child-facing app
│   └── packages/               # Shared packages (auth/math)
├── docker-compose.yml
├── nginx.conf
└── docs/                       # Project documentation
```

## 📚 Documentation & Development

| Doc | Description |
|-----|-------------|
| [Architecture](./docs/ARCHITECTURE.md) | System architecture, module breakdown |
| [Data Models](./docs/DATA_MODELS.md) | Entity relationships, field definitions |
| [API Spec](./docs/API_SPEC.md) | Endpoint list, request/response formats |
| [Test Spec](./tests/docs/TEST_SPEC.md) | Test accounts, E2E tests |

Auto-generated API docs after starting the backend: Swagger UI `http://localhost:8000/docs` · ReDoc `http://localhost:8000/redoc`

## 🤝 Contributing

Contributions are welcome! Fork → feature branch → commit → push → pull request.

## 📄 License

[MIT License](LICENSE)

---

<div align="center">

**Track wisely, decide smartly 💰**

Made with ❤️ by Numina Team

</div>
