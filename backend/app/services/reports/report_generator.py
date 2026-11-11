import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report import ReportMetadata, ReportStatus, ReportType
from app.schemas.report import (
    ReportGenerateRequest,
    ReportTypeInfo,
    ReportTypesListResponse,
)
from app.services.analytics import (
    ReportGenerationError,
    ReportNotFoundError,
    compute_agent_analytics,
    compute_disruption_analytics,
    compute_fleet_analytics,
    compute_order_analytics,
    compute_overview_analytics,
    compute_performance_comparisons,
    compute_recovery_analytics,
    compute_simulation_analytics,
    compute_warehouse_analytics,
)
from app.services.analytics.filters import build_filter_meta
from app.services.reports.pdf_builder import PDFReportBuilder

REPORTS_STORAGE_DIR = Path(__file__).resolve().parents[3] / "generated_reports"

REPORT_TYPE_DEFINITIONS: List[ReportTypeInfo] = [
    ReportTypeInfo(
        report_type=ReportType.EXECUTIVE_SUMMARY.value,
        title="Executive Logistics Control Tower Summary",
        description="Unified end-to-end overview of orders, fleet, warehouses, disruptions, AI intelligence, and recovery performance.",
        included_sections=[
            "Executive KPI Summary",
            "Order Fulfillment & SLA Performance",
            "Fleet & Warehouse Utilization",
            "Disruption, Multi-Agent AI & Recovery Overview",
            "Data Integrity & Metric Classifications",
        ],
    ),
    ReportTypeInfo(
        report_type=ReportType.FLEET_PERFORMANCE.value,
        title="Fleet Performance & Utilization Report",
        description="Detailed breakdown of vehicle statuses, load capacity utilization, assigned orders, and telemetry distance segments.",
        included_sections=[
            "Fleet Capacity & Status Summary",
            "Vehicle Type & Status Distribution Chart",
            "Per-Vehicle Utilization & Telemetry Distance Table",
            "Data Integrity & Limitations",
        ],
    ),
    ReportTypeInfo(
        report_type=ReportType.WAREHOUSE_PERFORMANCE.value,
        title="Warehouse & Inventory Operations Report",
        description="Storage capacity utilization, SKU stock health (In-Stock, Low-Stock, Out-of-Stock), and audit trail movement volumes.",
        included_sections=[
            "Warehouse Storage Capacity Summary",
            "Inventory Stock Health & Movement Audit",
            "Per-Warehouse Utilization Breakdown",
            "Data Integrity & Limitations",
        ],
    ),
    ReportTypeInfo(
        report_type=ReportType.DISRUPTION_REPORT.value,
        title="Disruption Impact & Resolution Analysis Report",
        description="Analysis of active and resolved logistics disruptions by severity, type, affected resources, and estimated delays.",
        included_sections=[
            "Disruption Status & Severity Breakdown",
            "Disruption Type Distribution Chart",
            "Resource Impact & Resolution Duration Metrics",
            "Data Integrity & Limitations",
        ],
    ),
    ReportTypeInfo(
        report_type=ReportType.AI_INTELLIGENCE_REPORT.value,
        title="Multi-Agent AI Intelligence & Recommendation Report",
        description="Performance metrics of specialist AI agents, execution latency, provider distribution, and recommendation validation.",
        included_sections=[
            "Agent Orchestration Run Summary",
            "Specialist Agent Execution & Provider Distribution",
            "Recommendation Validation Breakdown",
            "Data Integrity & Limitations",
        ],
    ),
    ReportTypeInfo(
        report_type=ReportType.RECOVERY_PERFORMANCE.value,
        title="Optimization & Recovery Engine Performance Report",
        description="Evaluation of OR-Tools recovery plans, human approval statuses, executed reassignments, and before-vs-after comparisons.",
        included_sections=[
            "Recovery Plan Lifecycle Summary",
            "Optimization Strategy & Action Execution Breakdown",
            "Before-vs-After Recovery Comparison Table",
            "Data Integrity & Limitations",
        ],
    ),
    ReportTypeInfo(
        report_type=ReportType.SIMULATION_REPORT.value,
        title="Digital Twin Simulation Performance Report",
        description="Summary of digital twin simulation runs, simulated vehicle telemetry distances, simulated disruptions, and recovery outcomes.",
        included_sections=[
            "Simulation Lifecycle Summary",
            "Simulated Fleet Telemetry & Distance Metrics",
            "Simulated Disruptions & Recovery Outcomes",
            "Data Integrity & Limitations",
        ],
    ),
]


def ensure_reports_directory() -> Path:
    REPORTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_STORAGE_DIR


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    if not cleaned:
        cleaned = "logipulse_report"
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned


def resolve_safe_report_path(file_reference: str) -> Path:
    if not file_reference or "/" in file_reference or "\\" in file_reference or ".." in file_reference:
        raise ReportNotFoundError("Invalid report file reference.")
    storage_dir = ensure_reports_directory().resolve()
    candidate = (storage_dir / file_reference).resolve()
    if candidate.parent != storage_dir:
        raise ReportNotFoundError("Report path traversal blocked.")
    return candidate


def get_report_types_catalog() -> ReportTypesListResponse:
    return ReportTypesListResponse(
        report_types=REPORT_TYPE_DEFINITIONS,
        total=len(REPORT_TYPE_DEFINITIONS),
    )


def _populate_report_content(
    builder: PDFReportBuilder,
    db: Session,
    req: ReportGenerateRequest,
) -> Dict[str, Any]:
    rt = req.report_type
    s = req.start_date
    e = req.end_date
    sim_id = req.simulation_id
    inc_sim = req.include_simulations

    if rt == ReportType.EXECUTIVE_SUMMARY:
        ov = compute_overview_analytics(db, s, e, sim_id, inc_sim)
        orders = compute_order_analytics(db, s, e, simulation_id=sim_id, include_simulations=inc_sim)
        builder.add_section_heading("Executive Summary")
        builder.add_paragraph(
            f"This executive report summarizes operational and analytical metrics across {ov.total_orders} orders, "
            f"{ov.total_vehicles} fleet vehicles, and {ov.total_warehouses} warehouses."
        )
        builder.add_kpi_table(
            ["Metric", "Value", "Classification"],
            [
                ["Total Orders", ov.total_orders, "ACTUAL"],
                ["Delivered Orders", ov.delivered_orders, "ACTUAL"],
                ["In-Transit Orders", ov.in_transit_orders, "ACTUAL"],
                ["Overdue Orders (Past Deadline)", ov.overdue_orders, "ACTUAL"],
                ["Estimated Delayed Orders (Disruption Impact)", ov.estimated_delayed_orders, "ESTIMATED"],
                ["Delivery Success Rate (%)", f"{ov.delivery_success_rate}%", "ACTUAL"],
                ["On-Time Delivery Rate (%)", f"{ov.on_time_delivery_rate}%", "ACTUAL"],
                ["Total Vehicles / Active Vehicles", f"{ov.total_vehicles} / {ov.active_vehicles}", "ACTUAL"],
                ["Fleet Capacity Utilization (%)", f"{ov.fleet_utilization_rate}%", "ACTUAL"],
                ["Warehouse Storage Utilization (%)", f"{ov.warehouse_utilization_rate}%", "ACTUAL"],
                ["Active / Resolved Disruptions", f"{ov.active_disruptions} / {ov.resolved_disruptions}", "ACTUAL"],
                ["Multi-Agent AI Runs", ov.total_agent_runs, "ACTUAL"],
                ["Recovery Plans (Executed / Total)", f"{ov.executed_recovery_plans} / {ov.total_recovery_plans}", "ACTUAL"],
                ["Recovery Success Rate (%)", f"{ov.recovery_success_rate}%", "ACTUAL"],
                ["Active Digital Twin Simulations", ov.active_simulations, "SIMULATED"],
            ],
            col_widths=[210, 120, 120],
        )
        builder.add_bar_chart(
            "Order Status Distribution",
            list(orders.orders_by_status.keys()),
            [float(v) for v in orders.orders_by_status.values()],
        )
        builder.add_notes_section(
            [
                "Overdue orders represent actual non-delivered orders past expected_delivery_at.",
                "Estimated delayed orders represent orders linked to disruption impact records.",
            ],
            orders.unavailable_metrics,
        )
        return {
            "total_orders": ov.total_orders,
            "delivery_success_rate": ov.delivery_success_rate,
            "fleet_utilization_rate": ov.fleet_utilization_rate,
            "warehouse_utilization_rate": ov.warehouse_utilization_rate,
            "active_disruptions": ov.active_disruptions,
            "recovery_success_rate": ov.recovery_success_rate,
        }

    if rt == ReportType.FLEET_PERFORMANCE:
        fl = compute_fleet_analytics(db, s, e, simulation_id=sim_id, include_simulations=inc_sim)
        builder.add_section_heading("Fleet Performance & Utilization Overview")
        builder.add_paragraph(
            f"Analysis of {fl.total_vehicles} registered vehicles with total capacity {fl.total_fleet_capacity_kg} kg "
            f"and current load {fl.total_current_load_kg} kg."
        )
        builder.add_kpi_table(
            ["Fleet Metric", "Value", "Classification"],
            [
                ["Total Vehicles", fl.total_vehicles, "ACTUAL"],
                ["Available Vehicles", fl.available_vehicles, "ACTUAL"],
                ["In-Transit Vehicles", fl.in_transit_vehicles, "ACTUAL"],
                ["Idle Vehicles", fl.idle_vehicles, "ACTUAL"],
                ["Breakdown / Maintenance / Offline", f"{fl.breakdown_vehicles} / {fl.maintenance_vehicles} / {fl.offline_vehicles}", "ACTUAL"],
                ["Total Capacity (kg)", fl.total_fleet_capacity_kg, "ACTUAL"],
                ["Total Current Load (kg)", fl.total_current_load_kg, "ACTUAL"],
                ["Fleet Capacity Utilization (%)", f"{fl.fleet_capacity_utilization_percentage}%", "ACTUAL"],
                ["Average Vehicle Load Utilization (%)", f"{fl.average_load_utilization_percentage}%", "ACTUAL"],
                ["Total Distance Travelled (km)", fl.total_distance_travelled_km, fl.metric_classifications.get("total_distance_travelled_km", "UNAVAILABLE")],
            ],
            col_widths=[210, 120, 120],
        )
        builder.add_bar_chart(
            "Vehicles by Operational Status",
            list(fl.vehicles_by_status.keys()),
            [float(v) for v in fl.vehicles_by_status.values()],
        )
        if fl.vehicles:
            builder.add_section_heading("Per-Vehicle Performance Breakdown")
            builder.add_kpi_table(
                ["Code", "Type", "Status", "Load / Cap (kg)", "Util (%)", "Distance (km)"],
                [
                    [
                        v.vehicle_code,
                        v.vehicle_type,
                        v.status,
                        f"{v.current_load_kg}/{v.capacity_kg}",
                        f"{v.load_utilization_percentage}%",
                        v.distance_travelled_km if v.distance_travelled_km is not None else "N/A",
                    ]
                    for v in fl.vehicles[:25]
                ],
                col_widths=[65, 85, 75, 90, 55, 80],
            )
        builder.add_notes_section(
            [
                "Distance travelled is computed strictly from chronological GPS/telemetry coordinate pairs using Haversine distance.",
                "Vehicles with fewer than 2 telemetry points report Distance as N/A (Unavailable).",
            ],
            fl.unavailable_metrics,
        )
        return {
            "total_vehicles": fl.total_vehicles,
            "fleet_capacity_utilization_percentage": fl.fleet_capacity_utilization_percentage,
            "in_transit_vehicles": fl.in_transit_vehicles,
            "total_distance_travelled_km": fl.total_distance_travelled_km,
        }

    if rt == ReportType.WAREHOUSE_PERFORMANCE:
        wh = compute_warehouse_analytics(db, s, e, simulation_id=sim_id, include_simulations=inc_sim)
        builder.add_section_heading("Warehouse Capacity & Inventory Health")
        builder.add_paragraph(
            f"Aggregated across {wh.total_warehouses} warehouses managing {wh.total_inventory_items} SKUs "
            f"and {wh.total_inventory_movements} stock movements."
        )
        builder.add_kpi_table(
            ["Warehouse / Inventory Metric", "Value", "Classification"],
            [
                ["Total Warehouses (Operational)", f"{wh.total_warehouses} ({wh.operational_warehouses})", "ACTUAL"],
                ["Total Storage Capacity", wh.total_capacity, "ACTUAL"],
                ["Total Used Capacity", wh.total_used_capacity, "ACTUAL"],
                ["Overall Storage Utilization (%)", f"{wh.overall_utilization_percentage}%", "ACTUAL"],
                ["Average Warehouse Utilization (%)", f"{wh.average_warehouse_utilization_percentage}%", "ACTUAL"],
                ["Total Inventory SKUs", wh.total_inventory_items, "ACTUAL"],
                ["In-Stock / Low-Stock / Out-of-Stock", f"{wh.in_stock_items} / {wh.low_stock_items} / {wh.out_of_stock_items}", "ACTUAL"],
                ["Inbound Movements (Total Qty)", f"{wh.inbound_movements_count} ({wh.inbound_quantity_total})", "ACTUAL"],
                ["Outbound Movements (Total Qty)", f"{wh.outbound_movements_count} ({wh.outbound_quantity_total})", "ACTUAL"],
                ["Adjustment Movements (Total Qty)", f"{wh.adjustment_movements_count} ({wh.adjustment_quantity_total})", "ACTUAL"],
            ],
            col_widths=[210, 120, 120],
        )
        if wh.warehouses:
            builder.add_bar_chart(
                "Warehouse Storage Utilization (%)",
                [w.warehouse_code for w in wh.warehouses],
                [w.utilization_percentage for w in wh.warehouses],
            )
            builder.add_section_heading("Per-Warehouse Breakdown")
            builder.add_kpi_table(
                ["Code", "Name", "Status", "Used / Cap", "Util (%)", "In / Low / Out SKUs"],
                [
                    [
                        w.warehouse_code,
                        w.name[:22],
                        w.status,
                        f"{w.used_capacity}/{w.total_capacity}",
                        f"{w.utilization_percentage}%",
                        f"{w.in_stock_count}/{w.low_stock_count}/{w.out_of_stock_count}",
                    ]
                    for w in wh.warehouses
                ],
                col_widths=[55, 105, 70, 85, 55, 80],
            )
        builder.add_notes_section(
            ["Stock status is derived deterministically from quantity vs reorder_level thresholds."],
            wh.unavailable_metrics,
        )
        return {
            "total_warehouses": wh.total_warehouses,
            "overall_utilization_percentage": wh.overall_utilization_percentage,
            "total_inventory_items": wh.total_inventory_items,
            "low_stock_items": wh.low_stock_items,
            "out_of_stock_items": wh.out_of_stock_items,
        }

    if rt == ReportType.DISRUPTION_REPORT:
        dis = compute_disruption_analytics(db, s, e, simulation_id=sim_id, include_simulations=inc_sim)
        builder.add_section_heading("Disruption Impact & Resolution Summary")
        builder.add_paragraph(
            f"Evaluation of {dis.total_disruptions} disruptions ({dis.active_disruptions} active, "
            f"{dis.resolved_disruptions} resolved)."
        )
        builder.add_kpi_table(
            ["Disruption Metric", "Value", "Classification"],
            [
                ["Total Disruptions", dis.total_disruptions, "ACTUAL"],
                ["Active Disruptions", dis.active_disruptions, "ACTUAL"],
                ["Resolved Disruptions", dis.resolved_disruptions, "ACTUAL"],
                ["Cancelled Disruptions", dis.cancelled_disruptions, "ACTUAL"],
                ["Distinct Affected Vehicles", dis.affected_vehicles_count, "ACTUAL"],
                ["Distinct Affected Orders", dis.affected_orders_count, "ACTUAL"],
                ["Distinct Affected Warehouses / Edges", f"{dis.affected_warehouses_count} / {dis.affected_edges_count}", "ACTUAL"],
                ["Average Resolution Time (min)", dis.average_resolution_time_minutes, dis.metric_classifications.get("average_resolution_time_minutes", "UNAVAILABLE")],
                ["Estimated Total Delay (min)", dis.estimated_total_delay_minutes, "ESTIMATED"],
            ],
            col_widths=[210, 120, 120],
        )
        builder.add_bar_chart(
            "Disruptions by Type",
            list(dis.disruptions_by_type.keys()),
            [float(v) for v in dis.disruptions_by_type.values()],
        )
        builder.add_notes_section(
            [
                "Average resolution time is calculated only for resolved disruptions with both start_time and actual_end_time.",
                "Estimated total delay is summed from deterministic DisruptionImpact assessments.",
            ],
            dis.unavailable_metrics,
        )
        return {
            "total_disruptions": dis.total_disruptions,
            "active_disruptions": dis.active_disruptions,
            "resolved_disruptions": dis.resolved_disruptions,
            "estimated_total_delay_minutes": dis.estimated_total_delay_minutes,
        }

    if rt == ReportType.AI_INTELLIGENCE_REPORT:
        ag = compute_agent_analytics(db, s, e, simulation_id=sim_id, include_simulations=inc_sim)
        builder.add_section_heading("Multi-Agent AI Intelligence Summary")
        builder.add_paragraph(
            f"Analysis of {ag.total_agent_runs} orchestration runs, {ag.total_agent_executions} specialist agent executions, "
            f"and {ag.total_recommendations} generated recommendations."
        )
        builder.add_kpi_table(
            ["AI Intelligence Metric", "Value", "Classification"],
            [
                ["Total Agent Orchestration Runs", ag.total_agent_runs, "ACTUAL"],
                ["Completed / Partially Completed Runs", f"{ag.completed_runs} / {ag.partially_completed_runs}", "ACTUAL"],
                ["Failed / AI Unavailable Runs", f"{ag.failed_runs} / {ag.ai_unavailable_runs}", "ACTUAL"],
                ["Total Specialist Agent Executions", ag.total_agent_executions, "ACTUAL"],
                ["Agent Execution Success Rate (%)", f"{ag.agent_success_rate}%", "ACTUAL"],
                ["Average Agent Execution Latency (ms)", ag.average_agent_execution_duration_ms, ag.metric_classifications.get("average_agent_execution_duration_ms", "UNAVAILABLE")],
                ["Total Recommendations", ag.total_recommendations, "ACTUAL"],
                ["Validated / Rejected Recommendations", f"{ag.validated_recommendations} / {ag.rejected_recommendations}", "ACTUAL"],
                ["Requires Validation / Informational", f"{ag.requires_validation_recommendations} / {ag.informational_recommendations}", "ACTUAL"],
                ["LLM Token Usage Total", ag.token_usage_total, "UNAVAILABLE"],
                ["Estimated LLM Cost (USD)", ag.estimated_llm_cost_usd, "UNAVAILABLE"],
            ],
            col_widths=[210, 120, 120],
        )
        builder.add_bar_chart(
            "Recommendation Validation Breakdown",
            list(ag.recommendations_by_validation_status.keys()),
            [float(v) for v in ag.recommendations_by_validation_status.values()],
        )
        builder.add_notes_section(
            [
                "Token usage and monetary LLM API cost are not persisted in AgentExecution records and are marked UNAVAILABLE.",
            ],
            ag.unavailable_metrics,
        )
        return {
            "total_agent_runs": ag.total_agent_runs,
            "total_agent_executions": ag.total_agent_executions,
            "agent_success_rate": ag.agent_success_rate,
            "total_recommendations": ag.total_recommendations,
        }

    if rt == ReportType.RECOVERY_PERFORMANCE:
        rec = compute_recovery_analytics(db, s, e, simulation_id=sim_id, include_simulations=inc_sim)
        comp = compute_performance_comparisons(
            db, simulation_id=sim_id, include_simulations=inc_sim, start_date=s, end_date=e
        )
        builder.add_section_heading("Recovery & Optimization Engine Summary")
        builder.add_paragraph(
            f"Summary of {rec.total_recovery_plans} optimization plans ({rec.executed_plans} executed, "
            f"{rec.total_recovered_orders} orders actually recovered)."
        )
        builder.add_kpi_table(
            ["Recovery Metric", "Value", "Classification"],
            [
                ["Total Recovery Plans", rec.total_recovery_plans, "ACTUAL"],
                ["Pending Approval / Approved Plans", f"{rec.pending_approval_plans} / {rec.approved_plans}", "ACTUAL"],
                ["Executed / Partially Executed Plans", f"{rec.executed_plans} / {rec.partially_executed_plans}", "ACTUAL"],
                ["Rejected / Failed / Infeasible Plans", f"{rec.rejected_plans} / {rec.failed_plans} / {rec.infeasible_plans}", "ACTUAL"],
                ["Recovery Plan Execution Success Rate (%)", f"{rec.recovery_success_rate}%", "ACTUAL"],
                ["Proposed Order Reassignments", rec.total_reassigned_orders_proposed, "ESTIMATED"],
                ["Actual Recovered Orders (Executed)", rec.total_recovered_orders, "ACTUAL"],
                ["Recovery Actions (Executed / Total)", f"{rec.executed_actions} / {rec.total_recovery_actions}", "ACTUAL"],
                ["Estimated Delay Reduction (min)", rec.estimated_delay_reduction_minutes, "ESTIMATED"],
                ["Estimated Distance Change (km)", rec.estimated_distance_change_km, "ESTIMATED"],
                ["Estimated Recovery Cost", rec.estimated_cost_change, "ESTIMATED"],
            ],
            col_widths=[210, 120, 120],
        )
        builder.add_section_heading("Before vs After Recovery Comparison")
        builder.add_kpi_table(
            ["Metric", "Before", "After", "Diff", "% Change", "Improved"],
            [
                [
                    m.label,
                    m.before_value,
                    m.after_value,
                    m.absolute_difference,
                    f"{m.percentage_change}%" if m.percentage_change is not None else "N/A",
                    str(m.is_improved) if m.is_improved is not None else "N/A",
                ]
                for m in comp.metrics
            ],
            col_widths=[140, 60, 60, 60, 65, 65],
        )
        builder.add_notes_section(
            comp.notes
            + [
                "Actual recovered orders count only orders from EXECUTED or PARTIALLY_EXECUTED recovery plans.",
            ],
            rec.unavailable_metrics,
        )
        return {
            "total_recovery_plans": rec.total_recovery_plans,
            "executed_plans": rec.executed_plans,
            "total_recovered_orders": rec.total_recovered_orders,
            "recovery_success_rate": rec.recovery_success_rate,
        }

    # Default: SIMULATION_REPORT
    sim = compute_simulation_analytics(db, s, e, simulation_id=sim_id)
    builder.add_section_heading("Digital Twin Simulation Performance Summary")
    builder.add_paragraph(
        f"Evaluation of {sim.total_simulations} digital twin simulation runs and {sim.total_simulated_vehicles} simulated vehicles."
    )
    builder.add_kpi_table(
        ["Simulation Metric", "Value", "Classification"],
        [
            ["Total Simulations", sim.total_simulations, "SIMULATED"],
            ["Running / Paused Simulations", f"{sim.running_simulations} / {sim.paused_simulations}", "SIMULATED"],
            ["Completed Simulations", sim.completed_simulations, "SIMULATED"],
            ["Stopped (Cancelled) / Failed Simulations", f"{sim.cancelled_simulations} / {sim.failed_simulations}", "SIMULATED"],
            ["Total Simulated Vehicles", sim.total_simulated_vehicles, "SIMULATED"],
            ["Total Simulated Distance (km)", sim.total_simulated_distance_km, sim.metric_classifications.get("total_simulated_distance_km", "UNAVAILABLE")],
            ["Average Simulation Duration (sec)", sim.average_simulation_duration_seconds, sim.metric_classifications.get("average_simulation_duration_seconds", "UNAVAILABLE")],
            ["Simulated Disruptions", sim.simulated_disruptions_count, "SIMULATED"],
            ["Simulated Recovery Plans", sim.simulated_recovery_plans_count, "SIMULATED"],
            ["Simulated Recovery Success Rate (%)", f"{sim.simulated_recovery_success_rate}%", "SIMULATED"],
        ],
        col_widths=[210, 120, 120],
    )
    builder.add_bar_chart(
        "Simulations by Lifecycle Status",
        list(sim.simulations_by_status.keys()),
        [float(v) for v in sim.simulations_by_status.values()],
    )
    builder.add_notes_section(
        [
            "Simulation metrics are strictly isolated from operational logistics records.",
            "Simulated distance is calculated from SimulationTelemetry coordinate trails.",
        ],
        sim.unavailable_metrics,
    )
    return {
        "total_simulations": sim.total_simulations,
        "completed_simulations": sim.completed_simulations,
        "total_simulated_vehicles": sim.total_simulated_vehicles,
        "simulated_disruptions_count": sim.simulated_disruptions_count,
    }


def generate_pdf_report(
    db: Session,
    req: ReportGenerateRequest,
    user_id: Optional[str] = None,
) -> ReportMetadata:
    # Validate date range upfront (raises InvalidDateRangeError if start_date > end_date)
    filter_meta = build_filter_meta(
        start_date=req.start_date,
        end_date=req.end_date,
        simulation_id=req.simulation_id,
        include_simulations=req.include_simulations,
    )

    now = datetime.now(timezone.utc)
    short_uid = uuid.uuid4().hex[:8].upper()
    report_code = f"RPT-{now.strftime('%Y%m%d')}-{short_uid}"

    default_titles = {info.report_type: info.title for info in REPORT_TYPE_DEFINITIONS}
    title = (req.title or default_titles.get(req.report_type.value, "LOGIPULSE Analytics Report")).strip()

    safe_file_ref = sanitize_filename(f"{report_code}_{req.report_type.value.lower()}.pdf")
    target_path = resolve_safe_report_path(safe_file_ref)

    filter_summary = {
        "start_date": filter_meta.start_date.isoformat() if filter_meta.start_date else None,
        "end_date": filter_meta.end_date.isoformat() if filter_meta.end_date else None,
        "simulation_id": filter_meta.simulation_id,
        "include_simulations": filter_meta.include_simulations,
        "data_scope": filter_meta.data_scope,
    }

    try:
        builder = PDFReportBuilder(
            title=title,
            report_code=report_code,
            report_type=req.report_type.value,
            generated_at=now,
            filter_summary=filter_summary,
        )
        summary_metrics = _populate_report_content(builder, db, req)
        pdf_bytes = builder.build_pdf_bytes()
        target_path.write_bytes(pdf_bytes)
        file_size = len(pdf_bytes)
    except Exception as exc:
        failed_meta = ReportMetadata(
            report_code=report_code,
            report_type=req.report_type.value,
            title=title,
            status=ReportStatus.FAILED.value,
            requested_by_user_id=user_id,
            simulation_id=req.simulation_id,
            include_simulations=req.include_simulations,
            start_date=filter_meta.start_date,
            end_date=filter_meta.end_date,
            filters=req.filters,
            summary_metrics=None,
            include_charts=req.include_charts,
            file_reference=None,
            file_name=None,
            file_size=None,
            generated_at=None,
            error_message=str(exc)[:1000],
        )
        db.add(failed_meta)
        db.commit()
        db.refresh(failed_meta)
        raise ReportGenerationError(f"Failed to generate PDF report: {exc}") from exc

    report_meta = ReportMetadata(
        report_code=report_code,
        report_type=req.report_type.value,
        title=title,
        status=ReportStatus.COMPLETED.value,
        requested_by_user_id=user_id,
        simulation_id=req.simulation_id,
        include_simulations=req.include_simulations,
        start_date=filter_meta.start_date,
        end_date=filter_meta.end_date,
        filters=req.filters,
        summary_metrics=summary_metrics,
        include_charts=req.include_charts,
        file_reference=safe_file_ref,
        file_name=safe_file_ref,
        file_size=file_size,
        generated_at=now,
        error_message=None,
    )
    db.add(report_meta)
    db.commit()
    db.refresh(report_meta)
    return report_meta


def list_reports(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    report_type: Optional[str] = None,
    status: Optional[str] = None,
) -> Tuple[List[ReportMetadata], int]:
    stmt = select(ReportMetadata)
    count_stmt = select(func.count(ReportMetadata.id))

    if report_type:
        stmt = stmt.where(ReportMetadata.report_type == report_type)
        count_stmt = count_stmt.where(ReportMetadata.report_type == report_type)
    if status:
        stmt = stmt.where(ReportMetadata.status == status)
        count_stmt = count_stmt.where(ReportMetadata.status == status)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.execute(
            stmt.order_by(ReportMetadata.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()
    )
    return items, total


def get_report_by_id(db: Session, report_id: str) -> ReportMetadata:
    report = db.get(ReportMetadata, report_id)
    if not report:
        raise ReportNotFoundError(f"Report '{report_id}' not found.")
    return report
