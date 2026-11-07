"""Safe parsing of uploaded CSV / JSONL text.

Only the standard `csv` and `json` modules are used. Nothing is executed, imported, pickled
or evaluated, and files are never written to disk.
"""
import csv
import io
import json
import random
from collections import Counter

from app.core.errors import PayloadTooLargeError, ValidationAppError

SPLITS = ("train", "validation", "eval")


def _scalar(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def parse_dataset(filename: str, content: str, max_bytes: int, max_rows: int):
    size = len(content.encode("utf-8"))
    if size > max_bytes:
        raise PayloadTooLargeError(
            f"File is {size:,} bytes; the limit is {max_bytes:,} bytes."
        )
    if "\x00" in content:
        raise ValidationAppError("File contains binary data; only text files are accepted.")
    lower = filename.lower()
    if lower.endswith(".csv"):
        fmt, rows = "csv", _parse_csv(content, max_rows)
    elif lower.endswith((".jsonl", ".ndjson")):
        fmt, rows = "jsonl", _parse_jsonl(content, max_rows)
    else:
        raise ValidationAppError("Unsupported file type. Upload a .csv or .jsonl file.")
    if not rows:
        raise ValidationAppError("The file has no data rows.")
    return fmt, rows


def _parse_csv(content: str, max_rows: int) -> list[dict]:
    text = content.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ValidationAppError("The CSV file is empty.") from None
    header = [h.strip() for h in header]
    if not all(header):
        raise ValidationAppError("The CSV header has an empty column name.")
    dupes = [h for h, n in Counter(header).items() if n > 1]
    if dupes:
        raise ValidationAppError(f"Duplicate column names: {', '.join(dupes)}.")
    rows: list[dict] = []
    try:
        for line_no, rec in enumerate(reader, start=2):
            if not rec or all(not c.strip() for c in rec):
                continue
            if len(rec) != len(header):
                raise ValidationAppError(
                    f"Line {line_no}: expected {len(header)} columns but found {len(rec)}."
                )
            rows.append(dict(zip(header, rec, strict=True)))
            if len(rows) > max_rows:
                raise ValidationAppError(f"Too many rows; the limit is {max_rows:,}.")
    except csv.Error as exc:
        raise ValidationAppError(f"Malformed CSV: {exc}") from None
    return rows


def _parse_jsonl(content: str, max_rows: int) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            raise ValidationAppError(f"Line {line_no} is not valid JSON.") from None
        if not isinstance(obj, dict):
            raise ValidationAppError(f"Line {line_no} must be a JSON object.")
        if any(not isinstance(k, str) or not k.strip() for k in obj):
            raise ValidationAppError(f"Line {line_no} has an empty field name.")
        rows.append({k: _scalar(v) for k, v in obj.items()})
        if len(rows) > max_rows:
            raise ValidationAppError(f"Too many rows; the limit is {max_rows:,}.")
    return rows


def _kind(value) -> str:
    if value is None or value == "":
        return "empty"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    s = str(value).strip()
    if s.lower() in ("true", "false"):
        return "boolean"
    try:
        float(s)
        return "number"
    except ValueError:
        return "string"


def infer_schema(rows: list[dict]) -> list[dict]:
    names: list[str] = []
    for r in rows:
        for k in r:
            if k not in names:
                names.append(k)
    schema = []
    for name in names:
        kinds = Counter(_kind(r.get(name)) for r in rows)
        empty = kinds.pop("empty", 0)
        ftype = "empty" if not kinds else (next(iter(kinds)) if len(kinds) == 1 else "mixed")
        example = next((r[name] for r in rows if _kind(r.get(name)) != "empty"), None)
        schema.append({
            "name": name, "type": ftype, "empty_count": empty,
            "example": None if example is None else str(example)[:80],
        })
    return schema


def validate_required(rows: list[dict], schema: list[dict], required: list[str]) -> None:
    present = {f["name"] for f in schema}
    missing_cols = [f for f in required if f not in present]
    if missing_cols:
        raise ValidationAppError(f"Required field(s) not found: {', '.join(missing_cols)}.")
    problems = []
    for i, row in enumerate(rows, start=1):
        for f in required:
            if _kind(row.get(f)) == "empty":
                problems.append(f"row {i}: '{f}' is empty")
    if problems:
        shown = "; ".join(problems[:8])
        extra = f" (and {len(problems) - 8} more)" if len(problems) > 8 else ""
        raise ValidationAppError(f"Required-field check failed: {shown}{extra}.")


def assign_splits(rows: list[dict], ratios: dict[str, float] | None, seed: int) -> list[str]:
    """A 'split' column wins; otherwise seeded random split by ratios; otherwise unassigned."""
    if any("split" in r for r in rows):
        out = []
        for i, r in enumerate(rows, start=1):
            val = str(r.get("split", "")).strip().lower()
            if val not in SPLITS:
                raise ValidationAppError(
                    f"Row {i}: 'split' must be one of {', '.join(SPLITS)} (got '{val}')."
                )
            out.append(val)
        return out
    if not ratios:
        return ["unassigned"] * len(rows)
    bad = [k for k in ratios if k not in SPLITS]
    if bad or any(v < 0 for v in ratios.values()) or abs(sum(ratios.values()) - 1.0) > 1e-6:
        raise ValidationAppError(
            "split_ratios must use train/validation/eval keys, be non-negative, and sum to 1."
        )
    order = list(range(len(rows)))
    random.Random(seed).shuffle(order)
    labels = [""] * len(rows)
    names = [k for k in SPLITS if ratios.get(k, 0) > 0]
    cuts, acc = [], 0.0
    for k in names:
        acc += ratios[k]
        cuts.append(round(acc * len(rows)))
    cuts[-1] = len(rows)
    start = 0
    for k, end in zip(names, cuts, strict=True):
        for idx in order[start:end]:
            labels[idx] = k
        start = end
    return labels
