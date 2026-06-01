"""
prompt_manager.py — Prompt Versioning & A/B Testing
Enterprise prompt management for the AI Copilot.

Features:
  - Versioned prompt templates with metadata
  - A/B testing: random assignment to prompt variants
  - Performance tracking per variant (success rate, latency)
  - Rollback capability
  - Dynamic prompt selection based on domain/intent
"""
import time
import random
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("prompt_manager")


@dataclass
class PromptVersion:
    version_id: str
    name: str
    template: str
    created_at: float = 0.0
    is_active: bool = True
    traffic_pct: float = 100.0  # % of traffic this version handles
    # Performance metrics
    total_uses: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0.0
    avg_row_count: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    @property
    def success_rate(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.success_count / self.total_uses

    def record_use(self, success: bool, latency_ms: int, row_count: int = 0):
        """Record usage metrics for this prompt version."""
        self.total_uses += 1
        if success:
            self.success_count += 1
        # Running average
        self.avg_latency_ms = (
            (self.avg_latency_ms * (self.total_uses - 1) + latency_ms) / self.total_uses
        )
        self.avg_row_count = (
            (self.avg_row_count * (self.total_uses - 1) + row_count) / self.total_uses
        )

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "name": self.name,
            "is_active": self.is_active,
            "traffic_pct": self.traffic_pct,
            "total_uses": self.total_uses,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms),
            "created_at": self.created_at,
        }


# ── Version Registry ─────────────────────────────────────────────
_versions: dict[str, PromptVersion] = {}
_active_experiment: Optional[dict] = None  # {name, variants: [version_ids], started_at}


def register_version(version_id: str, name: str, template: str,
                     traffic_pct: float = 100.0) -> PromptVersion:
    """Register a new prompt version."""
    v = PromptVersion(
        version_id=version_id,
        name=name,
        template=template,
        traffic_pct=traffic_pct,
    )
    _versions[version_id] = v
    log.info(f"[PROMPT] Registered version: {version_id} ({name}) traffic={traffic_pct}%")
    return v


def get_version(version_id: str) -> Optional[PromptVersion]:
    """Get a specific prompt version."""
    return _versions.get(version_id)


def select_prompt(user_id: str = "", domain: str = "") -> PromptVersion:
    """Select the appropriate prompt version for a request.
    Uses A/B traffic splitting if an experiment is active.
    """
    active = [v for v in _versions.values() if v.is_active]
    if not active:
        # Return default (first registered)
        if _versions:
            return list(_versions.values())[0]
        return _default_version()

    # If only one active version, use it
    if len(active) == 1:
        return active[0]

    # A/B split: deterministic assignment based on user_id
    # Same user always gets same variant (consistent experience)
    if user_id:
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)
    else:
        hash_val = random.randint(0, 100)

    # Weighted selection based on traffic_pct
    total_traffic = sum(v.traffic_pct for v in active)
    threshold = (hash_val % 100) * total_traffic / 100.0
    cumulative = 0.0
    for v in active:
        cumulative += v.traffic_pct
        if threshold < cumulative:
            return v

    return active[0]


def record_result(version_id: str, success: bool, latency_ms: int,
                  row_count: int = 0):
    """Record the result of using a prompt version."""
    v = _versions.get(version_id)
    if v:
        v.record_use(success, latency_ms, row_count)


def start_experiment(name: str, variant_ids: list[str],
                     traffic_split: list[float] = None):
    """Start an A/B experiment between prompt variants."""
    global _active_experiment
    if traffic_split is None:
        # Equal split
        split = 100.0 / len(variant_ids)
        traffic_split = [split] * len(variant_ids)

    for vid, pct in zip(variant_ids, traffic_split):
        v = _versions.get(vid)
        if v:
            v.is_active = True
            v.traffic_pct = pct

    _active_experiment = {
        "name": name,
        "variants": variant_ids,
        "traffic_split": traffic_split,
        "started_at": time.time(),
    }
    log.info(f"[PROMPT] Experiment started: {name} variants={variant_ids} split={traffic_split}")


def stop_experiment() -> Optional[dict]:
    """Stop the active experiment and return results."""
    global _active_experiment
    if not _active_experiment:
        return None

    results = {
        "experiment": _active_experiment["name"],
        "duration_hours": (time.time() - _active_experiment["started_at"]) / 3600,
        "variants": [],
    }
    for vid in _active_experiment["variants"]:
        v = _versions.get(vid)
        if v:
            results["variants"].append(v.to_dict())

    _active_experiment = None

    # Declare winner (highest success rate with >10 uses)
    valid = [r for r in results["variants"] if r["total_uses"] >= 10]
    if valid:
        winner = max(valid, key=lambda x: x["success_rate"])
        results["winner"] = winner["version_id"]
    else:
        results["winner"] = None

    return results


def get_all_versions() -> list[dict]:
    """Get all registered prompt versions with metrics."""
    return [v.to_dict() for v in _versions.values()]


def get_experiment_status() -> Optional[dict]:
    """Get current experiment status."""
    if not _active_experiment:
        return None
    result = dict(_active_experiment)
    result["variants_data"] = []
    for vid in _active_experiment["variants"]:
        v = _versions.get(vid)
        if v:
            result["variants_data"].append(v.to_dict())
    return result


def compute_significance(version_a: str, version_b: str) -> dict:
    """Compute statistical significance between two prompt versions.
    Uses a simple proportion z-test for success rates.
    """
    va = _versions.get(version_a)
    vb = _versions.get(version_b)
    if not va or not vb or va.total_uses < 10 or vb.total_uses < 10:
        return {"significant": False, "reason": "Insufficient samples (need >=10 each)"}

    pa = va.success_rate
    pb = vb.success_rate
    na = va.total_uses
    nb = vb.total_uses

    # Pooled proportion
    p_pool = (va.success_count + vb.success_count) / (na + nb)
    if p_pool == 0 or p_pool == 1:
        return {"significant": False, "reason": "No variance in data"}

    # Standard error
    se = (p_pool * (1 - p_pool) * (1/na + 1/nb)) ** 0.5
    if se == 0:
        return {"significant": False, "reason": "Zero standard error"}

    # Z-score
    z = (pa - pb) / se
    # |z| > 1.96 = 95% confidence
    significant = abs(z) > 1.96

    winner = version_a if pa > pb else version_b
    return {
        "significant": significant,
        "z_score": round(z, 3),
        "confidence": "95%" if significant else "insufficient",
        "winner": winner if significant else None,
        "rate_a": round(pa, 3),
        "rate_b": round(pb, 3),
        "samples_a": na,
        "samples_b": nb,
    }


def auto_promote_winner(min_samples: int = 30) -> Optional[str]:
    """Automatically promote the best performing prompt if significant.
    Called periodically or after experiment ends.
    Returns promoted version_id or None.
    """
    if not _active_experiment:
        return None

    variants = _active_experiment.get("variants", [])
    if len(variants) < 2:
        return None

    # Check all pairs
    best = None
    best_rate = -1
    all_have_samples = True

    for vid in variants:
        v = _versions.get(vid)
        if not v or v.total_uses < min_samples:
            all_have_samples = False
            break
        if v.success_rate > best_rate:
            best_rate = v.success_rate
            best = vid

    if not all_have_samples or not best:
        return None

    # Check significance against runner-up
    others = [vid for vid in variants if vid != best]
    for other in others:
        sig = compute_significance(best, other)
        if not sig.get("significant"):
            return None  # not yet significant

    # Promote winner: set to 100% traffic, deactivate others
    for vid in variants:
        v = _versions.get(vid)
        if v:
            if vid == best:
                v.traffic_pct = 100.0
                v.is_active = True
            else:
                v.is_active = False
                v.traffic_pct = 0.0

    log.info(f"[PROMPT] Auto-promoted {best} (rate={best_rate:.3f}, "
             f"samples={_versions[best].total_uses})")
    return best


# ── Database Persistence ─────────────────────────────────────────

def persist_metrics_to_db():
    """Flush prompt version metrics to database for durability."""
    try:
        from learning.store import get_conn, is_oracle
        with get_conn() as conn:
            if is_oracle():
                for v in _versions.values():
                    conn.execute("""
                        MERGE INTO AI_PROMPT_VERSIONS t
                        USING (SELECT :1 AS vid FROM DUAL) s
                        ON (t.VERSION_ID = s.vid)
                        WHEN MATCHED THEN UPDATE SET
                            TOTAL_USES = :2, SUCCESS_COUNT = :3,
                            AVG_LATENCY_MS = :4, TRAFFIC_PCT = :5,
                            IS_ACTIVE = :6, UPDATED_AT = SYSTIMESTAMP
                        WHEN NOT MATCHED THEN INSERT
                            (VERSION_ID, NAME, TEMPLATE, TOTAL_USES,
                             SUCCESS_COUNT, AVG_LATENCY_MS, TRAFFIC_PCT, IS_ACTIVE)
                        VALUES (:7, :8, :9, :10, :11, :12, :13, :14)
                    """, (
                        v.version_id, v.total_uses, v.success_count,
                        v.avg_latency_ms, v.traffic_pct,
                        1 if v.is_active else 0,
                        v.version_id, v.name, v.template[:500],
                        v.total_uses, v.success_count, v.avg_latency_ms,
                        v.traffic_pct, 1 if v.is_active else 0,
                    ))
            else:
                for v in _versions.values():
                    conn.execute("""
                        INSERT OR REPLACE INTO prompt_versions
                            (version_id, name, template, total_uses,
                             success_count, avg_latency_ms, traffic_pct, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        v.version_id, v.name, v.template[:500],
                        v.total_uses, v.success_count, v.avg_latency_ms,
                        v.traffic_pct, 1 if v.is_active else 0,
                    ))
    except Exception as e:
        log.debug(f"[PROMPT] persist failed: {e}")


def _ensure_prompt_table():
    """Create prompt versions table if needed."""
    try:
        from learning.store import get_conn, is_oracle
        with get_conn() as conn:
            if is_oracle():
                try:
                    conn.execute("""
                        CREATE TABLE AI_PROMPT_VERSIONS (
                            VERSION_ID VARCHAR2(50) PRIMARY KEY,
                            NAME VARCHAR2(200),
                            TEMPLATE CLOB,
                            TOTAL_USES NUMBER DEFAULT 0,
                            SUCCESS_COUNT NUMBER DEFAULT 0,
                            AVG_LATENCY_MS NUMBER(10,2) DEFAULT 0,
                            TRAFFIC_PCT NUMBER(5,2) DEFAULT 0,
                            IS_ACTIVE NUMBER(1) DEFAULT 1,
                            CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP,
                            UPDATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP
                        )
                    """)
                except Exception:
                    pass  # already exists
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_versions (
                        version_id TEXT PRIMARY KEY,
                        name TEXT,
                        template TEXT,
                        total_uses INTEGER DEFAULT 0,
                        success_count INTEGER DEFAULT 0,
                        avg_latency_ms REAL DEFAULT 0,
                        traffic_pct REAL DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now'))
                    )
                """)
    except Exception:
        pass


# ── Default Version ──────────────────────────────────────────────
def _default_version() -> PromptVersion:
    """Create a default version from the existing system prompt."""
    return PromptVersion(
        version_id="v1_default",
        name="Default Production Prompt",
        template="__USE_BUILTIN__",
    )


# ── Initialize ───────────────────────────────────────────────────
register_version("v1_default", "Production Prompt v1", "__USE_BUILTIN__", traffic_pct=100.0)
