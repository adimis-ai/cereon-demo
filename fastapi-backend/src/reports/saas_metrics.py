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


class MrrOverviewCard(BaseCard[NumberCardRecord]):
    kind = "number"
    card_id = "mrr_overview"
    report_id = "saas_metrics"
    route_prefix = "/cards/mrr_overview"
    response_model = NumberCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[NumberCardRecord]:
        # Compute basic KPIs from generated series
        series = _generate_revenue_series(90)
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
    route_prefix = "/cards/saas_user_growth"
    response_model = NumberCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[NumberCardRecord]:
        # Synthetic user metrics
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
                "label": "DAU",
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
    kind = "line"
    card_id = "revenue_trend"
    report_id = "saas_metrics"
    route_prefix = "/cards/revenue_trend"
    response_model = ChartCardRecord
    transport = "streaming-http"

    @classmethod
    async def handler(cls, ctx=None) -> AsyncIterable[ChartCardRecord]:
        # Stream time series in chunks (simulate streaming-http)
        series = _generate_revenue_series(90)

        async def _gen():
            chunk_size = 7
            for i in range(0, len(series), chunk_size):
                chunk = series[: i + chunk_size]
                payload = {
                    "kind": "line",
                    "report_id": cls.report_id,
                    "card_id": cls.card_id,
                    "data": {"data": chunk},
                    "meta": {"startedAt": datetime.utcnow().isoformat() + "Z"},
                }
                yield cls.response_model(**payload)

        return _gen()


class RevenueAreaTrendCard(BaseCard[ChartCardRecord]):
    kind = "area"
    card_id = "revenue_area_trend"
    report_id = "saas_metrics"
    route_prefix = "/cards/revenue_area_trend"
    response_model = ChartCardRecord
    transport = "streaming-http"

    @classmethod
    async def handler(cls, ctx=None) -> AsyncIterable[ChartCardRecord]:
        series = _generate_revenue_series(90)

        async def _gen():
            # yield cumulative view
            cumulative = []
            for i, row in enumerate(series):
                cumulative.append(
                    {
                        "date": row["date"],
                        "cumulative_mrr": row["mrr"],
                        "rolling_new": sum(r["new"] for r in series[max(0, i - 6) : i + 1]),
                    }
                )
                if i % 7 == 0:
                    payload = {
                        "kind": "area",
                        "report_id": cls.report_id,
                        "card_id": cls.card_id,
                        "data": {"data": cumulative.copy()},
                    }
                    yield cls.response_model(**payload)

        return _gen()


class PlansBreakdownCard(BaseCard[ChartCardRecord]):
    kind = "bar"
    card_id = "plans_breakdown"
    report_id = "saas_metrics"
    route_prefix = "/cards/plans_breakdown"
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
        payload = {
            "kind": "bar",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class RevenueSharePieCard(BaseCard[ChartCardRecord]):
    kind = "pie"
    card_id = "revenue_share_pie"
    report_id = "saas_metrics"
    route_prefix = "/cards/revenue_share_pie"
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
        payload = {
            "kind": "pie",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class FeatureUsageRadarCard(BaseCard[ChartCardRecord]):
    kind = "radar"
    card_id = "feature_usage_radar"
    report_id = "saas_metrics"
    route_prefix = "/cards/feature_usage_radar"
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
        payload = {
            "kind": "radar",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class HealthRadialCard(BaseCard[ChartCardRecord]):
    kind = "radial"
    card_id = "health_radial"
    report_id = "saas_metrics"
    route_prefix = "/cards/health_radial"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        data = [
            {"name": "Online", "value": 92},
            {"name": "Degraded", "value": 5},
            {"name": "Offline", "value": 3},
        ]
        payload = {
            "kind": "radial",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": data},
        }
        return [cls.response_model(**payload)]


class ChurnCohortCard(BaseCard[TableCardRecord]):
    kind = "table"
    card_id = "churn_cohort"
    report_id = "saas_metrics"
    route_prefix = "/cards/churn_cohort"
    response_model = TableCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[TableCardRecord]:
        # Simple static cohort matrix
        rows = []
        # cohort months
        for m in range(6):
            row = {"cohort_month": f"2025-0{m+1}", "month_0": 1.0}
            for off in range(1, 6):
                row[f"month_{off}"] = round(1.0 - 0.1 * off - 0.02 * m, 2)
            rows.append(row)

        payload = {
            "kind": "table",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"rows": rows, "columns": list(rows[0].keys()) if rows else []},
        }
        return [cls.response_model(**payload)]
