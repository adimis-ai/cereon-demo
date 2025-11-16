#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import os
import random
import string
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Iterator, Tuple, Any, TypedDict, Optional

import numpy as np
from faker import Faker
from dateutil import parser as date_parser
from tqdm import tqdm
from neo4j import GraphDatabase, basic_auth

# -----------------------
# Data classes / helpers
# -----------------------
fake = Faker()
Faker.seed(0)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def gen_isin(prefix: str = "US") -> str:
    # simplistic unique-ish ISIN: PREFIX + 9 digits + checksum char
    body = "".join(random.choices(string.digits, k=9))
    chk = random.choice(string.ascii_uppercase + string.digits)
    return f"{prefix}{body}{chk}"


def gen_ticker(name_len: int = 4) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=name_len))


def choose_ts_window(n: int, start_days_ago: int = 30) -> List[str]:
    # returns n timestamps over start_days_ago window during trading hours (09:30-16:00 UTC approximated)
    base = datetime.now(timezone.utc) - timedelta(days=start_days_ago)
    start_dt = base.replace(hour=9, minute=30, second=0, microsecond=0)
    end_dt = base.replace(hour=16, minute=0, second=0, microsecond=0)
    seconds = int((end_dt - start_dt).total_seconds())
    return [iso(start_dt + timedelta(seconds=random.randint(0, seconds))) for _ in range(n)]


@dataclass
class Instrument:
    isin: str
    ticker: str
    asset_class: str
    exchange: str
    lot_size: int
    currency: str


@dataclass
class Issuer:
    issuer_id: str
    name: str
    country: str
    sector: str


@dataclass
class Counterparty:
    id: str
    legal_name: str
    kyc_score: float


@dataclass
class Order:
    order_id: str
    side: str
    qty: int
    price: float
    ts: str
    counterparty_id: str
    isin: str


@dataclass
class Trade:
    trade_id: str
    price: float
    qty: int
    ts: str
    venue: str
    order_id: str
    isin: str


@dataclass
class Signal:
    signal_id: str
    name: str
    score: float
    ts: str
    isin: str


@dataclass
class Event:
    event_id: str
    type: str
    ts: str
    sentiment: float
    isin: str


class GenerateNeo4jMockArgs(TypedDict, total=False):
    seed: int
    n_instruments: int
    n_issuers: int
    n_counterparties: int
    n_trades: int
    n_signals: int
    n_events: int
    corr_top_k: int
    mode: str
    batch_size: int
    out_dir: str
    password: Optional[str]
    uri: Optional[str]
    user: Optional[str]


# -----------------------
# Generators
# -----------------------
def gen_instruments(n: int, seed: int | None = None) -> List[Instrument]:
    random.seed(seed)
    instruments = []
    asset_classes = ["equity", "fixed_income", "etf"]
    exchanges = ["NASDAQ", "NYSE", "CBOE", "LSE"]
    currencies = ["USD", "EUR", "GBP"]
    for i in range(n):
        isin = gen_isin(prefix=random.choice(["US", "GB", "EU", "JP"]))
        ticker = gen_ticker(name_len=random.choice([3, 4, 5]))
        instruments.append(
            Instrument(
                isin=isin,
                ticker=ticker,
                asset_class=random.choice(asset_classes),
                exchange=random.choice(exchanges),
                lot_size=random.choice([1, 10, 100]),
                currency=random.choice(currencies),
            )
        )
    return instruments


def gen_issuers(n: int, seed: int | None = None) -> List[Issuer]:
    random.seed(seed + 1 if seed is not None else None)
    issuers = []
    sectors = ["Technology", "Financials", "Healthcare", "Energy", "Industrial"]
    countries = ["US", "GB", "DE", "JP", "CN"]
    for i in range(n):
        issuer_id = f"ISS-{i:06d}"
        issuers.append(
            Issuer(
                issuer_id=issuer_id,
                name=fake.company(),
                country=random.choice(countries),
                sector=random.choice(sectors),
            )
        )
    return issuers


def gen_counterparties(n: int, seed: int | None = None) -> List[Counterparty]:
    random.seed(seed + 2 if seed is not None else None)
    cps = []
    for i in range(n):
        cid = f"CP-{i:07d}"
        cps.append(
            Counterparty(
                id=cid,
                legal_name=fake.company() + " " + random.choice(["LLC", "Ltd", "Group", "Inc"]),
                kyc_score=round(random.random() * 100, 2),
            )
        )
    return cps


def gen_orders(
    trades_n: int,
    instruments: List[Instrument],
    counterparties: List[Counterparty],
    seed: int | None = None,
) -> List[Order]:
    random.seed(seed + 3 if seed is not None else None)
    orders = []
    sides = ["BUY", "SELL"]
    # number of orders approximate to trades_n / avg_trades_per_order
    avg_trades_per_order = 1.5
    n_orders = max(1, int(trades_n / avg_trades_per_order))
    timestamps = choose_ts_window(n_orders, start_days_ago=7)
    for i in range(n_orders):
        order_id = f"O-{i:08d}"
        ins = random.choice(instruments)
        cp = random.choice(counterparties)
        price = round(random.uniform(10, 1000), 2)
        qty = random.choice([100, 200, 500, 1000])
        orders.append(
            Order(
                order_id=order_id,
                side=random.choice(sides),
                qty=qty,
                price=price,
                ts=timestamps[i],
                counterparty_id=cp.id,
                isin=ins.isin,
            )
        )
    return orders


def gen_trades(
    n: int, instruments: List[Instrument], orders: List[Order], seed: int | None = None
) -> List[Trade]:
    random.seed(seed + 4 if seed is not None else None)
    trades = []
    venues = ["NASDAQ", "NYSE", "CBOE", "ARCA"]
    timestamps = choose_ts_window(n, start_days_ago=7)
    for i in range(n):
        trade_id = f"T-{i:09d}"
        order = random.choice(orders)
        price = round(order.price * (1 + random.uniform(-0.002, 0.002)), 2)
        qty = max(1, int(order.qty * random.uniform(0.1, 1.0)))
        trades.append(
            Trade(
                trade_id=trade_id,
                price=price,
                qty=qty,
                ts=timestamps[i],
                venue=random.choice(venues),
                order_id=order.order_id,
                isin=order.isin,
            )
        )
    return trades


def gen_signals(n: int, instruments: List[Instrument], seed: int | None = None) -> List[Signal]:
    random.seed(seed + 5 if seed is not None else None)
    signals = []
    signal_names = ["momentum", "value", "quality", "low_vol"]
    timestamps = choose_ts_window(n, start_days_ago=30)
    for i in range(n):
        sig_id = f"SIG-{i:08d}"
        ins = random.choice(instruments)
        signals.append(
            Signal(
                signal_id=sig_id,
                name=random.choice(signal_names),
                score=round(random.uniform(-3, 3), 4),
                ts=timestamps[i],
                isin=ins.isin,
            )
        )
    return signals


def gen_events(n: int, instruments: List[Instrument], seed: int | None = None) -> List[Event]:
    random.seed(seed + 6 if seed is not None else None)
    events = []
    event_types = ["earnings", "merger", "regulatory", "downgrade", "upgrade"]
    timestamps = choose_ts_window(n, start_days_ago=90)
    for i in range(n):
        event_id = f"E-{i:08d}"
        ins = random.choice(instruments)
        events.append(
            Event(
                event_id=event_id,
                type=random.choice(event_types),
                ts=timestamps[i],
                sentiment=round(random.uniform(-1, 1), 4),
                isin=ins.isin,
            )
        )
    return events


def gen_correlation_edges(
    instruments: List[Instrument], top_k: int = 5, seed: int | None = None
) -> List[Dict[str, Any]]:
    """
    Creates a synthetic 'correlation' edge list: for each instrument pick top_k other instruments.
    Correlation scores are synthetic.
    """
    random.seed(seed + 7 if seed is not None else None)
    edges = []
    isins = [i.isin for i in instruments]
    for a in isins:
        neighbors = random.sample([x for x in isins if x != a], k=min(top_k, len(isins) - 1))
        for b in neighbors:
            edges.append(
                {"a_isin": a, "b_isin": b, "corr": round(random.uniform(-1, 1), 4), "window": "30d"}
            )
    return edges


# -----------------------
# Neo4j direct upload
# -----------------------
class Neo4jUploader:
    def __init__(self, uri: str, user: str, password: str, max_conn_lifetime: int = 600):
        if GraphDatabase is None:
            raise RuntimeError("neo4j driver not installed. Install with `pip install neo4j`.")
        self.driver = GraphDatabase.driver(
            uri, auth=basic_auth(user, password), max_connection_lifetime=max_conn_lifetime
        )

    def close(self):
        self.driver.close()

    def apply_constraints(self):
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Instrument) REQUIRE i.isin IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (iss:Issuer) REQUIRE iss.issuer_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Counterparty) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Order) REQUIRE o.order_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Trade) REQUIRE t.trade_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Signal) REQUIRE s.signal_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
        ]
        with self.driver.session() as s:
            for c in constraints:
                s.run(c)

    def batch_write(self, cypher: str, params_list: List[Dict], batch_size: int = 1000):
        with self.driver.session() as s:
            for i in range(0, len(params_list), batch_size):
                batch = params_list[i : i + batch_size]
                s.run(cypher, batch=batch)

    def upload_all(
        self,
        instruments: List[Instrument],
        issuers: List[Issuer],
        counterparties: List[Counterparty],
        orders: List[Order],
        trades: List[Trade],
        signals: List[Signal],
        events: List[Event],
        corr_edges: List[Dict[str, Any]],
        batch_size: int = 1000,
    ):
        self.apply_constraints()

        # Instruments
        cypher_ins = """
        UNWIND $batch AS row
        MERGE (i:Instrument {isin: row.isin})
        SET i.ticker = row.ticker, i.asset_class = row.asset_class, i.exchange = row.exchange,
            i.lot_size = row.lot_size, i.currency = row.currency
        """
        ins_params = [asdict(i) for i in instruments]
        print("Uploading instruments...")
        self.batch_write(cypher_ins, ins_params, batch_size=batch_size)

        # Issuers
        cypher_iss = """
        UNWIND $batch AS row
        MERGE (iss:Issuer {issuer_id: row.issuer_id})
        SET iss.name = row.name, iss.country = row.country, iss.sector = row.sector
        """
        iss_params = [asdict(i) for i in issuers]
        print("Uploading issuers...")
        self.batch_write(cypher_iss, iss_params, batch_size=batch_size)

        # Link random issuer to instrument (distribute issuers across instruments)
        print("Linking instruments to issuers...")
        link_params = []
        for ins in instruments:
            issuer = random.choice(issuers)
            link_params.append({"isin": ins.isin, "issuer_id": issuer.issuer_id})
        cypher_link = """
        UNWIND $batch AS row
        MATCH (i:Instrument {isin: row.isin})
        MATCH (iss:Issuer {issuer_id: row.issuer_id})
        MERGE (i)-[:ISSUED_BY]->(iss)
        """
        self.batch_write(cypher_link, link_params, batch_size=batch_size)

        # Counterparties
        cypher_cp = """
        UNWIND $batch AS row
        MERGE (c:Counterparty {id: row.id})
        SET c.legal_name = row.legal_name, c.kyc_score = row.kyc_score
        """
        cp_params = [asdict(c) for c in counterparties]
        print("Uploading counterparties...")
        self.batch_write(cypher_cp, cp_params, batch_size=batch_size)

        # Orders
        cypher_orders = """
        UNWIND $batch AS row
        MERGE (o:Order {order_id: row.order_id})
        SET o.side = row.side, o.qty = row.qty, o.price = row.price, o.ts = datetime(row.ts)
        WITH o, row
        MATCH (c:Counterparty {id: row.counterparty_id})
        MATCH (i:Instrument {isin: row.isin})
        MERGE (o)-[:PLACED_BY]->(c)
        MERGE (o)-[:ORDER_ON]->(i)
        """
        order_params = [asdict(o) for o in orders]
        print("Uploading orders...")
        self.batch_write(cypher_orders, order_params, batch_size=batch_size)

        # Trades
        cypher_trades = """
        UNWIND $batch AS row
        MERGE (t:Trade {trade_id: row.trade_id})
        SET t.price = row.price, t.qty = row.qty, t.ts = datetime(row.ts), t.venue = row.venue
        WITH t, row
        MATCH (o:Order {order_id: row.order_id})
        MATCH (i:Instrument {isin: row.isin})
        MERGE (t)-[:EXECUTES]->(o)
        MERGE (t)-[:EXECUTES_ON]->(i)
        """
        trade_params = [asdict(t) for t in trades]
        print("Uploading trades...")
        self.batch_write(cypher_trades, trade_params, batch_size=batch_size)

        # Signals
        cypher_signals = """
        UNWIND $batch AS row
        MERGE (s:Signal {signal_id: row.signal_id})
        SET s.name = row.name, s.score = row.score, s.ts = datetime(row.ts)
        WITH s, row
        MATCH (i:Instrument {isin: row.isin})
        MERGE (s)-[:APPLIES_TO]->(i)
        """
        sig_params = [asdict(s) for s in signals]
        print("Uploading signals...")
        self.batch_write(cypher_signals, sig_params, batch_size=batch_size)

        # Events
        cypher_events = """
        UNWIND $batch AS row
        MERGE (e:Event {event_id: row.event_id})
        SET e.type = row.type, e.sentiment = row.sentiment, e.ts = datetime(row.ts)
        WITH e, row
        MATCH (i:Instrument {isin: row.isin})
        MERGE (e)-[:AFFECTS]->(i)
        """
        ev_params = [asdict(e) for e in events]
        print("Uploading events...")
        self.batch_write(cypher_events, ev_params, batch_size=batch_size)

        # Correlations (edges)
        cypher_corr = """
        UNWIND $batch AS row
        MATCH (a:Instrument {isin: row.a_isin})
        MATCH (b:Instrument {isin: row.b_isin})
        MERGE (a)-[r:CORRELATED_WITH]->(b)
        SET r.corr = row.corr, r.window = row.window, r.last_updated = datetime()
        """
        print("Uploading correlation edges...")
        self.batch_write(cypher_corr, corr_edges, batch_size=batch_size)

        print("Upload complete.")


# -----------------------
# CSV export
# -----------------------
def write_csv_nodes_out(
    out_dir: str,
    instruments: List[Instrument],
    issuers: List[Issuer],
    counterparties: List[Counterparty],
    orders: List[Order],
    trades: List[Trade],
    signals: List[Signal],
    events: List[Event],
    corr_edges: List[Dict[str, Any]],
):
    os.makedirs(out_dir, exist_ok=True)

    # Nodes
    def write_nodes(filename: str, fieldnames: List[str], rows: Iterator[Dict[str, Any]]):
        path = os.path.join(out_dir, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"Wrote {path}")

    write_nodes(
        "instruments.csv",
        ["isin:ID(Instrument)", "ticker", "asset_class", "exchange", "lot_size:int", "currency"],
        (
            {
                "isin:ID(Instrument)": i.isin,
                "ticker": i.ticker,
                "asset_class": i.asset_class,
                "exchange": i.exchange,
                "lot_size:int": i.lot_size,
                "currency": i.currency,
            }
            for i in instruments
        ),
    )
    write_nodes(
        "issuers.csv",
        ["issuer_id:ID(Issuer)", "name", "country", "sector"],
        (
            {
                "issuer_id:ID(Issuer)": iss.issuer_id,
                "name": iss.name,
                "country": iss.country,
                "sector": iss.sector,
            }
            for iss in issuers
        ),
    )
    write_nodes(
        "counterparties.csv",
        ["id:ID(Counterparty)", "legal_name", "kyc_score:float"],
        (
            {
                "id:ID(Counterparty)": c.id,
                "legal_name": c.legal_name,
                "kyc_score:float": c.kyc_score,
            }
            for c in counterparties
        ),
    )
    write_nodes(
        "orders.csv",
        [
            "order_id:ID(Order)",
            "side",
            "qty:int",
            "price:float",
            "ts:datetime",
            "counterparty_id:ID(Counterparty)",
            "isin:ID(Instrument)",
        ],
        (
            {
                "order_id:ID(Order)": o.order_id,
                "side": o.side,
                "qty:int": o.qty,
                "price:float": o.price,
                "ts:datetime": o.ts,
                "counterparty_id:ID(Counterparty)": o.counterparty_id,
                "isin:ID(Instrument)": o.isin,
            }
            for o in orders
        ),
    )
    write_nodes(
        "trades.csv",
        [
            "trade_id:ID(Trade)",
            "price:float",
            "qty:int",
            "ts:datetime",
            "venue",
            "order_id:ID(Order)",
            "isin:ID(Instrument)",
        ],
        (
            {
                "trade_id:ID(Trade)": t.trade_id,
                "price:float": t.price,
                "qty:int": t.qty,
                "ts:datetime": t.ts,
                "venue": t.venue,
                "order_id:ID(Order)": t.order_id,
                "isin:ID(Instrument)": t.isin,
            }
            for t in trades
        ),
    )
    write_nodes(
        "signals.csv",
        ["signal_id:ID(Signal)", "name", "score:float", "ts:datetime", "isin:ID(Instrument)"],
        (
            {
                "signal_id:ID(Signal)": s.signal_id,
                "name": s.name,
                "score:float": s.score,
                "ts:datetime": s.ts,
                "isin:ID(Instrument)": s.isin,
            }
            for s in signals
        ),
    )
    write_nodes(
        "events.csv",
        ["event_id:ID(Event)", "type", "sentiment:float", "ts:datetime", "isin:ID(Instrument)"],
        (
            {
                "event_id:ID(Event)": e.event_id,
                "type": e.type,
                "sentiment:float": e.sentiment,
                "ts:datetime": e.ts,
                "isin:ID(Instrument)": e.isin,
            }
            for e in events
        ),
    )

    # Relationships
    # instruments -> issuers
    with open(
        os.path.join(out_dir, "inst_issued_by_rel.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Instrument)", ":END_ID(Issuer)", ":TYPE"])
        for ins in instruments:
            issuer = random.choice(issuers)
            w.writerow([ins.isin, issuer.issuer_id, "ISSUED_BY"])
    print(f"Wrote relationships inst_issued_by_rel.csv")

    # orders -> counterparty, orders -> instrument
    with open(os.path.join(out_dir, "order_rel.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Order)", ":END_ID(Counterparty)", ":TYPE"])
        for o in orders:
            w.writerow([o.order_id, o.counterparty_id, "PLACED_BY"])
    print("Wrote relationships order_rel.csv")

    with open(
        os.path.join(out_dir, "order_instrument_rel.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Order)", ":END_ID(Instrument)", ":TYPE"])
        for o in orders:
            w.writerow([o.order_id, o.isin, "ORDER_ON"])
    print("Wrote relationships order_instrument_rel.csv")

    # trades -> order and trades -> instrument
    with open(os.path.join(out_dir, "trade_rel.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Trade)", ":END_ID(Order)", ":TYPE"])
        for t in trades:
            w.writerow([t.trade_id, t.order_id, "EXECUTES"])
    print("Wrote relationships trade_rel.csv")

    with open(
        os.path.join(out_dir, "trade_instrument_rel.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Trade)", ":END_ID(Instrument)", ":TYPE"])
        for t in trades:
            w.writerow([t.trade_id, t.isin, "EXECUTES_ON"])
    print("Wrote relationships trade_instrument_rel.csv")

    # signals -> instrument
    with open(os.path.join(out_dir, "signal_rel.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Signal)", ":END_ID(Instrument)", ":TYPE"])
        for s in signals:
            w.writerow([s.signal_id, s.isin, "APPLIES_TO"])
    print("Wrote relationships signal_rel.csv")

    # events -> instrument
    with open(os.path.join(out_dir, "event_rel.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([":START_ID(Event)", ":END_ID(Instrument)", ":TYPE"])
        for e in events:
            w.writerow([e.event_id, e.isin, "AFFECTS"])
    print("Wrote relationships event_rel.csv")

    # correlation edges
    with open(os.path.join(out_dir, "corr_rel.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [":START_ID(Instrument)", ":END_ID(Instrument)", ":TYPE", "corr:float", "window"]
        )
        for r in corr_edges:
            w.writerow([r["a_isin"], r["b_isin"], "CORRELATED_WITH", r["corr"], r["window"]])
    print("Wrote relationships corr_rel.csv")

    print("CSV export ready for neo4j-admin import.")


def generate_neo4j_mock_data(args: GenerateNeo4jMockArgs):
    # Use mapping access with TypedDict for clearer typing
    random.seed(args.get("seed"))
    np.random.seed(args.get("seed"))

    print("Generating instruments...")
    instruments = gen_instruments(args.get("n_instruments"), seed=args.get("seed"))
    print("Generating issuers...")
    issuers = gen_issuers(args.get("n_issuers"), seed=args.get("seed"))
    print("Generating counterparties...")
    cps = gen_counterparties(args.get("n_counterparties"), seed=args.get("seed"))
    print("Generating orders (approx)...")
    orders = gen_orders(args.get("n_trades"), instruments, cps, seed=args.get("seed"))
    print("Generating trades...")
    trades = gen_trades(args.get("n_trades"), instruments, orders, seed=args.get("seed"))
    print("Generating signals...")
    signals = gen_signals(args.get("n_signals"), instruments, seed=args.get("seed"))
    print("Generating events...")
    events = gen_events(args.get("n_events"), instruments, seed=args.get("seed"))
    print("Generating correlation edges...")
    corr_edges = gen_correlation_edges(
        instruments, top_k=args.get("corr_top_k"), seed=args.get("seed")
    )

    if args.get("mode") != "direct":
        out_dir = args.get("out_dir") or os.environ.get("NEO4J_MOCK_OUT_DIR")
        if out_dir is None:
            seed_val = args.get("seed") or int(time.time())
            out_dir = os.path.abspath(f"neo4j_mock_out_seed_{seed_val}")
            print(f"No out_dir supplied, using default: {out_dir}")
        args = dict(args)
        args["out_dir"] = out_dir

    if args.get("mode") == "direct":
        if GraphDatabase is None:
            raise RuntimeError("neo4j driver not installed. Install with `pip install neo4j`.")

        # Allow credentials/uri to be supplied via environment variables as a fallback
        # This makes it easier to run the script in environments where CLI args
        # are not populated (for example when using a .env file or docker-compose).
        password = (
            args.get("password") or os.environ.get("NEO4J_PASSWORD") or os.environ.get("NEO4J_PASS")
        )
        uri = args.get("uri") or os.environ.get("NEO4J_URI")
        user = args.get("user") or os.environ.get("NEO4J_USER")

        if not password:
            raise RuntimeError(
                "Direct mode requires a Neo4j password. Provide via --password or set the NEO4J_PASSWORD environment variable."
            )

        uploader = Neo4jUploader(uri, user, password)
        try:
            start = time.time()
            uploader.upload_all(
                instruments=instruments,
                issuers=issuers,
                counterparties=cps,
                orders=orders,
                trades=trades,
                signals=signals,
                events=events,
                corr_edges=corr_edges,
                batch_size=args.get("batch_size"),
            )
            elapsed = time.time() - start
            print(f"Direct upload finished in {elapsed:.1f}s")
        finally:
            uploader.close()
    else:
        write_csv_nodes_out(
            args.get("out_dir"),
            instruments,
            issuers,
            cps,
            orders,
            trades,
            signals,
            events,
            corr_edges,
        )
