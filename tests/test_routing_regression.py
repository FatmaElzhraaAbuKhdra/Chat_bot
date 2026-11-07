"""
Regression tests: warehouse_transfer routing + credit_limit scope.

Run:
    python -m pytest tests/test_routing_regression.py -v
    python tests/test_routing_regression.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LEARNING_FORCE_SQLITE", "1")

from intent_classifier import classify_intent, _infer_domain_from_sub_intent


# ---------------------------------------------------------------------------
# warehouse_transfer — must ALWAYS route to warehouse_transfer, not stock_balance
# ---------------------------------------------------------------------------

def test_warehouse_transfer_basic():
    r = classify_intent("التحويلات بين المخازن")
    assert r.sub_intent == "warehouse_transfer", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_warehouse_transfer_pending():
    r = classify_intent("كام تحويل في كل حالة")
    assert r.sub_intent == "warehouse_transfer", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_warehouse_transfer_not_received():
    r = classify_intent("التحويلات اللي ما تم استلامها")
    assert r.sub_intent == "warehouse_transfer", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_warehouse_transfer_to_store():
    r = classify_intent("تحويلات من المخزن الرئيسي للمخزن الفرعي")
    assert r.sub_intent == "warehouse_transfer", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_warehouse_transfer_domain():
    assert _infer_domain_from_sub_intent("warehouse_transfer") == "inventory"


# ---------------------------------------------------------------------------
# credit_limit — must route to credit_limit (not fall through to LLM or scope refusal)
# ---------------------------------------------------------------------------

def test_credit_limit_adjective_form():
    # "الائتماني" adjective — was NOT matched before the fix
    r = classify_intent("الحد الائتماني للعملاء")
    assert r.sub_intent == "credit_limit", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_credit_limit_simple():
    r = classify_intent("حد الائتمان للعملاء")
    assert r.sub_intent == "credit_limit", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_credit_limit_noun_form():
    r = classify_intent("ما هو حد الائتمان")
    assert r.sub_intent == "credit_limit", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_credit_limit_plural_form():
    r = classify_intent("حدود الائتمان للعملاء")
    assert r.sub_intent == "credit_limit", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_credit_limit_english_keyword():
    r = classify_intent("CREDIT_LIMIT للعملاء")
    assert r.sub_intent == "credit_limit", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_credit_limit_domain_inference():
    assert _infer_domain_from_sub_intent("credit_limit") == "customers"


def test_credit_limit_confidence():
    # Regex matches must always fire at confidence 0.95
    r = classify_intent("الحد الائتماني للعملاء")
    assert r.confidence >= 0.95, f"conf={r.confidence}"


# ---------------------------------------------------------------------------
# autoprep_gaps — added in prior session, guard against regression
# ---------------------------------------------------------------------------

def test_autoprep_gaps_basic():
    r = classify_intent("أيام بدون قيد وسيط")
    assert r.sub_intent == "autoprep_gaps", f"got {r.sub_intent}"
    assert r.source == "regex"


def test_autoprep_gaps_domain():
    assert _infer_domain_from_sub_intent("autoprep_gaps") == "accounting"


# ---------------------------------------------------------------------------
# Non-overlap: credit_limit must NOT match customer_list / customer_info
# ---------------------------------------------------------------------------

def test_customer_list_not_credit():
    r = classify_intent("قائمة العملاء النشطين")
    assert r.sub_intent != "credit_limit", f"got credit_limit for customer_list question"


def test_stock_balance_not_transfer():
    r = classify_intent("رصيد المخزن الرئيسي")
    assert r.sub_intent != "warehouse_transfer", f"got warehouse_transfer for stock_balance question"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback
    passed = failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERR   {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
