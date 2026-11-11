# LOGIPULSE Backend

Self-optimizing logistics digital twin — backend modular monolith.

## Quickstart Guide

### 1. Create Virtual Environment

From within the `backend/` directory:

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy example configuration
cp .env.example .env
```

Default settings connect to SQLite (`sqlite:///./logipulse.db`) and bind to port `8000`.

### 4. Run Database Migrations

```bash
alembic upgrade head
```

### 5. Seed Demo Data

All seed scripts are idempotent and preserve existing data:

```bash
# 1. Seed 5 role-based demo accounts
python -m app.scripts.seed_demo_users

# 2. Seed Bengaluru demo logistics network (3 warehouse nodes, 15 customer nodes, 25 edges)
python -m app.scripts.seed_demo_network

# 3. Seed Demo Warehouses & Inventory Items (3 warehouses, 15 SKUs)
python -m app.scripts.seed_demo_warehouse

# 4. Seed Demo Fleet (8 vehicles, telemetry history)
python -m app.scripts.seed_demo_fleet

# 5. Seed Demo Orders (5 customers, 16 multi-status orders, assignments)
python -m app.scripts.seed_demo_orders

# 6. Seed Demo Disruptions (Vehicles, Corridors, Hubs, Orders)
python -m app.scripts.seed_demo_disruptions
```

> [!CAUTION]
> **DEVELOPMENT ONLY**: The default password for demo accounts is `LogiPulse#2026`. These demo accounts and default passwords must **NEVER** be used in production environments.

#### Demo Credentials:
- `admin` / `admin@logipulse.io` (`ADMIN`)
- `ops_manager` / `ops@logipulse.io` (`OPERATIONS_MANAGER`)
- `fleet_manager` / `fleet@logipulse.io` (`FLEET_MANAGER`)
- `warehouse_manager` / `warehouse@logipulse.io` (`WAREHOUSE_MANAGER`)
- `analyst` / `analyst@logipulse.io` (`ANALYST`)

### 6. Start Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- OpenAPI Spec: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- Network State: [http://localhost:8000/api/v1/network/state](http://localhost:8000/api/v1/network/state)
- Network Graph: [http://localhost:8000/api/v1/network/graph](http://localhost:8000/api/v1/network/graph)
- Network Analytics: [http://localhost:8000/api/v1/network/analytics](http://localhost:8000/api/v1/network/analytics)
- Network Validation: [http://localhost:8000/api/v1/network/validate](http://localhost:8000/api/v1/network/validate)
- Network GeoJSON: [http://localhost:8000/api/v1/network/geojson](http://localhost:8000/api/v1/network/geojson)
- Network Components: [http://localhost:8000/api/v1/network/components](http://localhost:8000/api/v1/network/components)
- Shortest Path: [http://localhost:8000/api/v1/network/shortest-path](http://localhost:8000/api/v1/network/shortest-path)
- Dashboard KPIs: [http://localhost:8000/api/v1/dashboard/summary](http://localhost:8000/api/v1/dashboard/summary)
- Warehouses: [http://localhost:8000/api/v1/warehouses](http://localhost:8000/api/v1/warehouses)
- Warehouse Summary: [http://localhost:8000/api/v1/warehouses/summary](http://localhost:8000/api/v1/warehouses/summary)
- Fleet Vehicles: [http://localhost:8000/api/v1/fleet/vehicles](http://localhost:8000/api/v1/fleet/vehicles)
- Fleet Summary: [http://localhost:8000/api/v1/fleet/summary](http://localhost:8000/api/v1/fleet/summary)
- Available Vehicles: [http://localhost:8000/api/v1/fleet/vehicles/available](http://localhost:8000/api/v1/fleet/vehicles/available)
- Customers: [http://localhost:8000/api/v1/customers](http://localhost:8000/api/v1/customers)
- Orders: [http://localhost:8000/api/v1/orders](http://localhost:8000/api/v1/orders)
- Orders Summary: [http://localhost:8000/api/v1/orders/summary](http://localhost:8000/api/v1/orders/summary)
- Pending Orders: [http://localhost:8000/api/v1/orders/pending](http://localhost:8000/api/v1/orders/pending)
- Overdue Orders: [http://localhost:8000/api/v1/orders/overdue](http://localhost:8000/api/v1/orders/overdue)
- Unassigned Orders: [http://localhost:8000/api/v1/orders/unassigned](http://localhost:8000/api/v1/orders/unassigned)
- Simulations: [http://localhost:8000/api/v1/simulations](http://localhost:8000/api/v1/simulations)
- Simulation WebSocket: `ws://localhost:8000/api/v1/simulations/{id}/ws`
- Disruptions: [http://localhost:8000/api/v1/disruptions](http://localhost:8000/api/v1/disruptions)
- Active Disruptions: [http://localhost:8000/api/v1/disruptions/active](http://localhost:8000/api/v1/disruptions/active)
- Multi-Agent AI Runs: [http://localhost:8000/api/v1/agents/runs](http://localhost:8000/api/v1/agents/runs)
- Multi-Agent AI Status: [http://localhost:8000/api/v1/agents/status](http://localhost:8000/api/v1/agents/status)
- Recovery Plans: [http://localhost:8000/api/v1/recovery/plans](http://localhost:8000/api/v1/recovery/plans)
- Recovery KPI Summary: [http://localhost:8000/api/v1/recovery/summary](http://localhost:8000/api/v1/recovery/summary)
- Analytics Overview: [http://localhost:8000/api/v1/analytics/overview](http://localhost:8000/api/v1/analytics/overview)
- Order Analytics & Trends: [http://localhost:8000/api/v1/analytics/orders](http://localhost:8000/api/v1/analytics/orders) | [http://localhost:8000/api/v1/analytics/orders/trends](http://localhost:8000/api/v1/analytics/orders/trends)
- Fleet Analytics & Trends: [http://localhost:8000/api/v1/analytics/fleet](http://localhost:8000/api/v1/analytics/fleet) | [http://localhost:8000/api/v1/analytics/fleet/trends](http://localhost:8000/api/v1/analytics/fleet/trends)
- Warehouse Analytics & Trends: [http://localhost:8000/api/v1/analytics/warehouses](http://localhost:8000/api/v1/analytics/warehouses) | [http://localhost:8000/api/v1/analytics/warehouses/trends](http://localhost:8000/api/v1/analytics/warehouses/trends)
- Disruption Analytics & Trends: [http://localhost:8000/api/v1/analytics/disruptions](http://localhost:8000/api/v1/analytics/disruptions) | [http://localhost:8000/api/v1/analytics/disruptions/trends](http://localhost:8000/api/v1/analytics/disruptions/trends)
- Agent Intelligence Analytics & Trends: [http://localhost:8000/api/v1/analytics/agents](http://localhost:8000/api/v1/analytics/agents) | [http://localhost:8000/api/v1/analytics/agents/trends](http://localhost:8000/api/v1/analytics/agents/trends)
- Recovery Analytics & Trends: [http://localhost:8000/api/v1/analytics/recovery](http://localhost:8000/api/v1/analytics/recovery) | [http://localhost:8000/api/v1/analytics/recovery/trends](http://localhost:8000/api/v1/analytics/recovery/trends)
- Simulation Analytics: [http://localhost:8000/api/v1/analytics/simulations](http://localhost:8000/api/v1/analytics/simulations)
- Performance Comparisons: [http://localhost:8000/api/v1/analytics/comparisons](http://localhost:8000/api/v1/analytics/comparisons)
- Analytics Health: [http://localhost:8000/api/v1/analytics/health](http://localhost:8000/api/v1/analytics/health)
- PDF Reports & Catalog: [http://localhost:8000/api/v1/reports](http://localhost:8000/api/v1/reports) | [http://localhost:8000/api/v1/reports/types](http://localhost:8000/api/v1/reports/types)

### 7. Run Test Suite (421 Automated Tests)

```bash
pytest -q
```
