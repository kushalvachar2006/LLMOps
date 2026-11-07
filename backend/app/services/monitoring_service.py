"""Monitoring logic. Every number comes from persisted request, evaluation or feedback records.

Where data is missing the answer is None / "unavailable", never a guess:
* no token usage reported  -> no cost for those requests
* no price configured      -> cost shown as unpriced, tokens still shown
* nothing recorded         -> empty results, never zeros dressed up as measurements
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.redaction import redact
from app.repositories.assets import PromptRepository
from app.repositories.monitoring import (
    FeedbackRepository,
    MetricsRepository,
    PricingRepository,
    SettingsRepository,
)
from app.repositories.request_repository import RequestRepository
from app.schemas.monitoring import FeedbackCreate, PricingCreate, Thresholds

MAX_RANGE_DAYS = 366


@dataclass(frozen=True)
class Filters:
    project_id: str | None
    start: datetime
    end: datetime
    provider: str | None = None
    model: str | None = None
    deployment_id: str | None = None


def resolve_range(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    def utc(d: datetime) -> datetime:
        return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)

    end_dt = utc(end) if end else datetime.now(UTC)
    start_dt = utc(start) if start else end_dt - timedelta(days=7)
    if start_dt >= end_dt:
        raise ValidationAppError("The start of the date range must be before its end.")
    if end_dt - start_dt > timedelta(days=MAX_RANGE_DAYS):
        raise ValidationAppError(f"Date range is limited to {MAX_RANGE_DAYS} days.")
    return start_dt, end_dt


def _match(f: Filters, start: datetime | None = None, end: datetime | None = None) -> dict:
    m: dict = {"created_at": {"$gte": start or f.start, "$lt": end or f.end}}
    if f.project_id:
        m["project_id"] = f.project_id
    if f.provider:
        m["provider"] = f.provider
    if f.model:
        m["model"] = f.model
    if f.deployment_id:
        m["deployment_id"] = f.deployment_id
    return m


def _round(x, n=2):
    return None if x is None else round(x, n)


# ---------------- cost ----------------
def estimate_costs(groups: list[dict], usage_counts: dict, pricing: list[dict]) -> dict:
    """Costs are ESTIMATES: reported token counts x the prices you configured.

    Hidden reasoning tokens may be billed differently by some vendors, and discounts, caching
    and taxes are not modelled.
    """
    table: dict[tuple[str, str], list[dict]] = {}
    for p in pricing:
        table.setdefault((p["provider"], p["model"]), []).append(p)
    for entries in table.values():
        entries.sort(key=lambda e: e["effective_from"])

    by_model: dict[tuple[str, str], dict] = {}
    for g in groups:
        key = (g["_id"]["provider"], g["_id"]["model"])
        day = g["_id"]["day"]
        row = by_model.setdefault(key, {
            "provider": key[0], "model": key[1], "requests": 0, "priced_requests": 0,
            "unpriced_requests": 0, "no_usage_requests": 0, "input_tokens": 0,
            "output_tokens": 0, "cost": 0.0, "currencies": set(),
        })
        n = g["requests"]
        with_usage = usage_counts.get((key[0], key[1], day), 0)
        row["requests"] += n
        row["no_usage_requests"] += n - with_usage
        row["input_tokens"] += g.get("input_tokens") or 0
        row["output_tokens"] += g.get("output_tokens") or 0
        applicable = [e for e in table.get(key, []) if e["effective_from"] <= day]
        if with_usage == 0:
            continue
        if not applicable:
            row["unpriced_requests"] += with_usage
            continue
        price = applicable[-1]
        div = 1_000_000 if price["unit"] == "per_1M_tokens" else 1_000
        row["cost"] += ((g.get("input_tokens") or 0) * price["input_price"]
                        + (g.get("output_tokens") or 0) * price["output_price"]) / div
        row["priced_requests"] += with_usage
        row["currencies"].add(price["currency"])

    rows, totals = [], {}
    for row in by_model.values():
        currencies = sorted(row.pop("currencies"))
        cost = row.pop("cost")
        if row["priced_requests"] == 0:
            status, value = "no_pricing" if row["unpriced_requests"] else "no_usage_data", None
        else:
            status = "partial" if (row["unpriced_requests"] or row["no_usage_requests"]) else "estimated"
            value = round(cost, 6)
        if len(currencies) > 1:
            status, value = "mixed_currency", None
        row.update(cost=value, currency=currencies[0] if len(currencies) == 1 else None,
                   status=status)
        if value is not None:
            totals[row["currency"]] = round(totals.get(row["currency"], 0.0) + value, 6)
        rows.append(row)
    rows.sort(key=lambda r: -r["requests"])
    complete = bool(rows) and all(r["status"] == "estimated" for r in rows)
    return {
        "totals_by_currency": totals, "by_model": rows, "complete": complete,
        "note": "Estimate only: reported token counts x prices you entered. Unpriced or "
                "usage-less requests are excluded from totals, never guessed.",
    }


# ---------------- service ----------------
class MonitoringService:
    def __init__(self, metrics: MetricsRepository, pricing: PricingRepository,
                 settings_repo: SettingsRepository, prompts: PromptRepository,
                 requests: RequestRepository, feedback: FeedbackRepository,
                 settings: Settings):
        self._m = metrics
        self._pricing = pricing
        self._settings_repo = settings_repo
        self._prompts = prompts
        self._requests = requests
        self._feedback = feedback
        self._settings = settings

    # ----- config
    def policy(self) -> dict:
        s = self._settings
        return {"retention_days": s.trace_retention_days, "redaction_enabled": s.redaction_enabled,
                "store_prompt_text": s.store_prompt_text,
                "never_stored": ["API keys", "authorization headers"],
                "streaming_first_token_time": "not captured (streaming is not implemented)",
                "retries": "not captured as retries (automatic retries are not implemented)"}

    def get_thresholds(self) -> dict:
        saved = self._settings_repo.get() or {}
        return Thresholds(**saved).model_dump()

    def save_thresholds(self, t: Thresholds) -> dict:
        self._settings_repo.save(t.model_dump())
        return t.model_dump()

    # ----- summary
    def summary(self, f: Filters) -> dict:
        match = _match(f)
        c = self._m.counts(match)
        window = {"start": f.start, "end": f.end}
        if c["total"] == 0:
            return {"window": window, "empty": True, "total": 0, "success": 0, "failed": 0,
                    "error_rate": None, "latency": None, "tokens": None,
                    "cost": estimate_costs([], {}, []), "feedback": self._m.feedback_summary(
                        self._fb_match(f)), "input_length": None}
        sums = self._m.sums(match)
        return {
            "window": window, "empty": False, **{k: c[k] for k in ("total", "success", "failed")},
            "error_rate": round(c["failed"] / c["total"], 4),
            "latency": {
                "avg_ms": _round(sums["avg_latency_ms"], 1),
                "p50_ms": self._m.percentile(match, "latency_ms", 50),
                "p95_ms": self._m.percentile(match, "latency_ms", 95),
                "p99_ms": self._m.percentile(match, "latency_ms", 99),
                "method": "nearest-rank percentile over recorded end-to-end latency",
            },
            "tokens": {"input": sums["input_tokens"], "output": sums["output_tokens"],
                       "total": sums["total_tokens"], "requests_with_usage": c["with_usage"],
                       "requests_without_usage": c["total"] - c["with_usage"]},
            "cost": estimate_costs(self._m.cost_groups(match),
                                   self._m.count_with_usage_by_group(match), self._pricing.list()),
            "feedback": self._m.feedback_summary(self._fb_match(f)),
            "input_length": self._m.input_stats(match),
        }

    @staticmethod
    def _fb_match(f: Filters) -> dict:
        m: dict = {"created_at": {"$gte": f.start, "$lt": f.end}}
        if f.project_id:
            m["project_id"] = f.project_id
        if f.provider:
            m["provider"] = f.provider
        if f.model:
            m["model"] = f.model
        return m

    # ----- series / breakdowns
    @staticmethod
    def _granularity(f: Filters, granularity: str | None) -> tuple[str, str]:
        g = granularity or ("hour" if f.end - f.start <= timedelta(days=2) else "day")
        if g not in ("hour", "day"):
            raise ValidationAppError("granularity must be 'hour' or 'day'.")
        return g, "%Y-%m-%dT%H:00" if g == "hour" else "%Y-%m-%d"

    def timeseries(self, f: Filters, granularity: str | None = None) -> dict:
        g, fmt = self._granularity(f, granularity)
        rows = self._m.series(_match(f), fmt)
        points = [{
            "bucket": r["_id"], "requests": r["requests"], "success": r["success"],
            "failed": r["failed"], "error_rate": round(r["failed"] / r["requests"], 4),
            "avg_latency_ms": _round(r["avg_latency_ms"], 1),
            "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
        } for r in rows]
        return {"granularity": g, "points": points,
                "note": "Only periods with at least one request appear; gaps mean no traffic."}

    def breakdown(self, f: Filters) -> dict:
        match = _match(f)
        models = [{
            "provider": r["_id"]["provider"], "model": r["_id"]["model"], "requests": r["requests"],
            "success": r["success"], "failed": r["failed"],
            "error_rate": round(r["failed"] / r["requests"], 4),
            "avg_latency_ms": _round(r["avg_latency_ms"], 1),
            "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
        } for r in self._m.by_model(match)]

        fb = {(r["_id"]["prompt_id"], r["_id"]["prompt_version"]): r
              for r in self._m.feedback_by_version(self._fb_match(f))}
        rows = self._m.by_prompt_version(match)
        names = self._prompt_names({r["_id"]["prompt_id"] for r in rows})
        versions = []
        for r in rows:
            k = (r["_id"]["prompt_id"], r["_id"]["prompt_version"])
            feedback = fb.get(k)
            versions.append({
                "prompt_id": k[0], "prompt": names.get(k[0], k[0]), "prompt_version": k[1],
                "requests": r["requests"], "failed": r["failed"],
                "error_rate": round(r["failed"] / r["requests"], 4),
                "avg_latency_ms": _round(r["avg_latency_ms"], 1),
                "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                "feedback_count": feedback["count"] if feedback else 0,
                "avg_rating": _round(feedback["avg_rating"], 2) if feedback else None,
            })
        return {"models": models, "prompt_versions": versions}

    def _prompt_names(self, ids: set[str]) -> dict[str, str]:
        out = {}
        for pid in ids:
            try:
                out[pid] = self._prompts.get(pid)["name"]
            except NotFoundError:
                pass
        return out

    # ----- quality
    def quality(self, f: Filters, granularity: str | None = None) -> dict:
        g, fmt = self._granularity(f, granularity)
        match = _match(f)
        series = [{
            "bucket": r["_id"]["bucket"], "metric": r["_id"]["name"], "type": r["_id"]["type"],
            "kind": r["_id"]["kind"], "mean_score": _round(r["mean_score"], 4),
            "n_scored": r["n_scored"], "passed": r["passed"], "failed": r["failed"],
        } for r in self._m.quality_series(match, fmt)]
        rows = self._m.quality_by_version(match)
        names = self._prompt_names({r["_id"]["prompt_id"] for r in rows})
        versions = [{
            "prompt_id": r["_id"]["prompt_id"], "prompt": names.get(r["_id"]["prompt_id"]),
            "prompt_version": r["_id"]["prompt_version"], "metric": r["_id"]["name"],
            "type": r["_id"]["type"], "kind": r["_id"]["kind"],
            "mean_score": _round(r["mean_score"], 4), "n_scored": r["n_scored"],
            "passed": r["passed"], "failed": r["failed"],
        } for r in rows]
        return {
            "granularity": g, "series": series, "by_prompt_version": versions,
            "note": "Scores come from evaluations recorded during experiments. Objective metrics "
                    "and model-judgment scores are different things and are labelled by kind.",
        }

    # ----- alerts
    def alerts(self, f: Filters) -> dict:
        t = Thresholds(**(self._settings_repo.get() or {}))
        alerts: list[dict] = []
        match = _match(f)
        counts = self._m.counts(match)

        if counts["total"] >= t.min_requests:
            rate = counts["failed"] / counts["total"]
            if rate > t.error_rate_max:
                alerts.append(_alert(
                    "error_rate", "warning", "High error rate",
                    f"{rate:.1%} of {counts['total']} requests failed (limit {t.error_rate_max:.0%}).",
                    {"failed": counts["failed"], "total": counts["total"]}))
            if t.latency_p95_ms_max is not None:
                p95 = self._m.percentile(match, "latency_ms", 95)
                if p95 is not None and p95 > t.latency_p95_ms_max:
                    alerts.append(_alert(
                        "latency_p95", "warning", "Slow responses",
                        f"95th percentile latency is {p95:,.0f} ms (limit {t.latency_p95_ms_max:,.0f}).",
                        {"p95_ms": p95}))

        alerts += self._quality_alerts(match, t)

        fb = self._m.feedback_summary(self._fb_match(f))
        if (t.feedback_avg_min is not None and fb["count"] >= t.min_samples
                and fb["avg_rating"] < t.feedback_avg_min):
            alerts.append(_alert(
                "feedback", "warning", "Low user ratings",
                f"Average rating {fb['avg_rating']:.2f}/5 across {fb['count']} ratings "
                f"(minimum {t.feedback_avg_min}).", fb))

        span = f.end - f.start
        prev = _match(f, f.start - span, f.start)
        if f.project_id:
            prev["project_id"] = f.project_id
        cur_in, prev_in = self._m.input_stats(match), self._m.input_stats(prev)
        if (cur_in["n"] >= t.min_requests and prev_in["n"] >= t.min_requests
                and cur_in["mean"] and prev_in["mean"]):
            change = (cur_in["mean"] - prev_in["mean"]) / prev_in["mean"]
            if abs(change) > t.input_length_change_max:
                alerts.append(_alert(
                    "input_length_change", "info", "Input length distribution changed",
                    f"Average prompt length moved {change:+.0%} versus the previous period "
                    f"({prev_in['mean']:.0f} to {cur_in['mean']:.0f} characters). This is a change "
                    "in a summary statistic, not proof of harmful data drift; check quality "
                    "scores or feedback before drawing conclusions.",
                    {"current": cur_in, "previous": prev_in}))
        return {"thresholds": t.model_dump(), "alerts": alerts,
                "checked_at": datetime.now(UTC), "window": {"start": f.start, "end": f.end},
                "note": "Alerts are evaluated when you open this page, over the selected date range."}

    def _quality_alerts(self, match: dict, t: Thresholds) -> list[dict]:
        rows = self._m.quality_by_version(match)
        names = self._prompt_names({r["_id"]["prompt_id"] for r in rows})
        grouped: dict[tuple, list[dict]] = {}
        for r in rows:
            k = (r["_id"]["prompt_id"], r["_id"]["name"])
            grouped.setdefault(k, []).append(r)
        out = []
        for (pid, metric), items in grouped.items():
            items.sort(key=lambda r: r["_id"]["prompt_version"])
            prompt = names.get(pid, pid)
            latest = items[-1]
            # Output-format failure rate (structured-output checks)
            if latest["_id"]["type"] == "json_valid":
                judged = latest["passed"] + latest["failed"]
                if judged >= t.min_samples and latest["failed"] / judged > t.format_failure_rate_max:
                    out.append(_alert(
                        "format_failure", "warning", "Output format failures",
                        f"'{prompt}' v{latest['_id']['prompt_version']}: "
                        f"{latest['failed'] / judged:.0%} of {judged} outputs failed the "
                        f"'{metric}' format check (limit {t.format_failure_rate_max:.0%}).",
                        {"prompt_id": pid, "failed": latest["failed"], "judged": judged}))
            # Version-to-version regression on recorded evaluation scores
            if len(items) >= 2:
                prev = items[-2]
                if (latest["n_scored"] >= t.min_samples and prev["n_scored"] >= t.min_samples
                        and latest["mean_score"] is not None and prev["mean_score"] is not None):
                    a, b = _norm(prev), _norm(latest)
                    if a - b > t.quality_drop_max:
                        out.append(_alert(
                            "quality_regression", "warning", "Possible prompt-version regression",
                            f"'{prompt}' {metric}: v{prev['_id']['prompt_version']} scored "
                            f"{a:.2f} and v{latest['_id']['prompt_version']} scored {b:.2f} "
                            f"(normalised 0-1; drop limit {t.quality_drop_max}). Based on "
                            f"{prev['n_scored']} and {latest['n_scored']} scored outputs; the "
                            "difference may also reflect different test data.",
                            {"prompt_id": pid, "metric": metric, "kind": latest["_id"]["kind"]}))
        return out

    # ----- pricing
    def add_price(self, data: PricingCreate) -> dict:
        return self._pricing.create(data.model_dump())

    def list_prices(self) -> list[dict]:
        return self._pricing.list()

    def delete_price(self, pricing_id: str) -> None:
        self._pricing.delete(pricing_id)

    # ----- feedback
    def add_feedback(self, data: FeedbackCreate) -> dict:
        trace = self._requests.get(data.request_id)
        if trace is None:
            raise NotFoundError("Request not found (it may be outside the retention period).")
        fields = {
            "rating": data.rating,
            "comment": redact(data.comment, self._settings.redaction_enabled),
            "project_id": trace.get("project_id"), "prompt_id": trace.get("prompt_id"),
            "prompt_version": trace.get("prompt_version"), "provider": trace.get("provider"),
            "model": trace.get("model"),
        }
        return self._feedback.upsert(data.request_id, fields)

    def recent_feedback(self, f: Filters, limit: int) -> list[dict]:
        return self._m.recent_feedback(self._fb_match(f), limit)


def _norm(row: dict) -> float:
    """Put judge scores (1-5) on the same 0-1 scale as objective metrics."""
    return (row["mean_score"] - 1) / 4 if row["_id"]["type"] == "llm_judge" else row["mean_score"]


def _alert(kind: str, severity: str, title: str, message: str, evidence: dict) -> dict:
    return {"type": kind, "severity": severity, "title": title, "message": message,
            "evidence": evidence}
