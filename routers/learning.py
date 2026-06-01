"""
routers/learning.py — Learning Engine API Endpoints (Enterprise)
Feedback, knowledge, ontology, visualization, BI context, metrics, events.
Secured with role-based API key authentication.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, field_validator
from typing import Optional

from learning.engine import (
    get_learning_dashboard, get_llm_context,
    get_chart_recommendation, check_followup,
)
from learning.feedback import (
    record_feedback, get_feedback_stats, get_approved_responses,
    get_common_rejections, get_feedback_by_intent,
)
from learning.template_tracker import (
    get_template_stats, get_best_templates, get_worst_templates,
)
from learning.synonym_learner import (
    learn_synonym, find_synonyms, get_synonym_stats,
)
from learning.knowledge_base import (
    add_knowledge, get_knowledge, search_knowledge,
)
from learning.embeddings import get_embedding_stats
from learning.analytics_tracker import (
    get_user_preferences, get_popular_queries, get_common_workflows,
    predict_next_intent,
)
from learning.events import get_event_stats, get_unprocessed, cleanup_old_events
from learning.ontology import (
    get_ontology_stats, find_join_path, get_tables_for_concept,
    get_tables_for_domain, add_node, add_edge,
)
from learning.visualization import (
    get_viz_stats, record_chart_selection, analyze_data_shape,
)
from learning.conversation_bi import (
    get_context as get_bi_context, clear_context as clear_bi_context,
    cleanup_expired as cleanup_bi_expired,
)
from learning.safety import (
    is_safe_sql, is_safe_knowledge, validate_feedback,
)
from learning.metrics import (
    get_health_report, get_all_metric_summaries,
    get_metric_summary, get_metric_timeseries, cleanup_old_metrics,
)
from learning.store import get_backend

log = logging.getLogger("router.learning")

router = APIRouter(prefix="/learning", tags=["learning"])


# ═══════════════════════════════════════════════════════════════════
# Role-Based Authentication for Learning Endpoints
# ═══════════════════════════════════════════════════════════════════

_LEARNING_API_KEY = os.getenv("LEARNING_API_KEY", "").strip()
_LEARNING_ADMIN_KEY = os.getenv("LEARNING_ADMIN_KEY", "").strip()


def _check_learning_auth(request: Request, require_admin: bool = False) -> str:
    """
    Validate learning API access.
    Returns the role: 'admin', 'user', or raises 401/403.

    When LEARNING_API_KEY is not set, all access is allowed (dev mode).
    """
    if not _LEARNING_API_KEY:
        return "admin"  # dev mode — no auth configured

    key = request.headers.get("X-Learning-Key") or request.headers.get("X-API-Key", "")

    # Admin key grants full access
    if _LEARNING_ADMIN_KEY and key == _LEARNING_ADMIN_KEY:
        return "admin"

    # Regular learning key grants read + feedback access
    if key == _LEARNING_API_KEY:
        if require_admin:
            raise HTTPException(403, "هذا الإجراء يتطلب صلاحيات مسؤول Learning")
        return "user"

    raise HTTPException(401, "مفتاح Learning API غير صالح — أضف X-Learning-Key header")


def require_learning_read(request: Request) -> str:
    """Dependency: require at least read access to learning endpoints."""
    return _check_learning_auth(request, require_admin=False)


def require_learning_admin(request: Request) -> str:
    """Dependency: require admin access for write/delete/cleanup operations."""
    return _check_learning_auth(request, require_admin=True)


# ═══════════════════════════════════════════════════════════════════
# Feedback Endpoints
# ═══════════════════════════════════════════════════════════════════

class FeedbackRequest(BaseModel):
    user_id: str
    question: str
    feedback_type: str

    @field_validator("feedback_type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("approve", "reject", "correct", "rephrase"):
            raise ValueError("feedback_type must be: approve|reject|correct|rephrase")
        return v

    category: str = ""
    domain: str = ""
    sub_intent: str = ""
    template_used: str = ""
    sql_generated: str = ""
    ai_response: str = ""
    corrected_response: str = ""
    corrected_sql: str = ""
    user_rephrased: str = ""
    rating: int = 0
    notes: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, _role: str = Depends(require_learning_read)):
    """Submit user feedback on an AI response."""
    # Safety validation
    valid, reason = validate_feedback(
        req.feedback_type, req.question,
        req.corrected_sql, req.user_id
    )
    if not valid:
        raise HTTPException(400, reason)

    feedback_id = record_feedback(
        user_id=req.user_id,
        question=req.question,
        feedback_type=req.feedback_type,
        category=req.category,
        domain=req.domain,
        sub_intent=req.sub_intent,
        template_used=req.template_used,
        sql_generated=req.sql_generated,
        ai_response=req.ai_response,
        corrected_response=req.corrected_response,
        corrected_sql=req.corrected_sql,
        user_rephrased=req.user_rephrased,
        rating=req.rating,
        notes=req.notes,
    )
    return {"status": "recorded", "feedback_id": feedback_id}


@router.get("/feedback/stats")
async def feedback_stats(_role: str = Depends(require_learning_read)):
    return get_feedback_stats()


@router.get("/feedback/rejections")
async def feedback_rejections(_role: str = Depends(require_learning_read)):
    return get_common_rejections()


@router.get("/feedback/approved")
async def feedback_approved(sub_intent: str = "", limit: int = 20, _role: str = Depends(require_learning_read)):
    return get_approved_responses(sub_intent, limit)


@router.get("/feedback/by-intent/{sub_intent}")
async def feedback_by_intent(sub_intent: str, limit: int = 20, _role: str = Depends(require_learning_read)):
    return get_feedback_by_intent(sub_intent, limit)


# ═══════════════════════════════════════════════════════════════════
# Template Stats
# ═══════════════════════════════════════════════════════════════════

@router.get("/templates/stats")
async def template_stats(_role: str = Depends(require_learning_read)):
    return get_template_stats()


@router.get("/templates/best")
async def templates_best(limit: int = 10, _role: str = Depends(require_learning_read)):
    return get_best_templates(limit)


@router.get("/templates/worst")
async def templates_worst(limit: int = 10, _role: str = Depends(require_learning_read)):
    return get_worst_templates(limit)


# ═══════════════════════════════════════════════════════════════════
# Synonyms & Terminology
# ═══════════════════════════════════════════════════════════════════

class SynonymRequest(BaseModel):
    term: str
    canonical: str
    domain: str = ""
    sub_intent: str = ""
    confidence: float = 0.8


@router.post("/synonyms")
async def add_synonym(req: SynonymRequest, _role: str = Depends(require_learning_admin)):
    from learning.safety import is_safe_synonym
    safe, reason = is_safe_synonym(req.term, req.canonical)
    if not safe:
        raise HTTPException(400, reason)

    ok = learn_synonym(
        term=req.term, canonical=req.canonical,
        domain=req.domain, sub_intent=req.sub_intent,
        confidence=req.confidence, source="manual",
    )
    return {"status": "added" if ok else "failed"}


@router.get("/synonyms/search")
async def search_synonyms(q: str, _role: str = Depends(require_learning_read)):
    return find_synonyms(q)


@router.get("/synonyms/stats")
async def synonym_stats(_role: str = Depends(require_learning_read)):
    return get_synonym_stats()


# ═══════════════════════════════════════════════════════════════════
# ERP Knowledge
# ═══════════════════════════════════════════════════════════════════

class KnowledgeRequest(BaseModel):
    concept: str
    description_ar: str = ""
    description_en: str = ""
    domain: str = ""
    tables: list[str] = []
    terms_ar: list[str] = []
    terms_en: list[str] = []
    sql_patterns: list[str] = []


@router.post("/knowledge")
async def add_knowledge_entry(req: KnowledgeRequest, _role: str = Depends(require_learning_admin)):
    safe, reason = is_safe_knowledge(
        req.concept, req.description_ar, req.sql_patterns
    )
    if not safe:
        raise HTTPException(400, reason)

    ok = add_knowledge(
        concept=req.concept,
        description_ar=req.description_ar,
        description_en=req.description_en,
        domain=req.domain,
        tables=req.tables,
        terms_ar=req.terms_ar,
        terms_en=req.terms_en,
        sql_patterns=req.sql_patterns,
        source="manual",
    )
    return {"status": "added" if ok else "failed"}


class TrainFromQueryRequest(BaseModel):
    report_name: str
    description: str
    sql: str
    company_code: str = "1"


@router.post("/train-from-query")
async def train_from_query_endpoint(
    req: TrainFromQueryRequest,
    _role: str = Depends(require_learning_read),
):
    """
    Train the AI from an ERP report's SQL.
    The AI extracts tables, maps to domains, and uses the SQL as a reference pattern.
    """
    from learning.knowledge_base import train_from_query
    if not req.report_name.strip():
        raise HTTPException(400, "report_name مطلوب")
    if not req.sql.strip():
        raise HTTPException(400, "sql مطلوب")
    if not req.description.strip():
        raise HTTPException(400, "description مطلوب")
    return train_from_query(
        report_name=req.report_name.strip(),
        description=req.description.strip(),
        sql=req.sql.strip(),
        company_code=req.company_code,
    )


@router.get("/knowledge")
async def list_knowledge(domain: str = "", _role: str = Depends(require_learning_read)):
    return get_knowledge(domain)


@router.get("/knowledge/search")
async def search_knowledge_entries(q: str, _role: str = Depends(require_learning_read)):
    return search_knowledge(q)


# ═══════════════════════════════════════════════════════════════════
# Ontology
# ═══════════════════════════════════════════════════════════════════

@router.get("/ontology/stats")
async def ontology_stats(_role: str = Depends(require_learning_read)):
    return get_ontology_stats()


@router.get("/ontology/join-path")
async def join_path(from_table: str, to_table: str, _role: str = Depends(require_learning_read)):
    """Find the JOIN path between two tables."""
    path = find_join_path(from_table, to_table)
    if path is None:
        return {"found": False, "path": []}
    return {"found": True, "path": [dict(e) for e in path]}


@router.get("/ontology/tables-for-concept/{concept}")
async def tables_for_concept(concept: str, _role: str = Depends(require_learning_read)):
    return {"concept": concept, "tables": get_tables_for_concept(concept)}


@router.get("/ontology/tables-for-domain/{domain}")
async def tables_for_domain(domain: str, _role: str = Depends(require_learning_read)):
    return {"domain": domain, "tables": get_tables_for_domain(domain)}


class OntologyNodeRequest(BaseModel):
    key: str
    node_type: str
    label_ar: str = ""
    label_en: str = ""
    domain: str = ""


@router.post("/ontology/node")
async def add_ontology_node(req: OntologyNodeRequest, _role: str = Depends(require_learning_admin)):
    ok = add_node(req.key, req.node_type, req.label_ar,
                  req.label_en, req.domain)
    return {"status": "added" if ok else "failed"}


class OntologyEdgeRequest(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0


@router.post("/ontology/edge")
async def add_ontology_edge(req: OntologyEdgeRequest, _role: str = Depends(require_learning_admin)):
    ok = add_edge(req.source, req.target, req.relation, req.weight)
    return {"status": "added" if ok else "failed"}


# ═══════════════════════════════════════════════════════════════════
# Visualization
# ═══════════════════════════════════════════════════════════════════

@router.get("/viz/stats")
async def viz_stats(_role: str = Depends(require_learning_read)):
    return get_viz_stats()


class VizFeedbackRequest(BaseModel):
    domain: str = ""
    sub_intent: str = ""
    data_shape: str
    chart_type: str
    feedback_score: float = 1.0


@router.post("/viz/feedback")
async def viz_feedback(req: VizFeedbackRequest, _role: str = Depends(require_learning_read)):
    record_chart_selection(
        req.domain, req.sub_intent,
        req.data_shape, req.chart_type,
        req.feedback_score,
    )
    return {"status": "recorded"}


# ═══════════════════════════════════════════════════════════════════
# Conversational BI
# ═══════════════════════════════════════════════════════════════════

@router.get("/bi/context/{session_id}")
async def bi_context(session_id: str, _role: str = Depends(require_learning_read)):
    return get_bi_context(session_id)


@router.delete("/bi/context/{session_id}")
async def bi_clear_context(session_id: str, _role: str = Depends(require_learning_admin)):
    clear_bi_context(session_id)
    return {"status": "cleared"}


@router.post("/bi/cleanup")
async def bi_cleanup(_role: str = Depends(require_learning_admin)):
    deleted = cleanup_bi_expired()
    return {"status": "ok", "deleted": deleted}


# ═══════════════════════════════════════════════════════════════════
# Analytics & Workflows
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/popular")
async def popular_queries(_role: str = Depends(require_learning_read)):
    return get_popular_queries()


@router.get("/analytics/workflows")
async def common_workflows(_role: str = Depends(require_learning_read)):
    return get_common_workflows()


@router.get("/analytics/predict")
async def predict_next(intents: str, _role: str = Depends(require_learning_read)):
    intent_list = [i.strip() for i in intents.split(",") if i.strip()]
    return predict_next_intent(intent_list)


@router.get("/analytics/preferences/{user_id}")
async def user_preferences(user_id: str, _role: str = Depends(require_learning_read)):
    return get_user_preferences(user_id)


# ═══════════════════════════════════════════════════════════════════
# Events
# ═══════════════════════════════════════════════════════════════════

@router.get("/events/stats")
async def events_stats(_role: str = Depends(require_learning_read)):
    return get_event_stats()


@router.get("/events/pending")
async def events_pending(event_type: str = "", limit: int = 50, _role: str = Depends(require_learning_read)):
    return get_unprocessed(event_type, limit)


@router.post("/events/cleanup")
async def events_cleanup(days: int = 30, _role: str = Depends(require_learning_admin)):
    deleted = cleanup_old_events(days)
    return {"status": "ok", "deleted": deleted}


# ═══════════════════════════════════════════════════════════════════
# Safety
# ═══════════════════════════════════════════════════════════════════

class SqlCheckRequest(BaseModel):
    sql: str


@router.post("/safety/check-sql")
async def check_sql_safety(req: SqlCheckRequest, _role: str = Depends(require_learning_read)):
    safe, reason = is_safe_sql(req.sql)
    return {"safe": safe, "reason": reason}


# ═══════════════════════════════════════════════════════════════════
# Metrics & Health
# ═══════════════════════════════════════════════════════════════════

@router.get("/health")
async def learning_health(_role: str = Depends(require_learning_read)):
    return get_health_report()


@router.get("/metrics/summary")
async def metrics_summary(hours: int = 24, _role: str = Depends(require_learning_read)):
    return get_all_metric_summaries(hours)


@router.get("/metrics/{metric_name}")
async def metric_detail(metric_name: str, hours: int = 24, _role: str = Depends(require_learning_read)):
    return {
        "summary": get_metric_summary(metric_name, hours),
        "timeseries": get_metric_timeseries(metric_name, hours),
    }


@router.post("/metrics/cleanup")
async def metrics_cleanup(days: int = 7, _role: str = Depends(require_learning_admin)):
    deleted = cleanup_old_metrics(days)
    return {"status": "ok", "deleted": deleted}


# ═══════════════════════════════════════════════════════════════════
# Dashboard (comprehensive)
# ═══════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def learning_dashboard(_role: str = Depends(require_learning_read)):
    return get_learning_dashboard()


@router.get("/embeddings/stats")
async def embedding_stats(_role: str = Depends(require_learning_read)):
    return get_embedding_stats()


@router.get("/status")
async def learning_status(_role: str = Depends(require_learning_read)):
    """Quick status check for the learning engine."""
    return {
        "backend": get_backend(),
        "feedback": get_feedback_stats(),
        "synonyms": get_synonym_stats(),
        "ontology": get_ontology_stats(),
    }
