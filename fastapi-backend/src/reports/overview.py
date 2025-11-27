# fastapi-backend/src/reports/summary.py

from cereon_sdk.fastapi import BaseCard, ChartCardRecord

import os
import httpx
import logging
import asyncio
from dotenv import load_dotenv
from urllib.parse import quote
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

load_dotenv()
logger = logging.getLogger(__name__)

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
    if package_name == "cereon-dashboard":
        package_name = "@cereon/dashboard"
    elif package_name == "cereon-recharts":
        package_name = "@cereon/recharts"
    encoded = quote(package_name, safe="")
    today = datetime.utcnow().date()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            import json

            # First try to get package creation date from the npm registry so we can
            # request downloads from the publish date until today (instead of only
            # last-N days). If anything goes wrong, fall back to the last-N-days API.
            start_date = None
            try:
                registry_url = f"https://registry.npmjs.org/{encoded}"
                logger.info(
                    "NPM: fetching registry metadata for package=%s url=%s",
                    package_name,
                    registry_url,
                )
                rmeta = await client.get(registry_url)
                logger.info(
                    "NPM: registry response status=%d for package=%s",
                    rmeta.status_code,
                    package_name,
                )
                if rmeta.status_code == 200:
                    meta = rmeta.json()
                    time = meta.get("time", {}) or {}
                    created = time.get("created") or time.get("created_at")
                    if created:
                        try:
                            created_date = datetime.fromisoformat(
                                created.replace("Z", "+00:00")
                            ).date()
                            # only use creation date when it's not in the future
                            if created_date <= today:
                                start_date = created_date.isoformat()
                        except Exception:
                            start_date = None
            except Exception:
                logger.debug(
                    "NPM: registry lookup failed for package=%s", package_name, exc_info=True
                )

            if start_date:
                url = f"https://api.npmjs.org/downloads/range/{start_date}:{today.isoformat()}/{encoded}"
            else:
                url = f"https://api.npmjs.org/downloads/range/last-{days}/{encoded}"

            logger.info(
                "NPM: fetching downloads for package=%s encoded=%s days=%d url=%s",
                package_name,
                encoded,
                days,
                url,
            )

            r = await client.get(url)
            logger.info("NPM: response status=%d for package=%s", r.status_code, package_name)

            r.raise_for_status()

            payload = r.json()
            downloads = payload.get("downloads", [])
            logger.info(
                "NPM: payload contains %s 'downloads' entries for package=%s",
                json.dumps(downloads),
                package_name,
            )

            result = [
                {"date": d.get("day") or d.get("date"), "downloads": d.get("downloads", 0)}
                for d in downloads
            ]

            logger.info(
                "NPM: returning %s daily entries for package=%s", json.dumps(result), package_name
            )
            return result

        except Exception as exc:
            # include status/text when available for easier debugging
            status = getattr(exc, "response", None)
            if status is not None:
                try:
                    body = status.text
                except Exception:
                    body = "<unreadable response body>"
                logger.error(
                    "NPM: failed package=%s status=%s body=%s error=%s",
                    package_name,
                    getattr(status, "status_code", "<no-status>"),
                    body,
                    exc,
                    exc_info=True,
                )
            else:
                logger.error("NPM: failed package=%s error=%s", package_name, exc, exc_info=True)
            raise


async def _fetch_pypi_downloads(package_name: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch per-day PyPI download counts for `package_name`.
    Tries (in order):
      1. pypistats range endpoints using earliest upload date discovered via PyPI JSON
      2. pepy.tech API (requires API key in CONFIG tokens or env PEPY_API_KEY)
      3. BigQuery public `bigquery-public-data.pypi.file_downloads` (if google-cloud-bigquery is installed and credentials available)

    Returns:
      list of {"date": "YYYY-MM-DD", "downloads": int} sorted ascending by date.
    Raises:
      RuntimeError if no authoritative per-day series could be obtained.
    """
    today = datetime.utcnow().date()
    start_date: Optional[str] = None

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1) determine earliest upload date from PyPI metadata
        try:
            pypi_meta_url = f"https://pypi.org/pypi/{package_name}/json"
            logger.info("PyPI: fetching metadata %s", pypi_meta_url)
            rmeta = await client.get(pypi_meta_url)
            rmeta.raise_for_status()
            meta = rmeta.json()
            releases = meta.get("releases", {}) or {}
            earliest: Optional[datetime.date] = None
            for version_files in releases.values():
                for f in version_files or []:
                    t = f.get("upload_time_iso_8601") or f.get("upload_time")
                    if not t:
                        continue
                    try:
                        dt = datetime.fromisoformat(t.replace("Z", "+00:00")).date()
                    except Exception:
                        continue
                    if earliest is None or dt < earliest:
                        earliest = dt
            if earliest and earliest <= today:
                start_date = earliest.isoformat()
                logger.info("PyPI: earliest upload date for %s = %s", package_name, start_date)
        except Exception:
            logger.debug("PyPI: metadata lookup failed for %s", package_name, exc_info=True)

        # helper to normalize an entries list (many shapes)
        def _normalize_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for item in entries or []:
                if not isinstance(item, dict):
                    continue
                # common shapes: {'date': 'YYYY-MM-DD', 'downloads': N} or {'key': 'YYYY-MM-DD', 'value': N}
                date = item.get("date") or item.get("day") or item.get("key")
                downloads = (
                    item.get("downloads")
                    or item.get("count")
                    or item.get("value")
                    or item.get("downloads_count")
                )
                # sometimes pypistats returns nested object like {"date":"..","category":"..","downloads":N}
                if date and downloads is not None:
                    try:
                        # normalize date string to YYYY-MM-DD
                        d = datetime.fromisoformat(str(date)).date()
                        out.append({"date": d.isoformat(), "downloads": int(downloads)})
                    except Exception:
                        continue
            # sort ascending by date
            out.sort(key=lambda x: x["date"])
            return out

        # 2) Try pypistats range endpoints (they return daily series when available)
        pypistats_candidates = []
        if start_date:
            pypistats_candidates.append(
                f"https://pypistats.org/api/packages/{package_name}/range/{start_date}:{today.isoformat()}"
            )
            pypistats_candidates.append(
                f"https://pypistats.org/api/packages/{package_name}/range/{start_date}/{today.isoformat()}"
            )
        # also try the overall endpoint which often returns daily arrays (note: pypistats retention ~180d)
        pypistats_candidates.append(
            f"https://pypistats.org/api/packages/{package_name}/overall?mirrors=false"
        )
        pypistats_candidates.append(f"https://pypistats.org/api/packages/{package_name}/recent")

        for url in pypistats_candidates:
            try:
                logger.info("PyPI: trying pypistats url=%s", url)
                r = await client.get(url)
                if r.status_code != 200:
                    logger.debug("PyPI: pypistats url=%s returned status=%s", url, r.status_code)
                    continue
                payload = r.json()
                # pypistats shapes: {'data': [...]} or [...], or {'data': {'downloads': [...]}} etc.
                entries: List[Dict[str, Any]] = []
                if isinstance(payload, dict):
                    data = payload.get("data")
                    if isinstance(data, list):
                        entries = data
                    elif (
                        isinstance(data, dict)
                        and "downloads" in data
                        and isinstance(data["downloads"], list)
                    ):
                        entries = data["downloads"]
                elif isinstance(payload, list):
                    entries = payload

                normalized = _normalize_entries(entries)
                if normalized:
                    # cap to requested days (return most recent `days`)
                    if len(normalized) > days:
                        normalized = normalized[-days:]
                    logger.info(
                        "PyPI: pypistats provided %d per-day entries for %s",
                        len(normalized),
                        package_name,
                    )
                    return normalized
            except Exception:
                logger.debug("PyPI: pypistats candidate failed for url=%s", url, exc_info=True)

        # 3) Try pepy.tech (needs API key). Look for key in CONFIG tokens or env PEPY_API_KEY
        pepy_key = None
        try:
            from __main__ import (
                CONFIG as _CFG,
            )  # attempt module-level CONFIG reference if available

            pepy_key = (_CFG.get("tokens") or {}).get(
                "pypi"
            )  # reuse CONFIG pypi token if populated
        except Exception:
            pepy_key = None
        if not pepy_key:
            pepy_key = os.getenv("PEPY_API_KEY") or os.getenv("PEPY_KEY") or os.getenv("PEPY_TOKEN")
        pepy_headers = {}
        if pepy_key:
            # pepy expects X-API-Key or X-API-KEY / X-API-Key depending on versions; include both to be safe
            pepy_headers["X-API-Key"] = pepy_key
            pepy_headers["X-API-KEY"] = pepy_key

        pepy_candidates = []
        if start_date:
            pepy_candidates.append(
                f"https://pepy.tech/api/v2/projects/{package_name}/downloads?from={start_date}&to={today.isoformat()}"
            )
        # project summary contains 'downloads' object with daily keys
        pepy_candidates.append(f"https://pepy.tech/api/v2/projects/{package_name}")
        pepy_candidates.append(f"https://api.pepy.tech/api/v2/projects/{package_name}")

        if pepy_key:
            for url in pepy_candidates:
                try:
                    logger.info("PyPI: trying pepy url=%s", url)
                    r = await client.get(url, headers=pepy_headers)
                    if r.status_code != 200:
                        logger.debug("PyPI: pepy url=%s returned status=%s", url, r.status_code)
                        continue
                    payload = r.json()
                    entries: List[Dict[str, Any]] = []
                    # pepy shapes: {'downloads': {'2025-11-01': N, ...}} or {'downloads': {'daily': [{...}]}} etc.
                    if isinstance(payload, dict):
                        dl = payload.get("downloads")
                        if isinstance(dl, dict):
                            # if mapping date->count
                            if all(
                                isinstance(k, str) and isinstance(v, int) for k, v in dl.items()
                            ):
                                entries = [{"date": k, "downloads": v} for k, v in dl.items()]
                            elif "daily" in dl and isinstance(dl["daily"], list):
                                entries = dl["daily"]
                        # sometimes top-level 'daily' exists
                        elif "daily" in payload and isinstance(payload["daily"], list):
                            entries = payload["daily"]
                        elif "data" in payload and isinstance(payload["data"], list):
                            entries = payload["data"]
                    elif isinstance(payload, list):
                        entries = payload

                    normalized = _normalize_entries(entries)
                    if normalized:
                        if len(normalized) > days:
                            normalized = normalized[-days:]
                        logger.info(
                            "PyPI: pepy provided %d per-day entries for %s",
                            len(normalized),
                            package_name,
                        )
                        return normalized
                except Exception:
                    logger.debug("PyPI: pepy candidate failed url=%s", url, exc_info=True)
        else:
            logger.debug("PyPI: skipping pepy (no API key found)")

        # 4) BigQuery fallback (authoritative, full-history) -- optional: only use if client installed & credentials present
        try:
            # check environment for BigQuery credentials
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("BIGQUERY_CREDENTIALS"):
                try:
                    from google.cloud import bigquery  # type: ignore
                except Exception:
                    raise RuntimeError("google-cloud-bigquery not available")

                # build a parameterized SQL query that groups per day
                sql = """
                SELECT
                  DATE(timestamp) AS day,
                  COUNTIF(JSON_EXTRACT_SCALAR(details, '$.installer.name') IS NOT NULL OR TRUE) AS downloads
                FROM `bigquery-public-data.pypi.file_downloads`
                WHERE LOWER(file.project) = @pkg
                  AND DATE(timestamp) BETWEEN @start_date AND @end_date
                GROUP BY day
                ORDER BY day
                """
                # determine start_date for query: either discovered earliest or 2018-01-01 fallback to keep query bounded
                bq_start = start_date or (today - timedelta(days=365 * 5)).isoformat()
                client = bigquery.Client()
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("pkg", "STRING", package_name.lower()),
                        bigquery.ScalarQueryParameter("start_date", "DATE", bq_start),
                        bigquery.ScalarQueryParameter("end_date", "DATE", today.isoformat()),
                    ]
                )
                logger.info(
                    "PyPI: running BigQuery per-day aggregation for %s from %s to %s",
                    package_name,
                    bq_start,
                    today.isoformat(),
                )

                # run in threadpool since google client is blocking
                def _run_bq():
                    query_job = client.query(sql, job_config=job_config)
                    return list(query_job.result())

                rows = await asyncio.to_thread(_run_bq)

                entries = [
                    {"date": r["day"].isoformat(), "downloads": int(r["downloads"])} for r in rows
                ]
                entries.sort(key=lambda x: x["date"])
                if entries:
                    if len(entries) > days:
                        entries = entries[-days:]
                    logger.info(
                        "PyPI: BigQuery returned %d per-day rows for %s", len(entries), package_name
                    )
                    return entries
        except Exception:
            logger.debug("PyPI: BigQuery candidate failed or unavailable", exc_info=True)

    # If we've reached here, we couldn't obtain per-day authoritative data
    msg = f"Unable to obtain per-day PyPI download counts for package '{package_name}' from pypistats/pepy/bigquery."
    logger.error(msg)
    raise RuntimeError(msg)


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
                        # NOTE: package_name here must be the registry identifier (e.g. @cereon/dashboard).
                        # If CONFIG keys are chart-keys (cereon-dashboard), replace with registry identifier.
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
                logger.warning("Using synthetic fallback series for pkg=%s", pkg)
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
            "kind": "recharts:area",
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
            "kind": "recharts:line",
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
                "kind": "recharts:bar",
                "report_id": cls.report_id,
                "card_id": cls.card_id,
                "data": {"data": merged},
            }
            return [cls.response_model(**payload)]

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
                likes = 0
            rows.append({"name": pkg, "value": likes})

        payload = {
            "kind": "recharts:bar",
            "report_id": cls.report_id,
            "card_id": cls.card_id,
            "data": {"data": rows},
        }
        return [cls.response_model(**payload)]
