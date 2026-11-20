# LOGIPULSE Production Deployment & Operational Runbook

## 1. System Overview

LOGIPULSE is an enterprise-grade Autonomous Logistics Intelligence and Digital Twin Platform tailored for Third-Party Logistics (3PL) providers, fleet operators, and retail fulfillment centers.

This guide provides operational specifications, database configurations, observability standards, and backup/recovery procedures required for production readiness.

---

## 2. Environment Configuration

LOGIPULSE enforces strict environment separation. When `ENVIRONMENT="production"`, the backend automatically performs startup validation to block insecure configurations.

### 2.1 Critical Production Variables

| Variable | Type | Default | Production Requirement |
|---|---|---|---|
| `ENVIRONMENT` | string | `development` | Set to `production` |
| `DATABASE_URL` | string | SQLite path | **Must be PostgreSQL** (`postgresql://user:pass@host:5432/dbname`) |
| `JWT_SECRET_KEY` | string | Insecure default | **Must be unique cryptographically secure key $\ge 32$ chars** |
| `JWT_ALGORITHM` | string | `HS256` | `HS256` or `RS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| int | `15` | Default 15 minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | Default 7 days |
| `ALLOWED_ORIGINS` | string | `http://localhost:5173` | Comma-separated trusted domains; **Wildcard `*` rejected** |
| `RATE_LIMIT_ENABLED` | bool | `true` | Must remain enabled |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | int | `10` | 10 requests / min / IP |
| `RATE_LIMIT_AI_PER_MINUTE` | int | `20` | 20 requests / min / IP |
| `RATE_LIMIT_REPORT_PER_MINUTE`| int | `15` | 15 requests / min / IP |
| `DB_POOL_SIZE` | int | `20` | 20 persistent pool connections |
| `DB_MAX_OVERFLOW` | int | `10` | 10 overflow connections |
| `DB_POOL_TIMEOUT` | int | `30` | 30s timeout |
| `DB_POOL_RECYCLE` | int | `1800` | 1800s (30m) recycling |
| `METRICS_ENABLED` | bool | `true` | Exposes `/metrics` |

---

## 3. Security & Token Lifecycle Architecture

### 3.1 Dual-Token Architecture with Rotation
1. **Access Tokens (`access_token`)**:
   - Short-lived (15 minutes).
   - Contains claims: `sub` (User ID), `username`, `role`, `jti` (unique token ID), `iat`, `exp`.
   - Validated against database revocation blacklist table (`token_blacklist`) on every authenticated request.
2. **Refresh Tokens (`refresh_token`)**:
   - Long-lived (7 days).
   - Stored in hashed form (SHA-256) in `refresh_tokens`.
   - Grouped into cryptographic `family_id` chains.
3. **Compromise Detection & Family Revocation**:
   - If an already-rotated or revoked refresh token is presented (indicating token theft or replay attack), the system automatically revokes the **entire family**, instantly terminating all compromised sessions.
4. **Explicit Logout**:
   - `POST /api/v1/auth/logout` places the access token's `jti` into `token_blacklist` until natural expiration and revokes the associated refresh token.

---

## 4. Database Production Configuration (PostgreSQL)

### 4.1 Recommended PostgreSQL Version
- PostgreSQL 15 or 16 with SSD storage and connection pooling.

### 4.2 Connection Pool Sizing Formula
For a service running $N$ worker processes (e.g. Uvicorn with 4 workers):
$$\text{Max Database Connections} = N \times (\text{DB\_POOL\_SIZE} + \text{DB\_MAX\_OVERFLOW}) + 10$$
With `DB_POOL_SIZE=20` and `DB_MAX_OVERFLOW=10` on 4 workers, ensure PostgreSQL `max_connections >= 130`.

### 4.3 Database Migrations
Migrations are managed via Alembic:
```bash
# Verify current migration status
alembic current

# Apply migrations to head
alembic upgrade head
```

---

## 5. Observability & Health Monitoring

### 5.1 Health Check Endpoints
LOGIPULSE provides standard container health probes exposed both at root and `/api/v1/`:
- **Liveness Probe**: `GET /health/live`
  - Returns `200 OK` (`{"status": "alive"}`) if the FastAPI ASGI loop is responsive.
- **Readiness Probe**: `GET /health/ready`
  - Verifies database reachability via `SELECT 1`.
  - Returns `200 OK` if database is connected; returns `503 Service Unavailable` if database is unreachable.
- **Dashboard Health**: `GET /health`
  - Comprehensive status report for UI monitoring.

### 5.2 Prometheus Metrics Exposition
Exposed at `GET /metrics` in Prometheus text format (version 0.0.4):
- `logipulse_http_requests_total{method="...", path="...", status="..."}` (Counter)
- `logipulse_http_request_duration_seconds{method="...", path="..."}` (Summary with sum & count)
- `logipulse_app_info{version="...", environment="..."}` (Gauge)

### 5.3 Request Correlation
- Every incoming request is stamped with a unique `X-Request-ID` UUID (or propagated from incoming gateway headers).
- Structured JSON logging includes `request_id`, method, path, HTTP status, and response duration in milliseconds.

---

## 6. Backup and Recovery Runbook

### 6.1 Database Backup Schedule
1. **Daily Full Logical Backup**:
   ```bash
   pg_dump -U logipulse_admin -h db.logipulse.internal -Fc logipulse > /backup/logipulse_$(date +%Y%m%d_%H%M%S).dump
   ```
2. **Point-in-Time Recovery (PITR)**:
   - Enable PostgreSQL Write-Ahead Logging (WAL) archiving to encrypted Cloud Storage / S3.
   - Retain WAL archives for 14 days.

### 6.2 Restoration Procedure
```bash
# 1. Stop backend services
systemctl stop logipulse-backend

# 2. Restore database from dump
pg_restore -U logipulse_admin -h db.logipulse.internal -d logipulse --clean --if-exists /backup/logipulse_target.dump

# 3. Verify schema version with Alembic
alembic upgrade head

# 4. Restart backend services and verify readiness
systemctl start logipulse-backend
curl -f http://localhost:8000/health/ready
```

---

## 7. Container Deployment (Docker / Kubernetes)

### 7.1 Kubernetes Pod Probes Example
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
```

