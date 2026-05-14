# packages/domain

Business logic layer for the Numina server monorepo. Contains five subpackages, each owning a distinct business domain. Apps call into domain services; domain services never call back into apps or across subdomain boundaries.

## Subpackages

| Subpackage | Entry Point | Domain |
|------------|-------------|--------|
| `audit` | `audit.service` | Security audit log writes and purge |
| `device` | `device.service` | Device session lifecycle and cleanup |
| `exchange_rate` | `exchange_rate.service` | Exchange rate fetching and storage |
| `notification` | `notification.service` | Reminder and notification dispatch |
| `snapshot` | `snapshot.service` | Daily asset snapshot generation |

Each subpackage has its own `README.md` with service-level details.
