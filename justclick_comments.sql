-- ============================================================
--  FILE   : justclick_comments.sql
--  SCHEMA : JUSTCLICK
--  PURPOSE: COMMENT ON TABLE / COLUMN لكل الجداول المهمة
--           هذه الـ Comments هي المصدر الوحيد اللي الـ LLM
--           بيقرأه لفهم الـ schema وتوليد SQL صحيح.
--
--  HOW TO RUN:
--    sqlplus justclick/password@db @justclick_comments.sql
--    أو من APEX SQL Workshop: تشغيل كاملاً
--
--  LAST UPDATED: 2025
-- ============================================================


-- ============================================================
--  قواعد كتابة الـ COMMENT  (للمراجع فقط - لا تحذف)
-- ============================================================
--
--  [1] TABLE COMMENT — لازم يحتوي على:
--        • الغرض التجاري (سطر واحد عربي + إنجليزي)
--        • ما يحتوي عليه الجدول لو فيه تعدد (بيع + شراء مثلاً)
--        • مسارات الـ JOIN الرئيسية بالضبط
--        • شرح الـ flags المهمة بكل قيمها
--        • تحذير ⚠ لو في سلوك غير متوقع
--
--  [2] COLUMN COMMENT — حسب نوع العمود:
--        • FK   → "FK → TABLE.COLUMN  شرط الـ JOIN"
--        • FLAG → كل قيمة ومعناها  (0=كذا, 1=كذا)
--        • AMOUNT → قبل ضريبة؟ بعدها؟ يشمل خصم؟
--        • KEY   → هل يُستخدم في JOIN ولا عرض فقط؟
--        • DATE  → هذا التاريخ يمثل إيه بالضبط؟
--
--  [3] أعمدة SaaS (في كل جدول) — تُكتب مرة وتُنسخ:
--        COMPANY_CODE, FISCAL_YEAR, BRANCH_ID
--
--  [4] لغة الكتابة: عربي + إنجليزي في نفس الـ comment
--
--  [5] أسلوب التحذير:  ⚠  للحالات الخاصة التي يُخطئ فيها الـ LLM
-- ============================================================


-- ============================================================
--
--  ██████╗ ██████╗ ██╗ ██████╗ ██████╗ ██╗████████╗██╗   ██╗
--  ██╔══██╗██╔══██╗██║██╔═══██╗██╔══██╗██║╚══██╔══╝╚██╗ ██╔╝
--  ██████╔╝██████╔╝██║██║   ██║██████╔╝██║   ██║    ╚████╔╝
--  ██╔═══╝ ██╔══██╗██║██║   ██║██╔══██╗██║   ██║     ╚██╔╝
--  ██║     ██║  ██║██║╚██████╔╝██║  ██║██║   ██║      ██║
--  ╚═╝     ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝   ╚═╝      ╚═╝
--
--  DOMAIN 1 — المبيعات والمشتريات  (أعلى أولوية)
--  Tables: MAIN_INV, DETAIL_INV, CUST, SAL_PURCH_TRANS_TYPE,
--          PAYED, MAIN_INV_PAYED, INV_CATEGORIES,
--          INV_EFFECTS, INV_EFFECTS_RULES
-- ============================================================


-- ------------------------------------------------------------
--  MAIN_INV — رأس الفاتورة
-- ------------------------------------------------------------
COMMENT ON TABLE MAIN_INV IS
'رأس فاتورة البيع والشراء. كل صف = فاتورة واحدة.
INVTYPE: 0=بيع/Sale, 1=شراء/Purchase.
RETURN_FLAG: 0=فاتورة عادية, 1=مرتجع/Return.
⚠ JOIN مع DETAIL_INV يكون على INV_KEY وليس INVID.
⚠ JOIN مع CUST يكون على (CUST_ID,CUST_TYPE) معاً وليس CUST_ID وحده.
لجلب مبيعات نقية: WHERE INVTYPE=0 AND RETURN_FLAG=0.
لجلب مرتجعات البيع: WHERE INVTYPE=0 AND RETURN_FLAG=1.
Header table for all sales and purchase invoices.';

COMMENT ON COLUMN MAIN_INV.INV_KEY IS
'المفتاح الداخلي الفريد للفاتورة — Internal unique surrogate key.
⚠ هذا هو المفتاح المستخدم في كل الـ JOINs مع DETAIL_INV وجميع الجداول الأخرى.
⚠ لا تستخدم INVID في الـ JOIN — استخدم INV_KEY دائماً.
Use this for ALL joins, never use INVID for joins.';

COMMENT ON COLUMN MAIN_INV.INVID IS
'رقم الفاتورة المرئي للمستخدم — User-visible invoice number.
⚠ غير فريد عبر أنواع الفواتير المختلفة (قد يتكرر نفس الرقم في بيع وشراء).
⚠ للعرض فقط — لا تستخدمه في JOIN.
Display only. NOT unique across transaction types.';

COMMENT ON COLUMN MAIN_INV.INVDATE IS
'تاريخ الفاتورة — Invoice date.
استخدمه في فلاتر التاريخ مثلاً: WHERE TRUNC(INVDATE) BETWEEN تاريخ_البداية AND تاريخ_النهاية.';

COMMENT ON COLUMN MAIN_INV.INVTOTAL IS
'إجمالي الفاتورة قبل الضريبة وقبل الخصم الإجمالي.
Invoice subtotal before tax and before header-level discount.';

COMMENT ON COLUMN MAIN_INV.FINALTOTAL IS
'الإجمالي النهائي للفاتورة = INVTOTAL + TAX - خصومات.
هو الرقم الذي يُعرض للمستخدم كإجمالي مستحق.
Final amount due: includes tax, after all discounts. This is what the customer pays.';

COMMENT ON COLUMN MAIN_INV.TAX IS
'قيمة الضريبة المضافة (مبلغ وليس نسبة).
⚠ هذا مبلغ فعلي بالعملة وليس نسبة مئوية.
Tax amount in currency (not a percentage).';

COMMENT ON COLUMN MAIN_INV.SDAD IS
'المبلغ المسدَّد نقداً فور إنشاء الفاتورة.
المتبقي غير المسدد = FINALTOTAL - SDAD.
Cash paid at invoice creation. Outstanding = FINALTOTAL - SDAD.';

COMMENT ON COLUMN MAIN_INV.CUST_ID IS
'كود العميل أو المورد.
FK → CUST.CUSTID
⚠ الـ JOIN لازم يكون على عمودين معاً:
  MAIN_INV.CUST_ID   = CUST.CUSTID
  MAIN_INV.CUST_TYPE = CUST.CUST_TYPE
بدون CUST_TYPE في الشرط ستظهر بيانات خاطئة.';

COMMENT ON COLUMN MAIN_INV.CUST_TYPE IS
'نوع الطرف الآخر في الفاتورة:
0 = عميل / Customer
1 = مورد / Supplier
2 = وكيل / Dealer
⚠ جزء أساسي من مفتاح الـ JOIN مع جدول CUST — لا تحذفه من شرط JOIN.';

COMMENT ON COLUMN MAIN_INV.INVTYPE IS
'نوع الفاتورة:
0 = بيع / Sale
1 = شراء / Purchase';

COMMENT ON COLUMN MAIN_INV.RETURN_FLAG IS
'حالة الفاتورة:
0 = فاتورة عادية / Normal invoice
1 = مرتجع / Return invoice
⚠ المرتجعات لها نفس INVTYPE (0 لمرتجع بيع، 1 لمرتجع شراء).
⚠ عند حساب صافي المبيعات: اطرح RETURN_FLAG=1 من RETURN_FLAG=0.';

COMMENT ON COLUMN MAIN_INV.STORE_CODE IS
'كود المخزن الذي تمت منه العملية.
FK → STORE.STORE_CODE';

COMMENT ON COLUMN MAIN_INV.INV_TRANS_TYPE IS
'نوع حركة الفاتورة التفصيلي (نقدي، آجل، إلخ).
FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE';

COMMENT ON COLUMN MAIN_INV.INV_CAT IS
'تصنيف الفاتورة.
FK → INV_CATEGORIES.INV_CAT';

COMMENT ON COLUMN MAIN_INV.EFFECT_VALUE IS
'قيمة الإضافة على مستوى رأس الفاتورة (ضريبة إجمالية أو رسوم).
Added value at invoice header level (overall tax or fees).';

COMMENT ON COLUMN MAIN_INV.EFFECT_VALUE_CUST IS
'قيمة الخصم الخاص بالعميل على مستوى رأس الفاتورة.
Customer-specific discount at invoice header level.';

COMMENT ON COLUMN MAIN_INV.CREATE_DATE_TM IS
'تاريخ ووقت إنشاء الفاتورة في النظام (يختلف عن INVDATE).
System creation timestamp (differs from INVDATE which is the business date).';

COMMENT ON COLUMN MAIN_INV.HEAD_NOTES IS
'ملاحظات الفاتورة — Notes/remarks on the invoice.';

COMMENT ON COLUMN MAIN_INV.DEALER_ID IS
'كود الوكيل المرتبط بالفاتورة (إن وجد).
FK → DEALER_DATA.DEALER_ID  (DEALER_TYPE=2)';

COMMENT ON COLUMN MAIN_INV.COMPANY_CODE IS
'كود الشركة — Tenant identifier (SaaS isolation).

COMMENT ON COLUMN MAIN_INV.FISCAL_YEAR IS
'السنة المالية — Fiscal year.

COMMENT ON COLUMN MAIN_INV.BRANCH_ID IS
'كود الفرع — Branch identifier.


-- ------------------------------------------------------------
--  DETAIL_INV — تفاصيل بنود الفاتورة
-- ------------------------------------------------------------
COMMENT ON TABLE DETAIL_INV IS
'تفاصيل بنود الفاتورة. كل صف = صنف واحد في فاتورة واحدة.
FK إلى MAIN_INV عبر INV_KEY.
FK إلى ITEMS عبر ITEMID.
⚠ إجمالي البند = (QTY * PRICE) + ADD_VAL - SUB_VAL.
Invoice line items — one row per item per invoice.
Line total formula: (QTY * PRICE) + ADD_VAL - SUB_VAL.';

COMMENT ON COLUMN DETAIL_INV.INV_KEY IS
'المفتاح الرابط مع رأس الفاتورة.
FK → MAIN_INV.INV_KEY
⚠ استخدم INV_KEY وليس INVID في الـ JOIN.';

COMMENT ON COLUMN DETAIL_INV.ITEMID IS
'كود الصنف.
FK → ITEMS.ITEMID';

COMMENT ON COLUMN DETAIL_INV.QTY IS
'الكمية المباعة أو المشتراة بوحدة القياس الأساسية.
Quantity in primary unit of measure.';

COMMENT ON COLUMN DETAIL_INV.PRICE IS
'سعر الوحدة الواحدة بدون ضريبة.
⚠ إجمالي البند = (QTY * PRICE) + ADD_VAL - SUB_VAL  — وليس QTY*PRICE فقط.
Unit price excluding tax. Line total = (QTY*PRICE)+ADD_VAL-SUB_VAL.';

COMMENT ON COLUMN DETAIL_INV.ADD_VAL IS
'قيمة الإضافة على البند (ضريبة، رسوم، إلخ). تُضاف للإجمالي.
Additional charge on line (tax, fees). Added to line total.';

COMMENT ON COLUMN DETAIL_INV.SUB_VAL IS
'قيمة الخصم على هذا البند تحديداً. تُطرح من الإجمالي.
Discount on this specific line. Subtracted from line total.';

COMMENT ON COLUMN DETAIL_INV.UNIT_ID IS
'وحدة القياس المستخدمة في هذا البند.
FK → UNITS.UNIT_ID';

COMMENT ON COLUMN DETAIL_INV.QTY_UNITS IS
'الكمية بالوحدة الفرعية (إن وُجدت).
Quantity in sub-unit (if applicable).';

COMMENT ON COLUMN DETAIL_INV.GROUPID IS
'مجموعة الصنف — لأغراض التصنيف والتقارير.
FK → ITEMGROUP.GROUPID';

COMMENT ON COLUMN DETAIL_INV.PRICEPERONE IS
'سعر الوحدة الفرعية — Price per sub-unit.';

COMMENT ON COLUMN DETAIL_INV.EXP_DATE IS
'تاريخ انتهاء صلاحية هذا البند (للأصناف ذات الصلاحية).
Expiry date of this item batch (for expiry-tracked items).';

COMMENT ON COLUMN DETAIL_INV.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN DETAIL_INV.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';

COMMENT ON COLUMN DETAIL_INV.BRANCH_ID IS
'كود الفرع — Branch filter if needed.';


-- ------------------------------------------------------------
--  CUST — العملاء والموردين والوكلاء
-- ------------------------------------------------------------
COMMENT ON TABLE CUST IS
'جدول موحد للعملاء والموردين والوكلاء.
CUST_TYPE: 0=عميل/Customer, 1=مورد/Supplier, 2=وكيل/Dealer.
⚠ المفتاح المركب: (CUSTID, CUST_TYPE) — CUSTID وحده ليس فريداً.
⚠ أي JOIN مع هذا الجدول يلزمه شرطان:
    table.CUST_ID   = CUST.CUSTID
    table.CUST_TYPE = CUST.CUST_TYPE
بدون CUST_TYPE ستظهر بيانات عملاء ومورديين مختلطة.
Unified table for customers(0), suppliers(1) and dealers(2).
ALWAYS join on BOTH CUSTID and CUST_TYPE.';

COMMENT ON COLUMN CUST.CUSTID IS
'كود العميل/المورد — Customer or Supplier code.
⚠ ليس فريداً وحده — الفريد هو (CUSTID, CUST_TYPE) معاً.';

COMMENT ON COLUMN CUST.CUST_TYPE IS
'نوع الطرف:
0 = عميل / Customer
1 = مورد / Supplier
2 = وكيل / Dealer
⚠ جزء من المفتاح الأساسي — لا تتجاهله في أي JOIN.';

COMMENT ON COLUMN CUST.CUST_NAME IS
'الاسم بالعربي — Arabic name (العملاء والموردين).';

COMMENT ON COLUMN CUST.CUST_NAME_E IS
'الاسم بالإنجليزي — English name.';

COMMENT ON COLUMN CUST.OPEN_BALANCE IS
'الرصيد الافتتاحي — Opening balance amount.
اتجاهه محدد بعمود DBCRD.';

COMMENT ON COLUMN CUST.DBCRD IS
'اتجاه الرصيد الافتتاحي:
0 = مدين / Debit (العميل مدين للشركة — customer owes us)
1 = دائن / Credit (الشركة مدينة للعميل — we owe customer)';

COMMENT ON COLUMN CUST.CREDIT_LIMIT IS
'حد الائتمان الأقصى المسموح للعميل — Maximum credit limit.
0 أو NULL = بلا حد.';

COMMENT ON COLUMN CUST.ACTIVE IS
'حالة النشاط:
0 = غير نشط / Inactive
1 = نشط / Active
⚠ عند جلب قائمة العملاء الفعليين: AND ACTIVE = 1';

COMMENT ON COLUMN CUST.CHART_CODE IS
'حساب العميل/المورد في شجرة الحسابات.
FK → CHARTS.CHART_CODE';

COMMENT ON COLUMN CUST.PRICE_LIST_ID IS
'قائمة الأسعار المخصصة لهذا العميل (إن وجدت).
FK → PRICE_LIST.PRICE_LIST_ID';

COMMENT ON COLUMN CUST.TAX_NO IS
'الرقم الضريبي للعميل/المورد — Tax registration number.';

COMMENT ON COLUMN CUST.MOB IS
'رقم الموبايل — Mobile number.';

COMMENT ON COLUMN CUST.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN CUST.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';

COMMENT ON COLUMN CUST.BRANCH_ID IS
'كود الفرع — Branch filter if needed.';


-- ------------------------------------------------------------
--  SAL_PURCH_TRANS_TYPE — أنواع حركات البيع والشراء
-- ------------------------------------------------------------
COMMENT ON TABLE SAL_PURCH_TRANS_TYPE IS
'تعريف أنواع الفواتير والحركات (نقدي، آجل، مرتجع، إلخ).
SAL_PURCH: 0=بيع/Sales, 1=شراء/Purchase, 2=وكيل/Dealer.
⚠ الربط مع MAIN_INV: SAL_PURCH_TRANS_TYPE.TRANS_CODE = MAIN_INV.INV_TRANS_TYPE
⚠ SAL_PURCH يساوي CUST_TYPE في جدول CUST — نفس القيم.
Defines invoice movement types: cash sale, credit purchase, return, etc.';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.TRANS_CODE IS
'كود نوع الحركة — Movement type code.
FK من MAIN_INV.INV_TRANS_TYPE';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.TRANS_NAME_AR IS
'اسم نوع الحركة بالعربي — Arabic type name (مثال: بيع نقدي، بيع آجل).';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.TRANS_NAME_EN IS
'اسم نوع الحركة بالإنجليزي — English type name.';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.SAL_PURCH IS
'جانب الحركة:
0 = بيع / Sales
1 = شراء / Purchase
2 = وكيل / Dealer
⚠ نفس قيم CUST.CUST_TYPE — يُستخدم للربط معها.';


-- ------------------------------------------------------------
--  PAYED — المدفوعات والتحصيلات
-- ------------------------------------------------------------
COMMENT ON TABLE PAYED IS
'سجل كل المدفوعات والتحصيلات للعملاء والموردين.
كل صف = عملية دفع أو تحصيل واحدة.
DEB_CRD: 0=دائن(تحصيل من عميل), 1=مدين(دفع لمورد).
⚠ JOIN مع CUST على (CUST_ID, SAL_PURCH) بدلاً من (CUSTID, CUST_TYPE).
Payment and collection records for customers and suppliers.';

COMMENT ON COLUMN PAYED.PAYED_ID IS
'كود المدفوعة الفريد — Unique payment record ID.';

COMMENT ON COLUMN PAYED.PAYED_DATE IS
'تاريخ الدفع أو التحصيل — Payment/collection date.';

COMMENT ON COLUMN PAYED.PAYED_AMOUNT IS
'قيمة المدفوعة — Payment amount.';

COMMENT ON COLUMN PAYED.DEB_CRD IS
'اتجاه المدفوعة:
0 = دائن = تحصيل من عميل / Collection received from customer
1 = مدين = دفع لمورد أو استرداد / Payment made to supplier';

COMMENT ON COLUMN PAYED.SAL_PURCH IS
'نوع الطرف:
0 = عميل / Customer
1 = مورد / Supplier
⚠ يساوي CUST_TYPE في جدول CUST — استخدمه في الـ JOIN.';

COMMENT ON COLUMN PAYED.CUST_ID IS
'كود العميل أو المورد.
FK → CUST.CUSTID
⚠ الـ JOIN: PAYED.CUST_ID = CUST.CUSTID AND PAYED.SAL_PURCH = CUST.CUST_TYPE';

COMMENT ON COLUMN PAYED.NOTES IS
'ملاحظات المدفوعة — Payment notes/remarks.';

COMMENT ON COLUMN PAYED.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN PAYED.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';

COMMENT ON COLUMN PAYED.BRANCH_ID IS
'Branch filter.';


-- ------------------------------------------------------------
--  MAIN_INV_PAYED — ربط الفواتير بالمدفوعات
-- ------------------------------------------------------------
COMMENT ON TABLE MAIN_INV_PAYED IS
'جدول الربط بين الفواتير والمدفوعات (تسوية الذمم).
كل صف = مبلغ من مدفوعة معينة يُسدَّد فاتورة معينة.
Link between invoices (MAIN_INV) and payments (PAYED).
Used to track which payment settles which invoice.';

COMMENT ON COLUMN MAIN_INV_PAYED.INV_KEY IS
'FK → MAIN_INV.INV_KEY — الفاتورة المُسوَّاة';

COMMENT ON COLUMN MAIN_INV_PAYED.PAYED_ID IS
'FK → PAYED.PAYED_ID — المدفوعة المرتبطة';

COMMENT ON COLUMN MAIN_INV_PAYED.SDAD IS
'المبلغ المُسدَّد من هذه المدفوعة لهذه الفاتورة تحديداً.
Amount from this payment applied to this specific invoice.';

COMMENT ON COLUMN MAIN_INV_PAYED.SDAD_TRANS_TYPE IS
'نوع حركة التسديد — Payment movement type code.
FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE';

COMMENT ON COLUMN MAIN_INV_PAYED.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN MAIN_INV_PAYED.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';


-- ------------------------------------------------------------
--  INV_CATEGORIES — تصنيفات الفواتير
-- ------------------------------------------------------------
COMMENT ON TABLE INV_CATEGORIES IS
'تصنيفات الفواتير (نقطة بيع، جملة، مشروع، إلخ).
FK من MAIN_INV.INV_CAT.
Invoice categories (POS, wholesale, project, etc.).';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT IS
'كود التصنيف — FK من MAIN_INV.INV_CAT';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT_TYPE IS
'نوع التصنيف — Category type.';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT_NAME_AR IS
'اسم التصنيف بالعربي — Arabic category name.';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT_NAME_EN IS
'اسم التصنيف بالإنجليزي — English category name.';


-- ============================================================
--
--  DOMAIN 2 — المخزون والأصناف  (أولوية عالية)
--  Tables: ITEMS, ITEMGROUP, UNITS, STORE, TRANSACTION,
--          TRANSACTION_TOT, ITEM_CARD, FIFO,
--          PRICE_LIST, PRICE_LIST_DET
-- ============================================================


-- ------------------------------------------------------------
--  ITEMS — الأصناف والمنتجات
-- ------------------------------------------------------------
COMMENT ON TABLE ITEMS IS
'الأصناف والمنتجات — بيانات الصنف الأساسية.
⚠ هذا جدول بيانات الصنف فقط — للكميات والحركات انظر TRANSACTION.
⚠ السعر هنا هو سعر البيع الافتراضي — للأسعار الخاصة انظر PRICE_LIST_DET.
Master table for all items and products. Prices and inventory movements are in other tables.';

COMMENT ON COLUMN ITEMS.ITEMID IS
'كود الصنف الفريد — Unique item/product code.';

COMMENT ON COLUMN ITEMS.ITEMNAME IS
'اسم الصنف بالعربي — Arabic item name.';

COMMENT ON COLUMN ITEMS.ITEM_NAME_E IS
'اسم الصنف بالإنجليزي — English item name.';

COMMENT ON COLUMN ITEMS.SELLPRICE IS
'سعر البيع الافتراضي (بدون ضريبة).
⚠ قد يُستبدل بسعر من PRICE_LIST_DET إذا كان للعميل قائمة أسعار خاصة.
Default selling price excluding tax.';

COMMENT ON COLUMN ITEMS.SELLPRICE_WITH_TAX IS
'سعر البيع شامل الضريبة — Selling price including tax.';

COMMENT ON COLUMN ITEMS.TOTAL_BUYPRICE IS
'تكلفة الشراء أو التكلفة المتوسطة.
Average or last purchase cost price.';

COMMENT ON COLUMN ITEMS.GROUPID IS
'مجموعة الصنف — يُستخدم في التصنيف والتقارير.
FK → ITEMGROUP.GROUPID';

COMMENT ON COLUMN ITEMS.UNIT_ID IS
'وحدة القياس الأساسية للصنف.
FK → UNITS.UNIT_ID';

COMMENT ON COLUMN ITEMS.SUB_UNIT_ID IS
'وحدة القياس الفرعية (إن وجدت).
FK → UNITS.UNIT_ID (sub-unit)';

COMMENT ON COLUMN ITEMS.SUB_UNIT_FACTOR IS
'معامل التحويل: كم وحدة فرعية تساوي وحدة أساسية.
Conversion factor: how many sub-units equal one primary unit.';

COMMENT ON COLUMN ITEMS.BAR_CODE IS
'الباركود — Item barcode for scanning.';

COMMENT ON COLUMN ITEMS.LIMIT IS
'الحد الأدنى للمخزون (نقطة إعادة الطلب).
Minimum stock level / reorder point.';

COMMENT ON COLUMN ITEMS.MAX_LIMIT IS
'الحد الأقصى للمخزون.
Maximum stock level.';

COMMENT ON COLUMN ITEMS.ITEM_TYPE IS
'نوع الصنف:
1 = صنف عادي / Regular item
2 = خدمة / Service (لا يؤثر على المخزون)
3 = مُنتَج / Production item
⚠ الخدمات (ITEM_TYPE=2) لا تُحتسب في كميات المخزون.';

-- ITEMS.ACTIVE removed — column does not exist in DB

COMMENT ON COLUMN ITEMS.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN ITEMS.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';

COMMENT ON COLUMN ITEMS.BRANCH_ID IS
'Branch filter.';


-- ------------------------------------------------------------
--  ITEMGROUP — مجموعات الأصناف
-- ------------------------------------------------------------
COMMENT ON TABLE ITEMGROUP IS
'مجموعات وتصنيفات الأصناف — شجرة هرمية.
PARENT_GROUPID يشير لمجموعة أب (للمجموعات الجذر = NULL).
Item categories/groups — hierarchical tree structure.';

COMMENT ON COLUMN ITEMGROUP.GROUPID IS
'كود المجموعة — Group code. FK من ITEMS.GROUPID';

COMMENT ON COLUMN ITEMGROUP.GROUPNAME IS
'اسم المجموعة بالعربي — Arabic group name.';

COMMENT ON COLUMN ITEMGROUP.GROUPNAME_EN IS
'اسم المجموعة بالإنجليزي — English group name.';

COMMENT ON COLUMN ITEMGROUP.PARENT_GROUPID IS
'كود المجموعة الأب (NULL للمستوى الأعلى).
Parent group code. NULL = top-level group.
للشجرة الكاملة: استخدم CONNECT BY PRIOR GROUPID = PARENT_GROUPID';


-- ------------------------------------------------------------
--  UNITS — وحدات القياس
-- ------------------------------------------------------------
COMMENT ON TABLE UNITS IS
'وحدات قياس الأصناف (قطعة، كيلو، لتر، إلخ).
Units of measure for items.';

COMMENT ON COLUMN UNITS.UNIT_ID IS
'كود الوحدة — Unit code. FK من ITEMS.UNIT_ID و DETAIL_INV.UNIT_ID';

COMMENT ON COLUMN UNITS.UNIT_NAME IS
'اسم الوحدة بالعربي — Arabic unit name.';

COMMENT ON COLUMN UNITS.UNIT_NAME_E IS
'اسم الوحدة بالإنجليزي — English unit name.';


-- ------------------------------------------------------------
--  STORE — المخازن / نقاط البيع
-- ------------------------------------------------------------
COMMENT ON TABLE STORE IS
'المخازن ونقاط البيع.
كل فاتورة وكل حركة مخزون مرتبطة بمخزن معين.
Warehouses and point-of-sale locations.
Every invoice and stock movement belongs to a specific store.';

COMMENT ON COLUMN STORE.STORE_CODE IS
'كود المخزن — Store/warehouse code. FK من MAIN_INV.STORE_CODE و TRANSACTION.STORE_CODE';

COMMENT ON COLUMN STORE.STORE_NAME IS
'اسم المخزن بالعربي — Arabic store name.';

COMMENT ON COLUMN STORE.STORE_NAME_EN IS
'اسم المخزن بالإنجليزي — English store name.';

COMMENT ON COLUMN STORE.MAIN_STORE IS
'1 = مخزن رئيسي / Main store.
0 = فرع أو نقطة بيع / Branch or sub-store.';

COMMENT ON COLUMN STORE.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';


-- ------------------------------------------------------------
--  TRANSACTION — حركات المخزون التفصيلية
-- ------------------------------------------------------------
COMMENT ON TABLE TRANSACTION IS
'حركات المخزون التفصيلية — كل إضافة وصرف لكل صنف في كل مخزن.
⚠ هذا الجدول للمخزون فقط — لبيانات المبيعات استخدم MAIN_INV + DETAIL_INV.
⚠ الكمية دائماً موجبة — الاتجاه (وارد/صادر) يحدده TRANS_TYPE_CODE عبر STORE_TRANS_TYPE.
لمعرفة الرصيد الحالي: استخدم TRANSACTION_TOT.
Detailed stock movement log — every item in/out of every store.
For sales/purchase data use MAIN_INV+DETAIL_INV instead.';

COMMENT ON COLUMN TRANSACTION.TRANS_TYPE_CODE IS
'نوع الحركة — يحدد إذا كانت وارد أو صادر.
FK → STORE_TRANS_TYPE.TRANS_CODE
⚠ للتحقق من اتجاه الحركة: JOIN STORE_TRANS_TYPE ON TRANS_TYPE_CODE = TRANS_CODE';

COMMENT ON COLUMN TRANSACTION.TRANS_CODE IS
'الرقم التسلسلي للحركة ضمن نفس النوع — Sequential movement number within type.';

COMMENT ON COLUMN TRANSACTION.ITEMID IS
'كود الصنف — FK → ITEMS.ITEMID';

COMMENT ON COLUMN TRANSACTION.QTY IS
'الكمية — دائماً موجبة.
⚠ الاتجاه (وارد أو صادر) محدد بـ TRANS_TYPE_CODE عبر جدول STORE_TRANS_TYPE
وليس بإشارة الكمية.
Always positive. Direction (in/out) determined by TRANS_TYPE_CODE.';

COMMENT ON COLUMN TRANSACTION.PRICE IS
'سعر الوحدة في وقت الحركة — Unit price at time of movement.';

COMMENT ON COLUMN TRANSACTION.STORE_CODE IS
'المخزن الذي حدثت فيه الحركة — FK → STORE.STORE_CODE';

COMMENT ON COLUMN TRANSACTION.INVID IS
'رقم الفاتورة المرتبطة (للعرض فقط).
⚠ للـ JOIN مع MAIN_INV استخدم TRANSACTION.TRANS_CODE + نوع الحركة وليس INVID.';

COMMENT ON COLUMN TRANSACTION.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN TRANSACTION.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';


-- ------------------------------------------------------------
--  TRANSACTION_TOT — أرصدة المخزون الإجمالية
-- ------------------------------------------------------------
COMMENT ON TABLE TRANSACTION_TOT IS
'أرصدة المخزون الإجمالية لكل صنف في كل مخزن (نتيجة مجمّعة).
⚠ هذا هو المصدر الصحيح لرصيد المخزون الحالي — وليس TRANSACTION مباشرة.
Current stock balance per item per store — aggregated result.
Use this for current stock queries, not the raw TRANSACTION table.';

COMMENT ON COLUMN TRANSACTION_TOT.ITEMID IS
'كود الصنف — FK → ITEMS.ITEMID';

COMMENT ON COLUMN TRANSACTION_TOT.STORE_CODE IS
'كود المخزن — FK → STORE.STORE_CODE';

COMMENT ON COLUMN TRANSACTION_TOT.QTY IS
'الرصيد الحالي للصنف في هذا المخزن.
⚠ قد يكون سالباً إذا كان المخزون منخفضاً.
Current stock quantity. May be negative if oversold.';

COMMENT ON COLUMN TRANSACTION_TOT.PRICE IS
'متوسط سعر التكلفة — Average cost price.';

COMMENT ON COLUMN TRANSACTION_TOT.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN TRANSACTION_TOT.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';


-- ------------------------------------------------------------
--  ITEM_CARD — كارت الصنف (حركة الصنف التاريخية)
-- ------------------------------------------------------------
COMMENT ON TABLE ITEM_CARD IS
'كارت الصنف — حركة تاريخية مجمّعة لكل صنف في كل مخزن.
يُستخدم للتقارير التاريخية (رصيد الصنف عبر الزمن).
Item ledger card — historical movement summary per item per store.';

COMMENT ON COLUMN ITEM_CARD.ITEMID IS 'FK → ITEMS.ITEMID';
COMMENT ON COLUMN ITEM_CARD.STORE_CODE IS 'FK → STORE.STORE_CODE';
COMMENT ON COLUMN ITEM_CARD.TRANS_DATE IS 'تاريخ الحركة — Movement date.';
COMMENT ON COLUMN ITEM_CARD.ADD_QTY IS 'الكمية الواردة في هذا السطر — Incoming quantity.';
COMMENT ON COLUMN ITEM_CARD.SUB_QTY IS 'الكمية الصادرة في هذا السطر — Outgoing quantity.';
COMMENT ON COLUMN ITEM_CARD.QTY IS 'الرصيد بعد هذه الحركة — Running balance after this movement.';


-- ------------------------------------------------------------
--  PRICE_LIST — قوائم الأسعار الخاصة
-- ------------------------------------------------------------
COMMENT ON TABLE PRICE_LIST IS
'قوائم الأسعار الخاصة (خصومات، عروض، أسعار عملاء مميزين).
كل قائمة لها فترة صلاحية (OPEN_FROM_DATE → OPEN_TO_DATE).
⚠ تفاصيل أسعار الأصناف في PRICE_LIST_DET.
Special price lists (discounts, offers, VIP customer prices).
Details are in PRICE_LIST_DET.';

COMMENT ON COLUMN PRICE_LIST.PRICE_LIST_ID IS
'كود قائمة الأسعار — FK من CUST.PRICE_LIST_ID و PRICE_LIST_DET';

COMMENT ON COLUMN PRICE_LIST.PRICE_LIST_AR IS
'اسم قائمة الأسعار بالعربي.';

COMMENT ON COLUMN PRICE_LIST.OPEN_FROM_DATE IS
'تاريخ بداية سريان قائمة الأسعار.';

COMMENT ON COLUMN PRICE_LIST.OPEN_TO_DATE IS
'تاريخ انتهاء سريان قائمة الأسعار.
⚠ للقوائم النشطة: TRUNC(SYSDATE) BETWEEN OPEN_FROM_DATE AND OPEN_TO_DATE';


-- ============================================================
--
--  DOMAIN 3 — المحاسبة
--  Tables: CHARTS, COST_CENTERS, VOUCHERS_HEAD,
--          VOUCHERS_DET, CHARTS_COST
-- ============================================================


-- ------------------------------------------------------------
--  CHARTS — شجرة الحسابات
-- ------------------------------------------------------------
COMMENT ON TABLE CHARTS IS
'⚠ حركات/تفاصيل/كشف الحساب موجودة في VOUCHERS_DET عبر CHART_CODE — هذا الجدول للتعريف فقط.
شجرة الحسابات المحاسبية (Chart of Accounts). شجرة هرمية — PARENT_CHART_CODE يشير للحساب الأب.
CHART_NATURE: 0=عام/Main Account, 1=مساعد/Sub Account. CHART_TYPE: 0=ميزانية, 1=قائمة الدخل';

COMMENT ON COLUMN CHARTS.CHART_CODE IS
'كود الحساب — Account code (unique).';

COMMENT ON COLUMN CHARTS.CHART_NAME_A IS
'اسم الحساب بالعربي — Arabic account name.';

COMMENT ON COLUMN CHARTS.CHART_NAME_E IS
'اسم الحساب بالإنجليزي — English account name.';

COMMENT ON COLUMN CHARTS.CHART_NATURE IS
'طبيعة الحساب:
0 = عام / Main Account
1 = مساعد / Sub Account';

COMMENT ON COLUMN CHARTS.CHART_TYPE IS
'نوع الحساب:
0 = ميزانية / Balance Sheet
1 = قائمة الدخل / Income Statement';

COMMENT ON COLUMN CHARTS.PARENT_CHART_CODE IS
'كود الحساب الأب في الشجرة.
NULL = حساب جذر / Root account.
للشجرة: CONNECT BY PRIOR CHART_CODE = PARENT_CHART_CODE';

COMMENT ON COLUMN CHARTS.CHART_OPEN_LOC IS
'الرصيد الافتتاحي للحساب — Opening balance.';

COMMENT ON COLUMN CHARTS.CHART_LEVEL IS
'مستوى الحساب في الشجرة (1=الجذر، أعلى=أكثر تفصيلاً).
Level in hierarchy — 1=root, higher=more detailed.';


-- ------------------------------------------------------------
--  COST_CENTERS — مراكز التكلفة
-- ------------------------------------------------------------
COMMENT ON TABLE COST_CENTERS IS
'مراكز التكلفة — شجرة هرمية لتوزيع التكاليف.
Cost centers — hierarchical tree for cost allocation.';

COMMENT ON COLUMN COST_CENTERS.COST_CODE IS
'كود مركز التكلفة — Unique cost center code.';

COMMENT ON COLUMN COST_CENTERS.COST_NAME IS
'اسم مركز التكلفة بالعربي.';

COMMENT ON COLUMN COST_CENTERS.COST_NAME_E IS
'اسم مركز التكلفة بالإنجليزي.';

COMMENT ON COLUMN COST_CENTERS.COST_PARENT IS
'كود مركز التكلفة الأب.
NULL = مركز جذر / Root cost center.';


-- ------------------------------------------------------------
--  VOUCHERS — رأس القيد المحاسبي
-- ------------------------------------------------------------
COMMENT ON TABLE VOUCHERS IS
'رأس القيد المحاسبي (اليومية).
⚠ تفاصيل الحسابات المدينة والدائنة في VOUCHERS_DET.
⚠ JOIN مع VOUCHERS_DET على (VOUCHER_MONTH, VOUCHER_CODE) معاً — لازم العمودين.
Journal entry header. Details in VOUCHERS_DET.
JOIN: ON vd.voucher_code = v.voucher_code AND vd.voucher_month = v.voucher_month';

COMMENT ON COLUMN VOUCHERS.VOUCHER_CODE IS
'رقم القيد — Voucher/journal entry number. FK من VOUCHERS_DET.VOUCHER_CODE';

COMMENT ON COLUMN VOUCHERS.VOUCHER_DATE IS
'تاريخ القيد — Entry date.';

COMMENT ON COLUMN VOUCHERS.VOUCHER_MONTH IS
'شهر القيد (1-12) — جزء من مفتاح الربط مع VOUCHERS_DET.
⚠ الـ JOIN مع VOUCHERS_DET: على (VOUCHER_MONTH, VOUCHER_CODE) معاً.';

COMMENT ON COLUMN VOUCHERS.VOUCHER_DESC IS
'وصف/بيان القيد — Journal entry description.';

COMMENT ON COLUMN VOUCHERS.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN VOUCHERS.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';

COMMENT ON COLUMN VOUCHERS.BRANCH_ID IS
'Branch filter.';


-- ------------------------------------------------------------
--  VOUCHERS_DET — تفاصيل القيد المحاسبي
-- ------------------------------------------------------------
COMMENT ON TABLE VOUCHERS_DET IS
'حركات الحسابات المالية (مدين/دائن). ⚠ لا يوجد تاريخ هنا — لازم JOIN مع VOUCHERS ON(VOUCHER_MONTH, VOUCHER_CODE) للتاريخ والوصف.';

COMMENT ON COLUMN VOUCHERS_DET.VOUCHER_CODE IS
'FK → VOUCHERS.VOUCHER_CODE';

COMMENT ON COLUMN VOUCHERS_DET.VOUCHER_MONTH IS
'FK → VOUCHERS.VOUCHER_MONTH — جزء من مفتاح الربط.';

COMMENT ON COLUMN VOUCHERS_DET.SERIAL IS
'رقم سطر القيد — Line sequence number within the voucher.';

COMMENT ON COLUMN VOUCHERS_DET.CHART_CODE IS
'الحساب المدين أو الدائن.
FK → CHARTS.CHART_CODE';

COMMENT ON COLUMN VOUCHERS_DET.AMOUNT IS
'مبلغ الحركة على الحساب.
⚠ AMOUNT موجب (+) = مدين / Debit.
⚠ AMOUNT سالب (-) = دائن / Credit (مخزون بقيمة سالبة).
لحساب المدين: SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END)
لحساب الدائن: SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END)
الرصيد = مدين - دائن.
⚠ لا يوجد عمود DEBIT أو CREDIT منفصل — الإشارة هي المؤشر الوحيد.';

COMMENT ON COLUMN VOUCHERS_DET.COST_CODE IS
'مركز التكلفة المرتبط بهذا السطر (اختياري).
FK → COST_CENTERS.COST_CODE';

COMMENT ON COLUMN VOUCHERS_DET.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN VOUCHERS_DET.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';


-- ============================================================
--
--  DOMAIN 4 — الموارد البشرية
--  Tables: EMPLOYEES, EMPLOYEE_SALARIES, CHARTS_ELEMENTS,
--          METHOD_SETUP, EMP_VACATION, EMP_LOANS, ATT_EMP
-- ============================================================


-- ------------------------------------------------------------
--  EMPLOYEES — بيانات الموظفين
-- ------------------------------------------------------------
COMMENT ON TABLE EMPLOYEES IS
'بيانات الموظفين الأساسية.
⚠ الرواتب في EMPLOYEE_SALARIES — وليس هنا.
⚠ الحضور والانصراف في ATT_EMP.
⚠ بيانات الموظف الشهرية المتغيرة في EMP_VAR_STATUS.
Master employee data. Salaries in EMPLOYEE_SALARIES. Attendance in ATT_EMP.';

COMMENT ON COLUMN EMPLOYEES.EMP_ID IS
'كود الموظف الفريد — Unique employee ID.';

COMMENT ON COLUMN EMPLOYEES.EMP_NAME_AR IS
'اسم الموظف بالعربي — Arabic employee name.';

COMMENT ON COLUMN EMPLOYEES.EMP_NAME_EN IS
'اسم الموظف بالإنجليزي — English employee name.';

COMMENT ON COLUMN EMPLOYEES.DEPT_CODE IS
'كود القسم — Department code.
FK → LOOK_UP (PARENT_ID=قسم)';

COMMENT ON COLUMN EMPLOYEES.JOB_CODE IS
'كود الوظيفة — Job title code.
FK → LOOK_UP (PARENT_ID=وظيفة)';

COMMENT ON COLUMN EMPLOYEES.BRANCH_ID IS
'الفرع الذي يعمل فيه الموظف — Employee branch.
FK → BRANCHES.BRANCH_ID';

COMMENT ON COLUMN EMPLOYEES.HIRE_DATE IS
'تاريخ التعيين — Hire date.';

COMMENT ON COLUMN EMPLOYEES.END_SERVICE_DATE IS
'تاريخ انتهاء الخدمة (NULL = لا يزال موظفاً).
Termination date. NULL = currently employed.';

COMMENT ON COLUMN EMPLOYEES.END_SERVICE_FLG IS
'حالة الخدمة:
N = موظف حالي / Currently employed
Y = منتهية خدمته / Terminated
⚠ للموظفين الحاليين: AND END_SERVICE_FLG = ''N''';

COMMENT ON COLUMN EMPLOYEES.EMP_ACTIVE IS
'1 = نشط, 0 = غير نشط — Active/Inactive flag.';

COMMENT ON COLUMN EMPLOYEES.CHART_CODE IS
'حساب الموظف في شجرة الحسابات.
FK → CHARTS.CHART_CODE';

COMMENT ON COLUMN EMPLOYEES.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';


-- ------------------------------------------------------------
--  EMPLOYEE_SALARIES — مسير الرواتب الشهري
-- ------------------------------------------------------------
COMMENT ON TABLE EMPLOYEE_SALARIES IS
'مسير الرواتب الشهري — كل صف = بند راتب لموظف في شهر معين.
المفتاح المركب: (SAL_YEAR, SAL_MONTH, EMP_ID, ELEMENT_CODE, METHOD_CODE).
Monthly payroll — one row per salary element per employee per month.';

COMMENT ON COLUMN EMPLOYEE_SALARIES.SAL_YEAR IS
'سنة الراتب — Payroll year.';

COMMENT ON COLUMN EMPLOYEE_SALARIES.SAL_MONTH IS
'شهر الراتب (1-12) — Payroll month.';

COMMENT ON COLUMN EMPLOYEE_SALARIES.EMP_ID IS
'كود الموظف — FK → EMPLOYEES.EMP_ID';

COMMENT ON COLUMN EMPLOYEE_SALARIES.ELEMENT_CODE IS
'كود بند الراتب (مرتب أساسي، بدل سكن، خصم، إلخ).
FK → CHARTS_ELEMENTS.ELEMENT_CODE';

COMMENT ON COLUMN EMPLOYEE_SALARIES.METHOD_CODE IS
'طريقة احتساب هذا البند.
FK → METHOD_SETUP.METHOD_CODE';

COMMENT ON COLUMN EMPLOYEE_SALARIES.SAL IS
'قيمة هذا البند لهذا الشهر.
⚠ للحصول على إجمالي الراتب: SUM(SAL) GROUP BY EMP_ID, SAL_YEAR, SAL_MONTH';

COMMENT ON COLUMN EMPLOYEE_SALARIES.PRINTED IS
'1 = تمت طباعة قسيمة الراتب, 0 = لم تُطبع.';

COMMENT ON COLUMN EMPLOYEE_SALARIES.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';

COMMENT ON COLUMN EMPLOYEE_SALARIES.FISCAL_YEAR IS
'السنة المالية — Fiscal year.';


-- ------------------------------------------------------------
--  CHARTS_ELEMENTS — بنود الرواتب (عناصر المسير)
-- ------------------------------------------------------------
COMMENT ON TABLE CHARTS_ELEMENTS IS
'تعريف بنود الرواتب (مرتب أساسي، بدل سكن، بدل مواصلات، خصومات، إلخ).
Salary elements definition (basic salary, housing, transport, deductions).';

COMMENT ON COLUMN CHARTS_ELEMENTS.ELEMENT_CODE IS
'كود البند — Element code. FK من EMPLOYEE_SALARIES.ELEMENT_CODE';

COMMENT ON COLUMN CHARTS_ELEMENTS.ELEMENT_NAME_AR IS
'اسم البند بالعربي — Arabic element name.';

COMMENT ON COLUMN CHARTS_ELEMENTS.ELEMENT_NAME_EN IS
'اسم البند بالإنجليزي — English element name.';


-- ------------------------------------------------------------
--  METHOD_SETUP — طرق احتساب بنود الرواتب
-- ------------------------------------------------------------
COMMENT ON TABLE METHOD_SETUP IS
'طرق احتساب بنود الرواتب (ثابت، نسبة مئوية، متغير، إلخ).
Payroll element calculation methods.';

COMMENT ON COLUMN METHOD_SETUP.METHOD_CODE IS
'كود الطريقة — FK من EMPLOYEE_SALARIES.METHOD_CODE';

COMMENT ON COLUMN METHOD_SETUP.METHOD_NAME_AR IS
'اسم الطريقة بالعربي.';

COMMENT ON COLUMN METHOD_SETUP.METHOD_NAME_EN IS
'اسم الطريقة بالإنجليزي.';


-- ------------------------------------------------------------
--  ATT_EMP — سجل الحضور والانصراف
-- ------------------------------------------------------------
COMMENT ON TABLE ATT_EMP IS
'سجل الحضور والانصراف اليومي للموظفين.
Employee daily attendance log.';

COMMENT ON COLUMN ATT_EMP.EMP_ID IS 'FK → EMPLOYEES.EMP_ID';
COMMENT ON COLUMN ATT_EMP.ATT_DATE IS 'تاريخ الحضور — Attendance date.';
COMMENT ON COLUMN ATT_EMP.ATT_FLAG IS
'نوع السجل:
I = حضور / Check-in
O = انصراف / Check-out';

COMMENT ON COLUMN ATT_EMP.ATT_TIME IS
'وقت الحضور أو الانصراف.
⚠ لحساب ساعات العمل: اطرح وقت الحضور من وقت الانصراف لنفس اليوم.';

COMMENT ON COLUMN ATT_EMP.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';


-- ------------------------------------------------------------
--  EMP_VACATION — إجازات الموظفين
-- ------------------------------------------------------------
COMMENT ON TABLE EMP_VACATION IS
'سجل إجازات الموظفين.
Employee leave/vacation records.';

COMMENT ON COLUMN EMP_VACATION.EMP_ID IS 'FK → EMPLOYEES.EMP_ID';
COMMENT ON COLUMN EMP_VACATION.VAC_TYPE_ID IS
'نوع الإجازة — FK → VACATIONS_TYPE.VAC_TYPE_ID
(سنوية، مرضية، عارضة، إلخ)';
COMMENT ON COLUMN EMP_VACATION.FROM_DATE IS 'تاريخ بداية الإجازة.';
COMMENT ON COLUMN EMP_VACATION.TO_DATE IS 'تاريخ نهاية الإجازة.';
COMMENT ON COLUMN EMP_VACATION.NO_DAYS IS 'عدد أيام الإجازة.';

COMMENT ON COLUMN EMP_VACATION.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';


-- ------------------------------------------------------------
--  EMP_LOANS — قروض الموظفين
-- ------------------------------------------------------------
COMMENT ON TABLE EMP_LOANS IS
'قروض وسلف الموظفين.
Employee loans and advances.';

COMMENT ON COLUMN EMP_LOANS.LOAN_CODE IS 'كود القرض الفريد.';
COMMENT ON COLUMN EMP_LOANS.EMP_ID IS 'FK → EMPLOYEES.EMP_ID';
COMMENT ON COLUMN EMP_LOANS.LOAN_AMOUNT IS 'قيمة القرض الإجمالية — Total loan amount.';
COMMENT ON COLUMN EMP_LOANS.LOAN_MONTH_AMOUNT IS 'القسط الشهري — Monthly installment.';
COMMENT ON COLUMN EMP_LOANS.DURATION_MONTHS IS 'مدة السداد بالأشهر — Repayment duration in months.';
COMMENT ON COLUMN EMP_LOANS.FIRST_PAYMENT_DATE IS 'تاريخ أول قسط — First installment date.';

COMMENT ON COLUMN EMP_LOANS.COMPANY_CODE IS
'كود الشركة — SaaS tenant identifier.';


-- ============================================================
--
--  DOMAIN 5 — الإعدادات والنظام
--  Tables: BRANCHES, COMPANIES, LOOK_UP, LOOK_UP_PARENT,
--          USERS, ACC_USERS, INST, YEARS
-- ============================================================


-- ------------------------------------------------------------
--  BRANCHES — الفروع
-- ------------------------------------------------------------
COMMENT ON TABLE BRANCHES IS
'تعريف فروع الشركة.
Company branches definition.';

COMMENT ON COLUMN BRANCHES.BRANCH_ID IS
'كود الفرع — Branch code. FK من معظم جداول النظام.';

COMMENT ON COLUMN BRANCHES.BRANCH_NAME_AR IS
'اسم الفرع بالعربي.';

COMMENT ON COLUMN BRANCHES.BRANCH_NAME_EN IS
'اسم الفرع بالإنجليزي.';


-- ------------------------------------------------------------
--  COMPANIES — بيانات الشركات (SaaS)
-- ------------------------------------------------------------
COMMENT ON TABLE COMPANIES IS
'بيانات الشركات المستأجرة في النظام (SaaS tenants).
⚠ جدول SaaS — لا يحتوي COMPANY_CODE كعمود فلتر (هو نفسه المفتاح).
Company/tenant master data in SaaS model.';

COMMENT ON COLUMN COMPANIES.COMPANY_CODE IS
'كود الشركة الفريد — Unique company/tenant code.';

COMMENT ON COLUMN COMPANIES.COMPANY_NAME_AR IS
'اسم الشركة بالعربي.';

COMMENT ON COLUMN COMPANIES.COMPANY_NAME_EN IS
'اسم الشركة بالإنجليزي.';

COMMENT ON COLUMN COMPANIES.VAT_NO IS
'الرقم الضريبي للشركة — Company VAT registration number.';


-- ------------------------------------------------------------
--  LOOK_UP — جدول القيم المرجعية
-- ------------------------------------------------------------
COMMENT ON TABLE LOOK_UP IS
'جدول القيم المرجعية (lookup) المستخدم لتخزين قوائم الاختيار.
⚠ يحتوي على بيانات متعددة الأنواع — يجب الفلتر دائماً بـ PARENT_ID.
General lookup table for dropdown values.
ALWAYS filter by PARENT_ID to get the right list.';

COMMENT ON COLUMN LOOK_UP.LOOK_UP_ID IS
'كود القيمة — Lookup value code.';

COMMENT ON COLUMN LOOK_UP.PARENT_ID IS
'نوع القائمة — يحدد أي مجموعة من القيم.
FK → LOOK_UP_PARENT.PARENT_ID
⚠ يجب دائماً تحديد PARENT_ID للحصول على القائمة الصحيحة.
MUST always filter by PARENT_ID to get correct list.';

COMMENT ON COLUMN LOOK_UP.LOOK_UP_NAME_AR IS
'اسم القيمة بالعربي.';

COMMENT ON COLUMN LOOK_UP.LOOK_UP_NAME_EN IS
'اسم القيمة بالإنجليزي.';

COMMENT ON COLUMN LOOK_UP.LOOK_UP_VAL IS
'القيمة الفعلية المخزّنة في النظام (رقم أو كود).
Actual stored value (number or code) used in system fields.';


-- ------------------------------------------------------------
--  LOOK_UP_PARENT — أنواع قوائم الاختيار
-- ------------------------------------------------------------
COMMENT ON TABLE LOOK_UP_PARENT IS
'تعريف أنواع قوائم الاختيار في LOOK_UP.
Defines what each PARENT_ID in LOOK_UP represents.';

COMMENT ON COLUMN LOOK_UP_PARENT.PARENT_ID IS
'كود نوع القائمة — FK من LOOK_UP.PARENT_ID';

COMMENT ON COLUMN LOOK_UP_PARENT.PARENT_NAME_AR IS
'اسم النوع بالعربي (مثال: الجنس، الحالة الاجتماعية، المؤهل).';

COMMENT ON COLUMN LOOK_UP_PARENT.PARENT_NAME_EN IS
'اسم النوع بالإنجليزي.';


-- ------------------------------------------------------------
--  INST — إعدادات النظام الأساسية
-- ------------------------------------------------------------
COMMENT ON TABLE INST IS
'إعدادات النظام الأساسية — صف واحد فقط لكل شركة.
⚠ لا تستخدم هذا الجدول في JOINs للبيانات — للإعدادات فقط.
System configuration — one row per company. For settings only.';

COMMENT ON COLUMN INST.PRICE_POLICY IS
'سياسة الأسعار:
0 = سعر واحد للوحدة
1 = سعر إجمالي (مجموع الوحدات الفرعية)';


-- ------------------------------------------------------------
--  STORE_TRANS_TYPE — أنواع حركات المخزون
-- ------------------------------------------------------------
COMMENT ON TABLE STORE_TRANS_TYPE IS
'تعريف أنواع حركات المخزون وما إذا كانت وارد أو صادر.
⚠ يُستخدم مع TRANSACTION لتحديد اتجاه الحركة.
Defines stock movement types and their direction (in/out).';

COMMENT ON COLUMN STORE_TRANS_TYPE.TRANS_CODE IS
'كود نوع الحركة — FK من TRANSACTION.TRANS_TYPE_CODE';

COMMENT ON COLUMN STORE_TRANS_TYPE.TRANS_TYPE IS
'اتجاه الحركة:
1 = وارد / Stock In
0 = صادر / Stock Out
2 = تحويل / Transfer
⚠ استخدم هذا مع TRANSACTION.QTY لحساب الرصيد:
  وارد: QTY+   صادر: QTY-';

COMMENT ON COLUMN STORE_TRANS_TYPE.TRANS_NAME IS
'اسم نوع الحركة بالعربي (مثال: بيع، شراء، تحويل، جرد).';


-- ============================================================
--  نهاية الملف
--  للتحقق من الـ Comments المكتوبة:
--
--  SELECT table_name, comments
--    FROM user_tab_comments
--   WHERE comments IS NOT NULL
--   ORDER BY table_name;
--
--  SELECT table_name, column_name, comments
--    FROM user_col_comments
--   WHERE comments IS NOT NULL
--   ORDER BY table_name, column_name;
-- ============================================================
