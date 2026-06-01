"""
erp_actions/planner.py — Action Planning Layer
Translates user intent into a structured ActionPlan.
Handles: intent detection for actions, parameter extraction,
         LLM-assisted parameter completion, and plan generation.
"""
import re
import json
import logging
from typing import Optional

from .models import ActionPlan, ActionType, ActionStatus, ActionRisk
from .registry import get_action_def, ACTIONS

log = logging.getLogger("erp_actions.planner")

# ══════════════════════════════════════════════════════════════════
# Action Intent Detection
# ══════════════════════════════════════════════════════════════════

# Regex patterns for detecting action intents in Arabic/English
_ACTION_PATTERNS = {
    # Approval workflow
    ActionType.APPROVE_REQUEST: re.compile(
        r"(واف[قي]|اعتمد|وافق\s*على|approve)\s*.*(طلب|request|أمر|order)\s*(?:رقم\s*)?#?(\d+)?",
        re.IGNORECASE
    ),
    ActionType.REJECT_REQUEST: re.compile(
        r"(ارفض|رفض|reject)\s*.*(طلب|request|أمر|order)\s*(?:رقم\s*)?#?(\d+)?",
        re.IGNORECASE
    ),

    # Customer/Supplier CRUD
    ActionType.CREATE_CUSTOMER: re.compile(
        r"(أنش[ئي]|انش[ئي]|سجّل|سجل|أضف|اضف|create|add)\s*.*(عميل|customer)",
        re.IGNORECASE
    ),
    ActionType.CREATE_SUPPLIER: re.compile(
        r"(أنش[ئي]|انش[ئي]|سجّل|سجل|أضف|اضف|create|add)\s*.*(مورد|supplier|vendor)",
        re.IGNORECASE
    ),
    ActionType.UPDATE_CUSTOMER: re.compile(
        r"(حدّث|حدث|عدّل|عدل|غيّر|غير|update|modify)\s*.*(بيانات\s*)?\.*(عميل|customer)",
        re.IGNORECASE
    ),
    ActionType.UPDATE_SUPPLIER: re.compile(
        r"(حدّث|حدث|عدّل|عدل|غيّر|غير|update|modify)\s*.*(بيانات\s*)?\.*(مورد|supplier|vendor)",
        re.IGNORECASE
    ),
    ActionType.DEACTIVATE_CUSTOMER: re.compile(
        r"(عطّل|عطل|ألغ[يِ]|الغ[يِ]|deactivate|disable)\s*.*(عميل|customer)",
        re.IGNORECASE
    ),

    # Item CRUD (price update BEFORE generic update — more specific wins)
    ActionType.CREATE_ITEM: re.compile(
        r"(أنش[ئي]|انش[ئي]|سجّل|سجل|أضف|اضف|create|add)\s*.*(صنف|منتج|item|product)",
        re.IGNORECASE
    ),
    ActionType.UPDATE_ITEM_PRICE: re.compile(
        r"(حدّث|حدث|غيّر|غير|عدّل|عدل|update|change)\s*.*(سعر|price)",
        re.IGNORECASE
    ),
    ActionType.UPDATE_ITEM: re.compile(
        r"(حدّث|حدث|عدّل|عدل|غيّر|غير|update|modify)\s*.*(بيانات\s*)?\.*(صنف|منتج|item|product)",
        re.IGNORECASE
    ),

    # Payments
    ActionType.CREATE_PAYMENT: re.compile(
        r"(أنش[ئي]|انش[ئي]|سجّل|سجل|create)\s*.*(سند\s*صرف|دفع[ةه]?|payment)",
        re.IGNORECASE
    ),
    ActionType.CREATE_COLLECTION: re.compile(
        r"(أنش[ئي]|انش[ئي]|سجّل|سجل|create)\s*.*(سند\s*قبض|تحصيل|collection)",
        re.IGNORECASE
    ),
}

# Confirmation patterns (user confirming a pending action)
_CONFIRM_PATTERNS = re.compile(
    r"^(نعم|أيوه|ايوه|ايوا|أيوا|تمام|موافق|اعتمد|نفذ|yes|confirm|ok|أكيد|اكيد|ماشي|يلا)\s*$",
    re.IGNORECASE
)
_REJECT_PATTERNS = re.compile(
    r"^(لا|لأ|الغ[يِ]|cancel|no|ارفض|stop|وقف)\s*$",
    re.IGNORECASE
)


def detect_action_intent(question: str) -> Optional[tuple[str, dict]]:
    """
    Detect if the user's question is an action request.
    Returns (action_type, extracted_params) or None.
    """
    q = question.strip()

    for action_type, pattern in _ACTION_PATTERNS.items():
        match = pattern.search(q)
        if match:
            params = _extract_action_params(q, action_type, match)
            log.info(f"[PLANNER] Detected action: {action_type} params={params}")
            return (action_type, params)

    return None


def is_confirmation(question: str) -> bool:
    """Check if user message is confirming a pending action."""
    return bool(_CONFIRM_PATTERNS.match(question.strip()))


def is_rejection(question: str) -> bool:
    """Check if user message is rejecting a pending action."""
    return bool(_REJECT_PATTERNS.match(question.strip()))


def _extract_action_params(question: str, action_type: str, match) -> dict:
    """Extract action parameters from the question text."""
    params = {}

    # Extract numeric IDs
    ids = re.findall(r'(?:رقم|#|كود)\s*(\d+)', question)
    if not ids:
        ids = re.findall(r'\b(\d{3,})\b', question)

    # Extract name (text after action verb, before numbers)
    name_match = re.search(
        r'(?:اسم[هه]?|باسم|اسمه)\s+([^\d\n]{2,40})',
        question
    )

    # Extract price/amount
    amount_match = re.search(
        r'(?:بقيمة|بمبلغ|سعر[هه]?|بسعر|amount|price)\s*(\d+[\.,]?\d*)',
        question
    )

    # Extract phone
    phone_match = re.search(r'(?:موبايل|هاتف|تليفون|phone|mob)\s*(\d{8,15})', question)

    # Map extracted values to action params
    if action_type in (ActionType.APPROVE_REQUEST, ActionType.REJECT_REQUEST):
        if ids:
            params["request_id"] = ids[0]
    elif action_type in (ActionType.CREATE_CUSTOMER, ActionType.CREATE_SUPPLIER):
        if name_match:
            params["cust_name"] = name_match.group(1).strip()
        elif not ids:
            # Try to find name as the last significant text
            parts = re.split(r'عميل|مورد|customer|supplier', question, flags=re.IGNORECASE)
            if len(parts) > 1:
                candidate = parts[-1].strip().rstrip('.')
                if candidate and len(candidate) > 1:
                    params["cust_name"] = candidate
        if phone_match:
            params["mob"] = phone_match.group(1)
    elif action_type in (ActionType.UPDATE_CUSTOMER, ActionType.UPDATE_SUPPLIER):
        if ids:
            params["custid"] = ids[0]
        if name_match:
            params["cust_name"] = name_match.group(1).strip()
        if phone_match:
            params["mob"] = phone_match.group(1)
    elif action_type == ActionType.DEACTIVATE_CUSTOMER:
        if ids:
            params["custid"] = ids[0]
    elif action_type in (ActionType.CREATE_ITEM, ActionType.UPDATE_ITEM):
        if ids:
            params["itemid"] = ids[0]
        if name_match:
            params["itemname"] = name_match.group(1).strip()
        if amount_match:
            params["sellprice"] = float(amount_match.group(1).replace(',', ''))
    elif action_type == ActionType.UPDATE_ITEM_PRICE:
        if ids:
            params["itemid"] = ids[0]
        if amount_match:
            params["sellprice"] = float(amount_match.group(1).replace(',', ''))
    elif action_type in (ActionType.CREATE_PAYMENT, ActionType.CREATE_COLLECTION):
        if ids:
            params["cust_id"] = ids[0]
        if amount_match:
            params["payed_amount"] = float(amount_match.group(1).replace(',', ''))

    return params


# ══════════════════════════════════════════════════════════════════
# Plan Generation
# ══════════════════════════════════════════════════════════════════

def plan_action(
    action_type: str,
    params: dict,
    user_id: str = "",
    company_code: str = "1",
    fiscal_year: str = "2024",
) -> ActionPlan:
    """
    Create an ActionPlan from detected intent and parameters.
    The plan is in PLANNED status, awaiting user confirmation.
    """
    action_def = get_action_def(action_type)

    # Check required params
    missing = [p for p in action_def.required_params if p not in params]

    # Build description
    desc_ar = action_def.description_template_ar
    desc_en = action_def.description_template_en
    try:
        desc_ar = desc_ar.format(**{**{p: "?" for p in action_def.required_params}, **params})
        desc_en = desc_en.format(**{**{p: "?" for p in action_def.required_params}, **params})
    except (KeyError, IndexError):
        pass

    # Build warnings
    warnings = []
    if missing:
        missing_labels = [
            action_def.param_labels.get(p, p) for p in missing
        ]
        warnings.append(f"بيانات ناقصة: {', '.join(missing_labels)}")

    if action_def.risk_level in (ActionRisk.HIGH.value, ActionRisk.CRITICAL.value):
        warnings.append("هذا الإجراء مالي ولا يمكن التراجع عنه")

    plan = ActionPlan(
        action_type=action_type,
        status=ActionStatus.PLANNED.value,
        risk_level=action_def.risk_level,
        user_id=user_id,
        company_code=company_code,
        fiscal_year=fiscal_year,
        description_ar=desc_ar,
        description_en=desc_en,
        target_table=action_def.target_table,
        parameters=params,
        validation_errors=missing,
        warnings=warnings,
    )

    log.info(f"[PLANNER] Plan created: {plan.id} type={action_type} "
             f"params={list(params.keys())} missing={missing}")
    return plan


def generate_missing_params_prompt(plan: ActionPlan) -> str:
    """
    Generate an Arabic prompt asking the user for missing parameters.
    Used when the plan has validation_errors (missing required params).
    """
    action_def = get_action_def(plan.action_type)
    missing = plan.validation_errors

    if not missing:
        return ""

    lines = [f"لتنفيذ: **{plan.description_ar}**", "", "أحتاج المعلومات التالية:"]
    for i, param in enumerate(missing, 1):
        label = action_def.param_labels.get(param, param)
        lines.append(f"{i}. {label}")

    lines.append("")
    lines.append("اكتب البيانات وسأكمل الإجراء.")
    return "\n".join(lines)
