# Security Policy

## Supported Versions

Only the latest release is actively supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < Latest| :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously, especially since Numina handles sensitive family financial data.

**Please do NOT open a public issue for security vulnerabilities.**

### How to Report

Use GitHub's [private vulnerability reporting](../../security/advisories/new) to confidentially disclose security issues. This ensures the vulnerability is not visible to the public until a fix is available.

Alternatively, email the maintainer directly if GitHub private reporting is unavailable.

### What to Include

- Description of the vulnerability
- Steps to reproduce or proof of concept
- Affected component (backend, frontend, agent, etc.)
- Potential impact
- Suggested fix (if any)

### What to Expect

- **Acknowledgement** — within 48 hours of submission
- **Initial assessment** — within 7 days, including severity rating and whether it is accepted
- **Fix timeline** — communicated once severity is determined
- **Public disclosure** — coordinated with the reporter after a patch is released

### Scope

In-scope components:

- `server/apps/backend` — API server
- `server/apps/agent` — AI agent service
- `server/apps/scheduler_worker` — Background task worker
- `server/packages/` — Shared packages (core, db, domain, security, storage)
- `frontend/apps/` — Web applications (main, child)
- Docker Compose deployment configuration
- Nginx configuration

Out of scope:

- Third-party dependencies (report upstream instead)
- Issues requiring physical access to the host
- Social engineering attacks

## Security Best Practices for Self-Hosted Instances

Since Numina is self-hosted, instance security depends on proper deployment:

1. **Use HTTPS** — Always deploy behind a TLS-enabled reverse proxy (nginx/Caddy)
2. **Change default secrets** — Generate unique `JWT_SECRET` and `ENCRYPTION_KEY` values
3. **Keep updated** — Pull the latest releases regularly
4. **Restrict network access** — Expose only necessary ports (typically 80/443)
5. **Database security** — Use strong passwords; restrict DB network access to the application container
6. **AI provider keys** — Store LLM API keys securely via environment variables; never commit them

## Security Architecture Notes

- **Authentication**: JWT-based with configurable token expiry
- **Authorization**: Role-based access control (RBAC) with family-scoped data isolation
- **Data encryption**: Sensitive fields encrypted at rest; Snowflake IDs for identifier obfuscation
- **Secret management**: All secrets injected via environment variables, never hardcoded
- **Dependency management**: Regular audits via GitHub Dependabot
