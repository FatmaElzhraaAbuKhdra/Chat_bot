"""
erp_actions/apex_nav.py — Oracle APEX Navigation Integration
Maps ERP concepts to APEX pages and generates deep links.
"""
import os
import re
import logging
from typing import Optional
from dataclasses import dataclass

log = logging.getLogger("erp_actions.apex")

# ══════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════

_APEX_BASE = os.getenv("APEX_BASE_URL", "").rstrip("/")
_APEX_APP_ID = os.getenv("APEX_APP_ID", "100")
_APEX_SESSION = "0"  # 0 = new session (APEX handles auth)


@dataclass
class ApexPage:
    """Definition of an APEX page."""
    page_id: int
    title_ar: str
    title_en: str
    domain: str
    keywords_ar: list[str]
    keywords_en: list[str]
    description: str = ""
    icon: str = ""


# ══════════════════════════════════════════════════════════════════
# APEX Page Registry
# ══════════════════════════════════════════════════════════════════

APEX_PAGES: list[ApexPage] = [
    # Sales & Invoicing
    ApexPage(1, "الفواتير", "Invoices", "invoicing",
             ["فاتورة", "فواتير", "بيع", "مبيعات"],
             ["invoice", "sales", "billing"],
             icon="cart"),
    ApexPage(2, "فواتير المشتريات", "Purchase Invoices", "invoicing",
             ["شراء", "مشتريات", "فاتورة شراء"],
             ["purchase", "buying"],
             icon="cart"),
    ApexPage(3, "المرتجعات", "Returns", "invoicing",
             ["مرتجع", "مرتجعات", "إرجاع"],
             ["return", "refund"],
             icon="refresh"),

    # Customers & Suppliers
    ApexPage(10, "العملاء", "Customers", "customers",
             ["عميل", "عملاء", "زبائن", "زبون"],
             ["customer", "client"],
             icon="users"),
    ApexPage(11, "الموردين", "Suppliers", "customers",
             ["مورد", "موردين", "مورّد"],
             ["supplier", "vendor"],
             icon="truck"),
    ApexPage(12, "كشف حساب العميل", "Customer Statement", "customers",
             ["كشف حساب", "حساب عميل", "مديونية"],
             ["statement", "account", "outstanding"],
             icon="file-text"),

    # Inventory
    ApexPage(20, "الأصناف", "Items", "inventory",
             ["صنف", "أصناف", "منتجات", "منتج"],
             ["item", "product"],
             icon="package"),
    ApexPage(21, "المخازن", "Stores", "inventory",
             ["مخزن", "مخازن", "مخزون", "المخزون", "مستودع"],
             ["store", "warehouse", "inventory"],
             icon="home"),
    ApexPage(22, "حركات المخزون", "Stock Movements", "inventory",
             ["حركة", "حركات", "وارد", "صادر", "تحويل"],
             ["movement", "transfer", "stock"],
             icon="activity"),
    ApexPage(23, "الجرد", "Inventory Count", "inventory",
             ["جرد", "تسوية", "عد"],
             ["count", "audit", "reconcile"],
             icon="clipboard"),

    # Accounting
    ApexPage(30, "شجرة الحسابات", "Chart of Accounts", "accounting",
             ["شجرة", "حسابات", "دليل الحسابات"],
             ["chart", "account", "coa"],
             icon="git-branch"),
    ApexPage(31, "القيود اليومية", "Journal Entries", "accounting",
             ["قيد", "قيود", "يومية"],
             ["journal", "voucher", "entry"],
             icon="edit"),
    ApexPage(32, "مراكز التكلفة", "Cost Centers", "accounting",
             ["تكلفة", "مركز تكلفة", "مراكز"],
             ["cost center"],
             icon="target"),
    ApexPage(33, "ميزان المراجعة", "Trial Balance", "accounting",
             ["ميزان", "مراجعة"],
             ["trial", "balance"],
             icon="bar-chart"),

    # HR
    ApexPage(40, "الموظفين", "Employees", "hr",
             ["موظف", "موظفين", "عمال"],
             ["employee", "staff"],
             icon="briefcase"),
    ApexPage(41, "الرواتب", "Payroll", "hr",
             ["راتب", "رواتب", "مسير"],
             ["salary", "payroll"],
             icon="dollar-sign"),
    ApexPage(42, "الحضور والانصراف", "Attendance", "hr",
             ["حضور", "انصراف", "دوام"],
             ["attendance", "time"],
             icon="clock"),
    ApexPage(43, "الإجازات", "Leave Management", "hr",
             ["إجازة", "إجازات", "اجازة"],
             ["leave", "vacation"],
             icon="calendar"),

    # Payments
    ApexPage(50, "سندات القبض", "Receipts", "invoicing",
             ["قبض", "تحصيل", "سند قبض"],
             ["receipt", "collection"],
             icon="download"),
    ApexPage(51, "سندات الصرف", "Payments", "invoicing",
             ["صرف", "دفع", "سند صرف"],
             ["payment", "disbursement"],
             icon="upload"),

    # Purchase Orders / Approvals
    ApexPage(60, "أوامر الشراء", "Purchase Orders", "invoicing",
             ["أمر شراء", "أوامر شراء", "طلب شراء"],
             ["purchase order", "po"],
             icon="shopping-bag"),
    ApexPage(61, "الاعتمادات", "Approvals", "system",
             ["اعتماد", "اعتمادات", "موافقة", "موافقات"],
             ["approval", "authorize"],
             icon="check-circle"),

    # Reports
    ApexPage(70, "التقارير", "Reports", "system",
             ["تقرير", "تقارير", "طباعة"],
             ["report", "print"],
             icon="printer"),

    # Settings
    ApexPage(80, "إعدادات النظام", "System Settings", "system",
             ["إعدادات", "ضبط", "تهيئة"],
             ["settings", "config"],
             icon="settings"),
]


# ══════════════════════════════════════════════════════════════════
# Navigation Functions
# ══════════════════════════════════════════════════════════════════

def build_apex_url(page_id: int, items: dict = None) -> str:
    """Build a full APEX deep link URL."""
    if not _APEX_BASE:
        return f"apex://page/{page_id}"

    url = f"{_APEX_BASE}/f?p={_APEX_APP_ID}:{page_id}:{_APEX_SESSION}::NO:::"
    if items:
        item_names = ",".join(items.keys())
        item_values = ",".join(str(v) for v in items.values())
        url = (f"{_APEX_BASE}/f?p={_APEX_APP_ID}:{page_id}:{_APEX_SESSION}"
               f"::NO::{item_names}:{item_values}")
    return url


def find_pages(question: str, limit: int = 5) -> list[dict]:
    """
    Find APEX pages matching a user's natural language request.
    Returns sorted list of matching pages with URLs.
    """
    q_lower = question.lower()
    scored: list[tuple[float, ApexPage]] = []

    for page in APEX_PAGES:
        score = 0.0
        # Arabic keyword matches (higher weight)
        for kw in page.keywords_ar:
            if kw in q_lower:
                score += 3.0
        # English keyword matches
        for kw in page.keywords_en:
            if kw in q_lower:
                score += 2.0
        # Title match
        if page.title_ar in q_lower:
            score += 5.0
        if page.title_en.lower() in q_lower:
            score += 4.0

        if score > 0:
            scored.append((score, page))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    results = []
    for score, page in scored[:limit]:
        results.append({
            "page_id": page.page_id,
            "title_ar": page.title_ar,
            "title_en": page.title_en,
            "domain": page.domain,
            "icon": page.icon,
            "url": build_apex_url(page.page_id),
            "relevance": round(score, 1),
        })
    return results


def get_related_pages(domain: str, limit: int = 3) -> list[dict]:
    """Get related APEX pages for a domain."""
    results = []
    for page in APEX_PAGES:
        if page.domain == domain:
            results.append({
                "page_id": page.page_id,
                "title_ar": page.title_ar,
                "title_en": page.title_en,
                "icon": page.icon,
                "url": build_apex_url(page.page_id),
            })
    return results[:limit]


# ══════════════════════════════════════════════════════════════════
# Navigation Intent Detection
# ══════════════════════════════════════════════════════════════════

_NAV_PATTERNS = re.compile(
    r"(افتح|فتح|انتقل|روح|خدني|اعرض|navigate|open|go\s*to)\s*"
    r"(شاشة|صفحة|page|screen)?\s*(.+)",
    re.IGNORECASE
)


def detect_navigation_intent(question: str) -> Optional[list[dict]]:
    """
    Detect if the user wants to navigate to an APEX page.
    Returns matched pages or None.
    """
    match = _NAV_PATTERNS.search(question.strip())
    if match:
        target = match.group(3).strip() if match.group(3) else question
        pages = find_pages(target)
        if pages:
            return pages

    # Also check for general page references without action verbs
    # Require very high confidence (title match) to avoid false positives on data queries
    pages = find_pages(question)
    return [p for p in pages if p.get("relevance", 0) >= 8.0] or None
