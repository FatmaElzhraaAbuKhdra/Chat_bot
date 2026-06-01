"""
learning/ontology.py — ERP Ontology Graph Engine
Maps entity relationships: tables, columns, business concepts, intents.
Enables intelligent join-path discovery and contextual SQL generation.
"""
import json
import logging
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.ontology")

_T_N = lambda: tbl("ontology_nodes")
_T_E = lambda: tbl("ontology_edges")


# ═══════════════════════════════════════════════════════════════════
# Node Types
# ═══════════════════════════════════════════════════════════════════

class NodeType:
    TABLE = "table"
    COLUMN = "column"
    CONCEPT = "concept"     # business concept (e.g., "invoice", "customer")
    INTENT = "intent"       # sub_intent
    DOMAIN = "domain"
    METRIC = "metric"       # KPI / measure


class Relation:
    HAS_COLUMN = "has_column"       # table → column
    JOINS_TO = "joins_to"           # table → table (via FK)
    BELONGS_TO = "belongs_to"       # column → concept
    USED_BY = "used_by"             # table/column → intent
    IN_DOMAIN = "in_domain"         # * → domain
    ALIAS_OF = "alias_of"           # Arabic term → canonical
    COMPUTED_FROM = "computed_from"  # metric → columns
    PARENT_OF = "parent_of"         # hierarchical


# ═══════════════════════════════════════════════════════════════════
# Seed Data — JustClick ERP Schema Ontology
# ═══════════════════════════════════════════════════════════════════

_SEED_NODES = [
    # Tables
    ("tbl:MAIN_INV", NodeType.TABLE, "الفواتير الرئيسية", "Main Invoices", "invoicing"),
    ("tbl:DETAIL_INV", NodeType.TABLE, "بنود الفواتير", "Invoice Details", "invoicing"),
    ("tbl:CUST", NodeType.TABLE, "العملاء والموردين", "Customers/Suppliers", "customers"),
    ("tbl:VOUCHERS", NodeType.TABLE, "القيود المحاسبية", "Accounting Vouchers", "accounting"),
    ("tbl:VOUCHERS_DET", NodeType.TABLE, "تفاصيل القيود", "Voucher Details", "accounting"),
    ("tbl:CHARTS", NodeType.TABLE, "شجرة الحسابات", "Chart of Accounts", "accounting"),
    ("tbl:ITEMS", NodeType.TABLE, "الأصناف", "Items", "inventory"),
    ("tbl:STORE", NodeType.TABLE, "المخازن", "Stores", "inventory"),
    ("tbl:TRANSACTION", NodeType.TABLE, "حركات المخازن", "Inventory Transactions", "inventory"),
    ("tbl:TRANSACTION_TOT", NodeType.TABLE, "أرصدة المخازن", "Inventory Balances", "inventory"),
    ("tbl:EMPLOYEES", NodeType.TABLE, "الموظفين", "Employees", "hr"),
    ("tbl:EMPLOYEE_SALARIES", NodeType.TABLE, "الرواتب", "Salaries", "hr"),
    ("tbl:ATT_EMP", NodeType.TABLE, "الحضور والانصراف", "Attendance", "hr"),
    ("tbl:PAYED", NodeType.TABLE, "المسددات", "Payments", "invoicing"),
    ("tbl:COST_CENTERS", NodeType.TABLE, "مراكز التكلفة", "Cost Centers", "accounting"),
    ("tbl:ITEMGROUP", NodeType.TABLE, "مجموعات الأصناف", "Item Groups", "inventory"),
    # Domains
    ("dom:invoicing", NodeType.DOMAIN, "الفواتير والمبيعات", "Invoicing & Sales", None),
    ("dom:accounting", NodeType.DOMAIN, "المحاسبة", "Accounting", None),
    ("dom:inventory", NodeType.DOMAIN, "المخازن", "Inventory", None),
    ("dom:hr", NodeType.DOMAIN, "الموارد البشرية", "Human Resources", None),
    ("dom:customers", NodeType.DOMAIN, "العملاء", "Customers", None),
    # Business concepts
    ("con:invoice", NodeType.CONCEPT, "فاتورة", "Invoice", "invoicing"),
    ("con:payment", NodeType.CONCEPT, "سداد", "Payment", "invoicing"),
    ("con:customer", NodeType.CONCEPT, "عميل", "Customer", "customers"),
    ("con:account", NodeType.CONCEPT, "حساب", "Account", "accounting"),
    ("con:journal", NodeType.CONCEPT, "قيد يومية", "Journal Entry", "accounting"),
    ("con:item", NodeType.CONCEPT, "صنف", "Item", "inventory"),
    ("con:stock", NodeType.CONCEPT, "مخزون", "Stock", "inventory"),
    ("con:employee", NodeType.CONCEPT, "موظف", "Employee", "hr"),
    ("con:salary", NodeType.CONCEPT, "راتب", "Salary", "hr"),
    # Key metrics
    ("met:total_sales", NodeType.METRIC, "إجمالي المبيعات", "Total Sales", "invoicing"),
    ("met:total_purchases", NodeType.METRIC, "إجمالي المشتريات", "Total Purchases", "invoicing"),
    ("met:revenue", NodeType.METRIC, "الإيرادات", "Revenue", "accounting"),
    ("met:expenses", NodeType.METRIC, "المصروفات", "Expenses", "accounting"),
    ("met:stock_value", NodeType.METRIC, "قيمة المخزون", "Stock Value", "inventory"),
]

_SEED_EDGES = [
    # Table relationships (JOINs)
    ("tbl:MAIN_INV", "tbl:DETAIL_INV", Relation.JOINS_TO, 1.0,
     '{"join": "INVID, INVTYPE, RETURN_FLAG"}'),
    ("tbl:MAIN_INV", "tbl:CUST", Relation.JOINS_TO, 1.0,
     '{"join": "CUSTID = CUST_ID AND CUST_TYPE"}'),
    ("tbl:MAIN_INV", "tbl:PAYED", Relation.JOINS_TO, 0.8,
     '{"join": "via MAIN_INV_PAYED"}'),
    ("tbl:VOUCHERS", "tbl:VOUCHERS_DET", Relation.JOINS_TO, 1.0,
     '{"join": "VOUCHER_MONTH, VOUCHER_CODE"}'),
    ("tbl:VOUCHERS_DET", "tbl:CHARTS", Relation.JOINS_TO, 1.0,
     '{"join": "CHART_CODE"}'),
    ("tbl:TRANSACTION", "tbl:ITEMS", Relation.JOINS_TO, 1.0,
     '{"join": "ITEMID"}'),
    ("tbl:TRANSACTION", "tbl:STORE", Relation.JOINS_TO, 1.0,
     '{"join": "STORE_CODE"}'),
    ("tbl:TRANSACTION_TOT", "tbl:ITEMS", Relation.JOINS_TO, 1.0,
     '{"join": "ITEMID"}'),
    ("tbl:TRANSACTION_TOT", "tbl:STORE", Relation.JOINS_TO, 1.0,
     '{"join": "STORE_CODE"}'),
    ("tbl:ITEMS", "tbl:ITEMGROUP", Relation.JOINS_TO, 0.9,
     '{"join": "GRP_CODE"}'),
    ("tbl:EMPLOYEES", "tbl:EMPLOYEE_SALARIES", Relation.JOINS_TO, 1.0,
     '{"join": "EMP_CODE"}'),
    ("tbl:EMPLOYEES", "tbl:ATT_EMP", Relation.JOINS_TO, 1.0,
     '{"join": "EMP_CODE"}'),
    # Table → Domain
    ("tbl:MAIN_INV", "dom:invoicing", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:DETAIL_INV", "dom:invoicing", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:CUST", "dom:customers", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:VOUCHERS", "dom:accounting", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:VOUCHERS_DET", "dom:accounting", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:CHARTS", "dom:accounting", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:ITEMS", "dom:inventory", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:STORE", "dom:inventory", Relation.IN_DOMAIN, 1.0, None),
    ("tbl:EMPLOYEES", "dom:hr", Relation.IN_DOMAIN, 1.0, None),
    # Concept → Table
    ("con:invoice", "tbl:MAIN_INV", Relation.USED_BY, 1.0, None),
    ("con:invoice", "tbl:DETAIL_INV", Relation.USED_BY, 0.9, None),
    ("con:payment", "tbl:PAYED", Relation.USED_BY, 1.0, None),
    ("con:customer", "tbl:CUST", Relation.USED_BY, 1.0, None),
    ("con:account", "tbl:CHARTS", Relation.USED_BY, 1.0, None),
    ("con:journal", "tbl:VOUCHERS", Relation.USED_BY, 1.0, None),
    ("con:journal", "tbl:VOUCHERS_DET", Relation.USED_BY, 0.9, None),
    ("con:item", "tbl:ITEMS", Relation.USED_BY, 1.0, None),
    ("con:stock", "tbl:TRANSACTION_TOT", Relation.USED_BY, 1.0, None),
    ("con:employee", "tbl:EMPLOYEES", Relation.USED_BY, 1.0, None),
    ("con:salary", "tbl:EMPLOYEE_SALARIES", Relation.USED_BY, 1.0, None),
]


def seed_ontology() -> int:
    """Load built-in ERP ontology (run once on init)."""
    count = 0

    with get_conn() as conn:
        # Seed nodes
        for key, ntype, label_ar, label_en, domain in _SEED_NODES:
            try:
                if is_oracle():
                    conn.execute(f"""
                        MERGE INTO {_T_N()} t
                        USING (SELECT :1 AS nk FROM DUAL) s
                        ON (t.NODE_KEY = s.nk)
                        WHEN NOT MATCHED THEN INSERT
                            (NODE_KEY, NODE_TYPE, LABEL_AR, LABEL_EN, DOMAIN)
                        VALUES (:2, :3, :4, :5, :6)
                    """, (key, key, ntype, label_ar, label_en, domain))
                else:
                    conn.execute(f"""
                        INSERT OR IGNORE INTO {_T_N()}
                            (node_key, node_type, label_ar, label_en, domain)
                        VALUES (?, ?, ?, ?, ?)
                    """, (key, ntype, label_ar, label_en, domain))
                count += 1
            except Exception:
                pass

        # Seed edges
        for src, tgt, rel, weight, meta in _SEED_EDGES:
            try:
                if is_oracle():
                    conn.execute(f"""
                        MERGE INTO {_T_E()} t
                        USING (SELECT :1 AS sk, :2 AS tk, :3 AS rl FROM DUAL) s
                        ON (t.SOURCE_KEY = s.sk AND t.TARGET_KEY = s.tk
                            AND t.RELATION = s.rl)
                        WHEN NOT MATCHED THEN INSERT
                            (SOURCE_KEY, TARGET_KEY, RELATION, WEIGHT,
                             METADATA_JSON)
                        VALUES (:4, :5, :6, :7, :8)
                    """, (src, tgt, rel, src, tgt, rel, weight, meta))
                else:
                    conn.execute(f"""
                        INSERT OR IGNORE INTO {_T_E()}
                            (source_key, target_key, relation, weight,
                             metadata_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (src, tgt, rel, weight, meta))
                count += 1
            except Exception:
                pass

    log.info(f"[ONTOLOGY] Seeded {count} nodes+edges")
    return count


# ═══════════════════════════════════════════════════════════════════
# Graph Queries
# ═══════════════════════════════════════════════════════════════════

def add_node(key: str, node_type: str, label_ar: str = "",
             label_en: str = "", domain: str = "",
             metadata: dict = None) -> bool:
    """Add or update an ontology node."""
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    with get_conn() as conn:
        try:
            if is_oracle():
                conn.execute(f"""
                    MERGE INTO {_T_N()} t
                    USING (SELECT :1 AS nk FROM DUAL) s
                    ON (t.NODE_KEY = s.nk)
                    WHEN MATCHED THEN UPDATE SET
                        LABEL_AR = COALESCE(NULLIF(:2, ''), t.LABEL_AR),
                        LABEL_EN = COALESCE(NULLIF(:3, ''), t.LABEL_EN),
                        DOMAIN = COALESCE(NULLIF(:4, ''), t.DOMAIN),
                        METADATA_JSON = COALESCE(NULLIF(:5, '{{}}'), t.METADATA_JSON)
                    WHEN NOT MATCHED THEN INSERT
                        (NODE_KEY, NODE_TYPE, LABEL_AR, LABEL_EN, DOMAIN,
                         METADATA_JSON)
                    VALUES (:6, :7, :8, :9, :10, :11)
                """, (key, label_ar, label_en, domain, meta_json,
                      key, node_type, label_ar, label_en, domain, meta_json))
            else:
                conn.execute(f"""
                    INSERT INTO {_T_N()}
                        (node_key, node_type, label_ar, label_en, domain,
                         metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_key) DO UPDATE SET
                        label_ar = COALESCE(NULLIF(?, ''), label_ar),
                        label_en = COALESCE(NULLIF(?, ''), label_en),
                        domain = COALESCE(NULLIF(?, ''), domain),
                        metadata_json = COALESCE(NULLIF(?, '{{}}'), metadata_json)
                """, (key, node_type, label_ar, label_en, domain, meta_json,
                      label_ar, label_en, domain, meta_json))
            return True
        except Exception as e:
            log.warning(f"[ONTOLOGY] Add node failed: {e}")
            return False


def add_edge(source: str, target: str, relation: str,
             weight: float = 1.0, metadata: dict = None) -> bool:
    """Add or update an ontology edge."""
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    with get_conn() as conn:
        try:
            if is_oracle():
                conn.execute(f"""
                    MERGE INTO {_T_E()} t
                    USING (SELECT :1 AS sk, :2 AS tk, :3 AS rl FROM DUAL) s
                    ON (t.SOURCE_KEY = s.sk AND t.TARGET_KEY = s.tk
                        AND t.RELATION = s.rl)
                    WHEN MATCHED THEN UPDATE SET
                        WEIGHT = :4,
                        METADATA_JSON = :5
                    WHEN NOT MATCHED THEN INSERT
                        (SOURCE_KEY, TARGET_KEY, RELATION, WEIGHT, METADATA_JSON)
                    VALUES (:6, :7, :8, :9, :10)
                """, (source, target, relation, weight, meta_json,
                      source, target, relation, weight, meta_json))
            else:
                conn.execute(f"""
                    INSERT INTO {_T_E()}
                        (source_key, target_key, relation, weight, metadata_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_key, target_key, relation) DO UPDATE SET
                        weight = ?,
                        metadata_json = ?
                """, (source, target, relation, weight, meta_json,
                      weight, meta_json))
            return True
        except Exception as e:
            log.warning(f"[ONTOLOGY] Add edge failed: {e}")
            return False


def get_neighbors(node_key: str, relation: str = "",
                  direction: str = "out") -> list[dict]:
    """
    Get neighboring nodes.
    direction: 'out' (source→target), 'in' (target→source), 'both'
    """
    results = []
    with get_conn() as conn:
        if direction in ("out", "both"):
            if is_oracle():
                if relation:
                    rows = conn.execute(f"""
                        SELECT e.TARGET_KEY, e.RELATION, e.WEIGHT,
                               e.METADATA_JSON, n.NODE_TYPE,
                               n.LABEL_AR, n.LABEL_EN, n.DOMAIN
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.NODE_KEY = e.TARGET_KEY
                        WHERE e.SOURCE_KEY = :1 AND e.RELATION = :2
                        ORDER BY e.WEIGHT DESC
                    """, (node_key, relation)).fetchall()
                else:
                    rows = conn.execute(f"""
                        SELECT e.TARGET_KEY, e.RELATION, e.WEIGHT,
                               e.METADATA_JSON, n.NODE_TYPE,
                               n.LABEL_AR, n.LABEL_EN, n.DOMAIN
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.NODE_KEY = e.TARGET_KEY
                        WHERE e.SOURCE_KEY = :1
                        ORDER BY e.WEIGHT DESC
                    """, (node_key,)).fetchall()
            else:
                if relation:
                    rows = conn.execute(f"""
                        SELECT e.target_key, e.relation, e.weight,
                               e.metadata_json, n.node_type,
                               n.label_ar, n.label_en, n.domain
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.node_key = e.target_key
                        WHERE e.source_key = ? AND e.relation = ?
                        ORDER BY e.weight DESC
                    """, (node_key, relation)).fetchall()
                else:
                    rows = conn.execute(f"""
                        SELECT e.target_key, e.relation, e.weight,
                               e.metadata_json, n.node_type,
                               n.label_ar, n.label_en, n.domain
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.node_key = e.target_key
                        WHERE e.source_key = ?
                        ORDER BY e.weight DESC
                    """, (node_key,)).fetchall()
            for r in rows:
                d = dict(r)
                d["direction"] = "out"
                results.append(d)

        if direction in ("in", "both"):
            if is_oracle():
                if relation:
                    rows = conn.execute(f"""
                        SELECT e.SOURCE_KEY, e.RELATION, e.WEIGHT,
                               e.METADATA_JSON, n.NODE_TYPE,
                               n.LABEL_AR, n.LABEL_EN, n.DOMAIN
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.NODE_KEY = e.SOURCE_KEY
                        WHERE e.TARGET_KEY = :1 AND e.RELATION = :2
                        ORDER BY e.WEIGHT DESC
                    """, (node_key, relation)).fetchall()
                else:
                    rows = conn.execute(f"""
                        SELECT e.SOURCE_KEY, e.RELATION, e.WEIGHT,
                               e.METADATA_JSON, n.NODE_TYPE,
                               n.LABEL_AR, n.LABEL_EN, n.DOMAIN
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.NODE_KEY = e.SOURCE_KEY
                        WHERE e.TARGET_KEY = :1
                        ORDER BY e.WEIGHT DESC
                    """, (node_key,)).fetchall()
            else:
                if relation:
                    rows = conn.execute(f"""
                        SELECT e.source_key, e.relation, e.weight,
                               e.metadata_json, n.node_type,
                               n.label_ar, n.label_en, n.domain
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.node_key = e.source_key
                        WHERE e.target_key = ? AND e.relation = ?
                        ORDER BY e.weight DESC
                    """, (node_key, relation)).fetchall()
                else:
                    rows = conn.execute(f"""
                        SELECT e.source_key, e.relation, e.weight,
                               e.metadata_json, n.node_type,
                               n.label_ar, n.label_en, n.domain
                        FROM {_T_E()} e
                        LEFT JOIN {_T_N()} n ON n.node_key = e.source_key
                        WHERE e.target_key = ?
                        ORDER BY e.weight DESC
                    """, (node_key,)).fetchall()
            for r in rows:
                d = dict(r)
                d["direction"] = "in"
                results.append(d)

    return results


def find_join_path(from_table: str, to_table: str,
                   max_depth: int = 3) -> list[dict] | None:
    """
    Find the shortest join path between two tables.
    Returns list of edges forming the path, or None if not reachable.
    Uses BFS on the ontology graph.
    """
    src = f"tbl:{from_table}"
    tgt = f"tbl:{to_table}"

    if src == tgt:
        return []

    visited = {src}
    queue = [(src, [])]

    for _ in range(max_depth):
        next_queue = []
        for current, path in queue:
            neighbors = get_neighbors(current, relation=Relation.JOINS_TO,
                                      direction="both")
            for n in neighbors:
                neighbor_key = (n.get("target_key") or n.get("TARGET_KEY")
                                or n.get("source_key") or n.get("SOURCE_KEY"))
                if not neighbor_key or neighbor_key in visited:
                    continue

                new_path = path + [n]
                if neighbor_key == tgt:
                    return new_path

                visited.add(neighbor_key)
                next_queue.append((neighbor_key, new_path))
        queue = next_queue
        if not queue:
            break

    return None  # no path found


def get_tables_for_concept(concept: str) -> list[str]:
    """Get related tables for a business concept."""
    key = f"con:{concept}"
    neighbors = get_neighbors(key, relation=Relation.USED_BY, direction="out")
    tables = []
    for n in neighbors:
        target = n.get("target_key") or n.get("TARGET_KEY", "")
        if target.startswith("tbl:"):
            tables.append(target.replace("tbl:", ""))
    return tables


def get_tables_for_domain(domain: str) -> list[str]:
    """Get all tables in a domain."""
    dom_key = f"dom:{domain}"
    neighbors = get_neighbors(dom_key, relation=Relation.IN_DOMAIN,
                              direction="in")
    tables = []
    for n in neighbors:
        src = n.get("source_key") or n.get("SOURCE_KEY", "")
        if src.startswith("tbl:"):
            tables.append(src.replace("tbl:", ""))
    return tables


def _normalize_arabic(text: str) -> str:
    """Normalize Arabic text for fuzzy matching.
    Removes diacritics, normalizes alef/ya/ta-marbuta variants.
    """
    if not text:
        return ""
    # Remove diacritics (tashkeel)
    import re
    text = re.sub(r'[ً-ٰٟ]', '', text)
    # Normalize alef variants (أإآا → ا)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    # Normalize ta-marbuta → ha
    text = text.replace('ة', 'ه')
    # Normalize alef-maqsura → ya
    text = text.replace('ى', 'ي')
    return text.lower().strip()


def _tokenize_arabic(text: str) -> set[str]:
    """Tokenize Arabic/English text into meaningful tokens (>= 2 chars)."""
    import re
    normalized = _normalize_arabic(text)
    tokens = set(re.split(r'\s+', normalized))
    # Remove very short tokens and stop words
    _STOP = {'في', 'من', 'على', 'الي', 'ال', 'هي', 'ما', 'لا', 'و', 'the', 'of', 'in', 'a'}
    return {t for t in tokens if len(t) >= 2 and t not in _STOP}


def find_related_tables(question: str, limit: int = 8) -> list[str]:
    """
    Phase 9: Find tables related to a question using ontology graph.
    Uses token-level matching with Arabic normalization for fuzzy matching.
    Searches concepts, tables, and metrics in the ontology.
    """
    q_normalized = _normalize_arabic(question)
    q_tokens = _tokenize_arabic(question)
    matched_tables: dict[str, float] = {}  # table -> score

    if not q_tokens:
        return []

    try:
        with get_conn() as conn:
            # Load all concept/table/metric nodes
            if is_oracle():
                rows = conn.execute(f"""
                    SELECT NODE_KEY, NODE_TYPE, LABEL_AR, LABEL_EN, DOMAIN
                    FROM {_T_N()}
                    WHERE NODE_TYPE IN ('concept', 'table', 'metric')
                """).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT node_key, node_type, label_ar, label_en, domain
                    FROM {_T_N()}
                    WHERE node_type IN ('concept', 'table', 'metric')
                """).fetchall()

            scored_keys: list[tuple[str, str, float]] = []

            for r in rows:
                row_dict = dict(r)
                label_ar = row_dict.get("label_ar") or row_dict.get("LABEL_AR") or ""
                label_en = row_dict.get("label_en") or row_dict.get("LABEL_EN") or ""
                node_key = row_dict.get("node_key") or row_dict.get("NODE_KEY") or ""
                node_type = row_dict.get("node_type") or row_dict.get("NODE_TYPE") or ""

                score = 0.0

                # Method 1: Full label substring match (highest confidence)
                label_ar_norm = _normalize_arabic(label_ar)
                label_en_lower = label_en.lower()
                if label_ar_norm and label_ar_norm in q_normalized:
                    score = 3.0
                elif label_en_lower and label_en_lower in q_normalized:
                    score = 2.5

                # Method 2: Token overlap matching
                if score == 0.0:
                    label_tokens = _tokenize_arabic(label_ar)
                    if label_en:
                        label_tokens.update(_tokenize_arabic(label_en))
                    if label_tokens:
                        overlap = q_tokens & label_tokens
                        if overlap:
                            # Score based on proportion of label tokens matched
                            token_score = len(overlap) / len(label_tokens)
                            if token_score >= 0.5:  # at least half the label tokens match
                                score = 1.5 * token_score

                # Method 3: Arabic root/stem partial matching (strict)
                # Only match if root is 4+ chars and covers >60% of the token
                if score == 0.0 and label_ar_norm:
                    label_words = label_ar_norm.split()
                    for lw in label_words:
                        if len(lw) >= 4:
                            root = lw[:4]
                            for qt in q_tokens:
                                if len(qt) >= 4 and qt.startswith(root):
                                    # Root must be >60% of query token to avoid noise
                                    if len(root) / len(qt) >= 0.6:
                                        score = max(score, 0.8)
                                        break

                if score > 0:
                    scored_keys.append((node_key, node_type, score))

            # Sort by score descending, filter low-confidence matches
            scored_keys = [(k, t, s) for k, t, s in scored_keys if s >= 1.0]
            scored_keys.sort(key=lambda x: -x[2])

            for key, ntype, score in scored_keys[:8]:
                if ntype == "table" and key.startswith("tbl:"):
                    tbl_name = key.replace("tbl:", "")
                    matched_tables[tbl_name] = max(matched_tables.get(tbl_name, 0), score)
                elif ntype in ("concept", "metric"):
                    # Get tables connected to this concept
                    neighbors = get_neighbors(key, relation=Relation.USED_BY, direction="out")
                    for n in neighbors:
                        target = n.get("target_key") or n.get("TARGET_KEY", "")
                        if target.startswith("tbl:"):
                            tbl_name = target.replace("tbl:", "")
                            matched_tables[tbl_name] = max(
                                matched_tables.get(tbl_name, 0), score * 0.9
                            )

    except Exception as e:
        log.debug(f"[ONTOLOGY] find_related_tables failed: {e}")

    # Return sorted by score
    sorted_tables = sorted(matched_tables.items(), key=lambda x: -x[1])
    return [t for t, _ in sorted_tables[:limit]]


def get_ontology_stats() -> dict:
    """Get ontology graph statistics."""
    with get_conn() as conn:
        nodes_row = conn.execute(f"""
            SELECT COUNT(*) AS total_nodes,
                   COUNT(DISTINCT node_type) AS node_types,
                   COUNT(DISTINCT domain) AS domains
            FROM {_T_N()}
        """).fetchone()

        edges_row = conn.execute(f"""
            SELECT COUNT(*) AS total_edges,
                   COUNT(DISTINCT relation) AS relation_types
            FROM {_T_E()}
        """).fetchone()

        return {
            "nodes": dict(nodes_row) if nodes_row else {},
            "edges": dict(edges_row) if edges_row else {},
        }
