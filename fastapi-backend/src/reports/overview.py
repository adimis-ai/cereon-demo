# fastapi-backend/src/reports/summary.py

from cereon_sdk.fastapi import (
    BaseCard,
    ChartCardRecord,
    TableCardRecord,
    NumberCardRecord,
)

import os
from fastapi import FastAPI
from dotenv import load_dotenv
from typing import List, AsyncIterable
from datetime import datetime, timedelta
import asyncio
import json
from typing import Dict, Any

import httpx

load_dotenv()

USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "false").lower() == "true"

CONFIG = {
    "tokens": {
        "npm": os.getenv("NPM_TOKEN"),
        "pypi": os.getenv("PYPI_TOKEN"),
        "github": os.getenv("GITHUB_TOKEN"),
    },
    "packages": {
        "cereon-dashboard": {
            "url": "https://www.npmjs.com/package/@cereon/dashboard",
            "type": "npm",
            "repo": "https://github.com/adimis-ai/cereon-dashboard",
        },
        "cereon-recharts": {
            "url": "https://www.npmjs.com/package/@cereon/recharts",
            "type": "npm",
            "repo": "https://github.com/adimis-ai/cereon-recharts",
        },
        "cereon-sdk": {
            "url": "https://pypi.org/project/cereon-sdk/",
            "type": "pypi",
            "repo": "https://github.com/adimis-ai/cereon-sdk",
        },
    },
}


async def _fetch_npm_downloads(package_name: str, days: int = 30) -> List[Dict[str, Any]]:
    """Try to fetch npm downloads API. Returns list of {date, downloads} or raises."""
    url = f"https://api.npmjs.org/downloads/range/last-{days}/{package_name}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        payload = r.json()
        # payload has 'downloads' list of {day, downloads}
        return [
            {"date": d.get("day") or d.get("date"), "downloads": d.get("downloads", 0)}
            for d in payload.get("downloads", [])
        ]


async def _fetch_pypi_downloads(package_name: str, days: int = 30) -> List[Dict[str, Any]]:
    """PyPI doesn't expose daily downloads; fallback to synthetic time series or try pypistats.org unofficial API."""
    # attempt pypistats.org JSON endpoint
    url = f"https://pypistats.org/api/packages/{package_name}/recent"  # limited endpoint
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise RuntimeError("pypistats unavailable")
        payload = r.json()
        # payload.recent contains counts for day/week/month (not daily); synthesize daily from monthly average
        recent = payload.get("data", {})
        month = recent.get("last_month", 0) or recent.get("month", 0)
        avg = int(month / max(1, 30))
        today = datetime.utcnow().date()
        return [
            {"date": (today - timedelta(days=i)).isoformat(), "downloads": avg}
            for i in reversed(range(days))
        ]


def _synth_series(days: int = 30, base: int = 1000, growth: float = 0.02, noise: int = 200):
    today = datetime.utcnow().date()
    data = []
    value = base
    import random

    for i in range(days):
        day = today - timedelta(days=days - i - 1)
        drift = int(value * growth)
        noise_val = random.randint(-noise, noise)
        value = max(0, value + drift + noise_val)
        data.append({"date": day.isoformat(), "value": value})
    return data


class PackageDownloadsAreaCard(BaseCard[ChartCardRecord]):
    kind = "recharts:area"
    card_id = "packages_downloads_area"
    report_id = "package_summary"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        params = (ctx or {}).get("params", {}) if ctx else {}
        # allow override, but ensure at least 365 days when using mock data
        days = int(params.get("days", 30))
        if USE_MOCK_DATA:
            days = max(days, 365)
        packages = list(CONFIG["packages"].keys())

        series_by_pkg: Dict[str, List[Dict[str, Any]]] = {}
        for pkg in packages:
            try:
                if USE_MOCK_DATA:
                    # generate larger synthetic series for mock
                    base = 2000 if CONFIG["packages"][pkg]["type"] == "npm" else 500
                    growth = 0.01 if CONFIG["packages"][pkg]["type"] == "npm" else 0.005
                    data = _synth_series(days, base=base, growth=growth, noise=int(base * 0.2))
                    series_by_pkg[pkg] = [{"date": d["date"], pkg: d["value"]} for d in data]
                else:
                    if CONFIG["packages"][pkg]["type"] == "npm":
                        data = await _fetch_npm_downloads(pkg, days=days)
                        series_by_pkg[pkg] = [
                            {"date": d["date"], pkg: d["downloads"]} for d in data
                        ]
                    elif CONFIG["packages"][pkg]["type"] == "pypi":
                        data = await _fetch_pypi_downloads(pkg, days=days)
                        series_by_pkg[pkg] = [
                            {"date": d["date"], pkg: d["downloads"]} for d in data
                        ]
                    else:
                        data = _synth_series(days, base=1000)
                        series_by_pkg[pkg] = [{"date": x["date"], pkg: x["value"]} for x in data]
            except Exception:
                # fallback to synthetic if anything goes wrong
                data = _synth_series(days, base=1000)
                series_by_pkg[pkg] = [{"date": x["date"], pkg: x["value"]} for x in data]

        # merge on date (assumes all series have same dates when generated)
        merged: List[Dict[str, Any]] = []
        dates = [d["date"] for d in next(iter(series_by_pkg.values()))]
        for idx, dt in enumerate(dates):
            point: Dict[str, Any] = {"date": dt}
            for pkg, s in series_by_pkg.items():
                point[pkg] = s[idx].get(pkg) if idx < len(s) else 0
            merged.append(point)

        payload = {
            "kind": "area",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": merged},
        }
        return [cls.response_model(**payload)]


class PackageCommitsLineCard(BaseCard[ChartCardRecord]):
    kind = "recharts:line"
    card_id = "packages_commits_line"
    report_id = "package_summary"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        params = (ctx or {}).get("params", {}) if ctx else {}
        days = int(params.get("days", 30))
        if USE_MOCK_DATA:
            days = max(days, 365)
        packages = list(CONFIG["packages"].keys())

        async def _fetch_commits_for_repo(repo_url: str, days: int = 30):
            # When not mocking, attempt to fetch recent commits from GitHub
            if not USE_MOCK_DATA and repo_url and "github.com" in repo_url:
                parts = repo_url.rstrip("/").split("/")
                owner, repo = parts[-2], parts[-1]
                url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=100"
                headers = {}
                token = CONFIG.get("tokens", {}).get("github")
                if token:
                    headers["Authorization"] = f"token {token}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(url, headers=headers)
                    r.raise_for_status()
                    commits = r.json()
                    counts: Dict[str, int] = {}
                    cutoff = datetime.utcnow() - timedelta(days=days)
                    for c in commits:
                        try:
                            dt = c.get("commit", {}).get("author", {}).get("date")
                            if not dt:
                                continue
                            d = datetime.fromisoformat(dt.replace("Z", "+00:00")).date()
                            if d < cutoff.date():
                                continue
                            counts.setdefault(d.isoformat(), 0)
                            counts[d.isoformat()] += 1
                        except Exception:
                            continue
                    out = []
                    for i in range(days):
                        day = (datetime.utcnow().date() - timedelta(days=days - i - 1)).isoformat()
                        out.append({"date": day, "commits": counts.get(day, 0)})
                    return out

            # Mock or fallback: return zeros or synthetic
            return [
                {
                    "date": (datetime.utcnow().date() - timedelta(days=days - i - 1)).isoformat(),
                    "commits": 0,
                }
                for i in range(days)
            ]

        series_by_pkg: Dict[str, List[Dict[str, Any]]] = {}
        for pkg, info in CONFIG["packages"].items():
            repo = info.get("repo")
            try:
                if USE_MOCK_DATA:
                    # synth commits per day for a year-ish
                    base = 3 if "github.com" in (repo or "") else 0
                    series = _synth_series(days, base=base, growth=0.01, noise=3)
                    series_by_pkg[pkg] = [
                        {"date": s["date"], pkg: s.get("value", 0)} for s in series
                    ]
                else:
                    series = await _fetch_commits_for_repo(repo, days=days)
                    series_by_pkg[pkg] = [
                        {"date": s["date"], pkg: s.get("commits", 0)} for s in series
                    ]
            except Exception:
                series = _synth_series(days, base=5, growth=0.01, noise=3)
                series_by_pkg[pkg] = [{"date": x["date"], pkg: x["value"]} for x in series]

        # merge
        dates = [d["date"] for d in next(iter(series_by_pkg.values()))]
        merged: List[Dict[str, Any]] = []
        for idx, dt in enumerate(dates):
            point: Dict[str, Any] = {"date": dt}
            for pkg, s in series_by_pkg.items():
                point[pkg] = s[idx].get(pkg) if idx < len(s) else 0
            merged.append(point)

        payload = {
            "kind": "line",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": merged},
        }
        return [cls.response_model(**payload)]


class PackageLikesBarCard(BaseCard[ChartCardRecord]):
    kind = "recharts:bar"
    card_id = "packages_likes_bar"
    report_id = "package_summary"
    route_prefix = "/cards"
    response_model = ChartCardRecord
    transport = "http"

    @classmethod
    async def handler(cls, ctx=None) -> List[ChartCardRecord]:
        params = (ctx or {}).get("params", {}) if ctx else {}
        # For likes timeline, respect days param if provided, but ensure >= 365 when mocking
        days = int(params.get("days", 30))
        if USE_MOCK_DATA:
            days = max(days, 365)

        packages = list(CONFIG["packages"].keys())

        # If mocking, generate a time series: each point is {date, "<pkgA>": val, "<pkgB>": val, ...}
        if USE_MOCK_DATA:
            # create synth series per package and merge by date
            series_by_pkg: Dict[str, List[Dict[str, Any]]] = {}
            # choose different bases so series look distinct
            bases = {
                "cereon-dashboard": 300,
                "cereon-recharts": 150,
                "cereon-sdk": 80,
            }
            for pkg in packages:
                base = bases.get(pkg, 100)
                # slight different growth/noise per package
                growth = 0.0005 if "pypi" in (CONFIG["packages"][pkg]["type"], "") else 0.001
                noise = int(base * 0.05)
                series = _synth_series(days, base=base, growth=growth, noise=noise)
                series_by_pkg[pkg] = [{"date": s["date"], pkg: s["value"]} for s in series]

            dates = [d["date"] for d in next(iter(series_by_pkg.values()))]
            merged: List[Dict[str, Any]] = []
            for idx, dt in enumerate(dates):
                point: Dict[str, Any] = {"date": dt}
                for pkg, s in series_by_pkg.items():
                    point[pkg] = s[idx].get(pkg) if idx < len(s) else 0
                merged.append(point)

            payload = {
                # 'bar' indicates grouped/vertical bars by date; front-end determines orientation from settings.
                "kind": "bar",
                "report_id": cls.report_id,
                "card_id": cls.card_id,
                "data": {"data": merged},
            }
            return [cls.response_model(**payload)]

        # Non-mock: return the simple horizontal bar summary as before (current stars per repo)
        rows = []
        for pkg, info in CONFIG["packages"].items():
            repo = info.get("repo")
            likes = 0
            try:
                if repo and "github.com" in repo:
                    parts = repo.rstrip("/").split("/")
                    owner, repo_name = parts[-2], parts[-1]
                    url = f"https://api.github.com/repos/{owner}/{repo_name}"
                    headers = {}
                    token = CONFIG.get("tokens", {}).get("github")
                    if token:
                        headers["Authorization"] = f"token {token}"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        r = await client.get(url, headers=headers)
                        r.raise_for_status()
                        repo_info = r.json()
                        likes = repo_info.get("stargazers_count", 0)
            except Exception:
                likes = 100
            rows.append({"name": pkg, "value": likes})

        payload = {
            "kind": "bar-horizontal",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": rows},
        }
        return [cls.response_model(**payload)]
