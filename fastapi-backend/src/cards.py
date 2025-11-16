from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Optional

from neo4j import AsyncGraphDatabase

from cereon_sdk import BaseCard
from cereon_sdk import (
    ChartCardRecord,
    ChartCardData,
    TableCardRecord,
    TableCardData,
    NumberCardRecord,
    NumberCardData,
    NumberCardMetadata,
    MarkdownCardRecord,
    MarkdownCardData,
    QueryMetadata,
)
from settings import get_settings

# ---------------------------------------------------------------------------
# Neo4j Driver Helpers
# ---------------------------------------------------------------------------

_driver = None


def _get_driver():
    """Return (and lazily create) the Async Neo4j driver using settings.

    The global is intentionally simple; FastAPI lifespan in `main.py` already
    initializes Neo4j separately for other components—this serves cards only.
    """
    global _driver
    if _driver:
        return _driver
    s = get_settings()
    if not s.neo4j_uri:
        return None
    auth = None
    if s.neo4j_user and s.neo4j_password:
        auth = (s.neo4j_user, s.neo4j_password)
    _driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=auth)
    return _driver


async def _run_cypher(cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Execute a Cypher query and return list of dictionaries.

    Returns empty list if driver unavailable or query fails (best-effort; cards
    should not crash dashboards on intermittent graph issues).
    """
    driver = _get_driver()
    if driver is None:
        return []
    params = params or {}
    try:
        async with driver.session() as session:
            result = await session.run(cypher, params)
            records = []
            async for record in result:
                records.append(dict(record))
            return records
    except Exception as e:
        print(f"Neo4j query error: {e}")
        import traceback
        traceback.print_exc()
        return []


# ---------------------------------------------------------------------------
# Utility / Transformation Helpers
# ---------------------------------------------------------------------------


def _meta(start: float) -> QueryMetadata:
    """Build QueryMetadata with elapsedMs."""
    end = time.perf_counter()
    return QueryMetadata(
        startedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(start))),
        finishedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(end))),
        elapsedMs=int((end - start) * 1000),
    )


def _pivot(
    rows: List[Dict[str, Any]], index_field: str, series_field: str, value_field: str
) -> List[Dict[str, Any]]:
    """Pivot long-form rows into wide-form multi-series.

    Input example rows: {date: '2024-01-01', exchange: 'NYSE', volume: 123}
    Output: [{date: '2024-01-01', NYSE: 123, NASDAQ: 456}, ...]
    """
    grid: Dict[Any, Dict[str, Any]] = {}
    series_values: set[str] = set()
    for r in rows:
        idx = r.get(index_field)
        series = r.get(series_field)
        val = r.get(value_field)
        if idx is None or series is None:
            continue
        series_values.add(str(series))
        row = grid.setdefault(idx, {index_field: idx})
        row[str(series)] = val

    # Sort index if temporal
    def _sort_key(v):
        return v

    ordered = [grid[k] for k in sorted(grid.keys(), key=_sort_key)]
    # Ensure all series present (fill None)
    for row in ordered:
        for s in series_values:
            row.setdefault(s, None)
    return ordered


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _single_chart_record(
    kind: str, report_id: str, card_id: str, rows: List[Dict[str, Any]], start: float
) -> ChartCardRecord:
    return ChartCardRecord(
        kind=kind,
        report_id=report_id,
        card_id=card_id,
        data=ChartCardData(data=rows),
        meta=_meta(start),
    )


def _single_table_record(
    report_id: str, card_id: str, rows: List[Dict[str, Any]]
) -> TableCardRecord:
    columns = sorted(list({k for r in rows for k in r.keys()})) if rows else []
    return TableCardRecord(
        report_id=report_id,
        card_id=card_id,
        data=TableCardData(rows=rows, columns=columns, totalCount=len(rows)),
        meta=_meta(time.perf_counter()),
    )


def _number_record(
    report_id: str,
    card_id: str,
    value: float,
    label: str,
    previous: Optional[float] = None,
    unit: Optional[str] = None,
) -> NumberCardRecord:
    trend = None
    trend_pct = None
    if previous is not None:
        if value > previous:
            trend = "up"
        elif value < previous:
            trend = "down"
        else:
            trend = "neutral"
        if previous != 0:
            trend_pct = ((value - previous) / previous) * 100.0
    return NumberCardRecord(
        report_id=report_id,
        card_id=card_id,
        data=NumberCardData(
            value=value, previousValue=previous, trend=trend, trendPercentage=trend_pct, label=label
        ),
        meta=NumberCardMetadata(
            unit=unit, format="number", startedAt=None, finishedAt=None, elapsedMs=None
        ),
    )


def _markdown_record(report_id: str, card_id: str, content: str) -> MarkdownCardRecord:
    return MarkdownCardRecord(
        report_id=report_id,
        card_id=card_id,
        data=MarkdownCardData(content=content),
        meta=_meta(time.perf_counter()),
    )


# Base naming constants
REPORT_ID = "overview"
ROUTE_PREFIX = "/api/cards/overview"


# ---------------------------------------------------------------------------
# Chart Cards (HTTP)
# ---------------------------------------------------------------------------


class MarketVolumeCard(BaseCard[ChartCardRecord]):
    kind = "area"
    card_id = "market_volume"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        params = (ctx or {}).get("params", {})
        dimension = params.get("dimension") or "exchange"  # or "asset_class"
        # Aggregate traded volume per date & dimension
        cypher = f"""
		MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
		WITH date(t.ts) AS d, i.{dimension} AS dim, sum(t.qty) AS volume
		RETURN toString(d) AS date, dim AS dimension, volume
		ORDER BY date ASC
		"""
        rows = await _run_cypher(cypher)
        pivoted = _pivot(rows, "date", "dimension", "volume")
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, pivoted, start)
        return [record]


class PriceMovementCard(BaseCard[ChartCardRecord]):
    kind = "line"
    card_id = "price_movement"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        params = (ctx or {}).get("params", {})
        tickers_param = params.get("tickers")
        tickers: List[str] = []
        if isinstance(tickers_param, str):
            tickers = [t.strip() for t in tickers_param.split(",") if t.strip()]
        # If no tickers provided pick top 5 by volume
        if not tickers:
            top = await _run_cypher(
                """
				MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
				WITH i.ticker AS ticker, sum(t.qty) AS volume
				ORDER BY volume DESC LIMIT 5
				RETURN ticker
				"""
            )
            tickers = [r.get("ticker") for r in top if r.get("ticker")]
        cypher = """
		MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
		WHERE i.ticker IN $tickers
		WITH i.ticker AS ticker, date(t.ts) AS d, avg(t.price) AS avg_price
		RETURN toString(d) AS date, ticker, avg_price ORDER BY date ASC
		"""
        rows = await _run_cypher(cypher, {"tickers": tickers})
        pivoted = _pivot(rows, "date", "ticker", "avg_price")
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, pivoted, start)
        return [record]


class VWAPvsOrderSpreadCard(BaseCard[ChartCardRecord]):
    kind = "line"
    card_id = "vwap_vs_median_order_price"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        params = (ctx or {}).get("params", {})
        # allow caller to limit number of returned tickers (default 20) and page via offset
        try:
            limit = int(params.get("limit") if params.get("limit") is not None else 20)
        except Exception:
            limit = 20
        try:
            offset = int(params.get("offset") or 0)
        except Exception:
            offset = 0

        # Safety clamps to prevent very large responses / abuse
        MAX_LIMIT = 100
        if limit < 1:
            limit = 1
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT
        if offset < 0:
            offset = 0

        cypher = """
		MATCH (o:Order)-[:ORDER_ON]->(i:Instrument)
		WITH i.ticker AS ticker, sum(o.qty * o.price) AS notional, sum(o.qty) AS total_qty,
			 percentileCont(o.price, 0.5) AS median_price
		WITH ticker, (CASE WHEN total_qty=0 THEN 0 ELSE notional / total_qty END) AS vwap, median_price, total_qty
		RETURN ticker, vwap, median_price, total_qty
		ORDER BY total_qty DESC SKIP $offset LIMIT $limit
		"""
        rows = await _run_cypher(cypher, {"limit": limit, "offset": offset})
        record_rows = [
            {
                "ticker": r.get("ticker"),
                "VWAP": r.get("vwap"),
                "MedianOrderPrice": r.get("median_price"),
            }
            for r in rows
        ]
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, record_rows, start)
        return [record]


class TradeCountAvgSizeCard(BaseCard[ChartCardRecord]):
    kind = "line"
    card_id = "trade_count_avg_size"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (t:Trade)
		WITH date(t.ts) AS d, count(t) AS trade_count, avg(t.qty) AS avg_qty
		RETURN toString(d) AS date, trade_count, avg_qty ORDER BY date ASC
		"""
        rows = await _run_cypher(cypher)
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


class TopInstrumentsByVolumeCard(BaseCard[ChartCardRecord]):
    kind = "bar"
    card_id = "top_instruments_by_volume"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        params = (ctx or {}).get("params", {})
        limit = int(params.get("limit") or 10)
        cypher = """
		MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
		WITH i.ticker AS ticker, sum(t.qty) AS volume
		RETURN ticker, volume ORDER BY volume DESC LIMIT $limit
		"""
        rows = await _run_cypher(cypher, {"limit": limit})
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


class CorrelationRadarCard(BaseCard[ChartCardRecord]):
    kind = "radar"
    card_id = "correlation_radar"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        params = (ctx or {}).get("params", {})
        ticker = params.get("ticker") or params.get("instrument")
        if not ticker:
            # pick top volume instrument as default
            default = await _run_cypher(
                """
				MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
				WITH i.ticker AS ticker, sum(t.qty) AS volume
				RETURN ticker ORDER BY volume DESC LIMIT 1
				"""
            )
            ticker = default[0]["ticker"] if default else None
        if not ticker:
            return [_single_chart_record(cls.kind, cls.report_id, cls.card_id, [], start)]
        cypher = """
        MATCH (i:Instrument {ticker:$ticker})-[r:CORRELATED_WITH]->(j:Instrument)
        RETURN j.ticker AS peer, coalesce(j.exchange,'') AS exchange, r.corr AS correlation, r.window AS window
        ORDER BY correlation DESC LIMIT 50
        """
        rows = await _run_cypher(cypher, {"ticker": ticker})
        record_rows = [
            {"peer": r.get("peer"), "correlation": r.get("correlation"), "window": r.get("window")}
            for r in rows
        ]
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, record_rows, start)
        return [record]


class SignalScoreTrendsCard(BaseCard[ChartCardRecord]):
    kind = "line"
    card_id = "signal_score_trends"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (s:Signal)
		WITH date(s.ts) AS d, s.name AS name, avg(s.score) AS score
		RETURN toString(d) AS date, name, score ORDER BY date ASC
		"""
        rows = await _run_cypher(cypher)
        pivoted = _pivot(rows, "date", "name", "score")
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, pivoted, start)
        return [record]


class EventImpactChartCard(BaseCard[ChartCardRecord]):
    kind = "area"
    card_id = "event_impact_chart"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        params = (ctx or {}).get("params", {})
        event_id = params.get("event_id")
        if not event_id:
            # pick latest event
            latest = await _run_cypher(
                """
				MATCH (e:Event)
				RETURN e.event_id AS event_id, e.ts AS ts
				ORDER BY e.ts DESC LIMIT 1
				"""
            )
            event_id = latest[0]["event_id"] if latest else None
        if not event_id:
            return [_single_chart_record(cls.kind, cls.report_id, cls.card_id, [], start)]
        cypher = """
		MATCH (e:Event {event_id:$event_id})
		MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
		WHERE t.ts >= e.ts - duration('P1D') AND t.ts <= e.ts + duration('P1D')
		WITH e, t
		RETURN toString(t.ts) AS ts, t.price AS price, e.event_id AS event_id
		ORDER BY ts ASC
		"""
        rows = await _run_cypher(cypher, {"event_id": event_id})
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


class OrderToTradeConversionCard(BaseCard[ChartCardRecord]):
    kind = "bar"
    card_id = "order_to_trade_conversion"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (o:Order)-[:ORDER_ON]->(i:Instrument)
		WITH i.asset_class AS bucket, count(o) AS orders
		MATCH (t:Trade)-[:EXECUTES]->(o2:Order)-[:ORDER_ON]->(i2:Instrument)
		WITH bucket, orders, i2.asset_class AS bucket2, count(t) AS trades
		WHERE bucket = bucket2
		WITH bucket AS asset_class, orders, trades, (CASE WHEN orders=0 THEN 0 ELSE toFloat(trades)/orders END) AS conversion
		RETURN asset_class, orders, trades, conversion ORDER BY conversion DESC
		"""
        rows = await _run_cypher(cypher)
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


class SpreadDistributionCard(BaseCard[ChartCardRecord]):
    kind = "bar"
    card_id = "spread_distribution"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (t:Trade)-[:EXECUTES]->(o:Order)
		WITH abs(t.price - o.price) AS spread
		WITH CASE
		  WHEN spread < 0.01 THEN '<0.01'
		  WHEN spread < 0.05 THEN '0.01-0.05'
		  WHEN spread < 0.10 THEN '0.05-0.10'
		  ELSE '>=0.10' END AS bucket, count(*) AS cnt
		RETURN bucket, cnt ORDER BY bucket ASC
		"""
        rows = await _run_cypher(cypher)
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


class SectorExposurePieCard(BaseCard[ChartCardRecord]):
    kind = "pie"
    card_id = "sector_exposure_pie"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (i:Instrument)-[:ISSUED_BY]->(iss:Issuer)
		WITH iss.sector AS sector, count(distinct i) AS instruments
		RETURN sector, instruments ORDER BY instruments DESC
		"""
        rows = await _run_cypher(cypher)
        # Pie chart expects label/value style; rename
        record_rows = [
            {"label": r.get("sector") or "(unknown)", "value": r.get("instruments")} for r in rows
        ]
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, record_rows, start)
        return [record]


class InstrumentHealthRadialCard(BaseCard[ChartCardRecord]):
    kind = "radial"
    card_id = "instrument_health_radial"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (i:Instrument)
		OPTIONAL MATCH (s:Signal)-[:APPLIES_TO]->(i)
		WITH i, avg(s.score) AS avg_signal
		OPTIONAL MATCH (e:Event)-[:AFFECTS]->(i)
		WITH i, avg_signal, avg(e.sentiment) AS avg_sentiment
		OPTIONAL MATCH (t:Trade)-[:EXECUTES_ON]->(i)
		WITH i, avg_signal, avg_sentiment, count(t) AS trade_count
		RETURN i.ticker AS ticker, avg_signal, avg_sentiment, trade_count LIMIT 50
		"""
        rows = await _run_cypher(cypher)
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


class TopSignalsLeaderboardCard(BaseCard[ChartCardRecord]):
    kind = "bar"
    card_id = "top_signals_leaderboard"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        start = time.perf_counter()
        cypher = """
		MATCH (s:Signal)
		RETURN s.name AS name, avg(s.score) AS avg_score, count(*) AS observations
		ORDER BY avg_score DESC LIMIT 20
		"""
        rows = await _run_cypher(cypher)
        record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, rows, start)
        return [record]


# ---------------------------------------------------------------------------
# Streaming WebSocket Card
# ---------------------------------------------------------------------------


class PriceMovementRealtimeCard(BaseCard[ChartCardRecord]):
    kind = "line"
    card_id = "price_movement_realtime"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = ChartCardRecord
    transport = "websocket"

    POLL_INTERVAL_SEC = 1.0
    STREAMING_MS = 1000
    STREAMING_BATCH = 100

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        params = (ctx or {}).get("params", {})
        tickers_param = params.get("tickers")
        tickers: List[str] = []
        if isinstance(tickers_param, str):
            tickers = [t.strip() for t in tickers_param.split(",") if t.strip()]
        # If not provided choose top 5 instruments
        if not tickers:
            tickers = [f"TICKER{i}" for i in range(1, 6)]

        # Import random locally to avoid changing top-level imports
        import random

        # Time origin and per-ticker parameters for deterministic-ish waveform
        now_origin = time.time()
        phases: Dict[str, float] = {t: random.uniform(0, 2 * math.pi) for t in tickers}
        baselines: Dict[str, float] = {t: random.uniform(150.0, 165.0) for t in tickers}
        amplitudes: Dict[str, float] = {t: random.uniform(20.0, 35.0) for t in tickers}

        # Convert batch size
        batch = max(1, int(cls.STREAMING_BATCH))

        # Use an async generator loop to yield batches of simulated ticks.
        while True:
            start = time.perf_counter()
            ticks: List[Dict[str, Any]] = []

            # Generate `batch` ticks distributed across tickers over the streaming window
            # We'll iterate tickers and append until we reach the batch size to keep rhythm
            for t in tickers:
                if len(ticks) >= batch:
                    break

                elapsed = time.time() - now_origin

                # slow modulation to simulate BPM drift
                slow_mod = math.sin(elapsed * 0.25 + phases[t]) * 2.0

                # heartbeat/beat component: create a pulse-like waveform
                # faster oscillation; positive half-waves create spikes
                beat = math.sin(elapsed * 2.0 + phases[t] * 0.5)
                spike = max(0.0, beat)
                spike_shaped = (spike ** 2) * amplitudes[t] * 1.5

                # small random jitter
                jitter = random.uniform(-1.0, 1.0)

                value = baselines[t] + slow_mod + spike_shaped + jitter

                # Clamp to band 120..200 bps
                value = max(120.0, min(200.0, value))

                # timestamp: ISO-ish string (match existing format used elsewhere)
                ts = time.time()
                ts_str = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime(ts))

                ticks.append({"ticker": t, "price": round(value, 2), "ts": ts_str})

            # Build record and yield
            record = _single_chart_record(cls.kind, cls.report_id, cls.card_id, ticks, start)
            yield record

            # Wait for next poll
            await asyncio.sleep(cls.POLL_INTERVAL_SEC)


# ---------------------------------------------------------------------------
# Table Cards (HTTP)
# ---------------------------------------------------------------------------


class TopInstrumentsTableCard(BaseCard[TableCardRecord]):
    kind = "table"  # model constrains literal
    card_id = "top_instruments_table"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = TableCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        params = (ctx or {}).get("params", {})
        limit = int(params.get("limit") or 25)
        cypher = """
		MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
		WITH i, sum(t.qty) AS volume
		RETURN i.ticker AS ticker, i.exchange AS exchange, i.asset_class AS asset_class, volume
		ORDER BY volume DESC LIMIT $limit
		"""
        rows = await _run_cypher(cypher, {"limit": limit})
        return [_single_table_record(cls.report_id, cls.card_id, rows)]


class CounterpartyRiskSnapshotCard(BaseCard[TableCardRecord]):
    kind = "table"
    card_id = "counterparty_risk_snapshot"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = TableCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        cypher = """
		MATCH (c:Counterparty)
		OPTIONAL MATCH (o:Order)-[:PLACED_BY]->(c)
		WITH c, count(o) AS orders
		RETURN c.legal_name AS name, c.kyc_score AS kyc_score, orders
		ORDER BY kyc_score DESC LIMIT 100
		"""
        rows = await _run_cypher(cypher)
        return [_single_table_record(cls.report_id, cls.card_id, rows)]


class AlertsTableCard(BaseCard[TableCardRecord]):
    kind = "table"
    card_id = "alerts_table"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = TableCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        cypher_alerts = """
		MATCH (a:Alert)
		RETURN a.id AS id, a.type AS type, a.severity AS severity, a.ts AS ts, a.description AS description
		ORDER BY ts DESC LIMIT 50
		"""
        alerts = await _run_cypher(cypher_alerts)
        if not alerts:
            # Fallback synthetic negative sentiment events
            cypher_fallback = """
			MATCH (e:Event) WHERE e.sentiment < -0.7
			RETURN e.event_id AS id, 'negative_sentiment' AS type, e.sentiment AS severity, e.ts AS ts, e.type AS description
			ORDER BY ts DESC LIMIT 20
			"""
            alerts = await _run_cypher(cypher_fallback)
        return [_single_table_record(cls.report_id, cls.card_id, alerts)]


class CorrelationClustersCard(BaseCard[TableCardRecord]):
    kind = "table"
    card_id = "correlation_clusters"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = TableCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        cypher = """
		MATCH (i:Instrument)-[:ISSUED_BY]->(iss:Issuer)
		WITH iss.sector AS cluster, collect(i.ticker) AS tickers, count(i) AS instruments
		RETURN cluster, instruments, tickers ORDER BY instruments DESC
		"""
        rows = await _run_cypher(cypher)
        return [_single_table_record(cls.report_id, cls.card_id, rows)]


# ---------------------------------------------------------------------------
# Number Cards (HTTP)
# ---------------------------------------------------------------------------


class LiquidityDepthNumberCard(BaseCard[NumberCardRecord]):
    kind = "number"
    card_id = "liquidity_depth_number"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = NumberCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        # Current total depth (BUY + SELL qty) and previous day depth
        cypher_current = """
		MATCH (o:Order)
		WITH sum(CASE WHEN o.side = 'BUY' THEN o.qty ELSE 0 END) AS buy_qty,
			 sum(CASE WHEN o.side = 'SELL' THEN o.qty ELSE 0 END) AS sell_qty
		RETURN buy_qty, sell_qty
		"""
        current = await _run_cypher(cypher_current)
        buy = current[0].get("buy_qty") if current else 0
        sell = current[0].get("sell_qty") if current else 0
        value = (buy or 0) + (sell or 0)
        # Previous day approximation: orders with ts < today -1 day (if ts exists)
        cypher_prev = """
		MATCH (o:Order)
		WHERE o.ts < datetime() - duration('P1D')
		WITH sum(CASE WHEN o.side = 'BUY' THEN o.qty ELSE 0 END) AS buy_qty,
			 sum(CASE WHEN o.side = 'SELL' THEN o.qty ELSE 0 END) AS sell_qty
		RETURN buy_qty + sell_qty AS depth
		"""
        prev = await _run_cypher(cypher_prev)
        prev_depth = prev[0].get("depth") if prev else None
        return [
            _number_record(
                cls.report_id,
                cls.card_id,
                float(value),
                label="Total Liquidity Depth (qty)",
                previous=_safe_float(prev_depth),
                unit="qty",
            )
        ]


class CounterpartyAvgKycNumberCard(BaseCard[NumberCardRecord]):
    kind = "number"
    card_id = "counterparty_avg_kyc"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = NumberCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        cypher = """
		MATCH (c:Counterparty)
		RETURN avg(c.kyc_score) AS avg_kyc
		"""
        rows = await _run_cypher(cypher)
        avg_kyc = rows[0].get("avg_kyc") if rows else 0
        return [
            _number_record(
                cls.report_id,
                cls.card_id,
                float(avg_kyc or 0),
                label="Average KYC Score",
                unit="score",
            )
        ]


# ---------------------------------------------------------------------------
# Markdown Cards (HTTP)
# ---------------------------------------------------------------------------


class EventImpactMarkdownCard(BaseCard[MarkdownCardRecord]):
    kind = "markdown"
    card_id = "event_impact_markdown"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = MarkdownCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        params = (ctx or {}).get("params", {})
        event_id = params.get("event_id")
        if not event_id:
            latest = await _run_cypher(
                """
				MATCH (e:Event)
				RETURN e.event_id AS event_id
				ORDER BY e.ts DESC LIMIT 1
				"""
            )
            event_id = latest[0].get("event_id") if latest else None
        if not event_id:
            return [_markdown_record(cls.report_id, cls.card_id, "No events present.")]
        cypher = """
		MATCH (e:Event {event_id:$event_id})
		OPTIONAL MATCH (t:Trade)-[:EXECUTES_ON]->(i:Instrument)
		WHERE t.ts >= e.ts - duration('P1D') AND t.ts <= e.ts + duration('P1D')
		WITH e, count(t) AS trades
		RETURN e.event_id AS event_id, e.type AS type, e.sentiment AS sentiment, trades
		"""
        rows = await _run_cypher(cypher, {"event_id": event_id})
        if not rows:
            return [_markdown_record(cls.report_id, cls.card_id, f"Event {event_id} not found.")]
        r = rows[0]
        md = f"""### Event Impact Summary\n\n*Event ID:* {r.get('event_id')}\n*Type:* {r.get('type')}\n*Sentiment:* {r.get('sentiment')}\n*Related Trades (±1d):* {r.get('trades')}\n\nInterpretation: Sentiment {'positive' if (r.get('sentiment') or 0) > 0 else 'negative' if (r.get('sentiment') or 0) < 0 else 'neutral'}.\n"""
        return [_markdown_record(cls.report_id, cls.card_id, md)]


class MetadataMarkdownCard(BaseCard[MarkdownCardRecord]):
    kind = "markdown"
    card_id = "metadata_markdown"
    report_id = REPORT_ID
    route_prefix = ROUTE_PREFIX
    response_model = MarkdownCardRecord
    transport = "http"

    SCHEMA_BLOCK = """```
:Instrument — pk isin (string). props: ticker, asset_class, exchange, lot_size:int, currency.
:Issuer — pk issuer_id. props: name, country, sector.
:Counterparty — pk id. props: legal_name, kyc_score:float.
:Order — pk order_id. props: side, qty:int, price:float, ts:datetime, links: counterparty_id, isin.
:Trade — pk trade_id. props: price:float, qty:int, ts:datetime, venue.
:Signal — pk signal_id. props: name, score:float, ts:datetime, isin.
:Event — pk event_id. props: type, sentiment:float, ts:datetime, isin.
Relationships: (Instrument)-[:ISSUED_BY]->(Issuer), (Order)-[:PLACED_BY]->(Counterparty), (Order)-[:ORDER_ON]->(Instrument),
(Trade)-[:EXECUTES]->(Order), (Trade)-[:EXECUTES_ON]->(Instrument), (Signal)-[:APPLIES_TO]->(Instrument),
(Event)-[:AFFECTS]->(Instrument), (Instrument)-[:CORRELATED_WITH]->(Instrument) (edges have corr:float, window; upload sets last_updated:datetime).
```"""

    @classmethod
    async def handler(cls, ctx):  # type: ignore[override]
        guidance = """
### Graph Metadata & Parameter Guidance

Below is the canonical Neo4j schema used by the Cereon dashboard cards:

{schema}

**Common query parameters** (add as HTTP query or websocket params JSON):
 - `tickers=AAA,BBB` (comma-separated instrument tickers)
 - `limit=50` (row limit for table / bar charts)
 - `dimension=exchange|asset_class` (for MarketVolumeCard)
 - `event_id=<id>` (select specific Event for impact cards)
 - `ticker=<symbol>` (root instrument for correlation)

All cards attempt graceful fallback (auto-selection) when a parameter is omitted.
		""".strip()
        return [
            _markdown_record(
                cls.report_id,
                cls.card_id,
                guidance.format(schema=cls.SCHEMA_BLOCK),
            )
        ]


# ---------------------------------------------------------------------------
# Route Registration Helper (optional)
# ---------------------------------------------------------------------------

ALL_OVERVIEW_CARDS = [
    MarketVolumeCard,
    PriceMovementRealtimeCard,
    PriceMovementCard,
    VWAPvsOrderSpreadCard,
    TradeCountAvgSizeCard,
    LiquidityDepthNumberCard,
    TopInstrumentsByVolumeCard,
    TopInstrumentsTableCard,
    CorrelationRadarCard,
    SignalScoreTrendsCard,
    EventImpactChartCard,
    EventImpactMarkdownCard,
    CounterpartyRiskSnapshotCard,
    CounterpartyAvgKycNumberCard,
    OrderToTradeConversionCard,
    SpreadDistributionCard,
    SectorExposurePieCard,
    InstrumentHealthRadialCard,
    AlertsTableCard,
    CorrelationClustersCard,
    TopSignalsLeaderboardCard,
    MetadataMarkdownCard,
]
