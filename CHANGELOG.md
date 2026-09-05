# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-05

First stable release of Numina — a privacy-first, self-hosted family asset visualization and management platform.

### Core Platform

- **Family management** — multi-member families with role-based access (parent/child), invite codes, and family isolation
- **Authentication** — JWT-based auth with device recognition, username/password login, and session management
- **Multi-currency support** — 13+ currencies with automatic exchange rate updates via APScheduler
- **Multi-database backend** — SQLite (dev), PostgreSQL (production) with SQLAlchemy + Alembic migrations
- **Docker deployment** — docker-compose for backend, agent, scheduler worker, and frontend nginx
- **i18n** — Chinese (zh-CN) and English (en-US) with vue-i18n frontend and backend localization

### Asset & Liability Management

- **Asset tracking** — physical assets (real estate, vehicles, electronics) and financial assets (deposits, funds, stocks)
- **Multi-currency asset values** — original currency + CNY conversion with exchange rate history
- **Liability tracking** — mortgages, car loans, credit cards with repayment schedules and interest calculation
- **Rental contracts** — landlord/tenant dual-role views, deposit tracking, expiry reminders
- **Wish management** — goal-based wish lists linked to assets
- **Batch operations** — multi-select archive, delete, and status changes
- **Data import/export** — multi-format intelligent import (CSV, JSON, Excel)

### Dashboard & Visualization

- **Financial overview** — net worth, asset/liability totals, daily cost analysis
- **Allocation charts** — ECharts-based asset distribution pie charts and trend lines
- **Narrative card** — AI-generated financial insights with streaming narrative display
- **Lifecycle progress** — asset lifespan progress bars with daily cost indicators
- **Category navigation** — icon-based category grid with usage frequency sorting

### AI Capabilities

- **AI Chat** — multi-mode conversational interface (chat/report/coach/deep-think) via DeerFlow integration
- **AI Skills** — 17 built-in skills including finance coach, wish advice, dashboard narrative, asset report
- **AI Report** — long-form financial analysis with step-by-step progress timeline
- **PDF/Document analysis** — upload and analyze financial documents via AI
- **MCP tools** — model context protocol integration for external tool access
- **Multi-provider LLM** — support for DashScope, OpenAI, Anthropic, and local models
- **Circuit breaker** — unified resilience layer with fallback across AI providers
- **SSE streaming** — real-time token streaming with reconnect and cache-first polling

### Child Frontend

- **Dedicated child app** — separate Vue app with age-appropriate UI
- **Chore gamification** — task assignment, approval loop, streak tracking, blind-box rewards
- **Wish advice** — AI-powered guidance linked to saved wishes
- **Weekly literacy report** — AI-generated family financial literacy summaries
- **Celebration animations** — task completion game-feel with polar rotation loading

### User Experience

- **Dark/light/system theme** — with cosmic background login animation
- **Mobile-first responsive** — Vant 4 components optimized for touch
- **SVG icon system** — sprite-based icons with 3D catalog icon picker
- **Pull-to-refresh** — native-feeling mobile interactions
- **Optimistic UI** — instant feedback on asset operations
- **Task completion celebration** — animations and streak milestones

### Infrastructure

- **Scheduler worker** — Celery-like task scheduling for exchange rates and reminders
- **Stream bridge** — unified SSE protocol between agent and frontend
- **ContextVar-based run context** — thread-safe request propagation
- **UTC datetime normalization** — UTCDateTime TypeDecorator across all models
- **Snowflake ID serialization** — bigint-safe string IDs for JS clients
- **Unified error codes** — i18n-aware validation error responses
- **Altcha CAPTCHA** — privacy-preserving proof-of-work captcha
- **GitHub Pages landing site** — promotional pages with feature highlights

[1.0.0]: https://github.com/vincentruan/numina/tree/v1.0.0
