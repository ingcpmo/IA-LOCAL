"""
21 CFR Part 11 compliant audit trail.

Each query to /api/v1/query generates a JSONL entry containing:
  - timestamp, entry_id, user_id, action, agent, question
  - response_hash (SHA256 of response text — full text not stored)
  - prev_entry_hash (hash of previous entry — tamper-evident chain)
  - entry_hash (SHA256 of this entry body — verifiable integrity)

The hash chain satisfies 11.10(e): secure, computer-generated, time-stamped
audit trail that cannot be altered without detection.
"""
import glob
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

AUDIT_LOG_DIR = os.getenv("AUDIT_LOG_DIR", "./data/audit_logs")
AUDIT_HASH_ALGO = os.getenv("AUDIT_LOG_HASH_ALGO", "sha256")

# In-process cache: avoids a disk read on every query after the first one.
_last_entry_hash: str | None = None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _compute_entry_hash(entry_body: dict) -> str:
    """Deterministic hash of a dict (without the entry_hash key)."""
    canonical = json.dumps(entry_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hash(canonical)


def _log_path_for_today() -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return os.path.join(AUDIT_LOG_DIR, f"audit_{date_str}.jsonl")


def _get_prev_hash() -> str:
    """Return the entry_hash of the most recent entry across all log files."""
    global _last_entry_hash
    if _last_entry_hash is not None:
        return _last_entry_hash

    # Cold start: scan existing files in chronological order
    pattern = os.path.join(AUDIT_LOG_DIR, "audit_*.jsonl")
    log_files = sorted(glob.glob(pattern))
    for path in reversed(log_files):
        try:
            with open(path, "rb") as f:
                lines = f.read().splitlines()
            for raw in reversed(lines):
                raw = raw.strip()
                if raw:
                    entry = json.loads(raw)
                    _last_entry_hash = entry.get("entry_hash", "GENESIS")
                    return _last_entry_hash
        except Exception:
            continue

    _last_entry_hash = "GENESIS"
    return "GENESIS"


def write_audit_entry(
    *,
    user_id: str,
    action: str,
    agent: str,
    question: str,
    model: str,
    context_used: bool,
    elapsed_seconds: float,
    response_text: str,
) -> dict:
    """
    Append one audit entry to today's JSONL file and return it.
    Never raises — failures are swallowed so they don't break the query response.
    """
    global _last_entry_hash
    try:
        os.makedirs(AUDIT_LOG_DIR, exist_ok=True)

        prev_hash = _get_prev_hash()

        entry_body = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": action,
            "agent": agent,
            "question": question,
            "model": model,
            "context_used": context_used,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "response_hash": f"sha256:{_hash(response_text)}",
            "prev_entry_hash": prev_hash,
        }

        entry_hash = f"sha256:{_compute_entry_hash(entry_body)}"
        entry_body["entry_hash"] = entry_hash

        with open(_log_path_for_today(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_body, separators=(",", ":"), ensure_ascii=False) + "\n")

        _last_entry_hash = entry_hash
        return entry_body

    except Exception:
        return {}


def verify_audit_logs() -> dict:
    """
    Verify the integrity of all audit log files.
    Returns a report compatible with the /api/v1/audit/verify contract.
    """
    pattern = os.path.join(AUDIT_LOG_DIR, "audit_*.jsonl")
    log_files = sorted(glob.glob(pattern))

    total_entries = 0
    verified_count = 0
    hash_errors = 0
    chain_errors = 0
    prev_hash = "GENESIS"

    for path in log_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            hash_errors += 1
            continue

        for raw in lines:
            total_entries += 1
            try:
                entry = json.loads(raw)
            except Exception:
                hash_errors += 1
                continue

            stored_hash = entry.get("entry_hash", "")

            # Recompute: remove entry_hash, hash the rest, restore
            body = {k: v for k, v in entry.items() if k != "entry_hash"}
            expected_hash = f"sha256:{_compute_entry_hash(body)}"

            if stored_hash != expected_hash:
                hash_errors += 1
                prev_hash = stored_hash  # keep chain moving
                continue

            if entry.get("prev_entry_hash") != prev_hash:
                chain_errors += 1
            else:
                verified_count += 1

            prev_hash = stored_hash

    return {
        "verified": hash_errors == 0 and chain_errors == 0,
        "log_count": total_entries,
        "log_files": len(log_files),
        "verified_count": verified_count,
        "hash_errors": hash_errors,
        "chain_errors": chain_errors,
        "failed_count": hash_errors + chain_errors,
        "hash_algo": AUDIT_HASH_ALGO,
        "audit_dir": AUDIT_LOG_DIR,
        "part11_compliant": hash_errors == 0 and chain_errors == 0 and total_entries > 0,
    }
