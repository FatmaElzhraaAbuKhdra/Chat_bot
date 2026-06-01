"""
learning/oracle_store.py — DEPRECATED
Oracle storage is now integrated into learning/store.py
This file is kept for backward compatibility only.
Import from learning.store instead.
"""
# Redirect all imports to the unified store
from .store import (  # noqa: F401
    get_conn,
    init_learning_db,
    get_backend,
    is_oracle,
    tbl,
)
