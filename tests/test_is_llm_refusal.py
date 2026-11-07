"""
Regression tests for pipeline._is_llm_refusal().

Run:
    python -m pytest tests/test_is_llm_refusal.py -v
    # or directly:
    python tests/test_is_llm_refusal.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import _is_llm_refusal


# ── True cases: LLM returned a scope-refusal sentence ────────────────

def test_arabic_refusal_in_scope_message():
    assert _is_llm_refusal(
        "أنا مختص بأسئلة نظام JustClick ERP ولا أستطيع الإجابة على هذا السؤال"
    ) is True


def test_arabic_refusal_short():
    assert _is_llm_refusal("أنا مختص بأسئلة ERP فقط") is True


def test_arabic_refusal_out_of_scope_msg():
    assert _is_llm_refusal(
        "أنا متخصص في بيانات نظام JustClick ERP. "
        "اسأليني عن المبيعات، المشتريات، الحسابات، المخازن، المرتبات والضرائب."
    ) is True


def test_arabic_mixed_with_english_no_sql():
    # Arabic > 25%, no SQL keywords
    assert _is_llm_refusal("هذا السؤال خارج نطاق ERP system") is True


# ── False cases: SQL text must NOT be flagged as refusal ─────────────

def test_valid_select():
    assert _is_llm_refusal(
        "SELECT * FROM MAIN_INV WHERE ROWNUM <= 10"
    ) is False


def test_valid_with_cte():
    assert _is_llm_refusal(
        "WITH totals AS (SELECT SUM(TOTAL) FROM MAIN_INV) SELECT * FROM totals"
    ) is False


def test_sql_with_arabic_comment():
    # Arabic column alias / label alongside SELECT
    assert _is_llm_refusal(
        "SELECT CUSTID, CUSTNAME AS اسم_العميل FROM CUST WHERE ACTIVE=1"
    ) is False


def test_sql_insert_blocked_as_dml():
    # INSERT has SQL keyword → not a refusal (it's DML, handled by security layer)
    assert _is_llm_refusal(
        "INSERT INTO CUST (CUSTNAME) VALUES ('test')"
    ) is False


def test_sql_update():
    assert _is_llm_refusal("UPDATE CUST SET ACTIVE=0 WHERE CUSTID=1") is False


def test_sql_delete():
    assert _is_llm_refusal("DELETE FROM TEMP_TABLE WHERE ID=99") is False


def test_english_refusal_low_arabic():
    # Mostly English, below 25% Arabic threshold
    assert _is_llm_refusal(
        "I cannot answer questions outside the ERP scope."
    ) is False


def test_empty_string():
    assert _is_llm_refusal("") is False


def test_whitespace_only():
    assert _is_llm_refusal("   \n\t  ") is False


def test_pure_english_no_sql():
    # No Arabic, no SQL — edge case: treat as not a refusal
    assert _is_llm_refusal("Error: out of scope question") is False


def test_arabic_with_from_keyword():
    # Arabic text that happens to contain "FROM" as a word should return False
    assert _is_llm_refusal(
        "هذا السؤال من (FROM) نوع آخر غير مدعوم"
    ) is False


# ── Edge cases ────────────────────────────────────────────────────────

def test_arabic_exactly_at_25_percent_boundary():
    # 1 Arabic char, 3 non-space chars total → 33% > 25% → True (no SQL keyword)
    assert _is_llm_refusal("أab") is True


def test_arabic_just_below_25_percent():
    # 1 Arabic char, 5 non-space chars total → 20% < 25% → False
    assert _is_llm_refusal("أabcd") is False


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
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
