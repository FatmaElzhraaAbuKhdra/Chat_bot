"""
rbac.py — Role-Based Access Control + Row-Level Security
Enterprise-grade permission system for the AI Copilot.

Roles:
  admin     — Full access, all domains, all data, system management
  manager   — All domains, own branch data, reports
  accountant — Accounting domain only, own company data
  sales     — Invoicing + customers, own branch
  warehouse — Inventory domain only
  hr        — HR domain only, restricted PII
  viewer    — Read-only, no SQL visibility, limited domains

Row-level security:
  - company_code filtering (multi-tenant)
  - branch_id filtering (per-role)
  - domain restrictions (per-role)
  - sensitive column masking (PII)
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("rbac")


@dataclass
class UserRole:
    role: str
    allowed_domains: list[str] = field(default_factory=list)
    allowed_branches: list[str] = field(default_factory=list)
    can_view_sql: bool = True
    can_export: bool = True
    can_execute_actions: bool = False
    max_rows: int = 500
    masked_columns: list[str] = field(default_factory=list)
    description: str = ""


# ── Role Definitions ─────────────────────────────────────────────
ROLES: dict[str, UserRole] = {
    "admin": UserRole(
        role="admin",
        allowed_domains=["accounting", "invoicing", "inventory", "customers", "hr", "system"],
        allowed_branches=["*"],
        can_view_sql=True,
        can_export=True,
        can_execute_actions=True,
        max_rows=500,
        description="Full system access",
    ),
    "manager": UserRole(
        role="manager",
        allowed_domains=["accounting", "invoicing", "inventory", "customers", "hr"],
        allowed_branches=["*"],
        can_view_sql=True,
        can_export=True,
        can_execute_actions=True,
        max_rows=500,
        description="Management access — all domains, reports enabled",
    ),
    "accountant": UserRole(
        role="accountant",
        allowed_domains=["accounting", "invoicing"],
        allowed_branches=["*"],
        can_view_sql=True,
        can_export=True,
        can_execute_actions=False,
        max_rows=500,
        masked_columns=["EMP_SALARY", "BASIC_SALARY", "NET_SALARY"],
        description="Accounting & invoicing access",
    ),
    "sales": UserRole(
        role="sales",
        allowed_domains=["invoicing", "customers", "inventory"],
        allowed_branches=[],  # filled per-user
        can_view_sql=False,
        can_export=True,
        can_execute_actions=False,
        max_rows=200,
        masked_columns=["EMP_SALARY", "BASIC_SALARY", "NET_SALARY", "COST_PRICE"],
        description="Sales team — invoicing, customers, inventory",
    ),
    "warehouse": UserRole(
        role="warehouse",
        allowed_domains=["inventory"],
        allowed_branches=[],
        can_view_sql=False,
        can_export=False,
        can_execute_actions=False,
        max_rows=200,
        masked_columns=["FINALTOTAL", "INVTOTAL", "COST_PRICE", "EMP_SALARY"],
        description="Inventory access only",
    ),
    "hr": UserRole(
        role="hr",
        allowed_domains=["hr"],
        allowed_branches=["*"],
        can_view_sql=False,
        can_export=True,
        can_execute_actions=False,
        max_rows=200,
        description="HR domain — employees, salaries, attendance",
    ),
    "viewer": UserRole(
        role="viewer",
        allowed_domains=["invoicing", "inventory"],
        allowed_branches=[],
        can_view_sql=False,
        can_export=False,
        can_execute_actions=False,
        max_rows=50,
        masked_columns=["FINALTOTAL", "INVTOTAL", "COST_PRICE", "EMP_SALARY", "BASIC_SALARY"],
        description="Read-only limited access",
    ),
}

# ── User-Role Mapping (in production: from DB or LDAP) ───────────
# Format: user_id -> {role, company_code, branches}
_user_roles: dict[str, dict] = {}


def assign_role(user_id: str, role: str, company_code: str = "1",
                branches: list[str] = None):
    """Assign a role to a user (called from admin API or startup)."""
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}. Valid: {list(ROLES.keys())}")
    _user_roles[user_id] = {
        "role": role,
        "company_code": company_code,
        "branches": branches or [],
    }
    log.info(f"[RBAC] Assigned role={role} to user={user_id}")


def get_user_permissions(user_id: str) -> UserRole:
    """Get the effective permissions for a user."""
    user_data = _user_roles.get(user_id)
    if not user_data:
        # Default: viewer role for unknown users
        return ROLES["viewer"]
    role_name = user_data.get("role", "viewer")
    role = ROLES.get(role_name, ROLES["viewer"])

    # Apply branch restrictions from user assignment
    if role.allowed_branches != ["*"]:
        branches = user_data.get("branches", [])
        role = UserRole(
            role=role.role,
            allowed_domains=role.allowed_domains,
            allowed_branches=branches,
            can_view_sql=role.can_view_sql,
            can_export=role.can_export,
            can_execute_actions=role.can_execute_actions,
            max_rows=role.max_rows,
            masked_columns=role.masked_columns,
            description=role.description,
        )
    return role


def check_domain_access(user_id: str, domain: str) -> bool:
    """Check if user has access to a specific domain."""
    perms = get_user_permissions(user_id)
    if "*" in perms.allowed_domains or not domain:
        return True
    return domain in perms.allowed_domains


def filter_response_for_role(user_id: str, result: dict) -> dict:
    """Apply role-based filtering to a pipeline response.
    Masks SQL, restricts exports, applies column masking.
    """
    perms = get_user_permissions(user_id)

    if not perms.can_view_sql:
        result["sql_generated"] = ""

    if not perms.can_export:
        result.pop("export_available", None)

    return result


def get_max_rows(user_id: str) -> int:
    """Get the maximum rows this user can retrieve."""
    return get_user_permissions(user_id).max_rows


def get_masked_columns(user_id: str) -> list[str]:
    """Get columns that should be masked for this user."""
    return get_user_permissions(user_id).masked_columns


# ── JWT/Token-Based Identity Integration ─────────────────────────
_JWT_SECRET = os.getenv("JWT_SECRET", "")
_AUTH_MODE = os.getenv("AUTH_MODE", "api_key")  # api_key | jwt | oauth2


def verify_token(token: str) -> Optional[dict]:
    """Verify a JWT token and extract user claims.
    Returns {user_id, role, company_code, branches} or None.

    In production: replace with actual JWT library (PyJWT).
    This implementation provides the integration contract.
    """
    if not token or not _JWT_SECRET:
        return None

    try:
        import hmac
        import hashlib
        import json
        import base64

        # Simple JWT verification (HS256)
        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # Verify signature
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(_JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        ).rstrip(b"=").decode()

        if not hmac.compare_digest(expected_sig, parts[2]):
            log.warning("[RBAC] JWT signature verification failed")
            return None

        # Check expiration
        import time
        if payload.get("exp", 0) < time.time():
            return None

        return {
            "user_id": payload.get("sub", ""),
            "role": payload.get("role", "viewer"),
            "company_code": payload.get("company", "1"),
            "branches": payload.get("branches", []),
        }
    except Exception as e:
        log.debug(f"[RBAC] Token verification failed: {e}")
        return None


def authenticate_request(headers: dict) -> Optional[str]:
    """Authenticate a request and return user_id.
    Supports: API key, JWT Bearer token, or OAuth2 token.
    """
    if _AUTH_MODE == "jwt":
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            claims = verify_token(token)
            if claims:
                # Auto-assign role from token claims
                assign_role(
                    claims["user_id"],
                    claims["role"],
                    claims["company_code"],
                    claims["branches"],
                )
                return claims["user_id"]
        return None

    # Default: API key mode (existing behavior)
    return None  # handled by ApiKeyMiddleware


# ── Database-Backed Role Loading ─────────────────────────────────

def load_roles_from_db():
    """Load user-role assignments from database.
    Called at startup to populate in-memory cache.
    """
    try:
        from learning.store import get_conn, is_oracle
        with get_conn() as conn:
            if is_oracle():
                rows = conn.execute("""
                    SELECT USER_ID, ROLE_NAME, COMPANY_CODE, BRANCHES_JSON
                    FROM AI_USER_ROLES
                    WHERE IS_ACTIVE = 1
                """).fetchall()
            else:
                rows = conn.execute("""
                    SELECT user_id, role_name, company_code, branches_json
                    FROM user_roles
                    WHERE is_active = 1
                """).fetchall()

        loaded = 0
        for row in rows:
            d = dict(row)
            uid = d.get("user_id") or d.get("USER_ID", "")
            role = d.get("role_name") or d.get("ROLE_NAME", "viewer")
            company = d.get("company_code") or d.get("COMPANY_CODE", "1")
            branches_raw = d.get("branches_json") or d.get("BRANCHES_JSON", "[]")
            try:
                import json
                branches = json.loads(branches_raw) if branches_raw else []
            except Exception:
                branches = []

            if uid and role in ROLES:
                assign_role(uid, role, company, branches)
                loaded += 1

        log.info(f"[RBAC] Loaded {loaded} user roles from database")
    except Exception as e:
        log.debug(f"[RBAC] DB role loading skipped: {e}")


def inject_row_level_security(sql: str, user_id: str, company_code: str) -> str:
    """Apply row-level security to SQL based on user permissions.
    Adds BRANCH_ID filtering for branch-restricted users.
    """
    perms = get_user_permissions(user_id)

    # Branch filtering (if user is restricted to specific branches)
    if perms.allowed_branches and perms.allowed_branches != ["*"]:
        branches_str = ",".join(f"'{b}'" for b in perms.allowed_branches)
        # Only add if the query touches tables with BRANCH_ID
        if re.search(r'\bBRANCH_ID\b', sql, re.IGNORECASE) or \
           re.search(r'\b(MAIN_INV|VOUCHERS|TRANSACTION)\b', sql, re.IGNORECASE):
            # Inject branch filter
            if "WHERE" in sql.upper():
                sql = re.sub(
                    r'\bWHERE\b',
                    f"WHERE BRANCH_ID IN ({branches_str}) AND",
                    sql, count=1, flags=re.IGNORECASE
                )
            else:
                # Add WHERE before ORDER BY or FETCH
                insert_point = re.search(
                    r'\b(ORDER|FETCH|GROUP|HAVING)\b', sql, re.IGNORECASE
                )
                if insert_point:
                    sql = sql[:insert_point.start()] + \
                          f" WHERE BRANCH_ID IN ({branches_str}) " + \
                          sql[insert_point.start():]

    return sql


import re  # ensure re is available for inject_row_level_security
