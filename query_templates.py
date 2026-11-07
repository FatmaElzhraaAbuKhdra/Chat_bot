"""
query_templates.py — ERP Query Template Registry
Predefined safe SQL patterns with parameter injection.
Each template = approved business operation with controlled parameters.

Column names verified against justclick_comments.sql:
- CHARTS: CHART_CODE, CHART_NAME_A, CHART_NAME_E, CHART_NATURE, CHART_TYPE, PARENT_CHART_CODE, CHART_LEVEL, CHART_OPEN_LOC
- VOUCHERS: VOUCHER_CODE, VOUCHER_DATE, VOUCHER_MONTH, VOUCHER_DESC (JOIN on VOUCHER_MONTH + VOUCHER_CODE)
- VOUCHERS_DET: VOUCHER_CODE, VOUCHER_MONTH, SERIAL, CHART_CODE, AMOUNT (+debit/-credit), COST_CODE
- MAIN_INV: INV_KEY, INVID, INVDATE, INVTOTAL, FINALTOTAL, TAX, SDAD, CUST_ID, CUST_TYPE, INVTYPE, RETURN_FLAG, STORE_CODE
- DETAIL_INV: INV_KEY, ITEMID, QTY, PRICE, ADD_VAL, SUB_VAL, UNIT_ID
- CUST: CUSTID, CUST_TYPE, CUST_NAME, CUST_NAME_E, OPEN_BALANCE, DBCRD, CREDIT_LIMIT, ACTIVE, CHART_CODE
- ITEMS: ITEMID, ITEMNAME, ITEM_NAME_E, SELLPRICE, TOTAL_BUYPRICE, GROUPID, UNIT_ID
- STORE: STORE_CODE, STORE_NAME, STORE_NAME_EN
- TRANSACTION_TOT: ITEMID, STORE_CODE, QTY, PRICE (current stock balance, aggregated)
- EMPLOYEES: EMP_ID, EMP_NAME_AR, EMP_NAME_EN, DEPT_CODE, JOB_CODE, HIRE_DATE, END_SERVICE_FLG (N/Y), EMP_ACTIVE (1/0), CHART_CODE
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QueryTemplate:
    name: str
    description: str
    sql: str
    required_params: list[str]
    optional_params: list[str] = field(default_factory=list)
    param_defaults: dict = field(default_factory=dict)
    domain: str = ""
    sub_intent: str = ""
    result_type: str = "table"


TEMPLATES: dict[str, QueryTemplate] = {}


def _register(t: QueryTemplate):
    TEMPLATES[t.name] = t


# ══════════════════════════════════════════════════════════════════
# Accounting Templates
# ══════════════════════════════════════════════════════════════════

_register(QueryTemplate(
    name="account_balance",
    description="رصيد حساب معين / Account balance lookup",
    domain="accounting",
    sub_intent="account_balance",
    sql="""
SELECT c.CHART_CODE,
       c.CHART_NAME_A,
       DECODE(c.CHART_TYPE, 0, 'ميزانية', 1, 'قائمة الدخل') AS CHART_TYPE,
       DECODE(c.CHART_NATURE, 0, 'عام', 1, 'مساعد') AS CHART_NATURE,
       NVL(SUM(CASE WHEN vd.AMOUNT > 0 THEN vd.AMOUNT ELSE 0 END), 0) AS total_debit,
       NVL(SUM(CASE WHEN vd.AMOUNT < 0 THEN ABS(vd.AMOUNT) ELSE 0 END), 0) AS total_credit,
       NVL(SUM(vd.AMOUNT), 0) AS balance
  FROM CHARTS c
  LEFT JOIN VOUCHERS_DET vd ON vd.CHART_CODE = c.CHART_CODE
 WHERE c.CHART_CODE LIKE '{{account_code}}%'
 GROUP BY c.CHART_CODE, c.CHART_NAME_A, c.CHART_TYPE, c.CHART_NATURE
 ORDER BY c.CHART_CODE
 FETCH FIRST 50 ROWS ONLY
""",
    required_params=["account_code"],
    result_type="table",
))

_register(QueryTemplate(
    name="account_info",
    description="بيانات حساب معين / Account info lookup",
    domain="accounting",
    sub_intent="account_info",
    sql="""
SELECT CHART_CODE,
       CHART_NAME_A,
       CHART_NAME_E,
       DECODE(CHART_TYPE, 0, 'ميزانية', 1, 'قائمة الدخل') AS CHART_TYPE,
       DECODE(CHART_NATURE, 0, 'عام', 1, 'مساعد') AS CHART_NATURE,
       PARENT_CHART_CODE,
       CHART_LEVEL,
       CHART_OPEN_LOC AS OPENING_BALANCE
  FROM CHARTS
 WHERE CHART_CODE LIKE '{{account_code}}%'
 ORDER BY CHART_CODE
 FETCH FIRST 50 ROWS ONLY
""",
    required_params=["account_code"],
    result_type="table",
))

_register(QueryTemplate(
    name="account_statement",
    description="كشف حساب / Account statement with voucher details",
    domain="accounting",
    sub_intent="account_statement",
    sql="""
SELECT v.VOUCHER_CODE,
       v.VOUCHER_DATE,
       v.VOUCHER_DESC,
       vd.CHART_CODE,
       c.CHART_NAME_A,
       CASE WHEN vd.AMOUNT > 0 THEN vd.AMOUNT ELSE 0 END AS DEBIT,
       CASE WHEN vd.AMOUNT < 0 THEN ABS(vd.AMOUNT) ELSE 0 END AS CREDIT,
       vd.AMOUNT
  FROM VOUCHERS_DET vd
  JOIN VOUCHERS v ON v.VOUCHER_CODE = vd.VOUCHER_CODE
                  AND v.VOUCHER_MONTH = vd.VOUCHER_MONTH
  JOIN CHARTS c ON c.CHART_CODE = vd.CHART_CODE
 WHERE vd.CHART_CODE LIKE '{{account_code}}%'
 ORDER BY v.VOUCHER_DATE DESC, v.VOUCHER_CODE
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=["account_code"],
    result_type="table",
))

_register(QueryTemplate(
    name="chart_of_accounts",
    description="شجرة الحسابات / Chart of accounts tree",
    domain="accounting",
    sub_intent="chart_of_accounts",
    sql="""
SELECT CHART_CODE,
       CHART_NAME_A,
       DECODE(CHART_TYPE, 0, 'ميزانية', 1, 'قائمة الدخل') AS CHART_TYPE,
       DECODE(CHART_NATURE, 0, 'عام', 1, 'مساعد') AS CHART_NATURE,
       PARENT_CHART_CODE,
       CHART_LEVEL
  FROM CHARTS
 WHERE CHART_CODE LIKE '{{account_code}}%'
 ORDER BY CHART_CODE
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=[],
    optional_params=["account_code"],
    param_defaults={"account_code": ""},
    result_type="table",
))

_register(QueryTemplate(
    name="trial_balance",
    description="ميزان المراجعة / Trial balance",
    domain="accounting",
    sub_intent="trial_balance",
    sql="""
SELECT c.CHART_CODE,
       c.CHART_NAME_A,
       NVL(SUM(CASE WHEN vd.AMOUNT > 0 THEN vd.AMOUNT ELSE 0 END), 0) AS total_debit,
       NVL(SUM(CASE WHEN vd.AMOUNT < 0 THEN ABS(vd.AMOUNT) ELSE 0 END), 0) AS total_credit,
       NVL(SUM(vd.AMOUNT), 0) AS balance
  FROM CHARTS c
  LEFT JOIN VOUCHERS_DET vd ON vd.CHART_CODE = c.CHART_CODE
 WHERE c.CHART_NATURE = {{flag:CHART_NATURE:مساعد}}
 GROUP BY c.CHART_CODE, c.CHART_NAME_A
HAVING NVL(SUM(CASE WHEN vd.AMOUNT > 0 THEN vd.AMOUNT ELSE 0 END), 0) <> 0
    OR NVL(SUM(CASE WHEN vd.AMOUNT < 0 THEN ABS(vd.AMOUNT) ELSE 0 END), 0) <> 0
 ORDER BY c.CHART_CODE
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))

_register(QueryTemplate(
    name="journal_entries",
    description="قيود اليومية / Journal entries list",
    domain="accounting",
    sub_intent="journal_entries",
    sql="""
SELECT v.VOUCHER_CODE,
       v.VOUCHER_DATE,
       v.VOUCHER_MONTH,
       v.VOUCHER_DESC
  FROM VOUCHERS v
 ORDER BY v.VOUCHER_DATE DESC, v.VOUCHER_CODE DESC
 FETCH FIRST 100 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))


# ══════════════════════════════════════════════════════════════════
# Invoicing Templates
# ══════════════════════════════════════════════════════════════════

_register(QueryTemplate(
    name="invoice_detail",
    description="تفاصيل فاتورة معينة / Invoice detail by ID",
    domain="invoicing",
    sub_intent="invoice_detail",
    sql="""
SELECT m.INVID,
       m.INVDATE,
       DECODE(m.INVTYPE, 0, 'بيع', 1, 'شراء') AS INV_TYPE,
       DECODE(m.RETURN_FLAG, 0, 'عادية', 1, 'مرتجع') AS RETURN_STATUS,
       cu.CUST_NAME,
       i.ITEMNAME,
       d.QTY,
       d.PRICE,
       (d.QTY * d.PRICE) + NVL(d.ADD_VAL,0) - NVL(d.SUB_VAL,0) AS LINE_TOTAL,
       m.FINALTOTAL
  FROM MAIN_INV m
  JOIN DETAIL_INV d ON d.INV_KEY = m.INV_KEY
  JOIN ITEMS i ON i.ITEMID = d.ITEMID
  LEFT JOIN CUST cu ON cu.CUSTID = m.CUST_ID AND cu.CUST_TYPE = m.CUST_TYPE
 WHERE m.INVID = {{invoice_id}}
   AND m.INVTYPE = {{invtype}}
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=["invoice_id", "invtype"],
    result_type="table",
))

_register(QueryTemplate(
    name="invoice_count_sales",
    description="عدد فواتير المبيعات (كل الفترات) / Count of sales invoices, all-time",
    domain="invoicing",
    sub_intent="invoice_count",
    sql="""
SELECT COUNT(*) AS invoice_count
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
""",
    required_params=[],
    result_type="scalar",
))

_register(QueryTemplate(
    name="invoice_count_purchase",
    description="عدد فواتير المشتريات (كل الفترات) / Count of purchase invoices, all-time",
    domain="invoicing",
    sub_intent="invoice_count_purchase",
    sql="""
SELECT COUNT(*) AS invoice_count
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
""",
    required_params=[],
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_alltime",
    description="إجمالي المبيعات (كل الفترات) / Sales total, all-time (default)",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales,
       NVL(SUM(TAX), 0) AS total_tax
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
""",
    required_params=[],
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_today",
    description="إجمالي مبيعات اليوم / Today's sales total",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales,
       NVL(SUM(TAX), 0) AS total_tax
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE) = TRUNC(SYSDATE)
""",
    required_params=["time_today"],   # P1: only when user explicitly says "today"
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_this_month",
    description="إجمالي مبيعات الشهر الحالي / This month's sales total",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales,
       NVL(SUM(TAX), 0) AS total_tax,
       TRUNC(SYSDATE, 'MM') AS month_start
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE, 'MM') = TRUNC(SYSDATE, 'MM')
""",
    required_params=["time_this_month"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_last_month",
    description="إجمالي مبيعات الشهر الماضي / Last month's sales total",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales,
       NVL(SUM(TAX), 0) AS total_tax,
       ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1) AS month_start
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE, 'MM') = ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
""",
    required_params=["time_last_month"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_this_year",
    description="إجمالي مبيعات هذه السنة / This year's sales total",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales,
       NVL(SUM(TAX), 0) AS total_tax,
       EXTRACT(YEAR FROM SYSDATE) AS sales_year
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND EXTRACT(YEAR FROM INVDATE) = EXTRACT(YEAR FROM SYSDATE)
""",
    required_params=["time_this_year"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_last_year",
    description="إجمالي مبيعات السنة الماضية / Last year's sales total",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales,
       NVL(SUM(TAX), 0) AS total_tax,
       EXTRACT(YEAR FROM SYSDATE) - 1 AS sales_year
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND EXTRACT(YEAR FROM INVDATE) = EXTRACT(YEAR FROM SYSDATE) - 1
""",
    required_params=["time_last_year"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="sales_summary_period",
    description="إجمالي مبيعات فترة / Sales summary for period",
    domain="invoicing",
    sub_intent="sales_summary",
    sql="""
SELECT TRUNC(INVDATE) AS sale_date,
       COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_sales
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:بيع}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE) BETWEEN TO_DATE('{{date_from}}', 'YYYY-MM-DD')
                           AND TO_DATE('{{date_to}}', 'YYYY-MM-DD')
 GROUP BY TRUNC(INVDATE)
 ORDER BY TRUNC(INVDATE) DESC
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=["date_from", "date_to"],
    result_type="table",
))

_register(QueryTemplate(
    name="purchase_summary_alltime",
    description="إجمالي المشتريات (كل الفترات) / Purchase total, all-time (default)",
    domain="invoicing",
    sub_intent="purchase_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_purchases,
       NVL(SUM(TAX), 0) AS total_tax
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
""",
    required_params=[],
    result_type="scalar",
))

_register(QueryTemplate(
    name="purchase_summary_today",
    description="إجمالي مشتريات اليوم / Today's purchase total",
    domain="invoicing",
    sub_intent="purchase_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_purchases,
       NVL(SUM(TAX), 0) AS total_tax
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE) = TRUNC(SYSDATE)
""",
    required_params=["time_today"],   # P1: only when user explicitly says "today"
    result_type="scalar",
))

_register(QueryTemplate(
    name="purchase_summary_this_month",
    description="إجمالي مشتريات الشهر الحالي / This month's purchase total",
    domain="invoicing",
    sub_intent="purchase_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_purchases,
       NVL(SUM(TAX), 0) AS total_tax,
       TRUNC(SYSDATE, 'MM') AS month_start
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE, 'MM') = TRUNC(SYSDATE, 'MM')
""",
    required_params=["time_this_month"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="purchase_summary_last_month",
    description="إجمالي مشتريات الشهر الماضي / Last month's purchase total",
    domain="invoicing",
    sub_intent="purchase_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_purchases,
       NVL(SUM(TAX), 0) AS total_tax,
       ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1) AS month_start
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND TRUNC(INVDATE, 'MM') = ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
""",
    required_params=["time_last_month"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="purchase_summary_this_year",
    description="إجمالي مشتريات هذه السنة / This year's purchase total",
    domain="invoicing",
    sub_intent="purchase_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_purchases,
       NVL(SUM(TAX), 0) AS total_tax,
       EXTRACT(YEAR FROM SYSDATE) AS purchase_year
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND EXTRACT(YEAR FROM INVDATE) = EXTRACT(YEAR FROM SYSDATE)
""",
    required_params=["time_this_year"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="purchase_summary_last_year",
    description="إجمالي مشتريات السنة الماضية / Last year's purchase total",
    domain="invoicing",
    sub_intent="purchase_summary",
    sql="""
SELECT COUNT(*) AS invoice_count,
       NVL(SUM(FINALTOTAL), 0) AS total_purchases,
       NVL(SUM(TAX), 0) AS total_tax,
       EXTRACT(YEAR FROM SYSDATE) - 1 AS purchase_year
  FROM MAIN_INV
 WHERE INVTYPE = {{flag:INVTYPE:شراء}}
   AND RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND EXTRACT(YEAR FROM INVDATE) = EXTRACT(YEAR FROM SYSDATE) - 1
""",
    required_params=["time_last_year"],
    result_type="scalar",
))

_register(QueryTemplate(
    name="top_customers_by_sales",
    description="أكثر العملاء شراءً / Top customers by sales",
    domain="invoicing",
    sub_intent="top_customers",
    sql="""
SELECT cu.CUSTID,
       cu.CUST_NAME,
       COUNT(m.INV_KEY) AS invoice_count,
       NVL(SUM(m.FINALTOTAL), 0) AS total_sales
  FROM MAIN_INV m
  JOIN CUST cu ON cu.CUSTID = m.CUST_ID AND cu.CUST_TYPE = m.CUST_TYPE
 WHERE m.INVTYPE = {{flag:INVTYPE:بيع}}
   AND m.RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND cu.CUST_TYPE = {{flag:CUST_TYPE:عميل}}
 GROUP BY cu.CUSTID, cu.CUST_NAME
 ORDER BY total_sales DESC
 FETCH FIRST {{top_n}} ROWS ONLY
""",
    required_params=[],
    optional_params=["top_n"],
    param_defaults={"top_n": "10"},
    result_type="table",
))

_register(QueryTemplate(
    name="top_items_by_sales",
    description="أكثر الأصناف مبيعاً / Top selling items",
    domain="invoicing",
    sub_intent="top_items",
    sql="""
SELECT i.ITEMID,
       i.ITEMNAME,
       NVL(SUM(d.QTY), 0) AS total_qty,
       NVL(SUM(d.QTY * d.PRICE), 0) AS total_sales
  FROM DETAIL_INV d
  JOIN ITEMS i ON i.ITEMID = d.ITEMID
  JOIN MAIN_INV m ON m.INV_KEY = d.INV_KEY
 WHERE m.INVTYPE = {{flag:INVTYPE:بيع}}
   AND m.RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
 GROUP BY i.ITEMID, i.ITEMNAME
 ORDER BY total_sales DESC
 FETCH FIRST {{top_n}} ROWS ONLY
""",
    required_params=[],
    optional_params=["top_n"],
    param_defaults={"top_n": "10"},
    result_type="table",
))

_register(QueryTemplate(
    name="customer_outstanding",
    description="مديونيات العملاء / Customer outstanding balances",
    domain="invoicing",
    sub_intent="outstanding",
    sql="""
SELECT cu.CUSTID,
       cu.CUST_NAME,
       NVL(SUM(m.FINALTOTAL - m.SDAD), 0) AS outstanding
  FROM MAIN_INV m
  JOIN CUST cu ON cu.CUSTID = m.CUST_ID AND cu.CUST_TYPE = m.CUST_TYPE
 WHERE m.INVTYPE = {{flag:INVTYPE:بيع}}
   AND m.RETURN_FLAG = {{flag:RETURN_FLAG:فاتورة عادية}}
   AND cu.CUST_TYPE = {{flag:CUST_TYPE:عميل}}
   AND (m.FINALTOTAL - m.SDAD) > 0
 GROUP BY cu.CUSTID, cu.CUST_NAME
 ORDER BY outstanding DESC
 FETCH FIRST 100 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))


# ══════════════════════════════════════════════════════════════════
# Inventory Templates
# ══════════════════════════════════════════════════════════════════

_register(QueryTemplate(
    name="stock_balance",
    description="رصيد المخزون / Stock balance by store",
    domain="inventory",
    sub_intent="stock_balance",
    sql="""
SELECT s.STORE_NAME,
       i.ITEMNAME,
       t.QTY AS current_qty,
       t.PRICE AS avg_cost
  FROM TRANSACTION_TOT t
  JOIN ITEMS i ON i.ITEMID = t.ITEMID
  JOIN STORE s ON s.STORE_CODE = t.STORE_CODE
 WHERE t.QTY <> 0
 ORDER BY s.STORE_NAME, i.ITEMNAME
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))

_register(QueryTemplate(
    name="item_info",
    description="بيانات صنف / Item info lookup",
    domain="inventory",
    sub_intent="item_info",
    sql="""
SELECT i.ITEMID,
       i.ITEMNAME,
       i.ITEM_NAME_E,
       g.GROUPNAME,
       u.UNIT_NAME,
       i.SELLPRICE,
       i.TOTAL_BUYPRICE
  FROM ITEMS i
  LEFT JOIN ITEMGROUP g ON g.GROUPID = i.GROUPID
  LEFT JOIN UNITS u ON u.UNIT_ID = i.UNIT_ID
 WHERE i.ITEMNAME LIKE '%{{item_name}}%'
    OR i.ITEMID = '{{item_code}}'
 FETCH FIRST 50 ROWS ONLY
""",
    required_params=[],
    optional_params=["item_name", "item_code"],
    result_type="table",
))


# ══════════════════════════════════════════════════════════════════
# Customer Templates
# ══════════════════════════════════════════════════════════════════

_register(QueryTemplate(
    name="customer_list",
    description="قائمة العملاء / Active customers list",
    domain="customers",
    sub_intent="customer_list",
    sql="""
SELECT CUSTID,
       CUST_NAME,
       CUST_NAME_E,
       DECODE(CUST_TYPE, 0, 'عميل', 1, 'مورد', 2, 'وكيل') AS CUST_TYPE_DESC,
       OPEN_BALANCE,
       CREDIT_LIMIT,
       TAX_NO
  FROM CUST
 WHERE CUST_TYPE = {{flag:CUST_TYPE:عميل}}
   AND ACTIVE = '{{flag:ACTIVE:نشط}}'
 ORDER BY CUST_NAME
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))

_register(QueryTemplate(
    name="customer_info",
    description="بيانات عميل / Customer info lookup",
    domain="customers",
    sub_intent="customer_info",
    sql="""
SELECT CUSTID,
       CUST_NAME,
       CUST_NAME_E,
       DECODE(CUST_TYPE, 0, 'عميل', 1, 'مورد', 2, 'وكيل') AS CUST_TYPE_DESC,
       OPEN_BALANCE,
       DECODE(DBCRD, 0, 'مدين', 1, 'دائن') AS BALANCE_DIR,
       CREDIT_LIMIT,
       TAX_NO,
       CHART_CODE
  FROM CUST
 WHERE CUSTID = {{customer_id}}
   AND CUST_TYPE = {{flag:CUST_TYPE:عميل}}
""",
    required_params=["customer_id"],
    result_type="table",
))

_register(QueryTemplate(
    name="supplier_list",
    description="قائمة الموردين / Active suppliers list",
    domain="customers",
    sub_intent="supplier_list",
    sql="""
SELECT CUSTID,
       CUST_NAME,
       CUST_NAME_E,
       OPEN_BALANCE,
       CREDIT_LIMIT,
       TAX_NO
  FROM CUST
 WHERE CUST_TYPE = {{flag:CUST_TYPE:مورد}}
   AND ACTIVE = '{{flag:ACTIVE:نشط}}'
 ORDER BY CUST_NAME
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))


# ══════════════════════════════════════════════════════════════════
# HR Templates
# ══════════════════════════════════════════════════════════════════

_register(QueryTemplate(
    name="employee_count",
    description="عدد الموظفين / Employee count",
    domain="hr",
    sub_intent="employee_count",
    sql="""
SELECT COUNT(*) AS employee_count
  FROM EMPLOYEES
 WHERE EMP_ACTIVE = '{{flag:EMP_ACTIVE:نشط}}'
   AND END_SERVICE_FLG = 'N'
""",
    required_params=[],
    result_type="scalar",
))

_register(QueryTemplate(
    name="employee_list",
    description="قائمة الموظفين / Active employees list",
    domain="hr",
    sub_intent="employee_list",
    sql="""
SELECT EMP_ID,
       EMP_NAME_AR,
       EMP_NAME_EN,
       HIRE_DATE,
       END_SERVICE_FLG
  FROM EMPLOYEES
 WHERE EMP_ACTIVE = '{{flag:EMP_ACTIVE:نشط}}'
   AND END_SERVICE_FLG = 'N'
 ORDER BY EMP_NAME_AR
 FETCH FIRST 200 ROWS ONLY
""",
    required_params=[],
    result_type="table",
))


# ══════════════════════════════════════════════════════════════════
# Template matching & SQL generation
# ══════════════════════════════════════════════════════════════════

def find_template(sub_intent: str, entities: dict) -> Optional[QueryTemplate]:
    """Find the best matching template for a sub-intent."""
    candidates = [t for t in TEMPLATES.values() if t.sub_intent == sub_intent]
    if not candidates:
        return None

    best = None
    best_score = -1
    for t in candidates:
        # Check required params availability
        missing = [p for p in t.required_params if p not in entities and p not in t.param_defaults]
        if missing:
            continue
        score = 0
        for p in t.required_params:
            if p in entities:
                score += 2
        for p in t.optional_params:
            if p in entities:
                score += 1
        if score > best_score or best is None:
            best = t
            best_score = score

    return best


class FlagResolutionError(Exception):
    """Raised when a {{flag:COL:label}} placeholder has no comment-defined value.
    The caller (template execution) treats this as INELIGIBLE → LLM fallback."""


_FLAG_PH = re.compile(r'\{\{flag:([A-Z_][A-Z0-9_]*):([^}]+)\}\}')


def _resolve_flag_placeholders(sql: str) -> str:
    """COMMENT-FIRST: replace every {{flag:COLUMN:label}} with the value the
    COMMENTS assign to that label. Comments are the only source of the value.
    """
    from schema_loader import resolve_flag

    def _repl(m):
        col, label = m.group(1), m.group(2).strip()
        val = resolve_flag(col, label)
        if val is None:
            raise FlagResolutionError(f"{col}:{label}")
        return str(val)

    return _FLAG_PH.sub(_repl, sql)


def render_template(template: QueryTemplate, entities: dict) -> str:
    """Render a template with extracted entities, producing safe SQL."""
    sql = template.sql.strip()

    # Comment-first: resolve coded literals from comments at render time (Phase A).
    sql = _resolve_flag_placeholders(sql)

    params = dict(template.param_defaults)
    params.update(entities)

    for param_name in template.required_params + template.optional_params:
        placeholder = "{{" + param_name + "}}"
        if placeholder in sql:
            value = params.get(param_name, "")
            safe_value = _sanitize_param(value)
            sql = sql.replace(placeholder, safe_value)

    # Clean up empty optional WHERE clauses
    # e.g. WHERE CHART_CODE LIKE '%' → remove condition (match all)
    sql = re.sub(r"\bWHERE\s+\w+\s+LIKE\s+'%'\s*\n?", "", sql, flags=re.IGNORECASE)
    # Clean leading AND after WHERE removal
    sql = re.sub(r"\bWHERE\s+AND\b", "WHERE", sql, flags=re.IGNORECASE)

    return sql.strip()


def _sanitize_param(value: str) -> str:
    """Sanitize a parameter value to prevent SQL injection."""
    if not value:
        return ""
    value = value.strip()
    value = re.sub(r"[;'\"\\\-\-\/\*]", "", value)
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "EXEC", "UNION", "--", "/*"]
    for d in dangerous:
        value = re.sub(re.escape(d), "", value, flags=re.IGNORECASE)
    return value.strip()


def list_templates(domain: str = None) -> list[dict]:
    """List available templates, optionally filtered by domain."""
    result = []
    for name, t in TEMPLATES.items():
        if domain and t.domain != domain:
            continue
        result.append({
            "name": name,
            "description": t.description,
            "domain": t.domain,
            "required_params": t.required_params,
        })
    return result
