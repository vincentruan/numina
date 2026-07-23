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

- 🏠 **Full Asset Coverage** — Physical assets (real estate, vehicles, electronics) and financial assets (deposits, funds, stocks, bonds)
- 💳 **Liability Management** — Track mortgages, car loans, credit cards with automatic net worth calculation
- 👨‍👩‍👧‍👦 **Multi-User Family** — Each family member records their own assets, with family-level aggregate views
- 📊 **Data Visualization** — Financial dashboard, net worth trend charts, asset allocation pie charts
- 💰 **Smart Analytics** — Daily cost calculation, low-usage asset alerts, investment return rankings
- 🤖 **AI Assistant** — Conversational finance assistant, finance coach, wish advice, asset report generation, PDF import parsing (DeerFlow/LangChain multi-provider)
- ⭐ **Child Incentive System** — Chores for star coins, wish redemption, three-tier currency system to build financial awareness
- 🔐 **Privacy & Security** — Fully self-hosted, data never leaves home, JWT auth, bcrypt password hashing
- 📱 **Mobile-First** — Responsive design optimized for mobile browsers
- 🐳 **One-Click Deploy** — Docker Compose for quick setup, supports LAN and cloud deployment

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Backend | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Agent | Python 3.12+ + FastAPI + DeerFlow/LangChain |
| Scheduler Worker | Python 3.12+ + FastAPI + APScheduler |
| Database | SQLite |
| Auth | JWT (access token + refresh token) |
| Deploy | Docker + docker-compose + Nginx |

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.12+, Node.js 18+, and [uv](https://docs.astral.sh/uv/) for local development

### Deploy with Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. Start all services
docker-compose up -d

# 3. Access the application
# Open http://localhost:8080 in your browser
```

**Environment Variables** (optional):

Create a `.env` file:

```env
PORT=8080                                    # Nginx port
SECRET_KEY=your-secret-key-here              # JWT signing key (must set in production)
DATABASE_URL=sqlite:////app/.numina/data/numina.db   # Database path
SNOWFLAKE_MACHINE_ID=1                       # Snowflake ID machine id (0-1023, set for multi-instance)
```

For full configuration (file storage architecture, all env vars, Docker volumes, Git backup), see [docs/configuration.md](docs/configuration.md).

### Local Development

For module-specific development setup, see the module READMEs: [Backend](./server/apps/backend/README.md) · [Frontend](./frontend/apps/main/README.md) · [Agent](./server/apps/agent/README.md)

## 📊 Features

### Asset Management

- **Physical Assets**: Real estate, vehicles, electronics, appliances, furniture, jewelry, clothing, cosmetics, sports equipment, toys, pets, instruments, bags
- **Financial Assets**: Deposits, funds, stocks, bonds, insurance, wealth management products, cryptocurrency
- **Asset Properties**: Purchase price, current value, purchase date, usage frequency, expected lifespan, annual maintenance cost
- **Smart Calculations**: Daily usage cost, investment return rate, low-usage detection

### Liability Management

- **Liability Types**: Mortgage, car loan, credit card, personal loan
- **Properties**: Original amount, remaining principal, monthly payment, annual interest rate, start/end date, institution
- **Payment Tracking**: Record each payment, auto-update remaining principal, auto-mark when fully paid
- **Asset Linking**: Link liabilities to corresponding assets (e.g., mortgage → property)

### Data Visualization

- **Financial Dashboard**: Total assets, total liabilities, net worth, asset count, month-over-month change
- **Net Worth Trend**: Monthly/quarterly/yearly net worth trend chart
- **Asset Allocation**: Pie chart showing asset distribution by category
- **Daily Cost Ranking**: Assets ranked by daily usage cost
- **Low-Usage Alerts**: Flag idle or rarely-used assets
- **Investment Returns**: Financial assets ranked by return rate

### Multi-User & Family

- **Registration**: Create a family and become the owner
- **Invite System**: Invite family members via 6-digit invite code
- **Role Management**: Owners can manage member roles
- **Family Aggregate**: View combined asset summary across all family members
- **Data Isolation**: Complete data isolation between different families

### 🤖 AI Assistant

A unified AI dispatch layer (`stream_run`) routes all AI applications through a single LangGraph SSE streaming entry point, with per-family skill loading and sandbox file isolation.

- **Conversational Assistant** — `/ai/chat`, family-scoped context, DeerFlow/LangChain multi-provider support
- **Finance Coach Card** — Personalized advice combining asset/liability context
- **Wish Advice Card** — Savings plan and feasibility analysis for wish redemption
- **Asset Report** — Three-step report pipeline (`asset-report` skill), supports image/PDF export
- **PDF Import** — Parse text-based and scanned PDFs with vision multimodal recognition (`import-parse` skill)

### ⭐ Child Star Coin System

An incentive system designed for children in the family — earn star coins by doing chores to build financial awareness and work habits.

- **Chore Management** — Parents create chore templates, assign to children, with daily/weekly/monthly repeat cycles
- **Star Coin Rewards** — Children submit completed chores for approval; parents award coins on approval
- **Combo Rewards** — Bonus multiplier for consecutive chore completion
- **Tiered Currency** — Copper → Silver → Gold three-tier exchange, ratio configurable by parents (default 10:1)
- **Star Ledger** — Full transaction history, supports gifting coins to siblings
- **Wish System** — Submit wish → parent review + point threshold → save up and request redemption → atomic fulfillment, auto-creating an asset
- **Treasure Collection** — Redeemed wishes convert into assets under the child's name, shown on the Treasure page
- **Parent Dashboard** — Per-child balance, pending chore/wish counts, quick-jump to approval pages

## 📖 Technical Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](./docs/ARCHITECTURE.md) | Tech stack, system architecture, module breakdown |
| [Data Models](./docs/DATA_MODELS.md) | Entity relationships, field definitions, taxonomy |
| [API Spec](./docs/API_SPEC.md) | Endpoint list, auth, request/response formats |
| [Frontend Components](./docs/FRONTEND_COMPONENTS.md) | Page routes, component responsibilities, store structure |
| [Coding Standards](./docs/CODING_STANDARDS.md) | Vue 3 / FastAPI coding style |
| [Git Workflow](./docs/GIT_WORKFLOW.md) | Branch strategy, commit format, PR process |
| [Test Spec](./tests/docs/TEST_SPEC.md) | Test accounts, test data, E2E tests |

## 🗂️ Project Structure

```
numina/
├── server/                     # Python server monorepo (uv)
│   ├── apps/
│   │   ├── backend/            # FastAPI core backend
│   │   ├── agent/              # AI analysis microservice
│   │   └── scheduler_worker/   # Scheduled task executor
│   ├── packages/               # Shared Python packages
│   │   ├── core/               # Core utilities and config
│   │   ├── db/                 # Database connection and model base
│   │   ├── domain/             # Domain models and business logic
│   │   ├── security/           # Auth and security utilities
│   │   └── storage/            # File storage abstraction
│   ├── tests/                  # Unified test suite
│   └── pyproject.toml          # Unified dependency management
├── frontend/                   # Vue 3 frontend monorepo (pnpm)
│   ├── apps/                   # Frontend applications
│   │   ├── main/               # Adult-facing app
│   │   └── child/              # Child-facing app
│   └── packages/               # Shared frontend packages
│       ├── auth/               # Shared auth logic
│       └── math/               # Math calculation utilities
├── docker-compose.yml          # Docker Compose configuration
├── nginx.conf                  # Nginx reverse proxy configuration
├── site/                       # Static site resources
└── docs/                       # Project documentation
```

## 📚 Module Documentation

Developer docs for each module (quick start, environment variables, architecture, testing):

| Module | README | Description |
|--------|--------|-------------|
| Backend | [server/apps/backend/README.md](./server/apps/backend/README.md) | FastAPI API development, database, testing |
| Agent | [server/apps/agent/README.md](./server/apps/agent/README.md) | AI microservice, DeerFlow integration, skills |
| Scheduler Worker | [server/apps/scheduler_worker/README.md](./server/apps/scheduler_worker/README.md) | Scheduled tasks, dispatch logic |
| Frontend (Main) | [frontend/apps/main/README.md](./frontend/apps/main/README.md) | Vue 3 UI development, components, testing |
| Frontend (Child) | [frontend/apps/child/CLAUDE.md](./frontend/apps/child/CLAUDE.md) | Child-specific UI |
| E2E Tests | [tests/README.md](./tests/README.md) | E2E tests, data seeding, screenshots |

## 🔐 Security

- **Password Encryption**: bcrypt hashing
- **JWT Authentication**: Access token (15 min) + refresh token (7 days)
- **Auto Refresh**: Frontend automatically refreshes expired tokens seamlessly
- **Family Isolation**: Users can only access their own family's data
- **HTTPS Support**: Recommended for production deployment

## 📝 API Documentation

After starting the backend, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

For the full endpoint list, see [backend/README.md](./server/apps/backend/README.md) and [agent/README.md](./server/apps/agent/README.md).

## 🧪 Testing

The backend includes automated tests covering authentication, assets, liabilities, dashboard, and the child star coin system.

See module READMEs for details: [Backend Tests](./server/apps/backend/README.md#测试) · [Agent Tests](./server/apps/agent/README.md#测试) · [E2E Tests](./tests/README.md)

## 🚢 Deployment

### LAN Deployment (Home NAS / Raspberry Pi)

```bash
# 1. Clone to NAS
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. Start services
docker-compose up -d

# 3. Access on LAN
# http://<NAS-IP>:8080
```

### Cloud Deployment

```bash
# 1. Clone the repository
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. Configure environment
cat > .env << EOF
SECRET_KEY=$(openssl rand -base64 32)
PORT=8080
EOF

# 3. Start services
docker-compose up -d

# 4. Configure HTTPS (Caddy or Nginx recommended)
# Example Caddy config:
# numina.yourdomain.com {
#     reverse_proxy localhost:8080
# }
```

### Data Backup

The SQLite database is stored at `./.numina/data/db/numina.db`. Back up this file regularly.

```bash
# Backup
cp ./.numina/data/db/numina.db ./backups/numina-$(date +%Y%m%d).db

# Restore
cp ./backups/numina-20260314.db ./.numina/data/db/numina.db
docker-compose restart backend
```

## 🗺️ Roadmap

### ✅ MVP (Current)

- [x] User authentication & family management
- [x] Asset & liability CRUD
- [x] Data visualization dashboard
- [x] Daily cost calculation & smart analytics
- [x] Token auto-refresh
- [x] Liability payment tracking
- [x] Automated tests

### ✅ Child Star Coin System (Done)

- [x] Chore management (template + assignment + repeat cycles)
- [x] Star coin rewards with combo bonus
- [x] Copper/Silver/Gold tiered currency (configurable ratio)
- [x] Star ledger & sibling gifting
- [x] Wish system (submit → review → threshold → redemption request → atomic fulfillment)
- [x] Treasure collection (redeemed wishes become child-owned assets)
- [x] Parent dashboard (balance overview + approval shortcuts)
- [x] Child-specific UI (dedicated bottom nav, savings jar progress animation)

### ✅ Phase 2: Smart Analysis (Done)

- [x] Spending leak detection (high idle cost, redundant holdings, high maintenance burden — 3 rule types + LLM advice)
- [x] Buy vs. rent comparison calculator (break-even point, recommendation)
- [x] Spending equivalence (daily cost, time cost, opportunity cost — 3 dimensions)

### ✅ Phase 2.5: AI Assistant & Family Finance Coach (Done)

- [x] Conversational AI assistant (unified `stream_run` dispatch, DeerFlow/LangChain multi-provider, family-scoped skills & sandbox)
- [x] Finance Coach Card (personalized advice from asset/liability context)
- [x] Wish Advice Card (savings plan & feasibility analysis)
- [x] Asset report generation (`asset-report` skill, three-step pipeline, image/PDF export)
- [x] PDF asset import (`import-parse` skill, text + scanned PDF with vision multimodal)
- [x] Education reward linkage (chores → education reward, dedicated spend stats, parent approval gate)
- [x] Interval return rate (1M/3M/6M/1Y presets, valuation history comparison)
- [x] Debt warning linkage (family-level thresholds + over-limit alerts)

### 🔮 Phase 3: Asset Time Machine (Future)

- [ ] What-if analysis for different spending choices
- [ ] Future financial projection based on historical data
- [ ] Inflation-adjusted purchasing power tracking

### 🔔 Phase 4: Smart Reminders (Future)

- [ ] Large purchase cooling-off reminders
- [ ] Asset allocation imbalance alerts
- [ ] Insurance/warranty expiration reminders
- [ ] Wealth product maturity reminders

### 📤 Phase 5: Data Import/Export (Future)

- [x] PDF asset import (import-parse — text + scanned vision)
- [x] Asset report PDF/image export (asset-report)
- [ ] CSV/Excel batch import
- [ ] Monthly/yearly financial report auto-generation

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- UI Components: [Vant](https://vant-ui.github.io/)
- Charts: [Apache ECharts](https://echarts.apache.org/)
- Backend: [FastAPI](https://fastapi.tiangolo.com/)
- Frontend: [Vue.js](https://vuejs.org/)

## 📧 Contact

For questions or suggestions:

- Submit an Issue: [GitHub Issues](https://github.com/vincentruan/numina/issues)
- Email: your.email@example.com

---

<div align="center">

**Track wisely, decide smartly 💰**

Made with ❤️ by Numina Team

</div>
