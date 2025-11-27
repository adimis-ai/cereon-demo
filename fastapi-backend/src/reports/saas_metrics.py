# fastapi-backend/src/reports/saas_metrics.py

from cereon_sdk.fastapi import (
    BaseCard,
    ChartCardRecord,
    TableCardRecord,
    NumberCardRecord,
)

from fastapi import FastAPI
from typing import List, AsyncIterable
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def _generate_revenue_series(days: int = 30):
    today = datetime.utcnow().date()
    data = []
    mrr = 10000
    for i in range(days):
        day = today - timedelta(days=days - i - 1)
        # simple growth/noise model
        new = max(0, int((mrr * 0.01) * (1 + (i / days) * 0.5)))
        expansion = int(new * 0.3)
        churn = int(new * 0.1)
        mrr = mrr + new + expansion - churn
        data.append(
            {
                "date": day.isoformat(),
                "mrr": mrr,
                "new": new,
                "expansion": expansion,
            }
        )
    return data


def _parse_date(s: Optional[str]):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None


def _apply_filters_to_series(series: list, filters: Optional[Dict[str, Any]]):
    if not filters:
        return series

    start = _parse_date(filters.get("start_date") if isinstance(filters, dict) else None)
    end = _parse_date(filters.get("end_date") if isinstance(filters, dict) else None)

    filtered = []
    for row in series:
        row_date = _parse_date(row.get("date"))
        if start and row_date and row_date < start:
            continue
        if end and row_date and row_date > end:
            continue
        # optional numeric min filter (applies to mrr or value)
        min_value = None
        try:
            min_value = (
                float(filters.get("min_value")) if filters and "min_value" in filters else None
            )
        except Exception:
            min_value = None
        if min_value is not None:
            # check mrr/new/expansion/value keys
            val = None
            for k in ("mrr", "value", "new", "expansion"):
                if k in row:
                    val = row[k]
                    break
            if val is None or float(val) < min_value:
                continue

        filtered.append(row)

    return filtered


class MrrOverviewCard(BaseCard[NumberCardRecord]):
    kind = "number"
    card_id = "mrr_overview"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = NumberCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[NumberCardRecord]:
        # Compute basic KPIs from generated series
        series = _generate_revenue_series(28)
        latest = series[-1]["mrr"] if series else 0
        prev = series[-2]["mrr"] if len(series) > 1 else None

        delta_pct = (latest - prev) / prev * 100 if prev and prev != 0 else 0

        payload = {
            "kind": "number",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {
                "value": latest,
                "previousValue": prev,
                "label": "Monthly Recurring Revenue",
                "meta": {"unit": "USD", "as_of": series[-1]["date"]},
                "trendPercentage": round(delta_pct, 2),
            },
        }

        return [cls.response_model(**payload)]


class SaasUserGrowthCard(BaseCard[NumberCardRecord]):
    kind = "number"
    card_id = "saas_user_growth"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = NumberCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[NumberCardRecord]:
        dau = 4200
        wau = 15000
        mau = 48000
        activation = 0.27
        new_users = 350
        payload = {
            "kind": "number",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {
                "value": dau,
                "previousValue": dau - 120,
                "label": "Daily Active Users",
                "meta": {
                    "dau": dau,
                    "wau": wau,
                    "mau": mau,
                    "activation_rate": activation,
                    "new_users": new_users,
                    "unit": "users",
                },
                "trendPercentage": round((120 / (dau - 120)) * 100, 2),
            },
        }
        return [cls.response_model(**payload)]


class RevenueTrendCard(BaseCard[ChartCardRecord]):
    kind = "recharts:line"
    card_id = "revenue_trend"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "streaming-http"

    @classmethod
    async def handler(cls, ctx=None) -> AsyncIterable[ChartCardRecord]:
        # Stream time series in chunks (simulate streaming-http)
        series = _generate_revenue_series(28)

        chunk_size = 7
        # send non-overlapping chunks to reduce repeated payloads
        for i in range(0, len(series), chunk_size):
            chunk = series[i : i + chunk_size]
            payload = {
                "kind": "line",
                "report_id": cls.report_id,
                "card_id": cls.card_id,
                "data": {"data": chunk},
                "meta": {"startedAt": datetime.utcnow().isoformat() + "Z"},
            }
            yield cls.response_model(**payload)


class RevenueAreaTrendCard(BaseCard[ChartCardRecord]):
    kind = "recharts:area"
    card_id = "revenue_area_trend"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "streaming-http"

    @classmethod
    async def handler(cls, ctx=None) -> AsyncIterable[ChartCardRecord]:
        series = _generate_revenue_series(28)
        # yield recent weekly windows (max 7 items) to avoid sending full cumulative history
        for i in range(0, len(series), 7):
            window = series[i : i + 7]
            data = [
                {
                    "date": row["date"],
                    "cumulative_mrr": row["mrr"],
                    "rolling_new": sum(r["new"] for r in series[max(0, idx - 6) : idx + 1]),
                }
                for idx, row in enumerate(window, start=i)
            ]
            payload = {
                "kind": "area",
                "report_id": cls.report_id,
                "card_id": cls.card_id,
                "data": {"data": data},
                "meta": {"startedAt": datetime.utcnow().isoformat() + "Z"},
            }
            yield cls.response_model(**payload)


class PlansBreakdownCard(BaseCard[ChartCardRecord]):
    kind = "recharts:bar"
    card_id = "plans_breakdown"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        data = [
            {"plan": "Free", "active_users": 1200, "seats": 1200},
            {"plan": "Startup", "active_users": 800, "seats": 2400},
            {"plan": "Growth", "active_users": 420, "seats": 2520},
            {"plan": "Enterprise", "active_users": 80, "seats": 1600},
        ]
        # no server-side filters for this demo card (frontend controls view)

        payload = {
            "kind": "bar",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class RevenueSharePieCard(BaseCard[ChartCardRecord]):
    kind = "recharts:pie"
    card_id = "revenue_share_pie"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        data = [
            {"name": "Product A", "value": 56000},
            {"name": "Product B", "value": 32000},
            {"name": "Service", "value": 12000},
            {"name": "Channel", "value": 8000},
        ]
        # no server-side filters for this demo card

        payload = {
            "kind": "pie",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class FeatureUsageRadarCard(BaseCard[ChartCardRecord]):
    kind = "recharts:radar"
    card_id = "feature_usage_radar"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        data = [
            {"subject": "Onboarding", "core": 80, "advanced": 60},
            {"subject": "Reporting", "core": 70, "advanced": 40},
            {"subject": "Integrations", "core": 65, "advanced": 55},
            {"subject": "API", "core": 50, "advanced": 30},
        ]
        # no server-side filters for this demo card

        payload = {
            "kind": "radar",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class HealthRadialCard(BaseCard[ChartCardRecord]):
    kind = "recharts:radial"
    card_id = "health_radial"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        data_point = {
            "online": 82,
            "degraded": 25,
            "offline": 49,
            "maintenance": 10,
            "unknown": 22,
        }
        # no server-side filters for this demo card

        payload = {
            "kind": "radial",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": [data_point]},
        }
        return [cls.response_model(**payload)]


class ChurnCohortCard(BaseCard[TableCardRecord]):
    kind = "table"
    card_id = "churn_cohort"
    report_id = "saas_metrics"
    route_prefix = "/cards"
    response_model = TableCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[TableCardRecord]:
        filters = cls._get_filters_from_ctx(ctx)
        print("[ChurnCohortCard] Cohort filters:", type(filters), filters)

        rows = []
        # smaller cohort months to reduce payload
        for m in range(3):
            row = {"cohort_month": f"2025-0{m+1}", "month_0": 1.0}
            for off in range(1, 3):
                row[f"month_{off}"] = round(1.0 - 0.1 * off - 0.02 * m, 2)
            rows.append(row)
        # optional filter to limit to recent cohorts
        if filters and isinstance(filters, dict):
            cohort = filters.get("cohort_month")
            if cohort:
                rows = [r for r in rows if r.get("cohort_month") == cohort]

        payload = {
            "kind": "table",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"rows": rows, "columns": list(rows[0].keys()) if rows else []},
        }
        return [cls.response_model(**payload)]
