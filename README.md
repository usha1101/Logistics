# LOGIPULSE

Self-optimizing logistics digital twin.

## Project Structure

- `backend/`: FastAPI backend modular monolith (Stage 0: Foundation, Stage 1: Core, Stage 2: Auth/RBAC, Stage 3: Network & Command Centre, Stage 4: Warehouse & Inventory Control, Stage 5: Fleet Management & Vehicle Tracking, Stage 6: Order Management System, Stage 7: Network Visualization & Graph Intelligence, Stage 8: Simulation Engine & Digital Twin, Stage 9: Disruption Management & Impact Analysis, Stage 10: Multi-Agent AI Intelligence, Stage 11: Intelligent Optimization & Recovery Engine, Stage 12: Analytics, Performance Monitoring & PDF Reporting)
- `docs/`: Technical specifications, Stage 0 gap report, and frontend handoff guide
  - `docs/STAGE0_GAP_REPORT.md`
  - `docs/BACKEND_HANDOFF.md`

## Backend Quickstart

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed_demo_users
python -m app.scripts.seed_demo_network
python -m app.scripts.seed_demo_warehouse
python -m app.scripts.seed_demo_fleet
python -m app.scripts.seed_demo_orders
python -m app.scripts.seed_demo_disruptions
uvicorn app.main:app --reload --port 8000
```

Tests:
```bash
cd backend
pytest -q
```
