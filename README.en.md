# Numina - Family Asset Visualization & Management

<div align="center">

**Privacy-first, self-hosted family financial management platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

[简体中文](./README.md) | English

</div>

## Overview

Numina is a fully self-hosted family asset visualization and management system. It helps family members collaboratively track, manage, and visualize assets and liabilities. The core design principle is **privacy** — all financial data stays entirely under your control, deployable on a home LAN or private cloud server.

### Key Features

- 🏠 **Full Asset Coverage** — Physical assets (real estate, vehicles, electronics) and financial assets (deposits, funds, stocks, bonds)
- 💳 **Liability Management** — Track mortgages, car loans, credit cards with automatic net worth calculation
- 👨‍👩‍👧‍👦 **Multi-User Family** — Each family member records their own assets, with family-level aggregate views
- 📊 **Data Visualization** — Financial dashboard, net worth trend charts, asset allocation pie charts
- 💰 **Smart Analytics** — Daily cost calculation, low-usage asset alerts, investment return rankings
- 🔐 **Privacy & Security** — Fully self-hosted, JWT authentication, bcrypt password hashing
- 📱 **Mobile-First** — Responsive design optimized for mobile browsers
- 🐳 **One-Click Deploy** — Docker Compose for quick setup, supports LAN and cloud deployment

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Backend | Python 3.11+ + FastAPI + SQLAlchemy + Alembic |
| Agent | Python 3.11+ + FastAPI + DeerFlow/LangChain |
| Database | SQLite |
| Auth | JWT (access token + refresh token) |
| Deploy | Docker + docker-compose + Nginx |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.11+, Node.js 18+, and [uv](https://docs.astral.sh/uv/) for local development

### Deploy with Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/numina.git
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
```

### Local Development

For module-specific development setup, see the module READMEs: [Backend](./backend/README.md) · [Frontend](./frontend/README.md) · [Agent](./agent/README.md)

## Features

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

## Project Structure

```
numina/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── routers/           # API route handlers
│   │   ├── services/          # Business logic layer
│   │   ├── auth/              # JWT authentication
│   │   └── seed/              # Database seed data
│   ├── tests/                 # pytest tests (532 tests, all passing)
│   ├── alembic/               # Database migrations
│   └── Dockerfile
├── agent/                    # AI analysis microservice
│   ├── app/                  # Entry point package
│   │   ├── main.py           # FastAPI entry
│   │   ├── config.py         # Configuration
│   │   ├── scheduler.py      # Scheduled tasks
│   │   ├── routers/          # API routes
│   │   ├── services/         # Business logic
│   │   ├── schemas/          # Data models
│   │   └── core/             # Core components
│   ├── tests/                # pytest tests
│   └── Dockerfile
├── frontend/                   # Vue 3 frontend
│   ├── src/
│   │   ├── api/               # Axios API client
│   │   ├── stores/            # Pinia state management
│   │   ├── pages/             # Page components
│   │   ├── components/        # Reusable components
│   │   ├── router/            # Vue Router configuration
│   │   └── types/             # TypeScript type definitions
│   └── Dockerfile
├── docker-compose.yml          # Docker Compose configuration
├── nginx.conf                  # Nginx reverse proxy configuration
└── docs/                       # Project documentation
```

## Module Documentation

Developer docs for each module (quick start, environment variables, architecture, testing):

| Module | README | Description |
|--------|--------|-------------|
| Backend | [backend/README.md](./backend/README.md) | FastAPI API development, database, testing |
| Agent | [agent/README.md](./agent/README.md) | AI microservice, DeerFlow integration, skills |
| Frontend | [frontend/README.md](./frontend/README.md) | Vue 3 UI development, components, testing |
| Tests | [tests/README.md](./tests/README.md) | E2E tests, data seeding, screenshots |

## Security

- **Password Encryption**: bcrypt hashing
- **JWT Authentication**: Access token (15 min) + refresh token (7 days)
- **Auto Refresh**: Frontend automatically refreshes expired tokens seamlessly
- **Family Isolation**: Users can only access their own family's data
- **HTTPS Support**: Recommended for production deployment

## API Documentation

After starting the backend, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

For the full endpoint list, see [backend/README.md](./backend/README.md) and [agent/README.md](./agent/README.md).

## Testing

The backend includes 532 automated tests covering authentication, assets, liabilities, and dashboard features.

**Test Results**: ✅ 532 passed, 0 failed

Agent includes unit and integration tests.

See module READMEs for details: [Backend Tests](./backend/README.md#testing) · [Agent Tests](./agent/README.md#testing) · [E2E Tests](./tests/README.md)

## Deployment

### LAN Deployment (Home NAS / Raspberry Pi)

```bash
git clone https://github.com/yourusername/numina.git
cd numina
docker-compose up -d
# Access at http://<NAS-IP>:8080
```

### Cloud Deployment

```bash
git clone https://github.com/yourusername/numina.git
cd numina

# Configure environment
cat > .env << EOF
SECRET_KEY=$(openssl rand -base64 32)
PORT=8080
EOF

docker-compose up -d
# Configure HTTPS with Caddy or Nginx
```

### Data Backup

The SQLite database is stored at `./.numina/data/db/numina.db`. Simply back up this file regularly.

```bash
cp ./.numina/data/db/numina.db ./backups/numina-$(date +%Y%m%d).db
```

## Roadmap

### ✅ MVP (Current)

- [x] User authentication & family management
- [x] Asset & liability CRUD
- [x] Data visualization dashboard
- [x] Daily cost calculation & smart analytics
- [x] Token auto-refresh
- [x] Liability payment tracking
- [x] 532 automated tests

### 🔜 Phase 2: Smart Analysis

- [ ] Spending leak detection (idle asset reports)
- [ ] Buy vs. rent comparison calculator
- [ ] Spending equivalence converter

### 🔮 Phase 3: Asset Time Machine

- [ ] What-if analysis for different spending choices
- [ ] Future financial projection based on historical data
- [ ] Inflation-adjusted purchasing power tracking

### 🔔 Phase 4: Smart Reminders

- [ ] Large purchase cooling-off reminders
- [ ] Asset allocation imbalance alerts
- [ ] Insurance/warranty expiration reminders

### 📤 Phase 5: Data Import/Export

- [ ] CSV/Excel batch import
- [ ] Monthly/yearly financial report PDF generation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Design inspired by the "YouShu" (有数) App
- UI Components: [Vant](https://vant-ui.github.io/)
- Charts: [Apache ECharts](https://echarts.apache.org/)
- Backend: [FastAPI](https://fastapi.tiangolo.com/)
- Frontend: [Vue.js](https://vuejs.org/)

---

<div align="center">

**Track wisely, decide smartly 💰**

Made with ❤️ by Numina Team

</div>
