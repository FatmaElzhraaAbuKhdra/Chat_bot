"""
intent_classifier.py — ERP Intelligence Router (v2)
2-Level classification:
  Level 1: Regex fast-path         → confidence 0.95  (< 1ms)
  Level 2: LLM micro-classify      → confidence 0.80-0.90  (200ms)

Plus:
  - Context-need detection (does the question need conversation history?)
  - Dashboard vs data detection
  - Entity-based domain overrides
"""
import re
import json
import logging
from dataclasses import dataclass, field

log = logging.getLogger("intent")


@dataclass
class Intent:
    category: str              # greeting | data_query | comparison | aggregation | detail_lookup | action_request | help | unclear
    domain: str = ""           # accounting | invoicing | inventory | customers | hr | system
    sub_intent: str = ""       # e.g. "balance_lookup", "invoice_detail", "sales_summary"
    entities: dict = field(default_factory=dict)
    confidence: float = 1.0
    needs_history: bool = False  # هل السؤال محتاج context من المحادثة السابقة؟
    original_question: str = ""
    source: str = "none"       # regex | keywords | llm | none


# ══════════════════════════════════════════════════════════════════
# Patterns & Signals
# ══════════════════════════════════════════════════════════════════

# ── Greeting patterns ────────────────────────────────────────────
_GREETINGS = re.compile(
    r"^(مرحبا|اهلا|السلام عليكم|صباح الخير|مساء الخير|هاي|هلا|يا هلا|"
    r"hello|hi|hey|good morning|good evening|مرحب|اهلاً|سلام)\b",
    re.IGNORECASE
)

# ── Help patterns ────────────────────────────────────────────────
_HELP = re.compile(
    r"(ايه الاسئلة|اقدر اسال|تقدر تعمل|ممكن تساعدني|المساعد|"
    r"what can you|help|how to use|ازاي اسال|ازاي استخدم)",
    re.IGNORECASE
)

# ── Contextual signals (السؤال محتاج history) ────────────────────
_CONTEXTUAL_SIGNALS = re.compile(
    r"(نفس|كمان|برضو|تاني|أكمل|فصّل|وضح\s*أكتر|الحاجة\s*دي|اللي\s*فات|"
    r"زي\s*ما\s*قلت|أكثر\s*تفصيل|same|more|also|continue|explain|"
    r"ليه\s*كده|وبعدين|وايه\s*كمان|طيب\s*و|هو\s*ليه)",
    re.IGNORECASE
)

# ── Dashboard signals (عرض شامل مش استعلام محدد) ─────────────────
_DASHBOARD_SIGNALS = re.compile(
    r"(داش\s*بورد|داشبورد|لوحة|لوحات|تحليلات|إحصائيات|احصائيات|"
    r"نظرة\s*عامة|ملخص\s*شامل|تقرير\s*شامل|overview|analytics|"
    r"dashboard|statistics|summary\s+report)",
    re.IGNORECASE
)

# ── Domain detection keywords ────────────────────────────────────
DOMAIN_SIGNALS = {
    "accounting": [
        "حساب", "حسابات", "قيد", "قيود", "مدين", "دائن", "رصيد",
        "ميزان", "كشف حساب", "يومية", "دفتر", "مركز تكلفة", "شجرة",
        "ميزانية", "قائمة الدخل",
        "account", "balance", "debit", "credit", "voucher", "journal",
        "chart", "ledger", "statement", "trial",
    ],
    "invoicing": [
        "فاتورة", "فواتير", "بيع", "شراء", "مبيعات", "مشتريات",
        "مرتجع", "ضريبة", "خصم", "سداد", "تحصيل", "قسط", "اقساط",
        "invoice", "sale", "purchase", "return", "tax", "payment",
        "discount", "installment",
    ],
    "inventory": [
        "صنف", "أصناف", "مخزون", "مخزن", "مخازن", "كارت", "كمية",
        "وحدة", "وحدات", "رصيد مخزن", "حركة مخزن", "جرد", "اصناف",
        "منتج", "منتجات", "بضاعة",
        "item", "stock", "inventory", "store", "warehouse", "quantity",
        "unit", "card", "product",
    ],
    "customers": [
        "عميل", "عملاء", "مورد", "موردين", "وكيل", "سعر", "أسعار",
        "قائمة أسعار", "ائتمان",
        "customer", "supplier", "vendor", "dealer", "price",
    ],
    "hr": [
        "موظف", "موظفين", "راتب", "رواتب", "حضور", "انصراف",
        "إجازة", "إجازات", "سلفة", "سلف", "بند", "بنود",
        "employee", "salary", "attendance", "vacation", "leave", "loan",
    ],
}

# ── Sub-intent patterns (Level 1: Regex exact match) ─────────────
SUB_INTENT_PATTERNS = {
    # Accounting
    "account_balance":    r"(رصيد\s*(حساب|الحساب)|balance\s*of\s*account|رصيد\s*\d+)",
    "account_statement":  r"(كشف\s*(حساب|الحساب)|حركات?\s*(حساب|الحساب)|statement)",
    "trial_balance":      r"(ميزان\s*المراجعة|trial\s*balance|ميزان)",
    "chart_of_accounts":  r"(شجرة\s*الحسابات|دليل\s*الحسابات|chart\s*of\s*accounts|الحسابات\s*(الفرعية|الرئيسية)|حسابات\s*(تبد[اأ]|اللي\s*تبد[اأ]|بتبد[اأ])\s*ب)",
    "account_info":       r"(نوع\s*(الحساب|حساب)|بيانات?\s*(الحساب|حساب)|معلومات?\s*(الحساب|حساب)|تفاصيل?\s*(الحساب|حساب))",
    "revenue_expenses":   r"(الإيرادات\s*وال?مصروفات|الايرادات\s*وال?مصروفات|إيرادات\s*و?مصروفات|ايرادات\s*و?مصروفات|مصروفات\s*و?إيرادات|مصروفات\s*و?ايرادات|income\s*(and|&)\s*expense|revenue.+expense|قائمة\s*الدخل|income\s*statement)",
    "voucher_details":    r"(تفاصيل?\s*(القيد|قيد)|بيانات?\s*(القيد|قيد)|voucher\s*detail)",
    "journal_entries":    r"(قيود?\s*اليومية|يومية|journal\s*entries)",

    # Invoicing
    # invoice_count* MUST precede sales_summary/invoice_detail so "عدد فواتير"
    # is read as a COUNT (all-time) and not mis-scored as a today sales summary.
    "invoice_count_purchase": r"(عدد\s*(ال)?فوات[يی]ر\s*(ال)?(مشتريات|شراء)|كم\s*فاتور[ةه]\s*(مشتريات|شراء)|count\s*(of\s*)?purchase\s*invoices?)",
    "invoice_count":          r"(عدد\s*(ال)?فوات[يی]ر|كم\s*(عدد\s*)?(ال)?فوات[يی]ر|كم\s*فاتور[ةه]|count\s*(of\s*)?invoices?|how\s*many\s*invoices?)",
    "invoice_detail":     r"(تفاصيل?\s*(الفاتور[ةه]|فاتور[ةه])|بيانات?\s*(الفاتور[ةه]|فاتور[ةه])|invoice\s*detail|فاتور[ةه]\s*(رقم|مبيعات|مشتريات)\s*\d+|فاتور[ةه]\s+\d+)",
    "sales_summary":      r"(إجمالي\s*المبيعات|مبيعات\s*(اليوم|الشهر|السنة)|total\s*sales|sales\s*summary|اجمالي\s*المبيعات)",
    "purchase_summary":   r"(إجمالي\s*المشتريات|مشتريات\s*(اليوم|الشهر|السنة)|total\s*purchase|اجمالي\s*المشتريات)",
    "top_customers":      r"(?:ل)?(أكثر|اكثر|أعلى|اعلى|أعلي|اعلي|top)\s*(\d+\s*)?(عمي?لاء|عملاء|customer)",
    "top_items":          r"(?:ل)?(أكثر|اكثر|أعلى|اعلى|أعلي|اعلي|top)\s*(\d+\s*)?(أصناف|اصناف|صنف|item|منتج|منتجات)",
    "outstanding":        r"(مستحق|متبقي|مديونية|مديون|outstanding|owing|unpaid|غير\s*مسدد)",

    # Inventory
    "stock_balance":      r"(رصيد\s*(المخزن|المخزون|مخزن)|كمية\s*(المخزن|المخزون)|stock\s*balance|اعرض\s*(المخازن|المخزن|مخازن|مخزن)|المخازن\s*كل|كل\s*المخازن|كم\s*مخزن|عدد\s*المخازن|ال?حركات?\s*(المخزن|مخزن|على\s*مخزن|اللي\s*على\s*مخزن)|عايز[هة]?\s*ال?حركات?\s*(اللي\s*)?(على|في|من|ع)\s*مخزن|حركات?\s*مخزن)",
    "item_card":          r"(كارت?\s*(الصنف|صنف)|حركات?\s*(الصنف|صنف)|item\s*card)",
    "item_info":          r"(بيانات?\s*(الصنف|صنف)|معلومات?\s*(الصنف|صنف)|تفاصيل?\s*(الصنف|صنف)|اعرض\s*(الاصناف|الأصناف|أصناف|اصناف)|كل\s*(الاصناف|الأصناف)|كم\s*صنف|عدد\s*الاصناف)",

    # Customers
    "customer_list":      r"(قائمة\s*العملاء|عملاء\s*(نشط|فعال)|list\s*customer|كل\s*العملاء)",
    "customer_info":      r"(بيانات?\s*(العميل|عميل)|معلومات?\s*(العميل|عميل)|تفاصيل?\s*(العميل|عميل)|customer\s*info)",
    "supplier_list":      r"(قائمة\s*الموردين|موردين\s*(نشط|فعال)|list\s*supplier|كل\s*الموردين)",

    # HR
    "employee_count":     r"(عدد\s*الموظفين|كم\s*موظف|employee\s*count)",
    "employee_list":      r"(قائمة\s*الموظفين|الموظفين\s*(النشط|الفعال)|كل\s*الموظفين)",
    "salary_info":        r"(رواتب|راتب|salary|مرتب|مرتبات)",
    "attendance":         r"(حضور|انصراف|غياب|attendance)",
}


# ══════════════════════════════════════════════════════════════════
# Entity extraction
# ══════════════════════════════════════════════════════════════════

ENTITY_PATTERNS = {
    "account_code":  r"(?:حساب|حسابات|كود|رقم|account|code|ب)\s*[#]?(\d{1,10})",
    "invoice_id":    r"(?:فاتور[ةه]|رقم|invoice|inv)?\s*[#]?(\d{1,12})",
    "customer_name": r"(?:عميل|اسم|customer)\s+([^\d\s].{2,30})",
    "date_single":   r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    # P1: explicit "today" signal (whole word — must NOT match اليومية/journal).
    # Templates that filter by SYSDATE require this entity, so a time-less query
    # falls through to the all-time default instead of a silent today filter.
    "time_today":    r"(?:^|\s)(اليوم|النهارده|today)(?:\s|$|؟|\?)",
    "top_n":         r"(?:ل)?(?:أكثر|اكثر|أعلى|اعلى|أعلي|اعلي|أقل|اقل|top|bottom)\s*(\d+)",
    "year":          r"(?:سنة|عام|year)\s*(\d{4})",
    "month":         r"(?:شهر|month)\s*(\d{1,2})",
    "store_name":    r"(?:مخزن|مستودع|store)\s+([^\d\s].{2,30})",
    "employee_name": r"(?:موظف|اسم|employee)\s+([^\d\s].{2,30})",
}


def _extract_entities(question: str) -> dict:
    """Extract named entities from the question."""
    entities = {}
    for name, pattern in ENTITY_PATTERNS.items():
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            entities[name] = match.group(1).strip()
    return entities


# ══════════════════════════════════════════════════════════════════
# Context-need detection
# ══════════════════════════════════════════════════════════════════

def _detect_needs_history(question: str, history: list = None) -> bool:
    """
    هل السؤال محتاج context من المحادثة السابقة؟
    يرجع True لو:
    1. فيه إشارات سياقية (نفس، كمان، برضو)
    2. أو السؤال قصير وعام + فيه history
    3. أو داشبورد بدون domain محدد + فيه history
    """
    if not history or len(history) < 2:
        return False

    # إشارات سياقية صريحة
    if _CONTEXTUAL_SIGNALS.search(question):
        return True

    # سؤال قصير جداً (أقل من 5 كلمات) + فيه history
    word_count = len(question.split())
    if word_count <= 4:
        return True

    # داشبورد/ملخص بدون domain keywords
    if _DASHBOARD_SIGNALS.search(question):
        has_domain = False
        q_lower = question.lower()
        for keywords in DOMAIN_SIGNALS.values():
            for kw in keywords:
                if kw in q_lower:
                    has_domain = True
                    break
            if has_domain:
                break
        if not has_domain:
            return True

    return False


# ══════════════════════════════════════════════════════════════════
# Main Classification
# ══════════════════════════════════════════════════════════════════

def classify_intent(question: str, history: list = None) -> Intent:
    """
    2-Level intent classification:
      Level 1: Regex exact match → confidence 0.95
      Level 2: LLM fallback      → confidence 0.80-0.90
    """
    q = question.strip()

    # Pre-normalize Arabic: collapse repeats, fix informal ة/ه, Levenshtein-1 typos
    try:
        from normalizer import normalize_question
        q_fixed, _corr = normalize_question(q)
        if _corr:
            log.info(f"[INTENT] Arabic corrected: {_corr}")
            q = q_fixed
    except Exception:
        pass

    q_lower = q.lower()

    # ── Greeting ──
    if _GREETINGS.match(q):
        return Intent(category="greeting", original_question=q)

    # ── Help ──
    if _HELP.search(q_lower):
        return Intent(category="help", original_question=q)

    # ── Context-need detection ──
    needs_history = _detect_needs_history(q, history)

    # ── Domain detection ──
    matched_domains = []
    domain_scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_SIGNALS.items():
        count = 0
        for kw in keywords:
            if kw in q_lower:
                count += 1
        if count > 0:
            matched_domains.append(domain)
            domain_scores[domain] = count

    # Pick domain with highest keyword count
    if domain_scores:
        domain = max(domain_scores, key=domain_scores.get)
    else:
        domain = ""

    # ══ Level 1: Regex exact match ══
    sub_intent = ""
    confidence = 0.7  # default (no match)
    source = "none"

    for intent_name, pattern in SUB_INTENT_PATTERNS.items():
        if re.search(pattern, q, re.IGNORECASE):
            sub_intent = intent_name
            confidence = 0.95
            source = "regex"
            break

    # ══ Level 2: LLM fallback (if regex missed) ══
    if not sub_intent:
        llm_result = _llm_classify(q, history)
        if llm_result:
            sub_intent = llm_result.get("sub_intent", "")
            confidence = 0.85
            source = "llm"
            if not domain and llm_result.get("domain"):
                domain = llm_result["domain"]
            log.info(f"[INTENT] LLM fallback: sub_intent={sub_intent} domain={domain}")

    # ── Entity extraction (always regex) ──
    entities = _extract_entities(q)

    # ── Entity-based overrides ──
    if "store_name" in entities:
        domain = "inventory"
        if not sub_intent or sub_intent in ("sales_summary", "invoice_detail", "customer_list"):
            sub_intent = "stock_balance"
            log.info("[INTENT] Override: store_name found -> inventory/stock_balance")

    # ── Category determination ──
    category = _determine_category(q_lower, sub_intent, entities)

    # ── Infer domain from sub_intent ──
    # When regex gives a high-confidence match (0.95), sub_intent domain
    # overrides DOMAIN_SIGNALS keyword detection (e.g. "رصيد المخزن" has
    # both "رصيد"→accounting and "مخزن"→inventory — sub_intent wins).
    if sub_intent:
        inferred = _infer_domain_from_sub_intent(sub_intent)
        if inferred and (not domain or (source == "regex" and confidence >= 0.95)):
            domain = inferred

    # ── Default domain ──
    if not domain and category == "data_query":
        domain = "accounting"

    log.info(f"[INTENT] result: cat={category} domain={domain} sub={sub_intent} "
             f"conf={confidence} source={source} needs_history={needs_history}")

    return Intent(
        category=category,
        domain=domain,
        sub_intent=sub_intent,
        entities=entities,
        confidence=confidence,
        needs_history=needs_history,
        original_question=q,
        source=source,
    )


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

def _determine_category(q_lower: str, sub_intent: str, entities: dict) -> str:
    """Determine the intent category."""
    # Aggregation signals
    agg_signals = [
        "إجمالي", "اجمالي", "مجموع", "total", "sum", "count",
        "عدد", "كم", "أكثر", "اكثر", "أعلى", "اعلى", "أقل", "اقل",
        "how many", "how much", "top", "bottom",
    ]
    for sig in agg_signals:
        if sig in q_lower:
            return "aggregation"

    # Comparison signals
    cmp_signals = ["مقارنة", "قارن", "الفرق", "compare", "difference", "vs", "مقابل"]
    for sig in cmp_signals:
        if sig in q_lower:
            return "comparison"

    # Detail lookup signals
    if sub_intent and ("detail" in sub_intent or "info" in sub_intent):
        return "detail_lookup"

    if entities.get("account_code") or entities.get("invoice_id"):
        return "detail_lookup"

    return "data_query"


def _infer_domain_from_sub_intent(sub_intent: str) -> str:
    """Infer domain from sub-intent name."""
    mapping = {
        "account_": "accounting",
        "trial_":   "accounting",
        "chart_":   "accounting",
        "voucher_": "accounting",
        "journal_": "accounting",
        "revenue_": "accounting",
        "invoice_": "invoicing",
        "sales_":   "invoicing",
        "purchase_": "invoicing",
        "top_customers": "invoicing",
        "top_items": "invoicing",
        "outstanding": "invoicing",
        "stock_":   "inventory",
        "item_":    "inventory",
        "customer_": "customers",
        "supplier_": "customers",
        "employee_": "hr",
        "salary_":  "hr",
        "attendance": "hr",
    }
    for prefix, domain in mapping.items():
        if sub_intent.startswith(prefix) or sub_intent == prefix:
            return domain
    return ""


# ══════════════════════════════════════════════════════════════════
# Level 3: LLM-assisted classification
# ══════════════════════════════════════════════════════════════════

_VALID_SUB_INTENTS = list(SUB_INTENT_PATTERNS.keys())
_VALID_DOMAINS = list(DOMAIN_SIGNALS.keys())

_CLASSIFY_PROMPT = f"""أنت مصنّف أسئلة لنظام ERP اسمه JustClick.
مهمتك: تحديد نوع السؤال (sub_intent) والمجال (domain) فقط.
إذا كان السؤال يشير إلى محادثة سابقة أو سياق معين، استخدم الرسائل السابقة لتحديد المجال الصحيح.

أرجع JSON فقط بدون أي نص إضافي — بالشكل:
{{"sub_intent": "...", "domain": "..."}}

القيم المتاحة لـ sub_intent:
{json.dumps(_VALID_SUB_INTENTS)}

القيم المتاحة لـ domain:
{json.dumps(_VALID_DOMAINS)}

إذا لم تتعرف على السؤال، أرجع:
{{"sub_intent": "", "domain": ""}}

أمثلة:
"عايز أعرف رصيد الحساب" → {{"sub_intent": "account_balance", "domain": "accounting"}}
"ورّيني فاتورة رقم 5000" → {{"sub_intent": "invoice_detail", "domain": "invoicing"}}
"كام موظف عندنا؟" → {{"sub_intent": "employee_count", "domain": "hr"}}
"أعلى 10 أصناف مبيعاً" → {{"sub_intent": "top_items", "domain": "invoicing"}}
"فاضل كام على العميل أحمد" → {{"sub_intent": "outstanding", "domain": "invoicing"}}
"""


def _llm_classify(question: str, history: list = None) -> dict:
    """
    Level 3: LLM micro-classification.
    Returns {{sub_intent, domain}} or None on failure.
    Uses low max_tokens (100) for speed.
    Includes recent history for contextual understanding.
    """
    try:
        from llm_client import _call_llm
        messages = [
            {"role": "system", "content": _CLASSIFY_PROMPT},
        ]
        # Include recent conversation history for context
        if history:
            for msg in history[-4:]:
                content = msg.get("content", "")[:200]
                messages.append({"role": msg["role"], "content": content})
        messages.append({"role": "user", "content": question})
        raw = _call_llm(messages, temperature=0, max_tokens=100)

        # Parse JSON from response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```json?\s*", "", raw)
            raw = re.sub(r"```\s*$", "", raw)
            raw = raw.strip()

        result = json.loads(raw)
        sub = result.get("sub_intent", "")
        dom = result.get("domain", "")

        # Validate against known values
        if sub and sub not in _VALID_SUB_INTENTS:
            log.warning(f"[INTENT] LLM returned unknown sub_intent: {sub}")
            sub = ""
        if dom and dom not in _VALID_DOMAINS:
            dom = ""

        if sub or dom:
            return {"sub_intent": sub, "domain": dom, "entities": {}}
        return None

    except Exception as e:
        log.warning(f"[INTENT] LLM classification failed: {e}")
        return None
