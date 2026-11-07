"""Database-side aggregation for monitoring. Everything is computed by MongoDB queries,
so the dashboard never loads whole request histories into Python."""
from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.repositories.assets import _guard

_HIDE = {"_id": 0}


def _ok(status: str):
    return {"$cond": [{"$eq": ["$status", status]}, 1, 0]}


class MetricsRepository:
    def __init__(self, db: Database):
        self._r = db["requests"]
        self._f = db["feedback"]

    @_guard
    def counts(self, match: dict) -> dict:
        return {
            "total": self._r.count_documents(match),
            "success": self._r.count_documents({**match, "status": "success"}),
            "failed": self._r.count_documents({**match, "status": "error"}),
            "with_usage": self._r.count_documents({**match, "total_tokens": {"$ne": None}}),
        }

    @_guard
    def sums(self, match: dict) -> dict:
        out = list(self._r.aggregate([
            {"$match": match},
            {"$group": {
                "_id": None, "avg_latency_ms": {"$avg": "$latency_ms"},
                "input_tokens": {"$sum": "$input_tokens"}, "output_tokens": {"$sum": "$output_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
            }},
        ]))
        return out[0] if out else {"avg_latency_ms": None, "input_tokens": 0, "output_tokens": 0,
                                   "total_tokens": 0}

    @_guard
    def percentile(self, match: dict, field: str, p: float) -> float | None:
        """Exact nearest-rank percentile using count + indexed sort/skip (no full scan in Python)."""
        q = {**match, field: {"$ne": None}}
        n = self._r.count_documents(q)
        if n == 0:
            return None
        rank = max(1, math.ceil(p / 100 * n))
        doc = next(iter(self._r.find(q, {field: 1, "_id": 0}).sort(field, 1).skip(rank - 1).limit(1)),
                   None)
        return doc[field] if doc else None

    @_guard
    def series(self, match: dict, fmt: str) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": match},
            {"$group": {
                "_id": {"$dateToString": {"format": fmt, "date": "$created_at"}},
                "requests": {"$sum": 1}, "success": {"$sum": _ok("success")},
                "failed": {"$sum": _ok("error")}, "avg_latency_ms": {"$avg": "$latency_ms"},
                "input_tokens": {"$sum": "$input_tokens"}, "output_tokens": {"$sum": "$output_tokens"},
            }},
            {"$sort": {"_id": 1}},
        ]))

    @_guard
    def by_model(self, match: dict) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": match},
            {"$group": {
                "_id": {"provider": "$provider", "model": "$model"}, "requests": {"$sum": 1},
                "success": {"$sum": _ok("success")}, "failed": {"$sum": _ok("error")},
                "avg_latency_ms": {"$avg": "$latency_ms"},
                "input_tokens": {"$sum": "$input_tokens"}, "output_tokens": {"$sum": "$output_tokens"},
            }},
            {"$sort": {"requests": -1}},
        ]))

    @_guard
    def by_prompt_version(self, match: dict) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": {**match, "prompt_id": {"$ne": None}}},
            {"$group": {
                "_id": {"prompt_id": "$prompt_id", "prompt_version": "$prompt_version"},
                "requests": {"$sum": 1}, "success": {"$sum": _ok("success")},
                "failed": {"$sum": _ok("error")}, "avg_latency_ms": {"$avg": "$latency_ms"},
                "input_tokens": {"$sum": "$input_tokens"}, "output_tokens": {"$sum": "$output_tokens"},
            }},
            {"$sort": {"_id.prompt_id": 1, "_id.prompt_version": 1}},
        ]))

    @_guard
    def group_by(self, match: dict, fields: dict[str, str]) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": match},
            {"$group": {
                "_id": {name: f"${path}" for name, path in fields.items()},
                "requests": {"$sum": 1}, "failed": {"$sum": _ok("error")},
                "avg_latency_ms": {"$avg": "$latency_ms"},
                "input_tokens": {"$sum": "$input_tokens"}, "output_tokens": {"$sum": "$output_tokens"},
            }},
            {"$sort": {"requests": -1}},
        ]))

    @_guard
    def cost_groups(self, match: dict) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": match},
            {"$group": {
                "_id": {"provider": "$provider", "model": "$model",
                        "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}},
                "requests": {"$sum": 1},
                "input_tokens": {"$sum": "$input_tokens"}, "output_tokens": {"$sum": "$output_tokens"},
            }},
        ]))

    @_guard
    def count_with_usage_by_group(self, match: dict) -> dict:
        """Requests whose provider reported token usage, per (provider, model, day)."""
        rows = self._r.aggregate([
            {"$match": {**match, "total_tokens": {"$ne": None}}},
            {"$group": {
                "_id": {"provider": "$provider", "model": "$model",
                        "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}},
                "n": {"$sum": 1},
            }},
        ])
        return {(r["_id"]["provider"], r["_id"]["model"], r["_id"]["day"]): r["n"] for r in rows}

    def _eval_match(self, match: dict) -> dict:
        return {**match, "evaluations.0": {"$exists": True}}

    @_guard
    def quality_series(self, match: dict, fmt: str) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": self._eval_match(match)},
            {"$unwind": "$evaluations"},
            {"$group": {
                "_id": {"bucket": {"$dateToString": {"format": fmt, "date": "$created_at"}},
                        "name": "$evaluations.name", "type": "$evaluations.type",
                        "kind": "$evaluations.kind"},
                "mean_score": {"$avg": "$evaluations.score"},
                "n_scored": {"$sum": {"$cond": [{"$gt": ["$evaluations.score", None]}, 1, 0]}},
                "passed": {"$sum": {"$cond": [{"$eq": ["$evaluations.passed", True]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$eq": ["$evaluations.passed", False]}, 1, 0]}},
            }},
            {"$sort": {"_id.bucket": 1}},
        ]))

    @_guard
    def quality_by_version(self, match: dict) -> list[dict]:
        return list(self._r.aggregate([
            {"$match": {**self._eval_match(match), "prompt_id": {"$ne": None}}},
            {"$unwind": "$evaluations"},
            {"$group": {
                "_id": {"prompt_id": "$prompt_id", "prompt_version": "$prompt_version",
                        "name": "$evaluations.name", "type": "$evaluations.type",
                        "kind": "$evaluations.kind"},
                "mean_score": {"$avg": "$evaluations.score"},
                "n_scored": {"$sum": {"$cond": [{"$gt": ["$evaluations.score", None]}, 1, 0]}},
                "passed": {"$sum": {"$cond": [{"$eq": ["$evaluations.passed", True]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$eq": ["$evaluations.passed", False]}, 1, 0]}},
            }},
        ]))

    @_guard
    def input_stats(self, match: dict) -> dict:
        out = list(self._r.aggregate([
            {"$match": match},
            {"$group": {"_id": None, "n": {"$sum": 1}, "mean": {"$avg": "$prompt_chars"},
                        "min": {"$min": "$prompt_chars"}, "max": {"$max": "$prompt_chars"}}},
        ]))
        base = out[0] if out else {"n": 0, "mean": None, "min": None, "max": None}
        base.pop("_id", None)
        base["p50"] = self.percentile(match, "prompt_chars", 50)
        base["p95"] = self.percentile(match, "prompt_chars", 95)
        return base

    @_guard
    def feedback_summary(self, match: dict) -> dict:
        rows = list(self._f.aggregate([
            {"$match": match}, {"$group": {"_id": "$rating", "n": {"$sum": 1}}},
        ]))
        dist = {int(r["_id"]): r["n"] for r in rows}
        n = sum(dist.values())
        avg = sum(k * v for k, v in dist.items()) / n if n else None
        return {"count": n, "avg_rating": round(avg, 3) if avg is not None else None,
                "distribution": {str(k): dist.get(k, 0) for k in range(1, 6)}}

    @_guard
    def feedback_by_version(self, match: dict) -> list[dict]:
        return list(self._f.aggregate([
            {"$match": {**match, "prompt_id": {"$ne": None}}},
            {"$group": {"_id": {"prompt_id": "$prompt_id", "prompt_version": "$prompt_version"},
                        "count": {"$sum": 1}, "avg_rating": {"$avg": "$rating"}}},
        ]))

    @_guard
    def recent_feedback(self, match: dict, limit: int) -> list[dict]:
        return list(self._f.find(match, _HIDE).sort("created_at", -1).limit(limit))


class FeedbackRepository:
    def __init__(self, db: Database):
        self._f = db["feedback"]

    @_guard
    def upsert(self, request_id: str, fields: dict) -> dict:
        now = datetime.now(UTC)
        return self._f.find_one_and_update(
            {"request_id": request_id},
            {"$set": {**fields, "updated_at": now},
             "$setOnInsert": {"id": uuid.uuid4().hex, "created_at": now, "request_id": request_id}},
            upsert=True, return_document=ReturnDocument.AFTER, projection=_HIDE,
        )


class PricingRepository:
    def __init__(self, db: Database):
        self._p = db["pricing"]

    @_guard
    def create(self, doc: dict) -> dict:
        doc = {"id": uuid.uuid4().hex, "created_at": datetime.now(UTC), **doc}
        try:
            self._p.insert_one(dict(doc))
        except DuplicateKeyError as exc:
            raise ConflictError(
                "A price for this provider, model and effective date already exists."
            ) from exc
        return doc

    @_guard
    def list(self) -> list[dict]:
        return list(self._p.find({}, _HIDE).sort([("provider", 1), ("model", 1),
                                                  ("effective_from", -1)]))

    @_guard
    def delete(self, pricing_id: str) -> None:
        if self._p.delete_one({"id": pricing_id}).deleted_count == 0:
            raise NotFoundError("Pricing entry not found")


class SettingsRepository:
    def __init__(self, db: Database):
        self._s = db["monitoring_settings"]

    @_guard
    def get(self) -> dict | None:
        return self._s.find_one({"scope": "global"}, {"_id": 0, "scope": 0})

    @_guard
    def save(self, thresholds: dict) -> None:
        self._s.update_one({"scope": "global"}, {"$set": thresholds}, upsert=True)
