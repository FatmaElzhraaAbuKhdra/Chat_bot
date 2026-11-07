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
    'راس فاتورة البيع والشراء. كل صف = فاتورة واحدة.
     INVTYPE     : 0=بيع , 1=شراء.
     RETURN_FLAG : 0=فاتورة عادية , 1=مرتجع.
     ⚠ JOIN مع DETAIL_INV      يكون على INV_KEY وليس INVID.
     ⚠ JOIN مع CUST             يكون على (CUST_ID + CUST_TYPE) معا وليس CUST_ID وحده.
     ⚠ JOIN مع MAIN_INV_EFFECTS يكون على INV_KEY مع فلتر ADD_DIS.
     لجلب مبيعات نقية    : WHERE INVTYPE=0 AND RETURN_FLAG=0.
     لجلب مرتجعات البيع  : WHERE INVTYPE=0 AND RETURN_FLAG=1.
     لجلب مشتريات نقية   : WHERE INVTYPE=1 AND RETURN_FLAG=0.
     صافي المبيعات = SUM(FINALTOTAL WHERE RETURN_FLAG=0) - SUM(FINALTOTAL WHERE RETURN_FLAG=1).';

COMMENT ON COLUMN MAIN_INV.INV_KEY IS
    'المفتاح الداخلي الفريد للفاتورة - Surrogate PK.
     ⚠ هذا هو المفتاح المستخدم في كل الـ JOINs مع DETAIL_INV و MAIN_INV_EFFECTS.
     ⚠ لا تستخدم INVID في JOIN - استخدم INV_KEY دائما';

COMMENT ON COLUMN MAIN_INV.INVID IS
    'رقم الفاتورة المرئي للمستخدم - للعرض والبحث فقط.
     ⚠ INVID غير فريد عبر أنواع الفواتير
     ⚠ إن حدّد المستخدم نوع الفاتورة (مبيعات/مشتريات) قيّد بـ INVTYPE
     ⚠ إن لم يذكر المستخدم النوع — اعرض كل الأنواع بدون أي INVTYPE filter
     ⚠ ممنوع إضافة INVTYPE filter من تلقاء نفسك إذا لم يذكره المستخدم صراحةً
     ⚠ للبحث بـ "رقم الفاتورة": JOIN مع MAIN_INV m على INV_KEY ثم WHERE m.INVID = الرقم
     ⚠ DETAIL_INV لا يحتوي عمود INVID — ممنوع كتابة WHERE d.INV_KEY = رقم_الفاتورة
     ⚠ لا تستخدمه في JOIN';

COMMENT ON COLUMN MAIN_INV.INVTYPE IS
    'نوع الفاتورة : 0=بيع , 1=شراء';

COMMENT ON COLUMN MAIN_INV.RETURN_FLAG IS
    'حالة الفاتورة : 0=فاتورة عادية , 1=مرتجع.
     ⚠ المرتجعات لها نفس INVTYPE (0=مرتجع بيع , 1=مرتجع شراء).
     ⚠ عند حساب صافي المبيعات : اطرح RETURN_FLAG=1 من RETURN_FLAG=0';

COMMENT ON COLUMN MAIN_INV.INVDATE IS
    'تاريخ الفاتورة (التاريخ المحاسبي).
     للفلترة : WHERE TRUNC(INVDATE) BETWEEN :from_date AND :to_date';

COMMENT ON COLUMN MAIN_INV.INVTOTAL IS
    'اجمالي الفاتورة قبل الخصومات والاضافات والضريبة';

COMMENT ON COLUMN MAIN_INV.FINALTOTAL IS
    'الاجمالي النهائي = INVTOTAL + اضافات - خصومات + ضريبة.
     هو الرقم المعروض للمستخدم كاجمالي مستحق الدفع';

COMMENT ON COLUMN MAIN_INV.TAX IS
    'قيمة الضريبة المضافة بالعملة (مبلغ وليس نسبة).
     ⚠ هذا مبلغ فعلي بالعملة وليس نسبة مئوية';

COMMENT ON COLUMN MAIN_INV.DISCOUNT IS
    'قيمة الخصم الاجمالي على راس الفاتورة';

COMMENT ON COLUMN MAIN_INV.SDAD IS
    'المبلغ المسدد نقدا فور انشاء الفاتورة.
     المتبقي غير المسدد = FINALTOTAL - SDAD';

COMMENT ON COLUMN MAIN_INV.CASH_AMOUNT IS
    'جزء الدفع نقدا عند تقسيم طريقة الدفع';

COMMENT ON COLUMN MAIN_INV.BANK_AMOUNT IS
    'جزء الدفع بالتحويل البنكي عند تقسيم طريقة الدفع';

COMMENT ON COLUMN MAIN_INV.PAY_METHOD IS
    'طريقة الدفع : 0=كاش , 1=شيك , 2=فيزا , 3=تحويل بنكي.
     ⚠ مخزن كرقم - استخدم DECODE او CASE للعرض النصي';

COMMENT ON COLUMN MAIN_INV.CUST_ID IS
    'كود العميل او المورد - FK → CUST.CUSTID.
     ⚠ الـ JOIN لازم يشمل CUST_TYPE ايضا :
       MAIN_INV.CUST_ID   = CUST.CUSTID
       MAIN_INV.CUST_TYPE = CUST.CUST_TYPE';

COMMENT ON COLUMN MAIN_INV.CUST_TYPE IS
    'نوع الجهة في الفاتورة : 0=عميل , 1=مورد , 2=وكيل.
     ⚠ جزء اساسي من شرط JOIN مع CUST - لا تحذفه';

COMMENT ON COLUMN MAIN_INV.STORE_CODE IS
    'كود المخزن الذي تمت منه العملية - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN MAIN_INV.TRANS_CODE IS
    'رقم الاذن المخزني المرتبط بالفاتورة - FK → TRANSMASTER.TRANS_CODE';

COMMENT ON COLUMN MAIN_INV.TRANS_TYPE_CODE IS
    'كود نوع الاذن المخزني المرتبط - FK → STORE_TRANS_TYPE.TRANS_CODE | التصنيف في STORE_TRANS_TYPE.TRANS_TYPE';

COMMENT ON COLUMN MAIN_INV.CHART_CODE IS
    'كود الحساب في دليل الحسابات - FK → CHARTS_ELEMENTS.CHART_CODE';

COMMENT ON COLUMN MAIN_INV.CREATE_TRANS IS
    'علم انشاء الحركة المخزنية تلقائيا عند حفظ الفاتورة : 1=نعم , 0=لا';

COMMENT ON COLUMN MAIN_INV.CASH_FLAG IS
    'نوع الفاتورة من حيث الدفع : 1=نقدي (فوري) , 0=آجل';

COMMENT ON COLUMN MAIN_INV.INV_TRANS_TYPE IS
    'نوع حركة الفاتورة (نقدي / آجل / إلخ) - FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE | الاسم في SAL_PURCH_TRANS_TYPE.TRANS_NAME';

COMMENT ON COLUMN MAIN_INV.INV_CAT IS
    'تصنيف الفاتورة - FK → INV_CATEGORIES.INV_CAT';

COMMENT ON COLUMN MAIN_INV.EFFECT_VALUE IS
    'قيمة الاضافة على مستوى راس الفاتورة (ضريبة اجمالية او رسوم)';

COMMENT ON COLUMN MAIN_INV.EFFECT_VALUE_CUST IS
    'قيمة الخصم الخاص بالعميل على مستوى راس الفاتورة';

COMMENT ON COLUMN MAIN_INV.DEALER_ID IS
    'كود الوكيل المرتبط بالفاتورة - FK → DEALER_DATA.DEALER_ID';

COMMENT ON COLUMN MAIN_INV.ADMIN_ID IS
    'كود المسؤول او المراجع - FK → ACC_USERS.USERID';

COMMENT ON COLUMN MAIN_INV.AREA_ID IS
    'كود المنطقة الجغرافية للفاتورة';

COMMENT ON COLUMN MAIN_INV.COST_CODE IS
    'مركز التكلفة المرتبط بالفاتورة - FK → COST_CENTERS.COST_CODE | الاسم في COST_CENTERS.COST_NAME';

COMMENT ON COLUMN MAIN_INV.CREATE_DATE_TM IS
    'تاريخ ووقت انشاء الفاتورة في النظام.
     ⚠ يختلف عن INVDATE : INVDATE=التاريخ المحاسبي , CREATE_DATE_TM=وقت الادخال الفعلي';

COMMENT ON COLUMN MAIN_INV.SER_IN_DAY IS
    'الرقم التسلسلي للفاتورة خلال اليوم الواحد';

COMMENT ON COLUMN MAIN_INV.HEAD_NOTES IS
    'ملاحظات راس الفاتورة';

COMMENT ON COLUMN MAIN_INV.DESERVE_DATE IS
    'تاريخ استحقاق الدفع للفواتير الآجلة';

COMMENT ON COLUMN MAIN_INV.CLIENT_NAME IS
    'اسم العميل حر النص - للعملاء غير المسجلين في CUST';

COMMENT ON COLUMN MAIN_INV.BOOK_INVNO IS
    'رقم الفاتورة في دفتر الفواتير الورقي للمطابقة اليدوية';

COMMENT ON COLUMN MAIN_INV.CLINET_ADDRESS IS
    '⚠ اسم الحقل فيه خطا املائي (CLINET بدلا من CLIENT).
     عنوان العميل غير المسجل';

COMMENT ON COLUMN MAIN_INV.CLINET_PERSONAL_ID IS
    '⚠ اسم الحقل فيه خطا املائي (CLINET بدلا من CLIENT).
     رقم الهوية الشخصية للعميل غير المسجل';

COMMENT ON COLUMN MAIN_INV.CLINET_GOVE_NAME IS
    '⚠ اسم الحقل فيه خطا املائي (CLINET بدلا من CLIENT).
     المحافظة / المنطقة للعميل غير المسجل';

COMMENT ON COLUMN MAIN_INV.CLIENT_TRAD_ID IS
    'رقم السجل التجاري للعميل غير المسجل';

COMMENT ON COLUMN MAIN_INV.ORIGINAL_INV_KEY IS
    'مفتاح الفاتورة الاصلية في حالة المرتجع - FK → MAIN_INV.INV_KEY';

COMMENT ON COLUMN MAIN_INV.OLD_INV_KEY IS
    'مفتاح الفاتورة في النظام القديم قبل الترحيل';

COMMENT ON COLUMN MAIN_INV.OLD_SESSION_ID IS
    'رقم الجلسة في النظام القديم قبل الترحيل';

COMMENT ON COLUMN MAIN_INV.SESSION_ID IS
    'معرف جلسة نقطة البيع (POS) المرتبطة بالفاتورة';

COMMENT ON COLUMN MAIN_INV.POS_INV_KEY IS
    'معرف الفاتورة في نظام نقطة البيع (POS)';

COMMENT ON COLUMN MAIN_INV.SUBMISSIONID IS
    'رقم تقديم الفاتورة الالكترونية لهيئة الزكاة والضريبة (ZATCA)';

COMMENT ON COLUMN MAIN_INV.UUID IS
    'المعرف الفريد للفاتورة الالكترونية (UUID) - مطلوب من ZATCA';

COMMENT ON COLUMN MAIN_INV.LONGID IS
    'المعرف الطويل للفاتورة الالكترونية من ZATCA';

COMMENT ON COLUMN MAIN_INV.HASHKEY IS
    'الـ Hash المشفر للفاتورة الالكترونية - للتحقق من سلامة البيانات';

COMMENT ON COLUMN MAIN_INV.STATUS IS
    'حالة تقديم الفاتورة الالكترونية لـ ZATCA (REPORTED / CLEARED / ERROR)';

COMMENT ON COLUMN MAIN_INV.MSG IS
    'رسالة الاستجابة من ZATCA عند تقديم الفاتورة الالكترونية';

COMMENT ON COLUMN MAIN_INV.INV_KEY_TAX IS
    'مفتاح الفاتورة الضريبية المرتبطة';

COMMENT ON COLUMN MAIN_INV.SENT_DATE IS
    'تاريخ ارسال الفاتورة الالكترونية لـ ZATCA';

COMMENT ON COLUMN MAIN_INV.GENERATEDQR IS
    'بيانات QR Code المولد للفاتورة الالكترونية.
     ⚠ نوع البيانات LONG (legacy) - تجنب استخدامه في WHERE او JOIN';

COMMENT ON COLUMN MAIN_INV.JSON_TAX_RESPONSE IS
    'الاستجابة الكاملة من ZATCA بصيغة JSON - نوع البيانات CLOB';

COMMENT ON COLUMN MAIN_INV.ACTION_TYPE IS
    'نوع الاجراء على الفاتورة الالكترونية (Submit / Report / Clear)';

COMMENT ON COLUMN MAIN_INV.ORD_NO IS
    'رقم امر الطلب / الشغل المرتبط بالفاتورة';

COMMENT ON COLUMN MAIN_INV.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';

COMMENT ON COLUMN MAIN_INV.FISCAL_YEAR IS
    'السنة المالية';

COMMENT ON COLUMN MAIN_INV.BRANCH_ID IS
    'كود الفرع';


-- ------------------------------------------------------------
--  DETAIL_INV — تفاصيل بنود الفاتورة
-- ------------------------------------------------------------
COMMENT ON TABLE DETAIL_INV IS
'تفاصيل بنود الفاتورة. كل صف = صنف واحد في فاتورة واحدة.
FK إلى MAIN_INV عبر INV_KEY.
FK إلى ITEMS عبر ITEMID.
⚠ إجمالي البند = (QTY * PRICE) + ADD_VAL - SUB_VAL.
⚠ لتفاصيل بنود الفواتير استخدم DETAIL_INV فقط — لا يوجد جدول اسمه PRICE_LIST_DET في هذا النظام.
⚠ JOINs الأساسية لتفاصيل الفاتورة: MAIN_INV (لـ INVID) و ITEMS (لاسم الصنف) فقط.
⚠ UNITS و ITEMGROUP اختيارية — إن استخدمتهما فاستخدم LEFT JOIN وليس INNER JOIN.
Invoice line items — one row per item per invoice.
Line total formula: (QTY * PRICE) + ADD_VAL - SUB_VAL.';

COMMENT ON COLUMN DETAIL_INV.INV_KEY IS
'المفتاح الرابط مع رأس الفاتورة — رقم داخلي وليس رقم الفاتورة المرئي للمستخدم.
FK → MAIN_INV.INV_KEY
⚠ INV_KEY ≠ رقم الفاتورة — لا تكتب WHERE d.INV_KEY = رقم_الفاتورة مطلقاً
⚠ للبحث بـ "رقم الفاتورة": JOIN مع MAIN_INV m ON m.INV_KEY = d.INV_KEY ثم WHERE m.INVID = الرقم
⚠ استخدم INV_KEY في JOIN فقط — وليس INVID';

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
'وحدة القياس المستخدمة في هذا البند — قد يكون NULL لبعض البنود.
FK → UNITS.UNIT_ID
⚠ استخدم LEFT JOIN UNITS وليس INNER JOIN — INNER JOIN يحذف جميع البنود التي UNIT_ID فيها NULL';

COMMENT ON COLUMN DETAIL_INV.QTY_UNITS IS
'الكمية بالوحدة الفرعية (إن وُجدت).
Quantity in sub-unit (if applicable).';

COMMENT ON COLUMN DETAIL_INV.GROUPID IS
'مجموعة الصنف — لأغراض التصنيف والتقارير. قد يكون NULL لبعض الأصناف.
FK → ITEMGROUP.GROUPID
⚠ استخدم LEFT JOIN ITEMGROUP وليس INNER JOIN — INNER JOIN يحذف جميع البنود التي GROUPID فيها NULL';

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
'الاسم بالعربي — Arabic name (العملاء والموردين).
⚠ عند البحث بالاسم استخدم LIKE دائماً: CUST_NAME LIKE ''%كلمة%'' — لا تستخدم المطابقة التامة لأن المستخدم قد يكتب الاسم بشكل مختلف قليلاً';

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
⚠ للأصناف والمنتجات استخدم ITEMS فقط — لا يوجد جدول اسمه PRODUCTS في هذا النظام.
Master table for all items and products. Prices and inventory movements are in other tables.';

COMMENT ON COLUMN ITEMS.ITEMID IS
'كود الصنف الفريد — Unique item/product code.';

COMMENT ON COLUMN ITEMS.ITEMNAME IS
'اسم الصنف بالعربي — Arabic item name.
⚠ عند البحث بالاسم استخدم LIKE دائماً: ITEMNAME LIKE ''%كلمة%'' — لا تستخدم المطابقة التامة';

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
⚠ أضف WHERE QTY <> 0 لاستبعاد الأصناف التي نفد رصيدها.
Current stock balance per item per store — aggregated result.
Use this for current stock queries, not the raw TRANSACTION table.
Filter: QTY <> 0 to exclude items with zero stock.';

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
'اسم الحساب بالعربي — Arabic account name.
⚠ عند البحث بالاسم استخدم LIKE دائماً: CHART_NAME_A LIKE ''%كلمة%'' — لا تستخدم المطابقة التامة';

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
'رأس القيد المحاسبي (اليومية) — للقيود المحاسبية فقط.
⚠ تفاصيل الحسابات المدينة والدائنة في VOUCHERS_DET.
⚠ JOIN مع VOUCHERS_DET على (VOUCHER_MONTH, VOUCHER_CODE) معاً — لازم العمودين.
⚠ هذا الجدول للقيود والمحاسبة فقط — استخدم CASH_TRANS_HEAD للمعاملات النقدية.
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
'اسم الموظف بالعربي — Arabic employee name.
⚠ عند البحث بالاسم استخدم LIKE دائماً: EMP_NAME_AR LIKE ''%كلمة%'' — لا تستخدم المطابقة التامة';

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

--------------------------------------------------------------------------------


---Abdullah
-- =============================================================================
-- Oracle APEX Page 20 - STORE_TRANSACTION_FORM
-- الحركات المخزنية
-- Comments on Tables and Columns extracted from f103_page_20.sql
-- Target Schema : JUSTCLICK2
-- =============================================================================

-- =============================================================================
-- 1. TRANSMASTER  (رأس الحركة المخزنية - Header)
-- =============================================================================
COMMENT ON TABLE TRANSMASTER IS
    'رأس الحركة المخزنية - يخزن بيانات رأس كل إذن صرف أو إضافة أو تحويل مخزني';

COMMENT ON COLUMN TRANSMASTER.STORE_CODE IS
    'كود المخزن المصدر - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN TRANSMASTER.TRANS_TYPE_CODE IS
    'كود نوع الإذن المخزني - FK → STORE_TRANS_TYPE.TRANS_CODE | التصنيف في STORE_TRANS_TYPE.TRANS_TYPE : 0=صرف ، 1=إضافة ، 2=تحويل';

COMMENT ON COLUMN TRANSMASTER.DIRECTION IS
    'كود الجهة (العميل أو المورد) - FK → CUST.CUSTID | الاسم في CUST.CUST_NAME | نوع الجهة في CUST.CUST_TYPE : 0=عميل ، 1=مورد';

COMMENT ON COLUMN TRANSMASTER.TRANS_DATE IS
    'تاريخ الحركة المخزنية';

COMMENT ON COLUMN TRANSMASTER.TRANS_CODE IS
    'رقم الإذن المخزني - رقم تسلسلي داخل نوع الحركة والمخزن';

COMMENT ON COLUMN TRANSMASTER.NOTES IS
    'ملاحظات الحركة المخزنية';

COMMENT ON COLUMN TRANSMASTER.INVID IS
    'رقم الفاتورة المرتبطة بالحركة - مرجع اختياري لفاتورة المورد أو العميل';

COMMENT ON COLUMN TRANSMASTER.TO_STORE_CODE IS
    'كود المخزن المستلِم في حالة التحويل - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN TRANSMASTER.PARENT_STORE_CODE IS
    'الرقم التسلسلي للإذن الأصلي عند التحويل - FK → TRANSMASTER.TRANS_SER';

COMMENT ON COLUMN TRANSMASTER.COST_CODE IS
    'كود مركز التكلفة المرتبط بالحركة - FK → COST_CENTERS.COST_CODE | الاسم في COST_CENTERS.COST_NAME | ⚠ اختياري NULL — استخدم LEFT JOIN فقط';

COMMENT ON COLUMN TRANSMASTER.TRANS_SER IS
    'الرقم التسلسلي الفريد للحركة عبر كل المخازن وأنواع الحركات - المفتاح الطبيعي القديم (Business PK)';

COMMENT ON COLUMN TRANSMASTER.PRODUCT_ORDER_CODE IS
    'رقم أمر الشغل أو الإنتاج المرتبط بالحركة - اختياري';

COMMENT ON COLUMN TRANSMASTER.USER_SEEN IS
    'آخر مستخدم اطلع على الحركة - تسجيل للمراجعة';

COMMENT ON COLUMN TRANSMASTER.INV_KEY IS
    'مفتاح الفاتورة الداخلية - ربط تفصيلي بالفاتورة';

COMMENT ON COLUMN TRANSMASTER.REAL_BALANCE_CODE IS
    'كود الجرد الفعلي المرتبط بالحركة - FK → REAL_BALANCE_HEAD.REAL_BALANCE_CODE';

COMMENT ON COLUMN TRANSMASTER.MASTER_ID IS
    'Surrogate Key للسجل - يستخدم في APEX لتحديد حالة الحفظ : IS NOT NULL = محفوظ مسبقاً';


-- =============================================================================
-- 2. TRANSACTION  (تفاصيل الحركة المخزنية - Detail IG)
-- =============================================================================
COMMENT ON TABLE TRANSACTION IS
    'تفاصيل الحركة المخزنية - يخزن بنود كل إذن صرف أو إضافة أو تحويل مخزني';

COMMENT ON COLUMN TRANSACTION.STORE_CODE IS
    'كود المخزن - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN TRANSACTION.TRANS_TYPE_CODE IS
    'كود نوع الإذن - FK → STORE_TRANS_TYPE.TRANS_CODE | التصنيف في STORE_TRANS_TYPE.TRANS_TYPE : 0=صرف ، 1=إضافة ، 2=تحويل';

COMMENT ON COLUMN TRANSACTION.TRANS_CODE IS
    'رقم الإذن - مطابق لـ TRANSMASTER.TRANS_CODE';

COMMENT ON COLUMN TRANSACTION.ITEMID IS
    'كود الصنف - FK → ITEMS.ITEMID | الاسم في ITEMS.ITEMNAME';

COMMENT ON COLUMN TRANSACTION.PRICE IS
    'سعر الوحدة في هذه الحركة';

COMMENT ON COLUMN TRANSACTION.QTY IS
    'كمية الوحدة الرئيسية للصنف في الحركة';

COMMENT ON COLUMN TRANSACTION.DISCOUNT IS
    'نسبة الخصم أو قيمة الخصم على السطر';

COMMENT ON COLUMN TRANSACTION.NOTES IS
    'ملاحظات على سطر الحركة';

COMMENT ON COLUMN TRANSACTION.INVID IS
    'رقم الفاتورة المرتبطة بالسطر - قد يختلف عن رأس الحركة';

COMMENT ON COLUMN TRANSACTION.COST_CODE IS
    'كود مركز التكلفة على مستوى السطر - FK → COST_CENTERS.COST_CODE | الاسم في COST_CENTERS.COST_NAME | ⚠ اختياري NULL — استخدم LEFT JOIN فقط';

COMMENT ON COLUMN TRANSACTION.UNIT_ID IS
    'كود وحدة القياس المستخدمة في هذا السطر - FK → UNITS.UNIT_ID | الاسم في UNITS.UNIT_NAME';

COMMENT ON COLUMN TRANSACTION.QTY_UNITS IS
    'كمية الوحدة الفرعية (sub-unit) للصنف في الحركة';

COMMENT ON COLUMN TRANSACTION.ADD_ID IS
    'الرقم التسلسلي لحركة الإضافة - يُولَّد عند تسجيل الإضافة في الرصيد';

COMMENT ON COLUMN TRANSACTION.SUB_ID IS
    'الرقم التسلسلي لحركة الصرف - يُولَّد عند خصم الكمية من الرصيد';

COMMENT ON COLUMN TRANSACTION.TURNON_ID IS
    'رقم التشغيلة (Batch/Lot Number) للصنف - يُستخدم لتتبع الدُفعات الإنتاجية';

COMMENT ON COLUMN TRANSACTION.TURNON_DT IS
    'تاريخ التشغيلة (تاريخ الدُفعة الإنتاجية)';

COMMENT ON COLUMN TRANSACTION.EXP_DATE IS
    'تاريخ صلاحية الصنف في هذا السطر';

COMMENT ON COLUMN TRANSACTION.PARENT_SUB_ID IS
    'رقم SUB_ID الأصلي في الإذن المحوَّل منه - FK → TRANSACTION.SUB_ID في إذن المصدر';

COMMENT ON COLUMN TRANSACTION.TRANSACTION_SER IS
    'الرقم التسلسلي الفريد للسطر داخل الحركة - يُستخدم للربط مع EXPIRY_DATA.TRANSACTION_SER';

COMMENT ON COLUMN TRANSACTION.ID_SEQ IS
    'رقم تسلسلي للسطر - يُميز بين سطور متعددة لنفس الصنف داخل الإذن الواحد';

COMMENT ON COLUMN TRANSACTION.UNIT_ID2 IS
    'كود وحدة القياس الثانوية - FK → UNITS.UNIT_ID | الاسم في UNITS.UNIT_NAME';

COMMENT ON COLUMN TRANSACTION.ITEMID2 IS
    'كود الصنف البديل أو المُحوَّل إليه - FK → ITEMS.ITEMID | الاسم في ITEMS.ITEMNAME';


-- =============================================================================
-- 3. TRANSACTION_TOT  (إجمالي الحركات - IG بسياسة السعر 0)
-- =============================================================================
COMMENT ON TABLE TRANSACTION_TOT IS
    'إجمالي بنود الحركة المخزنية - يُستخدم عند INST.PRICE_POLICY=0 (سعر موحد) بدون تفصيل تشغيلات';

COMMENT ON COLUMN TRANSACTION_TOT.STORE_CODE IS
    'كود المخزن - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN TRANSACTION_TOT.TRANS_TYPE_CODE IS
    'كود نوع الإذن - FK → STORE_TRANS_TYPE.TRANS_CODE | التصنيف في STORE_TRANS_TYPE.TRANS_TYPE : 0=صرف ، 1=إضافة ، 2=تحويل';

COMMENT ON COLUMN TRANSACTION_TOT.TRANS_CODE IS
    'رقم الإذن - مطابق لـ TRANSMASTER.TRANS_CODE';

COMMENT ON COLUMN TRANSACTION_TOT.ITEMID IS
    'كود الصنف - FK → ITEMS.ITEMID | الاسم في ITEMS.ITEMNAME';

COMMENT ON COLUMN TRANSACTION_TOT.PRICE IS
    'سعر الوحدة - read-only محسوب أو محمّل من سياسة الأسعار';

COMMENT ON COLUMN TRANSACTION_TOT.QTY IS
    'كمية الوحدة الرئيسية للصنف';

COMMENT ON COLUMN TRANSACTION_TOT.DISCOUNT IS
    'نسبة الخصم أو قيمة الخصم على السطر';

COMMENT ON COLUMN TRANSACTION_TOT.NOTES IS
    'ملاحظات على سطر الإجمالي';

COMMENT ON COLUMN TRANSACTION_TOT.INVID IS
    'رقم الفاتورة المرتبطة بالسطر';

COMMENT ON COLUMN TRANSACTION_TOT.COST_CODE IS
    'كود مركز التكلفة - FK → COST_CENTERS.COST_CODE | الاسم في COST_CENTERS.COST_NAME | ⚠ اختياري NULL — استخدم LEFT JOIN فقط';

COMMENT ON COLUMN TRANSACTION_TOT.UNIT_ID IS
    'كود وحدة القياس المستخدمة - FK → UNITS.UNIT_ID | الاسم في UNITS.UNIT_NAME';

COMMENT ON COLUMN TRANSACTION_TOT.QTY_UNITS IS
    'كمية الوحدة الفرعية للصنف';

COMMENT ON COLUMN TRANSACTION_TOT.SUB_ID IS
    'الرقم التسلسلي لحركة الصرف في جدول الرصيد';

COMMENT ON COLUMN TRANSACTION_TOT.TRANSACTION_SER IS
    'الرقم التسلسلي الفريد للسطر - يُستخدم للربط مع EXPIRY_DATA.TRANSACTION_SER';

COMMENT ON COLUMN TRANSACTION_TOT.ID_SEQ IS
    'رقم تسلسلي للسطر - يُميز السطور المتعددة للصنف الواحد في نفس الإذن';


-- =============================================================================
-- 4. EXPIRY_DATA  (بيانات تواريخ الصلاحية)
-- =============================================================================
COMMENT ON TABLE EXPIRY_DATA IS
    'تواريخ الصلاحية للأصناف - يُخزن تفاصيل الدُفعات وتواريخ الصلاحية لكل سطر حركة';

COMMENT ON COLUMN EXPIRY_DATA.STORE_CODE IS
    'كود المخزن - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN EXPIRY_DATA.TRANS_TYPE_CODE IS
    'كود نوع الإذن - FK → STORE_TRANS_TYPE.TRANS_CODE | التصنيف في STORE_TRANS_TYPE.TRANS_TYPE : 0=صرف ، 1=إضافة ، 2=تحويل';

COMMENT ON COLUMN EXPIRY_DATA.TRANS_CODE IS
    'رقم الإذن المرتبط - FK → TRANSMASTER.TRANS_CODE';

COMMENT ON COLUMN EXPIRY_DATA.EXPIRE_DATE IS
    'تاريخ انتهاء الصلاحية للدُفعة';

COMMENT ON COLUMN EXPIRY_DATA.TURNON_NUMBER IS
    'رقم التشغيلة (Batch/Lot) المرتبط بتاريخ الصلاحية';

COMMENT ON COLUMN EXPIRY_DATA.QTY IS
    'الكمية الخاصة بهذه الدُفعة / تاريخ الصلاحية';

COMMENT ON COLUMN EXPIRY_DATA.TRANSACTION_SER IS
    'الرقم التسلسلي للسطر - FK → TRANSACTION.TRANSACTION_SER';

COMMENT ON COLUMN EXPIRY_DATA.ITEM_ID IS
    'كود الصنف - FK → ITEMS.ITEMID | الاسم في ITEMS.ITEMNAME';


-- =============================================================================
-- 5. INST  (إعدادات النظام - System Configuration)
-- =============================================================================
COMMENT ON TABLE INST IS
    'إعدادات النظام - سجل واحد لكل شركة يضبط سلوك الحركات المخزنية والنظام ككل';

COMMENT ON COLUMN INST.CREATE_TRANS IS
    'علم إنشاء الحركة : 1=مسموح بإنشاء أذون جديدة ، 0=محظور';

COMMENT ON COLUMN INST.ADD_TRANS IS
    'علم إذن الإضافة : 1=مسموح ، 0=محظور';

COMMENT ON COLUMN INST.SUB_TRANS IS
    'علم إذن الصرف : 1=مسموح ، 0=محظور';

COMMENT ON COLUMN INST.RETURN_ADD_TRANS IS
    'علم إذن مرتجع الإضافة : 1=مسموح ، 0=محظور';

COMMENT ON COLUMN INST.RETURN_SUB_TRANS IS
    'علم إذن مرتجع الصرف : 1=مسموح ، 0=محظور';

COMMENT ON COLUMN INST.PRICE_POLICY IS
    'سياسة السعر : 0=سعر موحد يُكتب في TRANSACTION_TOT ، 1=سعر تفصيلي يُكتب في TRANSACTION';

COMMENT ON COLUMN INST.TURNON_FLAG IS
    'علم التشغيلة : 1=إلزامي إدخال رقم التشغيلة في بنود الحركة ، 0=اختياري';

COMMENT ON COLUMN INST.EXP_DATE_FLAG IS
    'علم تاريخ الصلاحية : 1=إلزامي إدخال تاريخ الصلاحية في بنود الحركة ، 0=اختياري';

COMMENT ON COLUMN INST.MAIN_SHEMA IS
    'اسم الـ Schema الرئيسي للنظام - يُستخدم في الاستعلامات الديناميكية';

COMMENT ON COLUMN INST.TO_TRANSFER_TRANS_CODE IS
    'كود نوع الإذن المستخدم في الجانب المستلِم عند التحويل التلقائي - FK → STORE_TRANS_TYPE.TRANS_CODE | الاسم في STORE_TRANS_TYPE.TRANS_NAME';

COMMENT ON COLUMN INST.MOTO_CHK IS
    'علم تحقق إضافي في الحركات (MOTO Check) : 1=مفعّل ، 0=معطّل';

COMMENT ON COLUMN INST.COST_IN_TRANSACTION IS
    'علم ظهور حقل مركز التكلفة في بنود الحركة : 1=يظهر ، 0=مخفي';

COMMENT ON COLUMN INST.DEFAULT_STORE IS
    'كود المخزن الافتراضي - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME | يُملأ تلقائياً عند فتح نموذج الحركة الجديدة';


-- =============================================================================
-- 6. STORE  (المخازن)
-- =============================================================================
COMMENT ON TABLE STORE IS
    'جدول المخازن - يُعرِّف المخازن المتاحة في النظام';

COMMENT ON COLUMN STORE.STORE_CODE IS
    'كود المخزن - المفتاح الأساسي';

COMMENT ON COLUMN STORE.STORE_NAME IS
    'اسم المخزن باللغة العربية';

COMMENT ON COLUMN STORE.STORE_NAME_EN IS
    'اسم المخزن باللغة الإنجليزية';


-- =============================================================================
-- 7. STORE_TRANS_TYPE  (أنواع الحركات المخزنية)
-- =============================================================================
COMMENT ON TABLE STORE_TRANS_TYPE IS
    'تعريف أنواع أذون الحركات المخزنية وخصائص كل نوع';

COMMENT ON COLUMN STORE_TRANS_TYPE.TRANS_CODE IS
    'كود نوع الحركة - المفتاح الأساسي';

COMMENT ON COLUMN STORE_TRANS_TYPE.TRANS_NAME IS
    'اسم نوع الحركة (مثلاً: إذن إضافة مواد خام ، إذن صرف إنتاج)';

COMMENT ON COLUMN STORE_TRANS_TYPE.TRANS_TYPE IS
    'تصنيف نوع الحركة : 0=صرف ، 1=إضافة ، 2=تحويل';

COMMENT ON COLUMN STORE_TRANS_TYPE.DUP_ITEM IS
    'السماح بتكرار الصنف في الإذن الواحد : 0=غير مسموح ، 1=مسموح';


-- =============================================================================
-- 8. ITEMS  (الأصناف)
-- =============================================================================
COMMENT ON TABLE ITEMS IS
    'جدول الأصناف المخزنية - يُعرِّف كل صنف وخصائصه.
     ⚠ للأصناف والمنتجات استخدم ITEMS فقط — لا يوجد جدول اسمه PRODUCTS في هذا النظام';

COMMENT ON COLUMN ITEMS.ITEMID IS
    'كود الصنف - المفتاح الأساسي';

COMMENT ON COLUMN ITEMS.ITEMNAME IS
    'اسم الصنف';

COMMENT ON COLUMN ITEMS.UNIT_ID IS
    'كود وحدة القياس الرئيسية - FK → UNITS.UNIT_ID | الاسم في UNITS.UNIT_NAME';

COMMENT ON COLUMN ITEMS.SUB_UNIT_ID IS
    'كود وحدة القياس الفرعية (مثلاً: كرتونة / قطعة) - FK → UNITS.UNIT_ID | الاسم في UNITS.UNIT_NAME';


-- =============================================================================
-- 9. UNITS  (وحدات القياس)
-- =============================================================================
COMMENT ON TABLE UNITS IS
    'جدول وحدات القياس المستخدمة للأصناف المخزنية';

COMMENT ON COLUMN UNITS.UNIT_ID IS
    'كود وحدة القياس - المفتاح الأساسي';

COMMENT ON COLUMN UNITS.UNIT_NAME IS
    'اسم وحدة القياس (مثلاً: كيلو ، طن ، قطعة ، كرتونة)';


-- =============================================================================
-- 10. CUST  (العملاء / الموردون)
-- =============================================================================
COMMENT ON TABLE CUST IS
    'جدول العملاء والموردين - يُستخدم كجهة الحركة في أذون الصرف والإضافة';

COMMENT ON COLUMN CUST.CUSTID IS
    'كود العميل / المورد - المفتاح الأساسي';

COMMENT ON COLUMN CUST.CUST_NAME IS
    'اسم العميل أو المورد';

COMMENT ON COLUMN CUST.CUST_TYPE IS
    'نوع الجهة : 0=عميل (مستلِم عند الصرف) ، 1=مورد (مُسلِّم عند الإضافة)';


-- =============================================================================
-- 11. COST_CENTERS  (مراكز التكلفة)
-- =============================================================================
COMMENT ON TABLE COST_CENTERS IS
    'جدول مراكز التكلفة - يُحدد الجهة المحاسبية التي تتحمل تكلفة الحركة المخزنية';

COMMENT ON COLUMN COST_CENTERS.COST_CODE IS
    'كود مركز التكلفة - المفتاح الأساسي';

COMMENT ON COLUMN COST_CENTERS.COST_NAME IS
    'اسم مركز التكلفة باللغة العربية';

COMMENT ON COLUMN COST_CENTERS.COST_NAME_E IS
    'اسم مركز التكلفة باللغة الإنجليزية';




-- =============================================
-- CASH_TRANS_HEAD — رأس حركات الخزينة
-- =============================================
COMMENT ON TABLE CASH_TRANS_HEAD IS
'حركات الخزينة النقدية — قبض وصرف الأموال من وإلى الخزائن.
⚠ هذا الجدول للحركات النقدية على الخزائن فقط — وليس لسداد الديون أو التحصيلات من العملاء.
⚠ لسداد الديون وتحصيلات العملاء والموردين استخدم جدول PAYED وليس هذا الجدول.
⚠ هذا هو الجدول الصحيح الوحيد لأي سؤال عن حركات الخزينة أو القبض أو الصرف النقدي.
⚠ VOUCHERS مخصص للقيود المحاسبية فقط — الخزينة النقدية هنا حصراً.
⚠ للبحث باسم الخزينة: JOIN مع CASHES على CASH_ID ثم WHERE c.CASH_NAME LIKE ''%اسم الخزينة كاملاً%'' — لا تستخدم CASH_ID أو STORE_CODE للبحث النصي فهي أرقام.
⚠ اسم الخزينة قد يتكون من أكثر من كلمة (مثل "رفائع الجيمش") — اكتبه كاملاً في شرط واحد: c.CASH_NAME LIKE ''%رفائع الجيمش%''. لا تقسّم الاسم إلى شروط AND أو OR منفصلة.
⚠ للبحث في البيان/الملاحظات: WHERE h.NOTES LIKE ''%نص%''
⚠ لا تضيف WHERE TRANS_TYPE إلا إذا ذكر المستخدم صراحةً (قبض أو صرف أو وارد أو صادر). لا تضيف WHERE VOUCH_POSTED إلا إذا طُلب ذلك.
⚠ لا توجد أعمدة AMOUNT ولا AMOUNT_BEFOR_TAX ولا TAX في CASH_TRANS_HEAD — هذه الأعمدة في CASH_TRANS_DETAIL حصراً. للحصول عليها: JOIN CASH_TRANS_DETAIL d ON d.TRANS_ID = h.TRANS_ID ثم SELECT d.AMOUNT, d.AMOUNT_BEFOR_TAX, d.TAX.
⚠ الأعمدة المطلوبة في SELECT لحركات الخزينة: h.TRANS_DATE, h.TRANS_CODE, h.TRANS_TYPE, h.NOTES, d.AMOUNT, d.AMOUNT_BEFOR_TAX, d.TAX, c.CASH_NAME — لا تختر كل الأعمدة من كل الجداول.
⚠ CASH_TRANS_DETAIL لا يحتوي عمود CASH_ID — إذا أردت اسم الخزينة استخدم c.CASH_NAME من CASHES فقط.
@lex حركات الخزينة = CASH_TRANS_HEAD
@lex ايصالات القبض = CASH_TRANS_HEAD
@lex سندات الصرف = CASH_TRANS_HEAD
@lex قبض نقدي = CASH_TRANS_HEAD
@lex صرف نقدي = CASH_TRANS_HEAD';

COMMENT ON COLUMN CASH_TRANS_HEAD.TRANS_ID IS
'رقم الحركة: المفتاح الأساسي الفريد للمعاملة النقدية';

COMMENT ON COLUMN CASH_TRANS_HEAD.TRANS_CODE IS
'رقم المستند: الرقم المرئي للمستخدم (رقم الإيصال)';

COMMENT ON COLUMN CASH_TRANS_HEAD.TRANS_DATE IS
'تاريخ المستند / تاريخ الحركة';

COMMENT ON COLUMN CASH_TRANS_HEAD.TRANS_TYPE IS
'نوع الحركة:
0 = وارد / قبض / تحصيل
1 = صادر / صرف / دفع
⚠ لا تعمل JOIN مع STORE_TRANS_TYPE — TRANS_TYPE هنا قيم 0/1 فقط وليس له علاقة بجدول أنواع حركات المخزن.
⚠ لا تضيف WHERE TRANS_TYPE إلا إذا ذكر السؤال نوع الحركة صراحةً (وارد أو صادر أو قبض أو صرف).';

COMMENT ON COLUMN CASH_TRANS_HEAD.CASH_ID IS
'كود الخزينة: مرتبط بـ CASHES.CASH_ID
⚠ للبحث باسم الخزينة استخدم JOIN مع CASHES على CASH_ID';

COMMENT ON COLUMN CASH_TRANS_HEAD.CHART_CODE IS
'كود الحساب الرئيسي: مرتبط بـ CHARTS.CHART_CODE.
⚠ CHART_CODE كود محاسبي رمزي (مثل 1010 أو ACC01) — لا تضع اسماً عربياً كقيمته أبداً ولا تستخدمه للبحث عن خزينة أو عميل بالاسم.';

COMMENT ON COLUMN CASH_TRANS_HEAD.COST_CODE IS
'كود مركز التكلفة: مرتبط بـ COST_CENTERS';

COMMENT ON COLUMN CASH_TRANS_HEAD.PAY_METHOD IS
'طريقة الدفع:
0 = كاش
1 = شيك
2 = فيزا
3 = تحويل بنكي';

COMMENT ON COLUMN CASH_TRANS_HEAD.NOTES IS
'ملاحظات على الحركة النقدية';

COMMENT ON COLUMN CASH_TRANS_HEAD.INV_KEY IS
'مفتاح الفاتورة المرتبطة: مرتبط بـ MAIN_INV.INV_KEY';

COMMENT ON COLUMN CASH_TRANS_HEAD.INV_CAT IS
'تصنيف الفاتورة المرتبطة';

COMMENT ON COLUMN CASH_TRANS_HEAD.REQUEST_TRANS_ID IS
'رقم اذن الصرف / الاضافة المرتبط';

COMMENT ON COLUMN CASH_TRANS_HEAD.VOUCH_POSTED IS
'حالة الترحيل للقيد المحاسبي:
0 = غير مرحّل
1 = مرحّل';

COMMENT ON COLUMN CASH_TRANS_HEAD.USER_NAME IS
'اسم المستخدم / أمين الخزينة الذي أجرى الحركة';

COMMENT ON COLUMN CASH_TRANS_HEAD.COMPANY_CODE IS
'كود الشركة: مرتبط بـ COMPANIES';

COMMENT ON COLUMN CASH_TRANS_HEAD.FISCAL_YEAR IS
'السنة المالية';

COMMENT ON COLUMN CASH_TRANS_HEAD.BRANCH_ID IS
'كود الفرع: مرتبط بـ BRANCHES';

COMMENT ON COLUMN CASH_TRANS_HEAD.CHILD_CASH_ID IS
'كود الخزينة الفرعية (لو الحركة بين خزينتين)';

COMMENT ON COLUMN CASH_TRANS_HEAD.OLD_TRANS_CODE IS
'رقم المستند القديم (للحركات المحوّلة من نظام سابق)';

COMMENT ON COLUMN CASH_TRANS_HEAD.STORE_CODE IS
'كود المخزن المرتبط بالحركة — رقم (NUMBER) فقط.
⚠ STORE_CODE رقم صحيح — لا تستخدم عليه LIKE أو مقارنة نصية أبداً.
⚠ للبحث بالاسم استخدم CASHES.CASH_NAME LIKE عبر JOIN على CASH_ID وليس STORE_CODE.
⚠ لا تضيف WHERE STORE_CODE ما لم يُذكر رقم المخزن صراحةً في السؤال — البحث بالاسم يكون عبر CASHES.CASH_NAME فقط.';

COMMENT ON COLUMN CASH_TRANS_HEAD.SESSION_ID IS
'رقم جلسة النظام عند إنشاء الحركة';

-- =============================================
-- CASH_TRANS_DETAIL — تفاصيل حركات الخزينة
-- =============================================
COMMENT ON TABLE CASH_TRANS_DETAIL IS
'تفاصيل حركات الخزينة: سطر لكل حساب أو توجيه في الحركة النقدية';

COMMENT ON COLUMN CASH_TRANS_DETAIL.SERIAL IS
'رقم السطر التسلسلي: المفتاح الأساسي للسطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.TRANS_ID IS
'رقم الحركة: مرتبط بـ CASH_TRANS_HEAD.TRANS_ID — JOIN: JOIN CASH_TRANS_DETAIL d ON d.TRANS_ID = h.TRANS_ID.
⚠ الأعمدة AMOUNT وAMOUNT_BEFOR_TAX وTAX تنتمي لـ CASH_TRANS_DETAIL (alias d) لا CASH_TRANS_HEAD (alias ct أو h) — اكتبها d.AMOUNT لا ct.AMOUNT.';

COMMENT ON COLUMN CASH_TRANS_DETAIL.ID IS
'معرف السطر الداخلي';

COMMENT ON COLUMN CASH_TRANS_DETAIL.FLAG IS
'نوع التوجيه:
0 = مدين / دائن عادي
1 = سطر خاص (اشتراكات / عقود)';

COMMENT ON COLUMN CASH_TRANS_DETAIL.AMOUNT IS
'مبلغ السطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.AMOUNT_BEFOR_TAX IS
'المبلغ قبل الضريبة';

COMMENT ON COLUMN CASH_TRANS_DETAIL.TAX IS
'قيمة الضريبة على السطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.CHART_CODE IS
'كود الحساب في هذا السطر: مرتبط بـ CHARTS.CHART_CODE';

COMMENT ON COLUMN CASH_TRANS_DETAIL.CHART_CODE_NEXT IS
'كود الحساب المقابل (الطرف الآخر من القيد)';

COMMENT ON COLUMN CASH_TRANS_DETAIL.COST_CODE IS
'كود مركز التكلفة للسطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.COST_CODE_NEXT IS
'كود مركز التكلفة للحساب المقابل';

COMMENT ON COLUMN CASH_TRANS_DETAIL.NOTES_DETAIL IS
'ملاحظات السطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.SELLER IS
'كود البائع / المندوب المرتبط بالسطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.CONTRACT_CODE IS
'رقم العقد المرتبط بالسطر';

COMMENT ON COLUMN CASH_TRANS_DETAIL.MEMBER_ST_DATE IS
'تاريخ بداية الاشتراك (للسطور من نوع اشتراك)';

COMMENT ON COLUMN CASH_TRANS_DETAIL.MEMBER_END_DATE IS
'تاريخ نهاية الاشتراك';

COMMENT ON COLUMN CASH_TRANS_DETAIL.MEMBER_ST_MO IS
'شهر بداية الاشتراك';

COMMENT ON COLUMN CASH_TRANS_DETAIL.MEMBER_END_MO IS
'شهر نهاية الاشتراك';

COMMENT ON COLUMN CASH_TRANS_DETAIL.DIFF_MO IS
'عدد الأشهر بين بداية ونهاية الاشتراك';

COMMENT ON COLUMN CASH_TRANS_DETAIL.FRACTION_PAYED IS
'المبلغ المدفوع كجزء من الاشتراك';

COMMENT ON COLUMN CASH_TRANS_DETAIL.INV_KEY IS
'مفتاح الفاتورة المرتبطة بالسطر — اختياري، قد يكون NULL.
⚠ لا تستخدم JOIN مع MAIN_INV إلا لو السؤال يطلب بيانات الفاتورة صراحةً.
⚠ لاستعراض حركات الخزينة لا تحتاج JOIN مع MAIN_INV.';

COMMENT ON COLUMN CASH_TRANS_DETAIL.COMPANY_CODE IS
'كود الشركة';

COMMENT ON COLUMN CASH_TRANS_DETAIL.FISCAL_YEAR IS
'السنة المالية';

COMMENT ON COLUMN CASH_TRANS_DETAIL.BRANCH_ID IS
'كود الفرع';

-- =============================================
-- CASHES — الخزائن
-- =============================================
COMMENT ON TABLE CASHES IS
'جدول الخزائن: يحتوي على جميع الخزائن النقدية والبنكية
@lex الخزينة = CASHES
@lex الخزائن = CASHES';

COMMENT ON COLUMN CASHES.CASH_ID IS
'رقم الخزينة: المفتاح الأساسي';

COMMENT ON COLUMN CASHES.CASH_NAME IS
'اسم الخزينة بالعربي — هذا هو الحقل الوحيد للبحث النصي عن الخزينة.
⚠ أي اسم خزينة مذكور في السؤال يُبحث حصراً بـ CASH_NAME LIKE ''%كلمة%'' (قسّم الاسم واستخدم LIKE لكل كلمة).
⚠ لا تستخدم CHART_CODE أو STORE_CODE أو CASH_ID كبديل عن CASH_NAME للبحث النصي — هذه أرقام وأكواد وليست نصوصاً.';

COMMENT ON COLUMN CASHES.CASH_NAME_E IS
'اسم الخزينة بالإنجليزي';

COMMENT ON COLUMN CASHES.OPEN_BALANCE IS
'الرصيد الافتتاحي للخزينة';

COMMENT ON COLUMN CASHES.OPEN_BALANCE_DATE IS
'تاريخ الرصيد الافتتاحي';

COMMENT ON COLUMN CASHES.CHART_CODE IS
'كود الحساب المرتبط بالخزينة في شجرة الحسابات: مرتبط بـ CHARTS.CHART_CODE';

COMMENT ON COLUMN CASHES.PARENT_CASH_ID IS
'رقم الخزينة الأب: للخزائن الفرعية
⚠ لو PARENT_CASH_ID فيه قيمة يبقى الخزينة فرعية';

COMMENT ON COLUMN CASHES.BANK_ACC_NO IS
'رقم الحساب البنكي (للخزائن البنكية)';

COMMENT ON COLUMN CASHES.BRANCH_ID IS
'كود الفرع: مرتبط بـ BRANCHES';

COMMENT ON COLUMN CASHES.COMPANY_CODE IS
'كود الشركة: مرتبط بـ COMPANIES'; 
-- =============================================================================
-- End of Comments Script - Page 20 (STORE_TRANSACTION_FORM)
-- =============================================================================
-- =============================================================================
-- نظام السداد - Page 30 + Page 46
-- payed_system_comments.sql
-- Tables : SAL_PURCH_TRANS_TYPE | PAYED | MAIN_INV_PAYED
--        | INV_CATEGORIES | DEALER_DATA | INST (additions)
-- Target Schema : JUSTCLICK2
-- =============================================================================


-- =============================================================================
-- Page 30 - SAL_PURCH_TRANS_TYPE
-- تكويد انواع حركات السداد (عملاء / موردون / مندوبون)
-- =============================================================================
-- التكامل مع شاشة السداد (Page 46) :
--   PAYED.SDAD_TRANS_TYPE  → FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE
--   PAYED.SAL_PURCH        → يطابق SAL_PURCH_TRANS_TYPE.SAL_PURCH
--   ⚠ الـ JOIN الصح دايما على الحقلين معا :
--       PAYED.SDAD_TRANS_TYPE = SAL_PURCH_TRANS_TYPE.TRANS_CODE
--       PAYED.SAL_PURCH       = SAL_PURCH_TRANS_TYPE.SAL_PURCH
-- =============================================================================

COMMENT ON TABLE SAL_PURCH_TRANS_TYPE IS
    'تكويد انواع حركات السداد للعملاء والموردين والمندوبين.
     المفتاح الاساسي المركب : (TRANS_CODE + SAL_PURCH).
     SAL_PURCH : 0=عملاء , 1=موردون , 2=مندوبون.
     ⚠ الربط مع PAYED يكون على (TRANS_CODE + SAL_PURCH) معا وليس TRANS_CODE وحده.

     للاجابة على اسئلة التحليل :
       مستحقات العملاء         : PAYED JOIN هذا الجدول WHERE SAL_PURCH=0 AND DEB_CRD=1
       تحليل التحصيلات النقدية : WHERE CASH_TRANS_TYPE=1 (نقدي)
       تحليل التحصيلات الآجلة  : WHERE CASH_TRANS_TYPE=0 (آجل/شيك/تحويل)

     الـ SDAD_TRANS_TYPE المحظور تعديله يدويا في Page 46
     (يتولد تلقائيا من الفاتورة) :
       100,101,200,201,310,320,110,111,210,211,311,321

     FORM_ID في APP_SEC :
       51  = انواع حركات العملاء    (SAL_PURCH=0)
       655 = انواع حركات الموردين   (SAL_PURCH=1)
       64  = انواع حركات المندوبين  (SAL_PURCH=2)';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.TRANS_CODE IS
    'كود نوع حركة السداد - جزء من المفتاح الاساسي.
     ⚠ ليس فريدا وحده - الفريد هو (TRANS_CODE + SAL_PURCH) معا.
     يُخزن في PAYED.SDAD_TRANS_TYPE للربط بنوع الحركة.
     الاكواد المحظور ادخالها يدويا في Page 46 (تولد من الفاتورة) :
       100,101,200,201,310,320,110,111,210,211,311,321';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.SAL_PURCH IS
    'نوع الطرف - جزء من المفتاح الاساسي :
     0 = عملاء / Customers
     1 = موردون / Suppliers
     2 = مندوبون / Dealers
     ⚠ جزء اساسي من شرط JOIN مع PAYED - لا تحذفه.
     يطابق PAYED.SAL_PURCH في كل الاستعلامات.';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.TRANS_NAME_AR IS
    'اسم نوع حركة السداد باللغة العربية - للعرض في الواجهة';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.TRANS_NAME_EN IS
    'اسم نوع حركة السداد باللغة الانجليزية - للعرض في الواجهة';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.DEB_CRD IS
    'اتجاه الحركة المحاسبي :
     0 = مدين  / Debit  (العميل مدين للشركة - فاتورة بيع / مرتجع شراء)
     1 = دائن  / Credit (العميل دائن للشركة - سداد / مرتجع بيع)
     ⚠ هذا الحقل يحدد جانب القيد المحاسبي - لا تخلط بين قيمه.
     للاستعلام عن المستحقات (العميل مدين) : WHERE DEB_CRD = 0
     للاستعلام عن السدادات (العميل يسدد) : WHERE DEB_CRD = 1';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.CASH_TRANS_TYPE IS
    'تصنيف الحركة من حيث طريقة الدفع :
     1 = نقدي   / Cash     (تحصيل فوري بالكاش)
     0 = غير نقدي / Non-Cash (شيك / تحويل بنكي / آجل)
     ⚠ هذا الحقل هو المفتاح لتحليل التحصيلات النقدية :
       تحليل التحصيلات النقدية :
         SELECT p.*, s.TRANS_NAME_AR
           FROM PAYED p
           JOIN SAL_PURCH_TRANS_TYPE s
             ON p.SDAD_TRANS_TYPE = s.TRANS_CODE
            AND p.SAL_PURCH       = s.SAL_PURCH
          WHERE s.CASH_TRANS_TYPE = 1
       تحليل التحصيلات الآجلة / الشيكات :
         ... WHERE s.CASH_TRANS_TYPE = 0';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.BENFIT_EFFECT IS
    'تاثير الحركة على الفائدة / العمولة.
     يحدد ما اذا كانت هذه الحركة تؤثر على حساب الفوائد المستحقة.
     يُستخدم في حسابات الوكلاء والمندوبين (SAL_PURCH=2).';

COMMENT ON COLUMN SAL_PURCH_TRANS_TYPE.DOC_ID IS
    'رقم نوع المستند المحاسبي المرتبط بهذه الحركة.
     يحدد القيد المحاسبي الذي يُنشا تلقائيا عند تسجيل السداد.';


-- =============================================================================
-- Page 46 - PayedForm (شاشة السداد)
-- =============================================================================
-- العلاقات الاساسية في نظام السداد :
--
--   PAYED (1) ────────────< MAIN_INV_PAYED (M)
--     on: PAYED_ID + SDAD_TRANS_TYPE
--
--   MAIN_INV (1) ─────────< MAIN_INV_PAYED (M)
--     on: INV_KEY
--
--   CUST (1) ─────────────< PAYED (M)
--     on: CUST_ID = CUSTID AND SAL_PURCH = CUST_TYPE
--
--   SAL_PURCH_TRANS_TYPE (1) < PAYED (M)
--     on: SDAD_TRANS_TYPE = TRANS_CODE AND SAL_PURCH = SAL_PURCH
--
-- معادلات التحليل المالي :
--   المستحق على عميل  = SUM(MAIN_INV.FINALTOTAL) - SUM(MAIN_INV_PAYED.SDAD)
--                        WHERE INVTYPE=0 AND RETURN_FLAG=0 AND CUST_ID=x
--   المتبقي على فاتورة = MAIN_INV.FINALTOTAL - SUM(MAIN_INV_PAYED.SDAD WHERE INV_KEY=x)
--   التحصيلات النقدية  = PAYED JOIN SAL_PURCH_TRANS_TYPE WHERE CASH_TRANS_TYPE=1
-- =============================================================================


-- =============================================================================
-- 1. PAYED  (راس ايصال السداد)
-- =============================================================================
COMMENT ON TABLE PAYED IS
    'حركات السداد - راس ايصال السداد - كل صف = عملية سداد واحدة (تحصيل من عميل او سداد لمورد).
     ⚠ لتفاصيل حركة السداد رقم X: استخدم هذا الجدول WHERE PAYED_ID = X — وليس CASH_TRANS_HEAD.
     ⚠ CASH_TRANS_HEAD للخزائن النقدية فقط — سداد الديون والتحصيلات هنا في PAYED.
     ⚠ SAL_PURCH يحدد نوع الطرف — استخدمه لما يذكر المستخدم نوع الطرف صراحةً:
         إذا قال "عميل"   → أضف AND p.SAL_PURCH = 0
         إذا قال "مورد"   → أضف AND p.SAL_PURCH = 1
         إذا قال "مندوب"  → أضف AND p.SAL_PURCH = 2
         إذا لم يذكر نوع الطرف → لا تضف فلتر SAL_PURCH
     المفتاح الاساسي المركب : (PAYED_ID + SDAD_TRANS_TYPE).
     SAL_PURCH : 0=عملاء , 1=موردون , 2=مندوبون.
     DEB_CRD   : 0=مدين (فاتورة بيع / مرتجع شراء) , 1=دائن (سداد / مرتجع بيع).
     ⚠ الربط مع MAIN_INV_PAYED يكون على (PAYED_ID + SDAD_TRANS_TYPE) معا.
     ⚠ الربط مع CUST يكون على (CUST_ID=CUSTID AND SAL_PURCH=CUST_TYPE).
     ⚠ الربط مع SAL_PURCH_TRANS_TYPE يكون على
         (SDAD_TRANS_TYPE=TRANS_CODE AND SAL_PURCH=SAL_PURCH).

     للاجابة على اسئلة التحليل المالي :

       اكثر 10 عملاء سداد :
         SELECT c.CUST_NAME, SUM(p.PAYED_AMOUNT) TOTAL
           FROM PAYED p
           JOIN CUST c ON c.CUSTID=p.CUST_ID AND c.CUST_TYPE=p.SAL_PURCH
          WHERE p.SAL_PURCH=0
          GROUP BY c.CUST_NAME
          ORDER BY TOTAL DESC FETCH FIRST 10 ROWS ONLY

       تحليل التحصيلات النقدية :
         SELECT s.TRANS_NAME_AR, SUM(p.PAYED_AMOUNT)
           FROM PAYED p
           JOIN SAL_PURCH_TRANS_TYPE s
             ON s.TRANS_CODE=p.SDAD_TRANS_TYPE AND s.SAL_PURCH=p.SAL_PURCH
          WHERE s.CASH_TRANS_TYPE=1 AND p.SAL_PURCH=0
          GROUP BY s.TRANS_NAME_AR';

COMMENT ON COLUMN PAYED.PAYED_ID IS
    'رقم ايصال السداد - جزء من المفتاح الاساسي.
     ⚠ ليس فريدا وحده - الفريد هو (PAYED_ID + SDAD_TRANS_TYPE) معا.
     يتولد تلقائيا : MAX(PAYED_ID)+1 لنفس SDAD_TRANS_TYPE و SAL_PURCH.';

COMMENT ON COLUMN PAYED.SDAD_TRANS_TYPE IS
    'نوع حركة السداد - جزء من المفتاح الاساسي.
     FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE (مع SAL_PURCH في الشرط).
     ⚠ الربط الصح : SDAD_TRANS_TYPE=TRANS_CODE AND SAL_PURCH=SAL_PURCH.
     الاكواد المحظور ادخالها يدويا (تولد تلقائيا من الفاتورة) :
       100,101,200,201,310,320,110,111,210,211,311,321.
     للتمييز بين نقدي وآجل : JOIN مع SAL_PURCH_TRANS_TYPE
       WHERE CASH_TRANS_TYPE=1 (نقدي) او CASH_TRANS_TYPE=0 (آجل).';

COMMENT ON COLUMN PAYED.CUST_ID IS
    'كود العميل او المورد او المندوب - FK → CUST.CUSTID.
     ⚠ الربط الصح : CUST_ID=CUST.CUSTID AND SAL_PURCH=CUST.CUST_TYPE.
     | الاسم في CUST.CUST_NAME';

COMMENT ON COLUMN PAYED.SAL_PURCH IS
    'نوع الطرف في عملية السداد :
     0 = عملاء / Customers  (تحصيل من عميل)
     1 = موردون / Suppliers  (سداد لمورد)
     2 = مندوبون / Dealers   (تسوية مع مندوب)
     ⚠ جزء اساسي من شرط JOIN مع CUST و SAL_PURCH_TRANS_TYPE - لا تحذفه.';

COMMENT ON COLUMN PAYED.PAYED_DATE IS
    'تاريخ ايصال السداد.
     للفلترة : WHERE TRUNC(PAYED_DATE) BETWEEN :from_date AND :to_date
     للتجميع الشهري : TRUNC(PAYED_DATE, ''MM'')';

COMMENT ON COLUMN PAYED.PAYED_AMOUNT IS
    'اجمالي مبلغ السداد في هذا الايصال.
     ⚠ هذا الاجمالي قد يُوزَّع على اكثر من فاتورة في MAIN_INV_PAYED.
     التوزيع التفصيلي : SELECT SUM(SDAD) FROM MAIN_INV_PAYED
                         WHERE PAYED_ID=x AND SDAD_TRANS_TYPE=y';

COMMENT ON COLUMN PAYED.NOTES IS
    'ملاحظات ايصال السداد';

COMMENT ON COLUMN PAYED.DEB_CRD IS
    'اتجاه الحركة المحاسبي :
     0 = مدين  (العميل مدين للشركة - فاتورة بيع / مرتجع شراء)
     1 = دائن  (العميل دائن للشركة - سداد من عميل / مرتجع بيع)
     ⚠ تفسير DEB_CRD يعتمد على SAL_PURCH معا :
       SAL_PURCH=0 AND DEB_CRD=1 → تحصيل من عميل (بيع آجل)
       SAL_PURCH=0 AND DEB_CRD=0 → رد مبلغ لعميل (مرتجع بيع)
       SAL_PURCH=1 AND DEB_CRD=0 → سداد لمورد (شراء آجل)
       SAL_PURCH=1 AND DEB_CRD=1 → استرداد من مورد (مرتجع شراء)';

COMMENT ON COLUMN PAYED.DEALER_ID IS
    'كود المندوب المرتبط بعملية السداد - FK → DEALER_DATA.DEALER_ID
     | الاسم في DEALER_DATA.NAME_AR
     يُملا عند ربط السداد بمندوب مبيعات محدد.';

COMMENT ON COLUMN PAYED.PARENT_PAYED IS
    'رقم الايصال الاصلي في حالة التعديل او الالغاء - FK → PAYED.PAYED_ID.
     يُستخدم لتتبع سلسلة التعديلات على نفس عملية السداد.';

COMMENT ON COLUMN PAYED.INV_CAT IS
    'تصنيف الفاتورة المرتبط بالسداد - FK → INV_CATEGORIES.INV_CAT
     | الاسم في INV_CATEGORIES.INV_CAT_NAME_AR.
     يُستخدم لتصنيف السدادات حسب نوع الفاتورة (نقدي / آجل / إلخ).';

COMMENT ON COLUMN PAYED.STORE_CODE IS
    'كود المخزن المرتبط بعملية السداد - FK → STORE.STORE_CODE
     | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN PAYED.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';

COMMENT ON COLUMN PAYED.FISCAL_YEAR IS
    'السنة المالية';

COMMENT ON COLUMN PAYED.BRANCH_ID IS
    'كود الفرع';


-- =============================================================================
-- 2. MAIN_INV_PAYED  (توزيع السداد على الفواتير)
-- =============================================================================
COMMENT ON TABLE MAIN_INV_PAYED IS
    'توزيع مبلغ السداد على الفواتير - كل صف = جزء من سداد موزَّع على فاتورة واحدة.
     المفتاح الاساسي المركب : (PAYED_ID + SDAD_TRANS_TYPE + INVID + CHILD_CUSTID).
     ⚠ JOIN مع PAYED يكون على (PAYED_ID + SDAD_TRANS_TYPE) معا.
     ⚠ JOIN مع MAIN_INV يكون على INV_KEY (وليس INVID).
     ⚠ INV_KEY قابل للـ NULL - استخدم LEFT JOIN و NVL عند الجمع.

     لحساب المتبقي على فاتورة :
       SELECT m.FINALTOTAL - NVL(SUM(mp.SDAD),0) AS REMAIN
         FROM MAIN_INV m
         LEFT JOIN MAIN_INV_PAYED mp ON mp.INV_KEY = m.INV_KEY
        WHERE m.INV_KEY = :inv_key
        GROUP BY m.FINALTOTAL

     لحساب اجمالي مستحقات العملاء :
       SELECT m.CUST_ID,
              SUM(m.FINALTOTAL) - NVL(SUM(mp.SDAD),0) AS OUTSTANDING
         FROM MAIN_INV m
         LEFT JOIN MAIN_INV_PAYED mp ON mp.INV_KEY = m.INV_KEY
        WHERE m.INVTYPE=0 AND m.RETURN_FLAG=0
        GROUP BY m.CUST_ID
        ORDER BY OUTSTANDING DESC';

COMMENT ON COLUMN MAIN_INV_PAYED.PAYED_ID IS
    'رقم ايصال السداد - جزء من المفتاح الاساسي.
     FK → PAYED.PAYED_ID (مع SDAD_TRANS_TYPE في الشرط).';

COMMENT ON COLUMN MAIN_INV_PAYED.SDAD_TRANS_TYPE IS
    'نوع حركة السداد - جزء من المفتاح الاساسي.
     FK → PAYED.SDAD_TRANS_TYPE = SAL_PURCH_TRANS_TYPE.TRANS_CODE.
     ⚠ جزء اساسي من شرط JOIN مع PAYED - لا تحذفه.';

COMMENT ON COLUMN MAIN_INV_PAYED.INVID IS
    'رقم الفاتورة للعرض - جزء من المفتاح الاساسي.
     ⚠ للعرض فقط - استخدم INV_KEY في الـ JOIN مع MAIN_INV.';

COMMENT ON COLUMN MAIN_INV_PAYED.INV_KEY IS
    'المفتاح الداخلي للفاتورة - FK → MAIN_INV.INV_KEY.
     ⚠ قابل للـ NULL في بعض الحالات - استخدم LEFT JOIN و NVL.
     ⚠ استخدم INV_KEY دائما في الـ JOIN مع MAIN_INV وليس INVID.';

COMMENT ON COLUMN MAIN_INV_PAYED.SAL_PURCH IS
    'نوع الحركة : 0=بيع , 1=شراء.
     يطابق MAIN_INV.INVTYPE للتحقق من تطابق نوع الفاتورة مع نوع السداد.';

COMMENT ON COLUMN MAIN_INV_PAYED.SDAD IS
    'المبلغ الموزَّع على هذه الفاتورة تحديدا من اجمالي الايصال.
     ⚠ SUM(SDAD) WHERE INV_KEY=x = اجمالي ما سُدِّد على الفاتورة.
     ⚠ MAIN_INV.FINALTOTAL - SUM(SDAD) = المتبقي على الفاتورة.';

COMMENT ON COLUMN MAIN_INV_PAYED.CHILD_CUSTID IS
    'كود العميل الفرعي - جزء من المفتاح الاساسي.
     يُستخدم عند السداد باسم عميل فرعي مرتبط بعميل رئيسي
     (PARENT_CUST_CODE في جدول CUST).
     FK → CUST.CUSTID';

COMMENT ON COLUMN MAIN_INV_PAYED.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';

COMMENT ON COLUMN MAIN_INV_PAYED.FISCAL_YEAR IS
    'السنة المالية';

COMMENT ON COLUMN MAIN_INV_PAYED.BRANCH_ID IS
    'كود الفرع';


-- =============================================================================
-- 3. INV_CATEGORIES  (تصنيفات الفواتير)
-- =============================================================================
COMMENT ON TABLE INV_CATEGORIES IS
    'تصنيفات الفواتير - يحدد نوع الفاتورة المحاسبي والقيود المرتبطة بها.
     المفتاح الاساسي : INV_CAT.
     INV_CAT_TYPE : يصنف التصنيف نفسه (1=مخصص للسداد , غيره=فواتير عادية).
     يُستخدم في Page 46 لتحديد نوع قيد السداد المحاسبي.';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT IS
    'كود تصنيف الفاتورة - المفتاح الاساسي.
     يُخزن في PAYED.INV_CAT و MAIN_INV.INV_CAT.';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT_NAME_AR IS
    'اسم تصنيف الفاتورة باللغة العربية - للعرض في الواجهة';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT_NAME_EN IS
    'اسم تصنيف الفاتورة باللغة الانجليزية - للعرض في الواجهة';

COMMENT ON COLUMN INV_CATEGORIES.INV_CAT_TYPE IS
    'نوع التصنيف :
     1       = مخصص للسداد (يظهر في LOV شاشة السداد Page 46)
     غير 1   = تصنيف فواتير عادية (يظهر في LOV شاشة الفواتير Page 52/53)
     ⚠ عند جلب تصنيفات السداد    : WHERE inv_cat_type = 1
     ⚠ عند جلب تصنيفات الفواتير  : WHERE inv_cat_type != 1';

COMMENT ON COLUMN INV_CATEGORIES.CHART_CODE IS
    'كود الحساب المحاسبي المرتبط بهذا التصنيف - FK → CHARTS_ELEMENTS.CHART_CODE
     يحدد الحساب الذي يُقيَّد فيه عند استخدام هذا التصنيف.';

COMMENT ON COLUMN INV_CATEGORIES.COST_CODE IS
    'مركز التكلفة المرتبط بهذا التصنيف - FK → COST_CENTERS.COST_CODE
     | الاسم في COST_CENTERS.COST_NAME';

COMMENT ON COLUMN INV_CATEGORIES.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';

COMMENT ON COLUMN INV_CATEGORIES.FISCAL_YEAR IS
    'السنة المالية';

COMMENT ON COLUMN INV_CATEGORIES.BRANCH_ID IS
    'كود الفرع';


-- =============================================================================
-- 4. DEALER_DATA  (بيانات الوكلاء والمندوبين)
-- =============================================================================
COMMENT ON TABLE DEALER_DATA IS
    'بيانات الوكلاء والمندوبين. كل صف = وكيل او مندوب.
     المفتاح الاساسي المركب : (DEALER_ID + DEALER_TYPE).
     ⚠ اي JOIN مع DEALER_DATA لازم يشمل DEALER_TYPE في الشرط.
     DEALER_TYPE : 0=وكيل مبيعات (يظهر في LOV Page 46)
                   2=وكيل مرتبط بعميل (في CUST.DEALER_ID و MAIN_INV.DEALER_ID)
     يُستخدم في شاشة السداد لتحديد المندوب المسؤول عن التحصيل.';

COMMENT ON COLUMN DEALER_DATA.DEALER_ID IS
    'كود الوكيل / المندوب - جزء من المفتاح الاساسي.
     ⚠ ليس فريدا وحده - الفريد هو (DEALER_ID + DEALER_TYPE) معا.
     يُخزن في PAYED.DEALER_ID و MAIN_INV.DEALER_ID و CUST.DEALER_ID.';

COMMENT ON COLUMN DEALER_DATA.DEALER_TYPE IS
    'نوع الوكيل - جزء من المفتاح الاساسي :
     0 = وكيل مبيعات / Sales Dealer (يظهر في LOV السداد)
     2 = وكيل مرتبط بعميل (في بيانات العميل والفاتورة)
     ⚠ جزء اساسي من شرط JOIN - لا تحذفه ابدا.';

COMMENT ON COLUMN DEALER_DATA.NAME_AR IS
    'اسم الوكيل / المندوب باللغة العربية - للعرض في الواجهة';

COMMENT ON COLUMN DEALER_DATA.NAME_EN IS
    'اسم الوكيل / المندوب باللغة الانجليزية - للعرض في الواجهة';

COMMENT ON COLUMN DEALER_DATA.PARENT_DEALER_ID IS
    'كود الوكيل الاب في التسلسل الهرمي - FK → DEALER_DATA.DEALER_ID';

COMMENT ON COLUMN DEALER_DATA.PARENT_DEALER_TYPE IS
    'نوع الوكيل الاب - FK → DEALER_DATA.DEALER_TYPE
     ⚠ لازم يُستخدم مع PARENT_DEALER_ID في الـ JOIN على DEALER_DATA.';

COMMENT ON COLUMN DEALER_DATA.PERCENT IS
    'نسبة العمولة % للوكيل / المندوب.
     تُستخدم في حساب عمولات المبيعات المرتبطة بالفواتير والتحصيلات.';

COMMENT ON COLUMN DEALER_DATA.CHART_CODE IS
    'كود الحساب المحاسبي للوكيل - FK → CHARTS_ELEMENTS.CHART_CODE
     يحدد الحساب الذي تُقيَّد فيه العمولات.';

COMMENT ON COLUMN DEALER_DATA.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';

COMMENT ON COLUMN DEALER_DATA.FISCAL_YEAR IS
    'السنة المالية';

COMMENT ON COLUMN DEALER_DATA.BRANCH_ID IS
    'كود الفرع';


-- =============================================================================
-- 5. INST  (حقول اضافية اتكشفت من Page 46)
-- =============================================================================
COMMENT ON COLUMN INST.DEALER_IN_INV IS
    'علم ربط المندوب بالفاتورة تلقائيا : 1=مفعل , 0=معطل.
     يُحدد ما اذا كان يجب اختيار مندوب عند انشاء الفاتورة.';

COMMENT ON COLUMN INST.DEALER_SDAD_TYPE IS
    'كود نوع حركة السداد الخاص بعمولات المندوبين.
     FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE (SAL_PURCH=2)';

COMMENT ON COLUMN INST.COMM_ON_INV IS
    'علم احتساب العمولة على الفاتورة : 1=محتسب , 0=غير محتسب.';

COMMENT ON COLUMN INST.NOTCASH_SELL_SDAD_TYPE IS
    'كود نوع حركة السداد الآجل للبيع (غير نقدي).
     FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE WHERE SAL_PURCH=0 AND CASH_TRANS_TYPE=0
     يُملا تلقائيا في PAYED.SDAD_TRANS_TYPE عند انشاء سداد بيع آجل.';

COMMENT ON COLUMN INST.CASH_SELL_SDAD_TYPE IS
    'كود نوع حركة السداد النقدي للبيع.
     FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE WHERE SAL_PURCH=0 AND CASH_TRANS_TYPE=1
     يُملا تلقائيا في PAYED.SDAD_TRANS_TYPE عند انشاء سداد بيع نقدي.';

COMMENT ON COLUMN INST.NOTCASH_PURCH_SDAD_TYPE IS
    'كود نوع حركة السداد الآجل للشراء (غير نقدي).
     FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE WHERE SAL_PURCH=1 AND CASH_TRANS_TYPE=0';

COMMENT ON COLUMN INST.CASH_PURCH_SDAD_TYPE IS
    'كود نوع حركة السداد النقدي للشراء.
     FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE WHERE SAL_PURCH=1 AND CASH_TRANS_TYPE=1';

COMMENT ON COLUMN INST.INV_CAT_CHK IS
    'علم الزامية اختيار تصنيف الفاتورة في السداد :
     1 = الزامي اختيار INV_CAT في شاشة السداد
     0 = اختياري';


-- =============================================================================
-- End of Comments Script - Payment System (Page 30 + Page 46)
-- Tables : SAL_PURCH_TRANS_TYPE | PAYED | MAIN_INV_PAYED
--        | INV_CATEGORIES | DEALER_DATA | INST (additions)
-- =============================================================================


-- =============================================================================
-- SQL Examples for LLM Guidance
-- هذا القسم يُقرأ تلقائياً من schema_loader.get_sql_examples()
-- ويُحقن في system prompt — هو جزء من مصدر المعنى الوحيد.
-- لتعديل أي مثال: عدّل هنا فقط — التغيير يسري فوراً بدون restart.
-- الصيغة: كل مثال بين علامتي SQL_EXAMPLE_START و SQL_EXAMPLE_END
-- =============================================================================

-- @SQL_EXAMPLE_START
-- ══ مثال صحيح لاستعلام حركات الخزينة ══
-- سؤال: "حركات الخزينة على رفائع الجيمش"
-- SQL الصح:
-- SELECT h.TRANS_DATE, h.TRANS_CODE, h.TRANS_TYPE, h.NOTES,
--        d.AMOUNT, d.AMOUNT_BEFOR_TAX, d.TAX, c.CASH_NAME
-- FROM CASH_TRANS_HEAD h
-- JOIN CASH_TRANS_DETAIL d ON d.TRANS_ID = h.TRANS_ID
-- JOIN CASHES c ON c.CASH_ID = h.CASH_ID
-- WHERE c.CASH_NAME LIKE '%رفائع الجيمش%'
-- FETCH FIRST 200 ROWS ONLY
--
-- لاحظ: لا يوجد VOUCH_POSTED ولا TRANS_TYPE لأن المستخدم لم يطلبهما.
-- @SQL_EXAMPLE_END

-- @SQL_EXAMPLE_START
-- ══ مثال صحيح لاستعلام تفاصيل الفاتورة ══
-- سؤال: "تفاصيل الفاتورة رقم 5"
-- SQL الصح:
-- SELECT m.INVID, m.INVTYPE, i.ITEMNAME,
--        d.QTY, d.PRICE, d.ADD_VAL, d.SUB_VAL,
--        (d.QTY * d.PRICE) + d.ADD_VAL - d.SUB_VAL AS TOTAL_PRICE
-- FROM DETAIL_INV d
-- JOIN MAIN_INV m ON m.INV_KEY = d.INV_KEY
-- JOIN ITEMS i ON i.ITEMID = d.ITEMID
-- WHERE m.INVID = 5
-- FETCH FIRST 200 ROWS ONLY
--
-- سؤال: "فاتورة مبيعات رقم 5"
-- SQL الصح:
-- SELECT m.INVID, m.INVTYPE, i.ITEMNAME,
--        d.QTY, d.PRICE, d.ADD_VAL, d.SUB_VAL,
--        (d.QTY * d.PRICE) + d.ADD_VAL - d.SUB_VAL AS TOTAL_PRICE
-- FROM DETAIL_INV d
-- JOIN MAIN_INV m ON m.INV_KEY = d.INV_KEY
-- JOIN ITEMS i ON i.ITEMID = d.ITEMID
-- WHERE m.INVID = 5 AND m.INVTYPE = 0
-- FETCH FIRST 200 ROWS ONLY
--
-- لاحظ:
-- - WHERE على m.INVID وليس d.INV_KEY — INV_KEY رقم داخلي وليس رقم الفاتورة.
-- - لا INNER JOIN على UNITS أو ITEMGROUP — قد تكون NULL فتُحذف كل البنود.
-- - INVTYPE: إذا قال المستخدم "مبيعات" → AND m.INVTYPE = 0 | "مشتريات" أو "شراء" → AND m.INVTYPE = 1 | بدون ذكر نوع → بدون فلتر INVTYPE على الإطلاق.
-- @SQL_EXAMPLE_END

-- @SQL_EXAMPLE_START
-- ══ مثال صحيح لاستعلام تفاصيل حركة السداد ══
-- سؤال: "تفاصيل حركة السداد رقم 20"
-- SQL الصح:
-- SELECT p.PAYED_ID, p.PAYED_DATE, p.PAYED_AMOUNT, p.NOTES,
--        c.CUST_NAME, mp.SDAD, m.INVID
-- FROM PAYED p
-- JOIN CUST c ON c.CUSTID = p.CUST_ID AND c.CUST_TYPE = p.SAL_PURCH
-- LEFT JOIN MAIN_INV_PAYED mp ON mp.PAYED_ID = p.PAYED_ID AND mp.SDAD_TRANS_TYPE = p.SDAD_TRANS_TYPE
-- LEFT JOIN MAIN_INV m ON m.INV_KEY = mp.INV_KEY
-- WHERE p.PAYED_ID = 20
-- FETCH FIRST 200 ROWS ONLY
--
-- سؤال: "تفاصيل حركة السداد عميل رقم السداد 16"
-- SQL الصح:
-- SELECT p.PAYED_ID, p.PAYED_DATE, p.PAYED_AMOUNT, p.NOTES,
--        c.CUST_NAME, mp.SDAD, m.INVID
-- FROM PAYED p
-- JOIN CUST c ON c.CUSTID = p.CUST_ID AND c.CUST_TYPE = p.SAL_PURCH
-- LEFT JOIN MAIN_INV_PAYED mp ON mp.PAYED_ID = p.PAYED_ID AND mp.SDAD_TRANS_TYPE = p.SDAD_TRANS_TYPE
-- LEFT JOIN MAIN_INV m ON m.INV_KEY = mp.INV_KEY
-- WHERE p.PAYED_ID = 16 AND p.SAL_PURCH = 0
-- FETCH FIRST 200 ROWS ONLY
--
-- لاحظ:
-- - PAYED هو جدول سداد الديون — وليس CASH_TRANS_HEAD الذي للخزائن النقدية فقط.
-- - WHERE على p.PAYED_ID = الرقم — وليس TRANS_CODE في CASH_TRANS_HEAD.
-- - JOIN مع MAIN_INV_PAYED على (PAYED_ID + SDAD_TRANS_TYPE) معاً.
-- - SAL_PURCH: إذا قال المستخدم "عميل" → SAL_PURCH=0 | "مورد" → SAL_PURCH=1 | "مندوب" → SAL_PURCH=2 | بدون ذكر → بدون فلتر.
-- @SQL_EXAMPLE_END

-- @SQL_EXAMPLE_START
-- ══ مثال صحيح لاستعلام شجرة الحسابات مع DECODE ══
-- عند عرض نوع الحساب أو طبيعته استخدم DECODE هكذا:
--
-- SELECT
--   c.CHART_CODE,
--   c.CHART_NAME,
--   DECODE(c.CHART_TYPE,   0, 'ميزانية',     1, 'قائمة الدخل') AS CHART_TYPE_AR,
--   DECODE(c.CHART_NATURE, 0, 'حساب رئيسي', 1, 'حساب مساعد')  AS CHART_NATURE_AR,
--   c.PARENT_CHART_CODE
-- FROM CHARTS c
-- WHERE c.COMPANY_CODE = :company_code
-- ORDER BY c.CHART_CODE;
--
-- ملاحظات:
-- CHART_TYPE:   0 = ميزانية (أصول/خصوم),  1 = قائمة الدخل (إيرادات/مصروفات)
-- CHART_NATURE: 0 = حساب رئيسي (main),    1 = حساب مساعد (sub/leaf)
-- للشجرة الهرمية: START WITH PARENT_CHART_CODE IS NULL CONNECT BY PRIOR CHART_CODE = PARENT_CHART_CODE
-- @SQL_EXAMPLE_END

-- @SQL_EXAMPLE_START
-- ══ مثال صحيح لاستعلام رصيد المخزون (TRANSACTION_TOT) ══
-- دائماً استخدم TRANSACTION_TOT للأرصدة الحالية — أسرع وأصح من TRANSACTION:
--
-- SELECT
--   i.ITEMNAME,
--   i.ITEMID,
--   s.STORE_NAME,
--   t.QTY,
--   t.PRICE,
--   (t.QTY * t.PRICE) AS STOCK_VALUE
-- FROM TRANSACTION_TOT t
-- JOIN ITEMS i ON i.ITEMID = t.ITEMID
-- JOIN STORE s ON s.STORE_CODE = t.STORE_CODE
-- WHERE t.QTY <> 0
--   AND t.COMPANY_CODE = :company_code
-- ORDER BY t.QTY DESC;
--
-- ملاحظات:
-- WHERE QTY <> 0 : لاستبعاد الأصناف التي نفد رصيدها (مهم للأداء)
-- لا تستخدم TRANSACTION مباشرة للأرصدة — استخدم TRANSACTION_TOT دائماً
-- @SQL_EXAMPLE_END



-- =============================================================================
-- COMMENTS ADDED FROM NEW FILE
-- =============================================================================


-- ==================== CASH_INST ====================
COMMENT ON TABLE CASH_INST IS
    'اعدادات نظام الكاش والقيود المحاسبية - سجل واحد للنظام.';

COMMENT ON COLUMN CASH_INST.AUTO_SERIAL IS
    'علم الترقيم التلقائي للقيود عند الترحيل :
     1 = ترقيم تلقائي مركب (نوع+شهر+نوع_مستند+تسلسل)
     0 = المستخدم يدخل ارقام القيود يدويا (من/الى)';


-- ==================== ACC_INST ====================
COMMENT ON TABLE ACC_INST IS
    'اعدادات نظام المحاسبة العامة - سجل واحد للنظام.';

COMMENT ON COLUMN ACC_INST.VOUCHER_MONTH IS
    'الشهر المحاسبي الحالي المفتوح للترحيل.
     يُملا في VOUCHERS.VOUCHER_MONTH عند الترحيل.
     ⚠ الترحيل يتم دائما على الشهر المحاسبي الحالي المفتوح.';


-- ==================== ACC_USERS ====================
COMMENT ON TABLE ACC_USERS IS
    'مستخدمو النظام وإعداداتهم وصلاحياتهم.
     ⚠ مستثنى من SaaS conversion - لا tenant filter عليه.
     ⚠ الربط مع APP_SEC يكون على ROLE_ID لتحديد صلاحيات المستخدم.
     Pattern التحقق من الصلاحية في APEX :
       SELECT 1 FROM ACC_USERS u, APP_SEC rf
       WHERE rf.ROLE_ID = u.ROLE_ID
         AND u.USER_NAME = :APP_USER
         AND rf.FORM_ID  = [رقم_النموذج]
         AND rf.INSERT_PREV = 1';

COMMENT ON COLUMN ACC_USERS.USER_NAME IS
    'اسم المستخدم - المفتاح الاساسي | يطابق :APP_USER في APEX';

COMMENT ON COLUMN ACC_USERS.ROLE_ID IS
    'كود الدور الوظيفي - FK → APP_SEC.ROLE_ID
     يحدد صلاحيات المستخدم على النماذج';

COMMENT ON COLUMN ACC_USERS.USER_TYPE IS
    'نوع المستخدم - يحدد مستوى الوصول العام في النظام';

COMMENT ON COLUMN ACC_USERS.IS_ADMIN IS
    'علم المسؤول : 1=مسؤول النظام , 0=مستخدم عادي';

COMMENT ON COLUMN ACC_USERS.IS_DEVELOPER IS
    'علم المطور : 1=مطور له صلاحيات اضافية , 0=مستخدم عادي';

COMMENT ON COLUMN ACC_USERS.SHOW_TRANS_VAL IS
    'علم اظهار قيم الحركات المالية للمستخدم : 1=يظهر , 0=مخفي';

COMMENT ON COLUMN ACC_USERS.STORE_CODE IS
    'المخزن الافتراضي للمستخدم - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN ACC_USERS.INV_CAT IS
    'تصنيف الفاتورة الافتراضي للمستخدم - FK → INV_CATEGORIES.INV_CAT';

COMMENT ON COLUMN ACC_USERS.COST_CODE IS
    'مركز التكلفة الافتراضي - FK → COST_CENTERS.COST_CODE | الاسم في COST_CENTERS.COST_NAME';

COMMENT ON COLUMN ACC_USERS.DEALER_ID IS
    'كود الوكيل اذا كان المستخدم مرتبطا بوكيل - FK → DEALER_DATA.DEALER_ID';

COMMENT ON COLUMN ACC_USERS.USERID IS
    'رقم تعريفي رقمي للمستخدم - Surrogate Key';

COMMENT ON COLUMN ACC_USERS.SYSTEM_ENABLE IS
    'حالة تفعيل المستخدم : Y=مفعل , N=معطل';

COMMENT ON COLUMN ACC_USERS.REAL_NAME IS
    'الاسم الحقيقي للمستخدم باللغة العربية';

COMMENT ON COLUMN ACC_USERS.REAL_NAME_E IS
    'الاسم الحقيقي للمستخدم باللغة الانجليزية';

COMMENT ON COLUMN ACC_USERS.BRANCHID IS
    'حقل قديم (legacy) - استخدم BRANCH_ID بدلا منه';

COMMENT ON COLUMN ACC_USERS.BRANCH_ID IS
    'كود الفرع الافتراضي للمستخدم';

COMMENT ON COLUMN ACC_USERS.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';


-- ==================== APP_SEC ====================
COMMENT ON TABLE APP_SEC IS
    'صلاحيات كل دور وظيفي على كل نموذج في النظام.
     ⚠ مستثنى من SaaS conversion - لا tenant filter عليه.
     المفتاح الاساسي المركب : (ROLE_ID + FORM_ID).
     FORM_IDs المهمة في موديول المبيعات :
       43  = قوائم الاسعار          55  = فواتير البيع
       51  = حركات العملاء          59  = بيانات المناطق
       60  = بيانات المشرفين        61  = بيانات المندوبين
       64  = حركات المندوبين        106 = فواتير الشراء
       607 = انواع الفواتير         608 = لوائح الخصم والاضافة
       655 = حركات الموردين
     Pattern التحقق :
       NOT EXISTS (SELECT 1 FROM ACC_USERS u, APP_SEC rf
                   WHERE rf.ROLE_ID=u.ROLE_ID AND u.USER_NAME=:APP_USER
                     AND rf.FORM_ID=[رقم] AND rf.INSERT_PREV=1)
       → TRUE = المستخدم ليس لديه صلاحية → يعطل زر الاضافة';

COMMENT ON COLUMN APP_SEC.ROLE_ID IS
    'كود الدور الوظيفي - جزء من المفتاح الاساسي | FK → ACC_USERS.ROLE_ID';

COMMENT ON COLUMN APP_SEC.FORM_ID IS
    'كود النموذج - جزء من المفتاح الاساسي';

COMMENT ON COLUMN APP_SEC.ENTER_PREV IS
    'صلاحية الدخول : 1=مسموح , 0=محظور';

COMMENT ON COLUMN APP_SEC.INSERT_PREV IS
    'صلاحية الاضافة : 1=مسموح , 0=محظور';

COMMENT ON COLUMN APP_SEC.UPDATE_PREV IS
    'صلاحية التعديل : 1=مسموح , 0=محظور';

COMMENT ON COLUMN APP_SEC.DELETE_PREV IS
    'صلاحية الحذف : 1=مسموح , 0=محظور';

COMMENT ON COLUMN APP_SEC.QUERY_PREV IS
    'صلاحية الاستعلام والتقارير : 1=مسموح , 0=محظور';

COMMENT ON COLUMN APP_SEC.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';


-- ==================== CUST ====================
COMMENT ON COLUMN CUST.CUST_NAME_EN IS
    'اسم العميل او المورد باللغة الانجليزية';

COMMENT ON COLUMN CUST.TEL IS
    'رقم الهاتف الارضي';

COMMENT ON COLUMN CUST.ADDRESS IS
    'العنوان';

COMMENT ON COLUMN CUST.NATIONAL_ADDRESS IS
    'العنوان الوطني بصيغة هيئة البريد السعودية';

COMMENT ON COLUMN CUST.PRICE_LIST_ID_PERIOD IS
    'قائمة الاسعار المؤقتة - FK → PRICE_LIST.PRICE_LIST_ID';

COMMENT ON COLUMN CUST.CUST_PERCENT IS
    'نسبة الخصم الافتراضية للعميل %';

COMMENT ON COLUMN CUST.EFFECT_RULE_CODE IS
    'كود لائحة الخصم والاضافة الخاصة بالعميل - FK → INV_EFFECTS_RULES.EFFECT_RULE_CODE';

COMMENT ON COLUMN CUST.PARENT_CUST_CODE IS
    'كود العميل الاب في التسلسل الهرمي - FK → CUST.CUSTID';

COMMENT ON COLUMN CUST.DEALER_ID IS
    'كود الوكيل المرتبط بالعميل - FK → DEALER_DATA.DEALER_ID';

COMMENT ON COLUMN CUST.STORE_CODE IS
    'المخزن الافتراضي للعميل - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN CUST.COST_CODE IS
    'مركز التكلفة - FK → COST_CENTERS.COST_CODE | الاسم في COST_CENTERS.COST_NAME';

COMMENT ON COLUMN CUST.DESERVE_AFTER IS
    'ايام الاستحقاق (شروط الدفع) - عدد الايام بعد الفاتورة';

COMMENT ON COLUMN CUST.VAT_ID IS
    'الرقم الضريبي لضريبة القيمة المضافة (VAT ID).
     ⚠ يجلب من CUST مع فلتر CUSTID + CUST_TYPE معا';

COMMENT ON COLUMN CUST.RECEIVER_TYPE IS
    'نوع المستلم للفاتورة الالكترونية : B=شركة , P=فرد';

COMMENT ON COLUMN CUST.RECEIVER_COUNTRY IS
    'دولة المستلم - لاغراض الفاتورة الالكترونية';

COMMENT ON COLUMN CUST.RECEIVER_GOVERNATE IS
    'المنطقة / المحافظة - لاغراض الفاتورة الالكترونية';

COMMENT ON COLUMN CUST.RECEIVER_REGIONCITY IS
    'المدينة - لاغراض الفاتورة الالكترونية';

COMMENT ON COLUMN CUST.RECEIVER_STREET IS
    'الشارع - لاغراض الفاتورة الالكترونية';

COMMENT ON COLUMN CUST.RECEIVER_BUILDINGNUMBER IS
    'رقم المبنى - لاغراض الفاتورة الالكترونية';

COMMENT ON COLUMN CUST.BANK_CODE IS
    'البنك المرتبط بالعميل / المورد - FK → BANKS.BANK_CODE';


-- ==================== PRICE_LIST ====================
COMMENT ON COLUMN PRICE_LIST.PRICE_LIST_EN IS
    'اسم قائمة الاسعار باللغة الانجليزية';

COMMENT ON COLUMN PRICE_LIST.STORE_CODE IS
    'كود المخزن - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME
     NULL = قائمة عامة تسري على كل المخازن';


-- ==================== INV_EFFECTS_RULES ====================
COMMENT ON TABLE INV_EFFECTS_RULES IS
    'تعريف لوائح الخصم والاضافة الخاصة بالعملاء.
     المفتاح الاساسي : EFFECT_RULE_CODE.
     يُربط بالعميل في CUST.EFFECT_RULE_CODE.
     تفاصيل كل لائحة محفوظة في INV_EFFECTS.
     INV_EFFECTS_RULES (1) ───< INV_EFFECTS (M) on: EFFECT_RULE_CODE';

COMMENT ON COLUMN INV_EFFECTS_RULES.EFFECT_RULE_CODE IS
    'كود لائحة الخصم / الاضافة - المفتاح الاساسي.
     يُخزن في CUST.EFFECT_RULE_CODE لربط العميل باللائحة';

COMMENT ON COLUMN INV_EFFECTS_RULES.EFFECT_RULE_NM_AR IS
    'اسم اللائحة باللغة العربية (مثلا: لائحة عملاء الجملة)';

COMMENT ON COLUMN INV_EFFECTS_RULES.EFFECT_RULE_NM_EN IS
    'اسم اللائحة باللغة الانجليزية';


-- ==================== INV_EFFECTS ====================
COMMENT ON TABLE INV_EFFECTS IS
    'تفاصيل بنود الخصم والاضافة لكل لائحة.
     المفتاح الاساسي : ID (Surrogate Key).
     ⚠ يختلف عن MAIN_INV_EFFECTS :
       INV_EFFECTS      = تعريف اللوائح المسبق (Page 101 - الاعداد)
       MAIN_INV_EFFECTS = الخصومات الفعلية المطبقة على فاتورة محددة (Page 52/53)
     ⚠ لا يمكن حذف سطر استُخدم في فواتير مبيعات او مرتجعاتها';

COMMENT ON COLUMN INV_EFFECTS.EFFECT_NAME IS
    'اسم بند الخصم او الاضافة (مثلا: خصم كمية , ضريبة قيمة مضافة)';

COMMENT ON COLUMN INV_EFFECTS.ADD_DIS IS
    'اتجاه التاثير : -1=خصم (يطرح) , +1=اضافة (يضاف)';

COMMENT ON COLUMN INV_EFFECTS.PERCENT_VAL IS
    'طريقة الاحتساب :
     0 = نسبة %    (AMOUNT = نسبة مئوية من الاجمالي)
     1 = قيمة      (AMOUNT = مبلغ ثابت بالعملة)
     2 = نسبة+قيمة (يجمع الطريقتين)';

COMMENT ON COLUMN INV_EFFECTS.AMOUNT IS
    'القيمة او النسبة حسب PERCENT_VAL';

COMMENT ON COLUMN INV_EFFECTS.TOT_TOTDISC IS
    'اساس تطبيق التاثير :
     0 = على الاجمالي الكلي قبل اي خصومات
     1 = على الاجمالي بعد الخصم السابق
     ⚠ ترتيب البنود مهم عند TOT_TOTDISC=1';

COMMENT ON COLUMN INV_EFFECTS.CHART_CODE IS
    'كود الحساب المحاسبي - FK → CHARTS_ELEMENTS.CHART_CODE';


-- ==================== DOCUMENTS ====================
COMMENT ON TABLE DOCUMENTS IS
    'تعريف انواع المستندات المحاسبية لحركات المبيعات والمشتريات.
     المفتاح الاساسي : DOC_ID.
     يُستخدم في SAL_PURCH_TRANS_TYPE.DOC_ID و VOUCHERS.DOC_ID';

COMMENT ON COLUMN DOCUMENTS.DOC_ID IS
    'كود نوع المستند المحاسبي - المفتاح الاساسي';

COMMENT ON COLUMN DOCUMENTS.DOC_NAME IS
    'اسم نوع المستند (مثلا: قيد مبيعات , قيد مشتريات , قيد سداد)';


-- ==================== MAIN_INV_EFFECTS ====================
COMMENT ON TABLE MAIN_INV_EFFECTS IS
    'الخصومات والاضافات الفعلية على راس الفاتورة. كل صف = تاثير واحد.
     ⚠ JOIN مع MAIN_INV على INV_KEY.
     ⚠ فلتر ADD_DIS ضروري : -1=خصم , +1=اضافة.
     IDs الثابتة في النظام :
       1=خصم مكتسب , 2=ضريبة خصم 3% , 3=ضريبة قيمة مضافة , 5=مصاريف نقل
     لجلب اجمالي الخصومات : WHERE INV_KEY=x AND ADD_DIS=-1 → SUM(TOT_TOTDISC)';

COMMENT ON COLUMN MAIN_INV_EFFECTS.INV_KEY IS
    'مفتاح الربط مع الفاتورة - FK → MAIN_INV.INV_KEY.
     ⚠ استخدم INV_KEY دائما وليس INVID';

COMMENT ON COLUMN MAIN_INV_EFFECTS.ID IS
    'Surrogate PK للسجل.
     قيم ثابتة : 1=خصم مكتسب , 2=ضريبة خصم 3% , 3=ضريبة قيمة مضافة , 5=مصاريف نقل';

COMMENT ON COLUMN MAIN_INV_EFFECTS.EFFECT_NAME IS
    'اسم الخصم او الاضافة للعرض';

COMMENT ON COLUMN MAIN_INV_EFFECTS.ADD_DIS IS
    'اتجاه التاثير : -1=خصم (يطرح) , +1=اضافة (يضاف).
     ⚠ جزء اساسي من شرط WHERE - لا تحذفه';

COMMENT ON COLUMN MAIN_INV_EFFECTS.TOT_TOTDISC IS
    'قيمة الخصم او الاضافة بالعملة (دائما موجبة - الاتجاه في ADD_DIS)';

COMMENT ON COLUMN MAIN_INV_EFFECTS.PERCENT_VAL IS
    'نسبة الخصم او الاضافة %';

COMMENT ON COLUMN MAIN_INV_EFFECTS.VAL_AMOUNT IS
    'المبلغ الاساسي الذي طبقت عليه النسبة';

COMMENT ON COLUMN MAIN_INV_EFFECTS.COMPANY_CODE IS
    'كود الشركة - Tenant identifier (SaaS isolation)';


-- ==================== ORDERS ====================
COMMENT ON TABLE ORDERS IS
    'طلبات البيع وعروض الاسعار والحجوزات.
     المفتاح الاساسي : ORD_ID (Surrogate Key).
     ORD_TYPE يحدد نوع الطلب (طلب بيع / عرض سعر / حجز).
     ⚠ الجدول يرتبط بنفسه (Self-JOIN) في حالتين :
       LOAD_FROM    → الامر الاصلي المحمل منه - FK → ORDERS.ORD_ID
       QUOTATION_NO → عرض السعر المحول لامر  - FK → ORDERS.ORD_ID
     الربط بالفاتورة : MAIN_INV.ORD_NO → ORDERS.ORD_ID';

COMMENT ON COLUMN ORDERS.ORD_ID IS
    'Surrogate PK للطلب.
     يُخزن في MAIN_INV.ORD_NO للربط بالفاتورة المنشاة من الطلب';

COMMENT ON COLUMN ORDERS.ORD_NO IS
    'رقم الطلب المرئي للمستخدم - للعرض والبحث.
     ⚠ استخدم ORD_ID في الـ JOIN وليس ORD_NO';

COMMENT ON COLUMN ORDERS.ORD_TYPE IS
    'نوع الطلب (طلب بيع / عرض سعر / حجز) - يمرر كـ :P309_ORD_TYPE';

COMMENT ON COLUMN ORDERS.ORD_DATE IS
    'تاريخ الطلب';

COMMENT ON COLUMN ORDERS.DELIV_DATE IS
    'تاريخ التسليم المتوقع';

COMMENT ON COLUMN ORDERS.CUSTID IS
    'كود العميل صاحب الطلب - FK → CUST.CUSTID (مع CUST_TYPE=0)
     الاسم في CUST.CUST_NAME';

COMMENT ON COLUMN ORDERS.PRICES IS
    'كود قائمة الاسعار - FK → PRICE_LIST.PRICE_LIST_ID
     الاسم في PRICE_LIST.PRICE_LIST_AR';

COMMENT ON COLUMN ORDERS.APPROVED_CHK IS
    'حالة الموافقة : NULL=قيد المراجعة , 1=موافقة , 2=رفض';

COMMENT ON COLUMN ORDERS.LOAD_FROM IS
    'ORD_ID الامر الاصلي المحمل منه - FK → ORDERS.ORD_ID';

COMMENT ON COLUMN ORDERS.QUOTATION_NO IS
    'ORD_ID عرض السعر المرتبط - FK → ORDERS.ORD_ID';

COMMENT ON COLUMN ORDERS.EXPIRE_DATE IS
    'تاريخ انتهاء صلاحية عرض السعر';


-- ==================== VOUCHERS_SAL_PURCH ====================
COMMENT ON TABLE vouchers_SAL_purch IS
    'قيود محاسبية مؤقتة للمبيعات والمشتريات قبل الترحيل.
     كل صف = راس قيد مؤقت.
     ⚠ دورة حياة القيد :
       1. ينشا تلقائيا عند حفظ الفاتورة / السداد
       2. يُرحَّل من Page 225 → ينقل الى VOUCHERS + VOUCHERS_DET
       3. بعد الترحيل : posted_voucher_code يُملا برقم القيد في VOUCHERS
     ⚠ الربط مع SAL_PURCH_TRANS_TYPE لمعرفة SAL_PURCH :
         JOIN SAL_PURCH_TRANS_TYPE spt ON vsp.INV_TRANS_TYPE=spt.TRANS_CODE
         WHERE spt.SAL_PURCH=:p_sal_purch';

COMMENT ON COLUMN vouchers_SAL_purch.VOUCHER_CODE IS
    'كود القيد المؤقت - المفتاح الاساسي.
     يُخزن في VOUCHERS.POST_FROM_VOUCH بعد الترحيل';

COMMENT ON COLUMN vouchers_SAL_purch.VOUCHER_DATE IS
    'تاريخ القيد - يستخدم كفلتر في عملية الترحيل (Page 225)';

COMMENT ON COLUMN vouchers_SAL_purch.INV_TRANS_TYPE IS
    'نوع حركة الفاتورة - FK → SAL_PURCH_TRANS_TYPE.TRANS_CODE.
     يحدد SAL_PURCH عبر الـ JOIN مع SAL_PURCH_TRANS_TYPE';

COMMENT ON COLUMN vouchers_SAL_purch.posted_voucher_code IS
    'كود القيد في VOUCHERS بعد الترحيل - FK → VOUCHERS.VOUCHER_CODE.
     NULL = لم يُرحَّل بعد | NOT NULL = تم الترحيل';


-- ==================== VOUCHERS_SAL_PURCH_TOT ====================
COMMENT ON TABLE vouchers_SAL_purch_tot IS
    'View / جدول اجمالي للقيود المؤقتة - مصدر الترحيل في Page 225.
     يحتوي على VOUCHER_CODE يربطه بـ VOUCHERS_det_SAL_purch_tot للتفاصيل.
     ⚠ مجموع AMOUNT في القيد الواحد يجب = صفر قبل الترحيل.';


-- ==================== VOUCHERS ====================
COMMENT ON COLUMN VOUCHERS.DOC_ID IS
    'نوع المستند المحاسبي - FK → DOCUMENTS.DOC_ID | الاسم في DOCUMENTS.DOC_NAME';

COMMENT ON COLUMN VOUCHERS.POST_FROM_VOUCH IS
    'كود القيد المؤقت المصدر - FK → vouchers_SAL_purch.VOUCHER_CODE.
     NULL=قيد يدوي | NOT NULL=مرحَّل من المبيعات/المشتريات.
     يُستخدم في الغاء الترحيل';

COMMENT ON COLUMN VOUCHERS.REGSITER IS
    '⚠ خطا املائي (REGSITER بدلا من REGISTER).
     حالة تسجيل القيد : 1=مسجل نهائيا , 0=مسودة';



-- ==================== ACC_USERS_STORES ====================
COMMENT ON TABLE ACC_USERS_STORES IS
    'صلاحيات المستخدمين على المخازن - يحدد نطاق المخازن المسموح للمستخدم الوصول إليها';

COMMENT ON COLUMN ACC_USERS_STORES.USER_NAME IS
    'اسم المستخدم - FK → ACC_USERS.USER_NAME';

COMMENT ON COLUMN ACC_USERS_STORES.FROM_STORE_CODE IS
    'كود المخزن الأول في النطاق المسموح به - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN ACC_USERS_STORES.TO_STORE_CODE IS
    'كود المخزن الأخير في النطاق المسموح به - FK → STORE.STORE_CODE | الاسم في STORE.STORE_NAME';

COMMENT ON COLUMN ACC_USERS_STORES.COMPANY_CODE IS
    'كود الشركة - FK → COMPANIES.COMPANY_CODE';

COMMENT ON COLUMN ACC_USERS_STORES.FISCAL_YEAR IS
    'السنة المالية';

COMMENT ON COLUMN ACC_USERS_STORES.BRANCH_ID IS
    'كود الفرع - FK → BRANCHES.BRANCH_ID | DEFAULT 0';

-- ============================================================
--  Tables / views added by the development plan (W2..W29), merged 7 Nov 2026 from chatbot_comments_new_modules.sql
-- ============================================================
COMMENT ON TABLE CHARTS_PARENT_FIX_LOG IS 'سجل ربط الحسابات اليتيمة بأبيها / log of orphan accounts re-parented. للتراجع: UPDATE CHARTS SET PARENT_CHART_CODE=NULL للحسابات في السجل';
COMMENT ON COLUMN CHARTS_PARENT_FIX_LOG.LOG_ID IS 'Log Id (LOG_ID)';
COMMENT ON COLUMN CHARTS_PARENT_FIX_LOG.CHART_CODE IS 'كود الحساب (CHART_CODE)';
COMMENT ON COLUMN CHARTS_PARENT_FIX_LOG.OLD_PARENT IS 'Old Parent (OLD_PARENT)';
COMMENT ON COLUMN CHARTS_PARENT_FIX_LOG.NEW_PARENT IS 'New Parent (NEW_PARENT)';
COMMENT ON COLUMN CHARTS_PARENT_FIX_LOG.FIXED_DATE IS 'Fixed Date (FIXED_DATE)';
COMMENT ON COLUMN CHARTS_PARENT_FIX_LOG.UNDONE_DATE IS 'Undone Date (UNDONE_DATE)';
COMMENT ON TABLE INS_RULE IS 'قواعد التأمينات الاجتماعية حسب البلد والفترة / social insurance rules per country and period. COUNTRY_CODE: EG مصر / SA السعودية. CATEGORY: MAIN أساسي، NON_NATIONAL غير مواطن. EMP_PCT نسبة الموظف و EMPLOYER_PCT نسبة صاحب العمل. MIN_WAGE/MAX_WAGE حد أدنى وأقصى للأجر الخاضع. يُقرأ بدالة HR_CALC_PKG حسب بلد الشركة الأساسية (COMPANY_COUNTRY.IS_MAIN)';
COMMENT ON COLUMN INS_RULE.RULE_ID IS 'رقم القاعدة (RULE_ID)';
COMMENT ON COLUMN INS_RULE.RULE_NAME IS 'اسم القاعدة (RULE_NAME)';
COMMENT ON COLUMN INS_RULE.EMP_PCT IS 'حصة الموظف % (EMP_PCT)';
COMMENT ON COLUMN INS_RULE.EMPLOYER_PCT IS 'حصة صاحب العمل % (EMPLOYER_PCT)';
COMMENT ON COLUMN INS_RULE.MIN_WAGE IS 'أدنى أجر (MIN_WAGE)';
COMMENT ON COLUMN INS_RULE.MAX_WAGE IS 'أقصى أجر خاضع (MAX_WAGE)';
COMMENT ON COLUMN INS_RULE.FROM_DATE IS 'من تاريخ (FROM_DATE)';
COMMENT ON COLUMN INS_RULE.TO_DATE IS 'إلى تاريخ (TO_DATE)';
COMMENT ON COLUMN INS_RULE.COUNTRY_CODE IS 'البلد (EG مصر / SA السعودية) (COUNTRY_CODE)';
COMMENT ON COLUMN INS_RULE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN INS_RULE.CATEGORY IS 'الفئة (MAIN أساسي / NON_NATIONAL غير مواطن) (CATEGORY)';
COMMENT ON TABLE TAX_BRACKET IS 'شرائح ضريبة الدخل السنوية حسب البلد / income tax brackets (annual) per country. FROM_AMOUNT/TO_AMOUNT شريحة سنوية، PCT النسبة، TO_AMOUNT فاضي = بلا حد أعلى. COUNTRY_CODE: EG/SA';
COMMENT ON COLUMN TAX_BRACKET.BRACKET_ID IS 'Bracket Id (BRACKET_ID)';
COMMENT ON COLUMN TAX_BRACKET.FROM_AMOUNT IS 'من (سنوي) (FROM_AMOUNT)';
COMMENT ON COLUMN TAX_BRACKET.TO_AMOUNT IS 'إلى (سنوي) (TO_AMOUNT)';
COMMENT ON COLUMN TAX_BRACKET.PCT IS 'النسبة % (PCT)';
COMMENT ON COLUMN TAX_BRACKET.FROM_DATE IS 'من تاريخ (FROM_DATE)';
COMMENT ON COLUMN TAX_BRACKET.TO_DATE IS 'إلى تاريخ (TO_DATE)';
COMMENT ON COLUMN TAX_BRACKET.COUNTRY_CODE IS 'البلد (EG مصر / SA السعودية) (COUNTRY_CODE)';
COMMENT ON COLUMN TAX_BRACKET.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE HR_TAX_PARAM IS 'إعفاء ضريبة الدخل السنوي لكل بلد / annual income tax exemption per country. صف لكل COUNTRY_CODE';
COMMENT ON COLUMN HR_TAX_PARAM.PARAM_ID IS 'م (PARAM_ID)';
COMMENT ON COLUMN HR_TAX_PARAM.ANNUAL_EXEMPTION IS 'الإعفاء السنوي (ANNUAL_EXEMPTION)';
COMMENT ON COLUMN HR_TAX_PARAM.COUNTRY_CODE IS 'البلد (EG مصر / SA السعودية) (COUNTRY_CODE)';
COMMENT ON COLUMN HR_TAX_PARAM.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE HR_VACANCY IS 'الوظائف الشاغرة (التوظيف) / job vacancies (recruitment). STATUS: OPEN مفتوحة، ON_HOLD معلّقة، FILLED اتشغلت، CLOSED مقفولة. JOIN: HR_CANDIDATE.VACANCY_ID = HR_VACANCY.VACANCY_ID';
COMMENT ON COLUMN HR_VACANCY.VACANCY_ID IS 'رقم الوظيفة (VACANCY_ID)';
COMMENT ON COLUMN HR_VACANCY.TITLE IS 'العنوان (TITLE)';
COMMENT ON COLUMN HR_VACANCY.DEPT_CODE IS 'القسم (DEPT_CODE)';
COMMENT ON COLUMN HR_VACANCY.POSITIONS IS 'عدد الوظائف (POSITIONS)';
COMMENT ON COLUMN HR_VACANCY.OPEN_DATE IS 'تاريخ الفتح (OPEN_DATE)';
COMMENT ON COLUMN HR_VACANCY.CLOSE_DATE IS 'تاريخ الإغلاق (CLOSE_DATE)';
COMMENT ON COLUMN HR_VACANCY.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، ON_HOLD=متوقف، FILLED=تم الشغل، CLOSED=مغلقة';
COMMENT ON COLUMN HR_VACANCY.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE HR_CANDIDATE IS 'المتقدمون للوظائف ومرحلة كل واحد / job candidates and their stage. STAGE: APPLIED تقدّم، SCREEN فرز، INTERVIEW مقابلة، OFFER عرض، HIRED تعيّن، REJECTED مرفوض';
COMMENT ON COLUMN HR_CANDIDATE.CANDIDATE_ID IS 'رقم المتقدم (CANDIDATE_ID)';
COMMENT ON COLUMN HR_CANDIDATE.VACANCY_ID IS 'رقم الوظيفة (VACANCY_ID) - FK → HR_VACANCY.VACANCY_ID';
COMMENT ON COLUMN HR_CANDIDATE.FULL_NAME IS 'الاسم (FULL_NAME)';
COMMENT ON COLUMN HR_CANDIDATE.MOBILE IS 'الموبايل (MOBILE)';
COMMENT ON COLUMN HR_CANDIDATE.EMAIL IS 'البريد (EMAIL)';
COMMENT ON COLUMN HR_CANDIDATE.SOURCE IS 'المصدر (SOURCE)';
COMMENT ON COLUMN HR_CANDIDATE.STAGE IS 'المرحلة (STAGE) - القيم: APPLIED=تقدّم، SCREEN=فرز، INTERVIEW=مقابلة، OFFER=عرض، HIRED=HIRED، REJECTED=مرفوض';
COMMENT ON COLUMN HR_CANDIDATE.EXPECTED_SALARY IS 'الراتب المتوقع (EXPECTED_SALARY)';
COMMENT ON COLUMN HR_CANDIDATE.APPLIED_DATE IS 'تاريخ التقديم (APPLIED_DATE)';
COMMENT ON COLUMN HR_CANDIDATE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE HR_INTERVIEW IS 'مقابلات المتقدمين ودرجاتها / candidate interviews and scores. JOIN: CANDIDATE_ID';
COMMENT ON COLUMN HR_INTERVIEW.INTERVIEW_ID IS 'م (INTERVIEW_ID)';
COMMENT ON COLUMN HR_INTERVIEW.CANDIDATE_ID IS 'رقم المتقدم (CANDIDATE_ID) - FK → HR_CANDIDATE.CANDIDATE_ID';
COMMENT ON COLUMN HR_INTERVIEW.INTERVIEW_DATE IS 'تاريخ المقابلة (INTERVIEW_DATE)';
COMMENT ON COLUMN HR_INTERVIEW.INTERVIEWER IS 'المقابل (INTERVIEWER)';
COMMENT ON COLUMN HR_INTERVIEW.SCORE IS 'الدرجة (SCORE)';
COMMENT ON COLUMN HR_INTERVIEW.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE HR_GOAL IS 'أهداف الموظفين وأوزانها ونسبة تحقيقها / employee goals, weights and achievement. EMP_ID كود الموظف. نسبة التحقيق = متوسط موزون بالوزن';
COMMENT ON COLUMN HR_GOAL.GOAL_ID IS 'م (GOAL_ID)';
COMMENT ON COLUMN HR_GOAL.EMP_ID IS 'كود الموظف (EMP_ID)';
COMMENT ON COLUMN HR_GOAL.PERIOD IS 'الفترة (PERIOD)';
COMMENT ON COLUMN HR_GOAL.TITLE IS 'العنوان (TITLE)';
COMMENT ON COLUMN HR_GOAL.WEIGHT IS 'الوزن (WEIGHT)';
COMMENT ON COLUMN HR_GOAL.TARGET IS 'المستهدف (TARGET)';
COMMENT ON COLUMN HR_GOAL.ACTUAL IS 'المحقق (ACTUAL)';
COMMENT ON COLUMN HR_GOAL.UNIT IS 'الوحدة (UNIT)';
COMMENT ON TABLE HR_APPRAISAL IS 'تقييمات أداء الموظفين / employee performance appraisals. EMP_ID كود الموظف';
COMMENT ON COLUMN HR_APPRAISAL.APPRAISAL_ID IS 'م (APPRAISAL_ID)';
COMMENT ON COLUMN HR_APPRAISAL.EMP_ID IS 'كود الموظف (EMP_ID)';
COMMENT ON COLUMN HR_APPRAISAL.PERIOD IS 'الفترة (PERIOD)';
COMMENT ON COLUMN HR_APPRAISAL.REVIEWER IS 'Reviewer (REVIEWER)';
COMMENT ON COLUMN HR_APPRAISAL.RATING IS 'التقييم (1-5) (RATING)';
COMMENT ON COLUMN HR_APPRAISAL.COMMENTS IS 'تعليقات (COMMENTS)';
COMMENT ON COLUMN HR_APPRAISAL.APPRAISAL_DATE IS 'تاريخ التقييم (APPRAISAL_DATE)';
COMMENT ON TABLE HR_COURSE IS 'الدورات التدريبية / training courses. JOIN: HR_COURSE_ATT.COURSE_ID';
COMMENT ON COLUMN HR_COURSE.COURSE_ID IS 'رقم الدورة (COURSE_ID)';
COMMENT ON COLUMN HR_COURSE.TITLE IS 'العنوان (TITLE)';
COMMENT ON COLUMN HR_COURSE.PROVIDER IS 'الجهة (PROVIDER)';
COMMENT ON COLUMN HR_COURSE.HOURS IS 'الساعات (HOURS)';
COMMENT ON COLUMN HR_COURSE.COST IS 'التكلفة (COST)';
COMMENT ON COLUMN HR_COURSE.START_DATE IS 'بداية العقد (START_DATE)';
COMMENT ON COLUMN HR_COURSE.END_DATE IS 'ينتهي في (END_DATE)';
COMMENT ON TABLE HR_COURSE_ATT IS 'حضور الموظفين للدورات وتكلفته / course attendance and cost. EMP_ID + COURSE_ID';
COMMENT ON COLUMN HR_COURSE_ATT.ATT_ID IS 'م (ATT_ID)';
COMMENT ON COLUMN HR_COURSE_ATT.COURSE_ID IS 'رقم الدورة (COURSE_ID) - FK → HR_COURSE.COURSE_ID';
COMMENT ON COLUMN HR_COURSE_ATT.EMP_ID IS 'كود الموظف (EMP_ID)';
COMMENT ON COLUMN HR_COURSE_ATT.STATUS IS 'الحالة (STATUS) - القيم: ENROLLED=ENROLLED، ATTENDED=ATTENDED، ABSENT=ABSENT، COMPLETED=أنهى';
COMMENT ON COLUMN HR_COURSE_ATT.SCORE IS 'الدرجة (SCORE)';
COMMENT ON TABLE MFG_MACHINE IS 'ماكينات التصنيع وساعات تشغيلها اليومية / manufacturing machines and daily hours. HOURS_PER_DAY ساعات اليوم. الطاقة الأسبوعية = HOURS_PER_DAY × 7';
COMMENT ON COLUMN MFG_MACHINE.MACHINE_ID IS 'الماكينة (MACHINE_ID)';
COMMENT ON COLUMN MFG_MACHINE.MACHINE_NAME IS 'اسم الماكينة (MACHINE_NAME)';
COMMENT ON COLUMN MFG_MACHINE.HOURS_PER_DAY IS 'ساعات اليوم (HOURS_PER_DAY)';
COMMENT ON COLUMN MFG_MACHINE.ACTIVE_FLAG IS 'نشط (Y/N) (ACTIVE_FLAG)';
COMMENT ON COLUMN MFG_MACHINE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE MFG_SCHEDULE IS 'جدول تشغيل الماكينات (مهام بتاريخ بداية ونهاية) / machine production schedule. مهمتان متداخلتان على نفس الماكينة تظهران في V_MFG_OVERLAP';
COMMENT ON COLUMN MFG_SCHEDULE.SCHED_ID IS 'م (SCHED_ID)';
COMMENT ON COLUMN MFG_SCHEDULE.MACHINE_ID IS 'الماكينة (MACHINE_ID) - FK → MFG_MACHINE.MACHINE_ID';
COMMENT ON COLUMN MFG_SCHEDULE.PRODUCT_ITEMID IS 'كود المنتج (PRODUCT_ITEMID)';
COMMENT ON COLUMN MFG_SCHEDULE.ORDER_ID IS 'رقم أمر البيع (ORDER_ID)';
COMMENT ON COLUMN MFG_SCHEDULE.PLANNED_START IS 'بداية مخططة (PLANNED_START)';
COMMENT ON COLUMN MFG_SCHEDULE.PLANNED_END IS 'نهاية مخططة (PLANNED_END)';
COMMENT ON COLUMN MFG_SCHEDULE.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN MFG_SCHEDULE.STATUS IS 'الحالة (STATUS) - القيم: PLANNED=مخطط، RUNNING=قيد التشغيل، DONE=منتهي، CANCELLED=ملغي';
COMMENT ON COLUMN MFG_SCHEDULE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE QC_PLAN IS 'خطة فحص الجودة لكل صنف (حدود دنيا وعليا) / quality inspection plan per item. MIN_VALUE/MAX_VALUE حدود القياس. JOIN: ITEMID = ITEMS.ITEMID';
COMMENT ON COLUMN QC_PLAN.PLAN_ID IS 'م (PLAN_ID)';
COMMENT ON COLUMN QC_PLAN.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN QC_PLAN.CHECK_NAME IS 'الفحص (CHECK_NAME)';
COMMENT ON COLUMN QC_PLAN.MIN_VALUE IS 'الحد الأدنى (MIN_VALUE)';
COMMENT ON COLUMN QC_PLAN.MAX_VALUE IS 'الحد الأقصى (MAX_VALUE)';
COMMENT ON COLUMN QC_PLAN.UNIT_TEXT IS 'الوحدة (UNIT_TEXT)';
COMMENT ON TABLE QC_INSPECTION IS 'فحوصات الجودة (دفعة صنف) ونتيجتها / quality inspections. RESULT: PENDING منتظر، PASS نجح، FAIL فشل (ويفتح QC_NCR تلقائي)';
COMMENT ON COLUMN QC_INSPECTION.INSP_ID IS 'رقم الفحص (INSP_ID)';
COMMENT ON COLUMN QC_INSPECTION.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN QC_INSPECTION.BATCH_NO IS 'التشغيلة (BATCH_NO)';
COMMENT ON COLUMN QC_INSPECTION.INSP_DATE IS 'تاريخ الفحص (INSP_DATE)';
COMMENT ON COLUMN QC_INSPECTION.INSPECTOR IS 'الفاحص (INSPECTOR)';
COMMENT ON COLUMN QC_INSPECTION.RESULT IS 'النتيجة (RESULT) - القيم: PENDING=قيد الفحص، PASS=ناجح، FAIL=راسب';
COMMENT ON COLUMN QC_INSPECTION.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE QC_RESULT IS 'قياسات كل فحص مقابل خطة الفحص / inspection measurements. JOIN: INSP_ID, PLAN_ID';
COMMENT ON COLUMN QC_RESULT.RES_ID IS 'م (RES_ID)';
COMMENT ON COLUMN QC_RESULT.INSP_ID IS 'رقم الفحص (INSP_ID) - FK → QC_INSPECTION.INSP_ID';
COMMENT ON COLUMN QC_RESULT.PLAN_ID IS 'م (PLAN_ID)';
COMMENT ON COLUMN QC_RESULT.MEASURED IS 'القيمة المقاسة (MEASURED)';
COMMENT ON COLUMN QC_RESULT.PASSED IS 'ناجح (PASSED)';
COMMENT ON TABLE QC_NCR IS 'تقارير عدم المطابقة الناتجة عن فحص فاشل / non-conformance reports. بتتعمل تلقائي من QC_PKG.RECORD_RESULT';
COMMENT ON COLUMN QC_NCR.NCR_ID IS 'رقم عدم المطابقة (NCR_ID)';
COMMENT ON COLUMN QC_NCR.INSP_ID IS 'رقم الفحص (INSP_ID) - FK → QC_INSPECTION.INSP_ID';
COMMENT ON COLUMN QC_NCR.DESCRIPTION IS 'البيان (DESCRIPTION)';
COMMENT ON COLUMN QC_NCR.ACTION_TAKEN IS 'الإجراء (ACTION_TAKEN)';
COMMENT ON COLUMN QC_NCR.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، CLOSED=مغلقة';
COMMENT ON COLUMN QC_NCR.OPENED_DATE IS 'تاريخ الفتح (OPENED_DATE)';
COMMENT ON COLUMN QC_NCR.CLOSED_DATE IS 'تاريخ الإغلاق (CLOSED_DATE)';
COMMENT ON TABLE MFG_STD_COST IS 'التكلفة المعيارية للصنف (خامات + عمالة + مصروفات) / standard cost per item. تُقارن بالتكلفة الفعلية في V_MFG_VARIANCE';
COMMENT ON COLUMN MFG_STD_COST.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN MFG_STD_COST.STD_MATERIAL IS 'مواد معيارية (STD_MATERIAL)';
COMMENT ON COLUMN MFG_STD_COST.STD_LABOUR IS 'عمالة معيارية (STD_LABOUR)';
COMMENT ON COLUMN MFG_STD_COST.STD_OVERHEAD IS 'غير مباشرة معيارية (STD_OVERHEAD)';
COMMENT ON COLUMN MFG_STD_COST.FROM_DATE IS 'من تاريخ (FROM_DATE)';
COMMENT ON TABLE MNT_PLAN IS 'خطط الصيانة الدورية للأصول (كل كام يوم) / preventive maintenance plans. EVERY_DAYS الدورية، LAST_DONE آخر تنفيذ. JOIN: ASSETS_ID = FIXED_ASSETS.ASSETS_ID';
COMMENT ON COLUMN MNT_PLAN.PLAN_ID IS 'م (PLAN_ID)';
COMMENT ON COLUMN MNT_PLAN.ASSETS_ID IS 'كود الأصل (ASSETS_ID)';
COMMENT ON COLUMN MNT_PLAN.TASK IS 'المهمة (TASK)';
COMMENT ON COLUMN MNT_PLAN.EVERY_DAYS IS 'كل (يوم) (EVERY_DAYS)';
COMMENT ON COLUMN MNT_PLAN.LAST_DONE IS 'آخر تنفيذ (LAST_DONE)';
COMMENT ON COLUMN MNT_PLAN.ACTIVE_FLAG IS 'نشط (Y/N) (ACTIVE_FLAG)';
COMMENT ON TABLE MNT_WO IS 'أوامر الصيانة / maintenance work orders. بتتولد من MNT_PKG.GENERATE_DUE أو بالإدخال';
COMMENT ON COLUMN MNT_WO.WO_ID IS 'رقم الأمر (WO_ID)';
COMMENT ON COLUMN MNT_WO.ASSETS_ID IS 'كود الأصل (ASSETS_ID)';
COMMENT ON COLUMN MNT_WO.PLAN_ID IS 'م (PLAN_ID)';
COMMENT ON COLUMN MNT_WO.WO_TYPE IS 'النوع (WO_TYPE) - القيم: PREV=وقائية، CORR=إصلاح';
COMMENT ON COLUMN MNT_WO.DESCRIPTION IS 'البيان (DESCRIPTION)';
COMMENT ON COLUMN MNT_WO.OPENED_DATE IS 'تاريخ الفتح (OPENED_DATE)';
COMMENT ON COLUMN MNT_WO.CLOSED_DATE IS 'تاريخ الإغلاق (CLOSED_DATE)';
COMMENT ON COLUMN MNT_WO.LABOUR_COST IS 'تكلفة العمالة (LABOUR_COST)';
COMMENT ON COLUMN MNT_WO.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، DONE=منتهي، CANCELLED=ملغي';
COMMENT ON TABLE MNT_WO_PART IS 'قطع الغيار المستخدمة في أمر الصيانة / spare parts used on a work order. تكلفة القطع = QTY × UNIT_COST';
COMMENT ON COLUMN MNT_WO_PART.PART_ID IS 'م (PART_ID)';
COMMENT ON COLUMN MNT_WO_PART.WO_ID IS 'رقم الأمر (WO_ID) - FK → MNT_WO.WO_ID';
COMMENT ON COLUMN MNT_WO_PART.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN MNT_WO_PART.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN MNT_WO_PART.UNIT_COST IS 'تكلفة الوحدة (UNIT_COST)';
COMMENT ON TABLE AST_COUNT IS 'جرد الأصول الثابتة بالباركود / fixed asset stocktake. JOIN: AST_COUNT_LINE.COUNT_ID';
COMMENT ON COLUMN AST_COUNT.COUNT_ID IS 'رقم الجرد (COUNT_ID)';
COMMENT ON COLUMN AST_COUNT.COUNT_DATE IS 'تاريخ الجرد (COUNT_DATE)';
COMMENT ON COLUMN AST_COUNT.LOC_ID IS 'الموقع (LOC_ID)';
COMMENT ON COLUMN AST_COUNT.COUNTED_BY IS 'القائم بالجرد (COUNTED_BY)';
COMMENT ON COLUMN AST_COUNT.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، CLOSED=مغلقة';
COMMENT ON TABLE AST_COUNT_LINE IS 'أسطر الجرد (باركود كل أصل اتمسح) / stocktake lines. BARCODE = كود الأصل. غير موجود في السجل يظهر "كود غير معروف"';
COMMENT ON COLUMN AST_COUNT_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN AST_COUNT_LINE.COUNT_ID IS 'رقم الجرد (COUNT_ID) - FK → AST_COUNT.COUNT_ID';
COMMENT ON COLUMN AST_COUNT_LINE.BARCODE IS 'الباركود (BARCODE)';
COMMENT ON COLUMN AST_COUNT_LINE.FOUND_LOC_ID IS 'مكان الجرد (FOUND_LOC_ID)';
COMMENT ON COLUMN AST_COUNT_LINE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE SYS_SETTING IS 'إعدادات النظام والحدود التشغيلية القابلة للتعديل من شاشة 591 / editable system settings and operating thresholds. VALUE_NUM القيمة الحالية، DEFAULT_NUM الأصلية. تُقرأ بدالة GET_SETTING_NUM(key, default). مفاتيح مهمة: DAILY_JOBS_ON الشغل اليومي، AUTO_POST_ON الترحيل التلقائي، PO_REQUIRE_APPROVAL، FLT_ALERT_DAYS. ⚠ الأصل في المفاتيح الخطرة 0 (مقفول)';
COMMENT ON COLUMN SYS_SETTING.SETTING_KEY IS 'كود الإعداد (SETTING_KEY)';
COMMENT ON COLUMN SYS_SETTING.SETTING_NAME_AR IS 'الإعداد (SETTING_NAME_AR)';
COMMENT ON COLUMN SYS_SETTING.GROUP_NAME IS 'اسم حساب المجموعة (GROUP_NAME)';
COMMENT ON COLUMN SYS_SETTING.VALUE_NUM IS 'القيمة الحالية (VALUE_NUM)';
COMMENT ON COLUMN SYS_SETTING.DEFAULT_NUM IS 'القيمة الأصلية (DEFAULT_NUM)';
COMMENT ON COLUMN SYS_SETTING.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE SAL_QUOTE IS 'عروض أسعار العملاء / customer quotations. STATUS: DRAFT مسودة، SENT مُرسل، CONVERTED تحوّل لأمر بيع، REJECTED مرفوض، EXPIRED منتهي. CUST_ID = CUST.CUSTID (عميل CUST_TYPE=0). الإجمالي في V_SAL_QUOTE_TOTAL';
COMMENT ON COLUMN SAL_QUOTE.QUOTE_ID IS 'رقم عرض السعر (QUOTE_ID)';
COMMENT ON COLUMN SAL_QUOTE.QUOTE_DATE IS 'تاريخ العرض (QUOTE_DATE)';
COMMENT ON COLUMN SAL_QUOTE.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN SAL_QUOTE.VALID_UNTIL IS 'ساري حتى (VALID_UNTIL)';
COMMENT ON COLUMN SAL_QUOTE.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، SENT=مُرسل، CONVERTED=تحوّل لأمر بيع، REJECTED=مرفوض، EXPIRED=منتهي';
COMMENT ON COLUMN SAL_QUOTE.SALES_USER IS 'مندوب البيع (SALES_USER)';
COMMENT ON COLUMN SAL_QUOTE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE SAL_QUOTE_LINE IS 'أصناف عرض السعر / quotation lines. إجمالي البند = QTY × PRICE × (1 − DISCOUNT_PCT/100)';
COMMENT ON COLUMN SAL_QUOTE_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN SAL_QUOTE_LINE.QUOTE_ID IS 'رقم عرض السعر (QUOTE_ID) - FK → SAL_QUOTE.QUOTE_ID';
COMMENT ON COLUMN SAL_QUOTE_LINE.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN SAL_QUOTE_LINE.UNIT_ID IS 'الوحدة (UNIT_ID)';
COMMENT ON COLUMN SAL_QUOTE_LINE.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN SAL_QUOTE_LINE.PRICE IS 'السعر (PRICE)';
COMMENT ON COLUMN SAL_QUOTE_LINE.DISCOUNT_PCT IS 'الخصم % (DISCOUNT_PCT)';
COMMENT ON TABLE SAL_ORDER IS 'أوامر البيع (ناتجة من قبول عرض سعر) / sales orders. STATUS: DRAFT, CONFIRMED مؤكد, PARTIAL تسليم جزئي, DELIVERED, CANCELLED. INV_KEY = رقم الفاتورة الفعلية MAIN_INV.INV_KEY (بيتربط يدوي). ⚠ الفاتورة نفسها مابتتعملش تلقائي. ⚠ لاسم العميل: JOIN justclick.CUST c ON c.CUSTID = SAL_ORDER.CUST_ID ثم استخدم c.CUSTNAME — لا يوجد عمود CUSTOMER_NAME في هذا الجدول';
COMMENT ON COLUMN SAL_ORDER.ORDER_ID IS 'رقم أمر البيع (ORDER_ID)';
COMMENT ON COLUMN SAL_ORDER.QUOTE_ID IS 'رقم عرض السعر (QUOTE_ID) - FK → SAL_QUOTE.QUOTE_ID';
COMMENT ON COLUMN SAL_ORDER.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN SAL_ORDER.ORDER_DATE IS 'تاريخ الأمر (ORDER_DATE)';
COMMENT ON COLUMN SAL_ORDER.DELIVERY_DATE IS 'تاريخ التسليم (DELIVERY_DATE)';
COMMENT ON COLUMN SAL_ORDER.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، CONFIRMED=مؤكد، PARTIAL=تسليم جزئي، DELIVERED=تم التسليم، CANCELLED=ملغي';
COMMENT ON COLUMN SAL_ORDER.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY)';
COMMENT ON COLUMN SAL_ORDER.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN SAL_ORDER.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE SAL_ORDER_LINE IS 'أصناف أمر البيع وكمية التسليم / sales order lines. DELIVERED_QTY مايزيدش عن QTY';
COMMENT ON COLUMN SAL_ORDER_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN SAL_ORDER_LINE.ORDER_ID IS 'رقم أمر البيع (ORDER_ID) - FK → SAL_ORDER.ORDER_ID';
COMMENT ON COLUMN SAL_ORDER_LINE.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN SAL_ORDER_LINE.UNIT_ID IS 'الوحدة (UNIT_ID)';
COMMENT ON COLUMN SAL_ORDER_LINE.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN SAL_ORDER_LINE.PRICE IS 'السعر (PRICE)';
COMMENT ON COLUMN SAL_ORDER_LINE.DISCOUNT_PCT IS 'الخصم % (DISCOUNT_PCT)';
COMMENT ON COLUMN SAL_ORDER_LINE.DELIVERED_QTY IS 'الكمية المسلّمة (DELIVERED_QTY)';
COMMENT ON TABLE REC_JE IS 'قوالب القيود الدورية والعكسية / recurring / reversing journal templates. FREQ: MONTHLY شهري, QUARTERLY, YEARLY. REVERSE_NEXT=Y يولّد قيد معكوس في الفترة التالية. بيتولد في القيد الجاهز VOUCHERS_READY مش الأستاذ';
COMMENT ON COLUMN REC_JE.JE_ID IS 'رقم القالب (JE_ID)';
COMMENT ON COLUMN REC_JE.JE_NAME IS 'اسم القيد (JE_NAME)';
COMMENT ON COLUMN REC_JE.FREQ IS 'التكرار (FREQ) - القيم: MONTHLY=شهري، QUARTERLY=ربع سنوي، YEARLY=سنوي';
COMMENT ON COLUMN REC_JE.NEXT_DATE IS 'الموعد القادم (NEXT_DATE)';
COMMENT ON COLUMN REC_JE.END_DATE IS 'ينتهي في (END_DATE)';
COMMENT ON COLUMN REC_JE.ACTIVE IS 'نشط (Y/N) (ACTIVE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN REC_JE.REVERSE_NEXT IS 'يُعكس في الفترة التالية (Y/N) (REVERSE_NEXT) - القيم: Y=Y، N=N';
COMMENT ON COLUMN REC_JE.DOC_ID IS 'نوع المستند (DOC_ID)';
COMMENT ON COLUMN REC_JE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE REC_JE_LINE IS 'بنود قالب القيد الدوري / recurring journal lines. AMOUNT بإشارة: مدين +، دائن −. لازم مجموع البنود = 0';
COMMENT ON COLUMN REC_JE_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN REC_JE_LINE.JE_ID IS 'رقم القالب (JE_ID) - FK → REC_JE.JE_ID';
COMMENT ON COLUMN REC_JE_LINE.CHART_CODE IS 'كود الحساب (CHART_CODE)';
COMMENT ON COLUMN REC_JE_LINE.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN REC_JE_LINE.COST_CODE IS 'مركز التكلفة (COST_CODE)';
COMMENT ON COLUMN REC_JE_LINE.LINE_DESC IS 'بيان البند (LINE_DESC)';
COMMENT ON TABLE REC_JE_LOG IS 'سجل توليد القيود الدورية / recurring journal generation log. KIND: RECURRING أو REVERSAL. RESULT: CREATED أو SKIPPED';
COMMENT ON COLUMN REC_JE_LOG.LOG_ID IS 'Log Id (LOG_ID)';
COMMENT ON COLUMN REC_JE_LOG.JE_ID IS 'رقم القالب (JE_ID)';
COMMENT ON COLUMN REC_JE_LOG.PERIOD_DATE IS 'تاريخ الاستحقاق (PERIOD_DATE)';
COMMENT ON COLUMN REC_JE_LOG.KIND IS 'النوع (KIND) - القيم: RECURRING=RECURRING، REVERSAL=REVERSAL';
COMMENT ON COLUMN REC_JE_LOG.VOUCHER_CODE IS 'رقم القيد (VOUCHER_CODE)';
COMMENT ON COLUMN REC_JE_LOG.RESULT IS 'النتيجة (RESULT) - القيم: CREATED=CREATED، SKIPPED=SKIPPED';
COMMENT ON COLUMN REC_JE_LOG.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN REC_JE_LOG.RUN_DATE IS 'Run Date (RUN_DATE)';
COMMENT ON TABLE SAL_NOTE IS 'الإشعارات الدائنة والمدينة للعملاء والموردين / credit and debit notes. PARTY_TYPE: 0 عميل، 1 مورد (PARTY_ID = CUST.CUSTID مع CUST_TYPE). NOTE_TYPE: CREDIT دائن / DEBIT مدين. STATUS: DRAFT, APPROVED, CANCELLED. الاعتماد يولّد قيد جاهز';
COMMENT ON COLUMN SAL_NOTE.NOTE_ID IS 'رقم الإشعار (NOTE_ID)';
COMMENT ON COLUMN SAL_NOTE.NOTE_TYPE IS 'النوع (CREDIT دائن / DEBIT مدين) (NOTE_TYPE) - القيم: CREDIT=دائن، DEBIT=مدين';
COMMENT ON COLUMN SAL_NOTE.PARTY_TYPE IS 'نوع الطرف (0 عميل / 1 مورد) (PARTY_TYPE) - القيم: ';
COMMENT ON COLUMN SAL_NOTE.PARTY_ID IS 'كود العميل/المورد (PARTY_ID)';
COMMENT ON COLUMN SAL_NOTE.NOTE_DATE IS 'تاريخ الإشعار (NOTE_DATE)';
COMMENT ON COLUMN SAL_NOTE.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN SAL_NOTE.CONTRA_CHART_CODE IS 'الحساب المقابل (CONTRA_CHART_CODE)';
COMMENT ON COLUMN SAL_NOTE.REASON IS 'السبب (REASON)';
COMMENT ON COLUMN SAL_NOTE.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY)';
COMMENT ON COLUMN SAL_NOTE.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، APPROVED=معتمد (طلع له قيد جاهز)، CANCELLED=ملغي';
COMMENT ON COLUMN SAL_NOTE.READY_VOUCHER_CODE IS 'رقم القيد الجاهز (READY_VOUCHER_CODE)';
COMMENT ON COLUMN SAL_NOTE.APPROVED_BY IS 'اعتمده (APPROVED_BY)';
COMMENT ON COLUMN SAL_NOTE.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE CON_CONTRACT IS 'عقود العملاء المتكررة (فوترة دورية) / customer recurring contracts. FREQ: MONTHLY/QUARTERLY/YEARLY. NEXT_BILL_DATE موعد المطالبة القادم';
COMMENT ON COLUMN CON_CONTRACT.CONTRACT_ID IS 'رقم العقد (CONTRACT_ID)';
COMMENT ON COLUMN CON_CONTRACT.CONTRACT_NAME IS 'اسم العقد (CONTRACT_NAME)';
COMMENT ON COLUMN CON_CONTRACT.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN CON_CONTRACT.START_DATE IS 'بداية العقد (START_DATE)';
COMMENT ON COLUMN CON_CONTRACT.END_DATE IS 'ينتهي في (END_DATE)';
COMMENT ON COLUMN CON_CONTRACT.FREQ IS 'التكرار (FREQ) - القيم: MONTHLY=شهري، QUARTERLY=ربع سنوي، YEARLY=سنوي';
COMMENT ON COLUMN CON_CONTRACT.NEXT_BILL_DATE IS 'موعد الفاتورة القادم (NEXT_BILL_DATE)';
COMMENT ON COLUMN CON_CONTRACT.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN CON_CONTRACT.ACTIVE IS 'نشط (Y/N) (ACTIVE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN CON_CONTRACT.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE CON_BILL IS 'مطالبات العقود المستحقة (لم تُفوتر / تمت الفوترة) / contract bills due. STATUS: PENDING لم تُفوتر، INVOICED تمت الفوترة (مع INV_KEY)، CANCELLED. ⚠ الفاتورة بتتعمل يدوي من شاشة الفاتورة';
COMMENT ON COLUMN CON_BILL.BILL_ID IS 'رقم المطالبة (BILL_ID)';
COMMENT ON COLUMN CON_BILL.CONTRACT_ID IS 'رقم العقد (CONTRACT_ID) - FK → CON_CONTRACT.CONTRACT_ID';
COMMENT ON COLUMN CON_BILL.PERIOD_DATE IS 'تاريخ الاستحقاق (PERIOD_DATE)';
COMMENT ON COLUMN CON_BILL.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN CON_BILL.STATUS IS 'الحالة (STATUS) - القيم: PENDING=لم تُفوتر (مطالبة مستحقة)، INVOICED=تمت الفوترة، CANCELLED=ملغي';
COMMENT ON COLUMN CON_BILL.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY)';
COMMENT ON COLUMN CON_BILL.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE ALLOC_RULE IS 'قواعد توزيع التكاليف (حساب مصدر يتوزع على أهداف) / cost allocation rules. SOURCE_CHART_CODE حساب المصدر. النسب في ALLOC_TARGET لازم = 100';
COMMENT ON COLUMN ALLOC_RULE.RULE_ID IS 'رقم القاعدة (RULE_ID)';
COMMENT ON COLUMN ALLOC_RULE.RULE_NAME IS 'اسم القاعدة (RULE_NAME)';
COMMENT ON COLUMN ALLOC_RULE.SOURCE_CHART_CODE IS 'حساب المصدر (اللي هيتوزع) (SOURCE_CHART_CODE)';
COMMENT ON COLUMN ALLOC_RULE.SOURCE_COST_CODE IS 'مركز تكلفة المصدر (SOURCE_COST_CODE)';
COMMENT ON COLUMN ALLOC_RULE.ACTIVE IS 'نشط (Y/N) (ACTIVE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN ALLOC_RULE.DOC_ID IS 'نوع المستند (DOC_ID)';
COMMENT ON COLUMN ALLOC_RULE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE ALLOC_TARGET IS 'أهداف قاعدة التوزيع ونسبها / allocation targets. PCT نسبة كل هدف';
COMMENT ON COLUMN ALLOC_TARGET.TARGET_ID IS 'م (TARGET_ID)';
COMMENT ON COLUMN ALLOC_TARGET.RULE_ID IS 'رقم القاعدة (RULE_ID) - FK → ALLOC_RULE.RULE_ID';
COMMENT ON COLUMN ALLOC_TARGET.TARGET_CHART_CODE IS 'حساب الهدف (TARGET_CHART_CODE)';
COMMENT ON COLUMN ALLOC_TARGET.TARGET_COST_CODE IS 'مركز تكلفة الهدف (TARGET_COST_CODE)';
COMMENT ON COLUMN ALLOC_TARGET.PCT IS 'النسبة % (PCT)';
COMMENT ON TABLE ALLOC_LOG IS 'سجل تنفيذ قواعد التوزيع (قاعدة + فترة مرة واحدة) / allocation run log. القاعدة لا تتنفذ مرتين لنفس الفترة';
COMMENT ON COLUMN ALLOC_LOG.LOG_ID IS 'Log Id (LOG_ID)';
COMMENT ON COLUMN ALLOC_LOG.RULE_ID IS 'رقم القاعدة (RULE_ID)';
COMMENT ON COLUMN ALLOC_LOG.FROM_DATE IS 'من تاريخ (FROM_DATE)';
COMMENT ON COLUMN ALLOC_LOG.TO_DATE IS 'إلى تاريخ (TO_DATE)';
COMMENT ON COLUMN ALLOC_LOG.SOURCE_NET IS 'Source Net (SOURCE_NET)';
COMMENT ON COLUMN ALLOC_LOG.VOUCHER_CODE IS 'رقم القيد (VOUCHER_CODE)';
COMMENT ON COLUMN ALLOC_LOG.RUN_DATE IS 'Run Date (RUN_DATE)';
COMMENT ON TABLE EXP_CLAIM IS 'طلبات المصروفات والسلف للموظفين / expense claims and advances. CLAIM_KIND: EXPENSE مصروفات / ADVANCE سلفة. STATUS: DRAFT, APPROVED, REJECTED. CREDIT_CHART_CODE حساب الدائن (الخزينة أو العهدة). الاعتماد يولّد قيد جاهز';
COMMENT ON COLUMN EXP_CLAIM.CLAIM_ID IS 'رقم الطلب (CLAIM_ID)';
COMMENT ON COLUMN EXP_CLAIM.CLAIM_KIND IS 'النوع (EXPENSE مصروفات / ADVANCE سلفة) (CLAIM_KIND) - القيم: EXPENSE=مصروفات، ADVANCE=سلفة';
COMMENT ON COLUMN EXP_CLAIM.EMP_ID IS 'كود الموظف (EMP_ID)';
COMMENT ON COLUMN EXP_CLAIM.CLAIM_DATE IS 'تاريخ الطلب (CLAIM_DATE)';
COMMENT ON COLUMN EXP_CLAIM.CREDIT_CHART_CODE IS 'حساب الدائن (الخزينة أو العهدة) (CREDIT_CHART_CODE)';
COMMENT ON COLUMN EXP_CLAIM.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، APPROVED=معتمد (طلع له قيد جاهز)، REJECTED=مرفوض';
COMMENT ON COLUMN EXP_CLAIM.READY_VOUCHER_CODE IS 'رقم القيد الجاهز (READY_VOUCHER_CODE)';
COMMENT ON COLUMN EXP_CLAIM.APPROVED_BY IS 'اعتمده (APPROVED_BY)';
COMMENT ON COLUMN EXP_CLAIM.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE EXP_CLAIM_LINE IS 'بنود طلب المصروفات (حساب مدين ومبلغ) / expense claim lines. AMOUNT موجب دائماً';
COMMENT ON COLUMN EXP_CLAIM_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN EXP_CLAIM_LINE.CLAIM_ID IS 'رقم الطلب (CLAIM_ID) - FK → EXP_CLAIM.CLAIM_ID';
COMMENT ON COLUMN EXP_CLAIM_LINE.CHART_CODE IS 'كود الحساب (CHART_CODE)';
COMMENT ON COLUMN EXP_CLAIM_LINE.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN EXP_CLAIM_LINE.COST_CODE IS 'مركز التكلفة (COST_CODE)';
COMMENT ON COLUMN EXP_CLAIM_LINE.LINE_DESC IS 'بيان البند (LINE_DESC)';
COMMENT ON TABLE AUDIT_LOG IS 'سجل تدقيق التعديلات على الجداول المحاسبية / audit trail of table changes. يُقرأ من V_AUDIT_LOG';
COMMENT ON COLUMN AUDIT_LOG.AUDIT_ID IS 'رقم المراجعة (AUDIT_ID)';
COMMENT ON COLUMN AUDIT_LOG.AUDIT_DATE IS 'تاريخ المراجعة (AUDIT_DATE)';
COMMENT ON COLUMN AUDIT_LOG.TABLE_NAME IS 'الجدول (TABLE_NAME)';
COMMENT ON COLUMN AUDIT_LOG.ACTION IS 'Action (ACTION) - القيم: I=I، U=U، D=مصروف';
COMMENT ON COLUMN AUDIT_LOG.PK_VALUE IS 'Pk Value (PK_VALUE)';
COMMENT ON COLUMN AUDIT_LOG.CHANGED_COLS IS 'Changed Cols (CHANGED_COLS)';
COMMENT ON COLUMN AUDIT_LOG.OLD_DATA IS 'Old Data (OLD_DATA)';
COMMENT ON COLUMN AUDIT_LOG.NEW_DATA IS 'New Data (NEW_DATA)';
COMMENT ON COLUMN AUDIT_LOG.APP_USER IS 'App User (APP_USER)';
COMMENT ON COLUMN AUDIT_LOG.DB_USER IS 'Db User (DB_USER)';
COMMENT ON COLUMN AUDIT_LOG.CLIENT_INFO IS 'Client Info (CLIENT_INFO)';
COMMENT ON TABLE NOTIFICATIONS IS 'الإشعارات داخل النظام / in-app notifications. للمستخدم عبر V_MY_NOTIFICATIONS';
COMMENT ON COLUMN NOTIFICATIONS.NOTIF_ID IS 'Notif Id (NOTIF_ID)';
COMMENT ON COLUMN NOTIFICATIONS.USER_NAME IS 'المستخدم (USER_NAME)';
COMMENT ON COLUMN NOTIFICATIONS.TITLE IS 'العنوان (TITLE)';
COMMENT ON COLUMN NOTIFICATIONS.BODY IS 'النص (BODY)';
COMMENT ON COLUMN NOTIFICATIONS.LINK_URL IS 'Link Url (LINK_URL)';
COMMENT ON COLUMN NOTIFICATIONS.NOTIF_TYPE IS 'Notif Type (NOTIF_TYPE)';
COMMENT ON COLUMN NOTIFICATIONS.REF_TABLE IS 'Ref Table (REF_TABLE)';
COMMENT ON COLUMN NOTIFICATIONS.REF_KEY IS 'المرجع (REF_KEY)';
COMMENT ON COLUMN NOTIFICATIONS.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON COLUMN NOTIFICATIONS.READ_DATE IS 'Read Date (READ_DATE)';
COMMENT ON COLUMN NOTIFICATIONS.EMAIL_STATUS IS 'Email Status (EMAIL_STATUS) - القيم: NONE=NONE، QUEUED=QUEUED، SENT=مُرسل، FAILED=FAILED، SKIPPED=SKIPPED';
COMMENT ON TABLE NOTIFY_CONTACT IS 'جهات اتصال الإشعارات / notification contacts.';
COMMENT ON COLUMN NOTIFY_CONTACT.USER_NAME IS 'المستخدم (USER_NAME)';
COMMENT ON COLUMN NOTIFY_CONTACT.EMAIL IS 'البريد (EMAIL)';
COMMENT ON COLUMN NOTIFY_CONTACT.WHATSAPP IS 'Whatsapp (WHATSAPP)';
COMMENT ON COLUMN NOTIFY_CONTACT.EMAIL_ENABLED IS 'Email Enabled (EMAIL_ENABLED)';
COMMENT ON TABLE NOTIFY_SETTINGS IS 'إعدادات الإشعارات / notification settings.';
COMMENT ON COLUMN NOTIFY_SETTINGS.SETTING_ID IS 'Setting Id (SETTING_ID)';
COMMENT ON COLUMN NOTIFY_SETTINGS.EMAIL_ENABLED IS 'Email Enabled (EMAIL_ENABLED)';
COMMENT ON COLUMN NOTIFY_SETTINGS.FROM_ADDRESS IS 'From Address (FROM_ADDRESS)';
COMMENT ON TABLE DMS_FILES IS 'إدارة المستندات: ملفات مرتبطة بسجلات النظام / document management files. الأحدث في V_DMS_CURRENT';
COMMENT ON COLUMN DMS_FILES.FILE_ID IS 'File Id (FILE_ID)';
COMMENT ON COLUMN DMS_FILES.ENTITY_TYPE IS 'Entity Type (ENTITY_TYPE)';
COMMENT ON COLUMN DMS_FILES.ENTITY_KEY IS 'Entity Key (ENTITY_KEY)';
COMMENT ON COLUMN DMS_FILES.FILE_NAME IS 'اسم الملف (FILE_NAME)';
COMMENT ON COLUMN DMS_FILES.MIME_TYPE IS 'Mime Type (MIME_TYPE)';
COMMENT ON COLUMN DMS_FILES.FILE_SIZE IS 'File Size (FILE_SIZE)';
COMMENT ON COLUMN DMS_FILES.FILE_CONTENT IS 'File Content (FILE_CONTENT)';
COMMENT ON COLUMN DMS_FILES.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN DMS_FILES.TAGS IS 'Tags (TAGS)';
COMMENT ON COLUMN DMS_FILES.VERSION_NO IS 'الإصدار (VERSION_NO)';
COMMENT ON COLUMN DMS_FILES.IS_CURRENT IS 'Is Current (IS_CURRENT) - القيم: Y=Y، N=N';
COMMENT ON COLUMN DMS_FILES.UPLOADED_BY IS 'Uploaded By (UPLOADED_BY)';
COMMENT ON COLUMN DMS_FILES.UPLOAD_DATE IS 'Upload Date (UPLOAD_DATE)';
COMMENT ON COLUMN DMS_FILES.DELETED_BY IS 'Deleted By (DELETED_BY)';
COMMENT ON COLUMN DMS_FILES.DELETED_DATE IS 'Deleted Date (DELETED_DATE)';
COMMENT ON TABLE HEALTH_KPI IS 'تعريف مؤشرات صحة النظام / system health KPI definitions.';
COMMENT ON COLUMN HEALTH_KPI.KPI_KEY IS 'Kpi Key (KPI_KEY)';
COMMENT ON COLUMN HEALTH_KPI.LABEL IS 'الفحص (LABEL)';
COMMENT ON COLUMN HEALTH_KPI.SQL_TEXT IS 'Sql Text (SQL_TEXT)';
COMMENT ON COLUMN HEALTH_KPI.TARGET_TXT IS 'Target Txt (TARGET_TXT)';
COMMENT ON COLUMN HEALTH_KPI.IS_ACTIVE IS 'Is Active (IS_ACTIVE)';
COMMENT ON TABLE HEALTH_SNAPSHOT IS 'لقطات يومية لمؤشرات صحة النظام / daily health snapshots. آخر لقطة في V_HEALTH_LATEST';
COMMENT ON COLUMN HEALTH_SNAPSHOT.SNAP_ID IS 'Snap Id (SNAP_ID)';
COMMENT ON COLUMN HEALTH_SNAPSHOT.SNAP_DATE IS 'Snap Date (SNAP_DATE)';
COMMENT ON COLUMN HEALTH_SNAPSHOT.KPI_KEY IS 'Kpi Key (KPI_KEY)';
COMMENT ON COLUMN HEALTH_SNAPSHOT.KPI_VALUE IS 'Kpi Value (KPI_VALUE)';
COMMENT ON COLUMN HEALTH_SNAPSHOT.ERROR_TEXT IS 'Error Text (ERROR_TEXT)';
COMMENT ON TABLE PAGE_ACCESS_SETTINGS IS 'إعداد صلاحيات الصفحات (مراقبة / فرض) / page access settings. ENFORCE: N مراقبة فقط تسجّل من كان هيتمنع، Y فرض. صف واحد';
COMMENT ON COLUMN PAGE_ACCESS_SETTINGS.SETTING_ID IS 'Setting Id (SETTING_ID)';
COMMENT ON COLUMN PAGE_ACCESS_SETTINGS.ENFORCE IS 'Enforce (ENFORCE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN PAGE_ACCESS_SETTINGS.UNMAPPED_MODE IS 'Unmapped Mode (UNMAPPED_MODE) - القيم: ALLOW=ALLOW، DENY=DENY';
COMMENT ON TABLE PAGE_ACCESS_LOG IS 'سجل من كان هيتمنع من فتح صفحة (وضع المراقبة) / page access log. REASON سبب المنع';
COMMENT ON COLUMN PAGE_ACCESS_LOG.LOG_ID IS 'Log Id (LOG_ID)';
COMMENT ON COLUMN PAGE_ACCESS_LOG.LOG_DATE IS 'Log Date (LOG_DATE)';
COMMENT ON COLUMN PAGE_ACCESS_LOG.PAGE_ID IS 'Page Id (PAGE_ID)';
COMMENT ON COLUMN PAGE_ACCESS_LOG.USER_NAME IS 'المستخدم (USER_NAME)';
COMMENT ON COLUMN PAGE_ACCESS_LOG.WOULD_DENY IS 'Would Deny (WOULD_DENY)';
COMMENT ON COLUMN PAGE_ACCESS_LOG.REASON IS 'السبب (REASON)';
COMMENT ON TABLE AUTOPOST_LOG IS 'سجل الترحيل التلقائي للقيود الوسيطة للأستاذ / auto-post log. RESULT: POSTED اترحّل، SKIPPED اتخطّى مع REASON (غير متزن / حساب غير موجود / فترة مقفولة)';
COMMENT ON COLUMN AUTOPOST_LOG.LOG_ID IS 'Log Id (LOG_ID)';
COMMENT ON COLUMN AUTOPOST_LOG.RUN_DATE IS 'Run Date (RUN_DATE)';
COMMENT ON COLUMN AUTOPOST_LOG.SOURCE_KEY IS 'المصدر (SOURCE_KEY)';
COMMENT ON COLUMN AUTOPOST_LOG.SOURCE_CODE IS 'Source Code (SOURCE_CODE)';
COMMENT ON COLUMN AUTOPOST_LOG.RESULT IS 'النتيجة (RESULT) - القيم: POSTED=POSTED، SKIPPED=SKIPPED';
COMMENT ON COLUMN AUTOPOST_LOG.REASON IS 'السبب (REASON)';
COMMENT ON COLUMN AUTOPOST_LOG.POSTED_CODE IS 'Posted Code (POSTED_CODE)';
COMMENT ON TABLE CONS_COMPANY IS 'شركات مجموعة التوحيد / consolidation group companies. IS_LOCAL=Y شركة القاعدة دي (بتتحمل من الأستاذ). OWNERSHIP_PCT للعلم فقط (توحيد كامل)';
COMMENT ON COLUMN CONS_COMPANY.CO_ID IS 'رقم الشركة (CO_ID)';
COMMENT ON COLUMN CONS_COMPANY.CO_NAME IS 'اسم الشركة (CO_NAME)';
COMMENT ON COLUMN CONS_COMPANY.IS_LOCAL IS 'شركة القاعدة دي (Y/N) (IS_LOCAL) - القيم: Y=Y، N=N';
COMMENT ON COLUMN CONS_COMPANY.OWNERSHIP_PCT IS 'نسبة الملكية % (OWNERSHIP_PCT)';
COMMENT ON COLUMN CONS_COMPANY.CURRENCY_NOTE IS 'العملة (CURRENCY_NOTE)';
COMMENT ON COLUMN CONS_COMPANY.ACTIVE IS 'نشط (Y/N) (ACTIVE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN CONS_COMPANY.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE CONS_ACCOUNT IS 'حسابات المجموعة الموحدة / group chart of accounts. GROUP_TYPE: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE';
COMMENT ON COLUMN CONS_ACCOUNT.GROUP_CODE IS 'كود حساب المجموعة (GROUP_CODE)';
COMMENT ON COLUMN CONS_ACCOUNT.GROUP_NAME IS 'اسم حساب المجموعة (GROUP_NAME)';
COMMENT ON COLUMN CONS_ACCOUNT.GROUP_TYPE IS 'النوع (GROUP_TYPE) - القيم: ASSET=أصول، LIABILITY=التزامات، EQUITY=حقوق ملكية، REVENUE=إيرادات، EXPENSE=مصروفات';
COMMENT ON TABLE CONS_MAP IS 'ربط حساب كل شركة بحساب المجموعة / company-to-group account mapping. غير المربوط يظهر في V_CONS_UNMAPPED ويطلع من التوحيد';
COMMENT ON COLUMN CONS_MAP.MAP_ID IS 'م (MAP_ID)';
COMMENT ON COLUMN CONS_MAP.CO_ID IS 'رقم الشركة (CO_ID) - FK → CONS_COMPANY.CO_ID';
COMMENT ON COLUMN CONS_MAP.CO_ACCOUNT IS 'حساب الشركة (CO_ACCOUNT)';
COMMENT ON COLUMN CONS_MAP.GROUP_CODE IS 'كود حساب المجموعة (GROUP_CODE) - FK → CONS_ACCOUNT.GROUP_CODE';
COMMENT ON TABLE CONS_TB IS 'ميزان المراجعة لكل شركة في تاريخ / company trial balance snapshot. DEBIT/CREDIT موجبين. الشركة المحلية تتحمل بـ CONS_PKG.LOAD_LOCAL';
COMMENT ON COLUMN CONS_TB.TB_ID IS 'م (TB_ID)';
COMMENT ON COLUMN CONS_TB.CO_ID IS 'رقم الشركة (CO_ID) - FK → CONS_COMPANY.CO_ID';
COMMENT ON COLUMN CONS_TB.AS_OF IS 'بتاريخ (AS_OF)';
COMMENT ON COLUMN CONS_TB.CO_ACCOUNT IS 'حساب الشركة (CO_ACCOUNT)';
COMMENT ON COLUMN CONS_TB.ACCOUNT_NAME IS 'اسم الحساب (ACCOUNT_NAME)';
COMMENT ON COLUMN CONS_TB.DEBIT IS 'مدين (DEBIT)';
COMMENT ON COLUMN CONS_TB.CREDIT IS 'دائن (CREDIT)';
COMMENT ON TABLE CONS_FX IS 'سعر تحويل عملة الشركة لعملة المجموعة في تاريخ / consolidation exchange rate. الأصل 1 لو مفيش صف';
COMMENT ON COLUMN CONS_FX.FX_ID IS 'م (FX_ID)';
COMMENT ON COLUMN CONS_FX.CO_ID IS 'رقم الشركة (CO_ID) - FK → CONS_COMPANY.CO_ID';
COMMENT ON COLUMN CONS_FX.AS_OF IS 'بتاريخ (AS_OF)';
COMMENT ON COLUMN CONS_FX.RATE IS 'سعر التحويل (RATE)';
COMMENT ON TABLE CONS_ELIM IS 'قيود استبعاد المعاملات بين شركات المجموعة / intercompany eliminations. AMOUNT بإشارة: مدين +، دائن −';
COMMENT ON COLUMN CONS_ELIM.ELIM_ID IS 'م (ELIM_ID)';
COMMENT ON COLUMN CONS_ELIM.AS_OF IS 'بتاريخ (AS_OF)';
COMMENT ON COLUMN CONS_ELIM.GROUP_CODE IS 'كود حساب المجموعة (GROUP_CODE) - FK → CONS_ACCOUNT.GROUP_CODE';
COMMENT ON COLUMN CONS_ELIM.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN CONS_ELIM.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE FLT_VEHICLE IS 'مركبات الأسطول (رخص وتأمين وعداد) / fleet vehicles. PLATE_NO فريد. ODOMETER_START عداد البداية';
COMMENT ON COLUMN FLT_VEHICLE.VEHICLE_ID IS 'رقم المركبة (VEHICLE_ID)';
COMMENT ON COLUMN FLT_VEHICLE.PLATE_NO IS 'رقم اللوحة (PLATE_NO)';
COMMENT ON COLUMN FLT_VEHICLE.VEHICLE_TYPE IS 'نوع المركبة (VEHICLE_TYPE)';
COMMENT ON COLUMN FLT_VEHICLE.DRIVER_NAME IS 'السائق (DRIVER_NAME)';
COMMENT ON COLUMN FLT_VEHICLE.DRIVER_LICENSE_EXPIRY IS 'انتهاء رخصة السائق (DRIVER_LICENSE_EXPIRY)';
COMMENT ON COLUMN FLT_VEHICLE.VEHICLE_LICENSE_EXPIRY IS 'انتهاء رخصة المركبة (VEHICLE_LICENSE_EXPIRY)';
COMMENT ON COLUMN FLT_VEHICLE.INSURANCE_EXPIRY IS 'انتهاء التأمين (INSURANCE_EXPIRY)';
COMMENT ON COLUMN FLT_VEHICLE.ODOMETER_START IS 'عداد البداية (ODOMETER_START)';
COMMENT ON COLUMN FLT_VEHICLE.ACTIVE IS 'نشط (Y/N) (ACTIVE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN FLT_VEHICLE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE FLT_FUEL IS 'تعبئة الوقود (لترات وتكلفة وعداد) / fuel fill-ups. JOIN: VEHICLE_ID';
COMMENT ON COLUMN FLT_FUEL.FUEL_ID IS 'م (FUEL_ID)';
COMMENT ON COLUMN FLT_FUEL.VEHICLE_ID IS 'رقم المركبة (VEHICLE_ID) - FK → FLT_VEHICLE.VEHICLE_ID';
COMMENT ON COLUMN FLT_FUEL.FUEL_DATE IS 'تاريخ التعبئة (FUEL_DATE)';
COMMENT ON COLUMN FLT_FUEL.LITERS IS 'لترات (LITERS)';
COMMENT ON COLUMN FLT_FUEL.COST IS 'التكلفة (COST)';
COMMENT ON COLUMN FLT_FUEL.ODOMETER IS 'العداد (ODOMETER)';
COMMENT ON TABLE FLT_MAINT IS 'صيانة المركبات (نوع وتكلفة وموعد قادم) / vehicle maintenance. NEXT_DUE_DATE موعد الصيانة القادم';
COMMENT ON COLUMN FLT_MAINT.MAINT_ID IS 'م (MAINT_ID)';
COMMENT ON COLUMN FLT_MAINT.VEHICLE_ID IS 'رقم المركبة (VEHICLE_ID) - FK → FLT_VEHICLE.VEHICLE_ID';
COMMENT ON COLUMN FLT_MAINT.MAINT_DATE IS 'تاريخ الصيانة (MAINT_DATE)';
COMMENT ON COLUMN FLT_MAINT.KIND IS 'النوع (KIND)';
COMMENT ON COLUMN FLT_MAINT.COST IS 'التكلفة (COST)';
COMMENT ON COLUMN FLT_MAINT.ODOMETER IS 'العداد (ODOMETER)';
COMMENT ON COLUMN FLT_MAINT.NEXT_DUE_DATE IS 'الصيانة القادمة (NEXT_DUE_DATE)';
COMMENT ON COLUMN FLT_MAINT.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE LOG_TRIP IS 'رحلات التوزيع (مركبة + سائق) / delivery trips. STATUS: PLANNED مخططة, ON_ROAD في الطريق, DONE, CANCELLED';
COMMENT ON COLUMN LOG_TRIP.TRIP_ID IS 'رقم الرحلة (TRIP_ID)';
COMMENT ON COLUMN LOG_TRIP.TRIP_DATE IS 'تاريخ الرحلة (TRIP_DATE)';
COMMENT ON COLUMN LOG_TRIP.VEHICLE_ID IS 'رقم المركبة (VEHICLE_ID) - FK → FLT_VEHICLE.VEHICLE_ID';
COMMENT ON COLUMN LOG_TRIP.DRIVER_NAME IS 'السائق (DRIVER_NAME)';
COMMENT ON COLUMN LOG_TRIP.STATUS IS 'الحالة (STATUS) - القيم: PLANNED=مخطط، ON_ROAD=في الطريق، DONE=منتهي، CANCELLED=ملغي';
COMMENT ON COLUMN LOG_TRIP.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE LOG_TRIP_STOP IS 'محطات الرحلة (عميل / أمر بيع) وحالتها / delivery stops. STATUS: PENDING, DELIVERED تم التسليم, FAILED فشل (مع FAIL_REASON). ORDER_ID = SAL_ORDER.ORDER_ID: تسليم المحطة بيسلّم باقي أصناف الأمر';
COMMENT ON COLUMN LOG_TRIP_STOP.STOP_ID IS 'م (STOP_ID)';
COMMENT ON COLUMN LOG_TRIP_STOP.TRIP_ID IS 'رقم الرحلة (TRIP_ID) - FK → LOG_TRIP.TRIP_ID';
COMMENT ON COLUMN LOG_TRIP_STOP.STOP_SEQ IS 'ترتيب المحطة (STOP_SEQ)';
COMMENT ON COLUMN LOG_TRIP_STOP.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN LOG_TRIP_STOP.ORDER_ID IS 'رقم أمر البيع (ORDER_ID)';
COMMENT ON COLUMN LOG_TRIP_STOP.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY)';
COMMENT ON COLUMN LOG_TRIP_STOP.STATUS IS 'الحالة (STATUS) - القيم: PENDING=منتظر، DELIVERED=تم التسليم، FAILED=فشل (مع سبب)';
COMMENT ON COLUMN LOG_TRIP_STOP.DELIVERED_AT IS 'وقت التسليم (DELIVERED_AT)';
COMMENT ON COLUMN LOG_TRIP_STOP.FAIL_REASON IS 'سبب الفشل (FAIL_REASON)';
COMMENT ON TABLE QMS_DOC IS 'مستندات نظام الجودة ودورة مراجعتها / quality system documents. REVIEW_EVERY_MONTHS دورة المراجعة. المراجعة القادمة في V_QMS_DOC_REVIEW';
COMMENT ON COLUMN QMS_DOC.DOC_ID IS 'نوع المستند (DOC_ID)';
COMMENT ON COLUMN QMS_DOC.DOC_NAME IS 'اسم المستند (DOC_NAME)';
COMMENT ON COLUMN QMS_DOC.DOC_TYPE IS 'نوع المستند (DOC_TYPE)';
COMMENT ON COLUMN QMS_DOC.VERSION_NO IS 'الإصدار (VERSION_NO)';
COMMENT ON COLUMN QMS_DOC.OWNER_USER IS 'المسؤول (OWNER_USER)';
COMMENT ON COLUMN QMS_DOC.ISSUE_DATE IS 'تاريخ الإصدار (ISSUE_DATE)';
COMMENT ON COLUMN QMS_DOC.REVIEW_EVERY_MONTHS IS 'دورة المراجعة (شهور) (REVIEW_EVERY_MONTHS)';
COMMENT ON COLUMN QMS_DOC.LAST_REVIEW IS 'آخر مراجعة (LAST_REVIEW)';
COMMENT ON COLUMN QMS_DOC.STATUS IS 'الحالة (STATUS) - القيم: ACTIVE=نشط، OBSOLETE=ملغي';
COMMENT ON COLUMN QMS_DOC.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE QMS_AUDIT IS 'عمليات المراجعة الداخلية (الجودة والمطابقة) / internal audits. RESULT: OPEN, CLOSED';
COMMENT ON COLUMN QMS_AUDIT.AUDIT_ID IS 'رقم المراجعة (AUDIT_ID)';
COMMENT ON COLUMN QMS_AUDIT.AUDIT_DATE IS 'تاريخ المراجعة (AUDIT_DATE)';
COMMENT ON COLUMN QMS_AUDIT.AREA IS 'المجال (AREA)';
COMMENT ON COLUMN QMS_AUDIT.AUDITOR IS 'المراجع (AUDITOR)';
COMMENT ON COLUMN QMS_AUDIT.RESULT IS 'النتيجة (RESULT) - القيم: OPEN=مفتوحة، CLOSED=مغلقة';
COMMENT ON COLUMN QMS_AUDIT.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE QMS_CAPA IS 'الإجراءات التصحيحية والوقائية / corrective and preventive actions. SOURCE_KIND: AUDIT, NCR, COMPLAINT, OTHER. STATUS: OPEN, IN_PROGRESS, DONE, VERIFIED';
COMMENT ON COLUMN QMS_CAPA.CAPA_ID IS 'رقم الإجراء (CAPA_ID)';
COMMENT ON COLUMN QMS_CAPA.AUDIT_ID IS 'رقم المراجعة (AUDIT_ID) - FK → QMS_AUDIT.AUDIT_ID';
COMMENT ON COLUMN QMS_CAPA.NCR_ID IS 'رقم عدم المطابقة (NCR_ID)';
COMMENT ON COLUMN QMS_CAPA.SOURCE_KIND IS 'المصدر (SOURCE_KIND) - القيم: AUDIT=مراجعة، NCR=عدم مطابقة، COMPLAINT=شكوى، OTHER=أخرى';
COMMENT ON COLUMN QMS_CAPA.DESCRIPTION IS 'البيان (DESCRIPTION)';
COMMENT ON COLUMN QMS_CAPA.OWNER_USER IS 'المسؤول (OWNER_USER)';
COMMENT ON COLUMN QMS_CAPA.DUE_DATE IS 'الموعد (DUE_DATE)';
COMMENT ON COLUMN QMS_CAPA.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، IN_PROGRESS=جاري، DONE=منتهي، VERIFIED=تم التحقق';
COMMENT ON COLUMN QMS_CAPA.DONE_DATE IS 'تاريخ الإنجاز (DONE_DATE)';
COMMENT ON TABLE BUD_HEAD IS 'الموازنات السنوية / annual budgets. STATUS: DRAFT, APPROVED. المقارنة بالفعلي في V_BUD_VS_ACTUAL';
COMMENT ON COLUMN BUD_HEAD.BUD_ID IS 'رقم الموازنة (BUD_ID)';
COMMENT ON COLUMN BUD_HEAD.BUD_YEAR IS 'السنة (BUD_YEAR)';
COMMENT ON COLUMN BUD_HEAD.BUD_NAME IS 'اسم الموازنة (BUD_NAME)';
COMMENT ON COLUMN BUD_HEAD.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، APPROVED=معتمدة، CLOSED=مغلقة';
COMMENT ON COLUMN BUD_HEAD.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN BUD_HEAD.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN BUD_HEAD.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON COLUMN BUD_HEAD.APPROVED_BY IS 'اعتمده (APPROVED_BY)';
COMMENT ON COLUMN BUD_HEAD.APPROVED_DATE IS 'تاريخ الاعتماد (APPROVED_DATE)';
COMMENT ON TABLE BUD_LINE IS 'بنود الموازنة (حساب وشهر ومبلغ) / budget lines. JOIN: BUD_ID. SIDE: D مصروف / C إيراد';
COMMENT ON COLUMN BUD_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN BUD_LINE.BUD_ID IS 'رقم الموازنة (BUD_ID) - FK → BUD_HEAD.BUD_ID';
COMMENT ON COLUMN BUD_LINE.CHART_CODE IS 'كود الحساب (CHART_CODE)';
COMMENT ON COLUMN BUD_LINE.COST_CODE IS 'مركز التكلفة (COST_CODE)';
COMMENT ON COLUMN BUD_LINE.BUD_MONTH IS 'الشهر (BUD_MONTH)';
COMMENT ON COLUMN BUD_LINE.SIDE IS 'الجانب (D مصروف / C إيراد) (SIDE) - القيم: D=مصروف، C=إيراد';
COMMENT ON COLUMN BUD_LINE.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON TABLE BANK_STMT IS 'كشوف حساب البنك المرفوعة / bank statements. STATUS: OPEN, RECONCILED. المطابقة تلقائي بـ RECON_PKG.AUTO_MATCH';
COMMENT ON COLUMN BANK_STMT.STMT_ID IS 'رقم الكشف (STMT_ID)';
COMMENT ON COLUMN BANK_STMT.CASH_ID IS 'الخزينة/البنك (CASH_ID) - FK → CASHES.CASH_ID';
COMMENT ON COLUMN BANK_STMT.STMT_FROM IS 'من تاريخ (STMT_FROM)';
COMMENT ON COLUMN BANK_STMT.STMT_TO IS 'إلى تاريخ (STMT_TO)';
COMMENT ON COLUMN BANK_STMT.OPENING_BAL IS 'رصيد أول (OPENING_BAL)';
COMMENT ON COLUMN BANK_STMT.CLOSING_BAL IS 'رصيد آخر (CLOSING_BAL)';
COMMENT ON COLUMN BANK_STMT.FILE_NAME IS 'اسم الملف (FILE_NAME)';
COMMENT ON COLUMN BANK_STMT.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، RECONCILED=تمت المطابقة';
COMMENT ON COLUMN BANK_STMT.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN BANK_STMT.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE BANK_STMT_LINE IS 'أسطر كشف البنك وحالة مطابقتها بدفتر الخزينة / bank statement lines. MATCH_STATUS: UNMATCHED لم يُطابق، AUTO مطابق آلياً، MANUAL مطابق يدوياً، IGNORED متجاهل. DEBIT سحب، CREDIT إيداع';
COMMENT ON COLUMN BANK_STMT_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN BANK_STMT_LINE.STMT_ID IS 'رقم الكشف (STMT_ID) - FK → BANK_STMT.STMT_ID';
COMMENT ON COLUMN BANK_STMT_LINE.LINE_DATE IS 'التاريخ (LINE_DATE)';
COMMENT ON COLUMN BANK_STMT_LINE.DESCRIPTION IS 'البيان (DESCRIPTION)';
COMMENT ON COLUMN BANK_STMT_LINE.REFERENCE IS 'المرجع (REFERENCE)';
COMMENT ON COLUMN BANK_STMT_LINE.DEBIT IS 'مدين (DEBIT)';
COMMENT ON COLUMN BANK_STMT_LINE.CREDIT IS 'دائن (CREDIT)';
COMMENT ON COLUMN BANK_STMT_LINE.MATCH_STATUS IS 'حالة المطابقة (MATCH_STATUS) - القيم: UNMATCHED=غير مطابق، AUTO=آلي، MANUAL=يدوي، IGNORED=متجاهل';
COMMENT ON COLUMN BANK_STMT_LINE.MATCH_TRANS_ID IS 'رقم حركة الدفتر (MATCH_TRANS_ID)';
COMMENT ON COLUMN BANK_STMT_LINE.MATCH_NOTE IS 'ملاحظة المطابقة (MATCH_NOTE)';
COMMENT ON TABLE CLOSE_CHECK_RESULT IS 'نتائج فحوصات ما قبل إقفال الفترة / period close check results. SEVERITY: BLOCKING مانع / WARNING تحذير. CLOSE_PKG.CAN_CLOSE(run_id)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.RUN_ID IS 'رقم التشغيل (RUN_ID)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.RUN_DATE IS 'Run Date (RUN_DATE)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.RUN_BY IS 'Run By (RUN_BY)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.PERIOD_FROM IS 'Period From (PERIOD_FROM)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.PERIOD_TO IS 'Period To (PERIOD_TO)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.CHECK_KEY IS 'كود الفحص (CHECK_KEY)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.LABEL IS 'الفحص (LABEL)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.ISSUES IS 'عدد المشاكل (ISSUES)';
COMMENT ON COLUMN CLOSE_CHECK_RESULT.SEVERITY IS 'الخطورة (SEVERITY)';
COMMENT ON TABLE COMM_RULE IS 'نسب عمولات المناديب (فاضية لحد ما تتحدد) / sales commission rules. DEALER_ID فاضي = الكل';
COMMENT ON COLUMN COMM_RULE.RULE_ID IS 'رقم القاعدة (RULE_ID)';
COMMENT ON COLUMN COMM_RULE.DEALER_ID IS 'المندوب (فاضي = الكل) (DEALER_ID)';
COMMENT ON COLUMN COMM_RULE.PCT IS 'النسبة % (PCT)';
COMMENT ON COLUMN COMM_RULE.FROM_DATE IS 'من تاريخ (FROM_DATE)';
COMMENT ON COLUMN COMM_RULE.TO_DATE IS 'إلى تاريخ (TO_DATE)';
COMMENT ON COLUMN COMM_RULE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE CRM_LEAD IS 'العملاء المحتملون / CRM leads. STAGE مراحل المسار. المسار في V_CRM_PIPELINE';
COMMENT ON COLUMN CRM_LEAD.LEAD_ID IS 'رقم العميل المحتمل (LEAD_ID)';
COMMENT ON COLUMN CRM_LEAD.LEAD_NAME IS 'الاسم (LEAD_NAME)';
COMMENT ON COLUMN CRM_LEAD.CONTACT IS 'جهة الاتصال (CONTACT)';
COMMENT ON COLUMN CRM_LEAD.MOBILE IS 'الموبايل (MOBILE)';
COMMENT ON COLUMN CRM_LEAD.EMAIL IS 'البريد (EMAIL)';
COMMENT ON COLUMN CRM_LEAD.SOURCE IS 'المصدر (SOURCE)';
COMMENT ON COLUMN CRM_LEAD.STAGE IS 'المرحلة (STAGE) - القيم: NEW=جديد، CONTACTED=تم التواصل، QUOTED=عرض سعر، NEGOTIATE=تفاوض، WON=تم الكسب، LOST=خسارة';
COMMENT ON COLUMN CRM_LEAD.EXPECTED_VALUE IS 'القيمة المتوقعة (EXPECTED_VALUE)';
COMMENT ON COLUMN CRM_LEAD.OWNER_USER IS 'المسؤول (OWNER_USER)';
COMMENT ON COLUMN CRM_LEAD.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN CRM_LEAD.LOST_REASON IS 'سبب الخسارة (LOST_REASON)';
COMMENT ON COLUMN CRM_LEAD.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON COLUMN CRM_LEAD.CLOSED_DATE IS 'تاريخ الإغلاق (CLOSED_DATE)';
COMMENT ON TABLE CRM_ACTIVITY IS 'أنشطة المتابعة على العميل المحتمل / CRM activities. NEXT_ACTION_DATE موعد المتابعة القادم';
COMMENT ON COLUMN CRM_ACTIVITY.ACT_ID IS 'م (ACT_ID)';
COMMENT ON COLUMN CRM_ACTIVITY.LEAD_ID IS 'رقم العميل المحتمل (LEAD_ID) - FK → CRM_LEAD.LEAD_ID';
COMMENT ON COLUMN CRM_ACTIVITY.ACT_TYPE IS 'نوع النشاط (ACT_TYPE) - القيم: CALL=مكالمة، VISIT=زيارة، MEETING=اجتماع، EMAIL=بريد، WHATSAPP=واتساب، NOTE=ملاحظة';
COMMENT ON COLUMN CRM_ACTIVITY.ACT_DATE IS 'تاريخ النشاط (ACT_DATE)';
COMMENT ON COLUMN CRM_ACTIVITY.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN CRM_ACTIVITY.NEXT_ACTION_DATE IS 'موعد المتابعة (NEXT_ACTION_DATE)';
COMMENT ON COLUMN CRM_ACTIVITY.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON TABLE HD_SLA IS 'مستويات الخدمة SLA حسب الأولوية / helpdesk SLA levels. RESPONSE_HRS ساعات الرد، RESOLVE_HRS ساعات الحل';
COMMENT ON COLUMN HD_SLA.PRIORITY IS 'الأولوية (الأقل أولاً) (PRIORITY)';
COMMENT ON COLUMN HD_SLA.RESPONSE_HRS IS 'ساعات الرد (RESPONSE_HRS)';
COMMENT ON COLUMN HD_SLA.RESOLVE_HRS IS 'ساعات الحل (RESOLVE_HRS)';
COMMENT ON TABLE HD_TICKET IS 'تذاكر الدعم الفني / helpdesk tickets. STATUS: OPEN, ASSIGNED, WAITING, RESOLVED, CLOSED. حالة المهلة في V_HD_SLA_STATUS';
COMMENT ON COLUMN HD_TICKET.TICKET_ID IS 'رقم التذكرة (TICKET_ID)';
COMMENT ON COLUMN HD_TICKET.TITLE IS 'العنوان (TITLE)';
COMMENT ON COLUMN HD_TICKET.DESCRIPTION IS 'البيان (DESCRIPTION)';
COMMENT ON COLUMN HD_TICKET.CATEGORY IS 'الفئة (MAIN أساسي / NON_NATIONAL غير مواطن) (CATEGORY)';
COMMENT ON COLUMN HD_TICKET.PRIORITY IS 'الأولوية (الأقل أولاً) (PRIORITY) - FK → HD_SLA.PRIORITY';
COMMENT ON COLUMN HD_TICKET.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، ASSIGNED=مسندة، WAITING=انتظار، RESOLVED=تم الحل، CLOSED=مغلقة';
COMMENT ON COLUMN HD_TICKET.REQUESTER IS 'مقدم الطلب (REQUESTER)';
COMMENT ON COLUMN HD_TICKET.ASSIGNEE IS 'المسؤول (ASSIGNEE)';
COMMENT ON COLUMN HD_TICKET.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN HD_TICKET.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON COLUMN HD_TICKET.FIRST_RESPONSE_DATE IS 'تاريخ أول رد (FIRST_RESPONSE_DATE)';
COMMENT ON COLUMN HD_TICKET.CLOSED_DATE IS 'تاريخ الإغلاق (CLOSED_DATE)';
COMMENT ON TABLE HD_COMMENT IS 'تعليقات التذكرة / ticket comments.';
COMMENT ON COLUMN HD_COMMENT.COMMENT_ID IS 'م (COMMENT_ID)';
COMMENT ON COLUMN HD_COMMENT.TICKET_ID IS 'رقم التذكرة (TICKET_ID) - FK → HD_TICKET.TICKET_ID';
COMMENT ON COLUMN HD_COMMENT.BODY IS 'النص (BODY)';
COMMENT ON COLUMN HD_COMMENT.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN HD_COMMENT.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE PRJ_PROJECT IS 'المشروعات / projects. COST_CODE مركز التكلفة. الملخص في V_PRJ_SUMMARY';
COMMENT ON COLUMN PRJ_PROJECT.PROJECT_ID IS 'رقم المشروع (PROJECT_ID)';
COMMENT ON COLUMN PRJ_PROJECT.PROJECT_NAME IS 'اسم المشروع (PROJECT_NAME)';
COMMENT ON COLUMN PRJ_PROJECT.CUST_ID IS 'كود العميل (CUST_ID)';
COMMENT ON COLUMN PRJ_PROJECT.COST_CODE IS 'مركز التكلفة (COST_CODE)';
COMMENT ON COLUMN PRJ_PROJECT.START_DATE IS 'بداية العقد (START_DATE)';
COMMENT ON COLUMN PRJ_PROJECT.END_DATE IS 'ينتهي في (END_DATE)';
COMMENT ON COLUMN PRJ_PROJECT.BUDGET IS 'الموازنة (BUDGET)';
COMMENT ON COLUMN PRJ_PROJECT.STATUS IS 'الحالة (STATUS) - القيم: PLANNED=مخطط، ACTIVE=نشط، ON_HOLD=متوقف، DONE=منتهي، CANCELLED=ملغي';
COMMENT ON COLUMN PRJ_PROJECT.MANAGER_USER IS 'مدير المشروع (MANAGER_USER)';
COMMENT ON TABLE PRJ_TASK IS 'مهام المشروع / project tasks. PCT_DONE نسبة الإنجاز';
COMMENT ON COLUMN PRJ_TASK.TASK_ID IS 'رقم المهمة (TASK_ID)';
COMMENT ON COLUMN PRJ_TASK.PROJECT_ID IS 'رقم المشروع (PROJECT_ID) - FK → PRJ_PROJECT.PROJECT_ID';
COMMENT ON COLUMN PRJ_TASK.TASK_NAME IS 'المهمة (TASK_NAME)';
COMMENT ON COLUMN PRJ_TASK.ASSIGNEE IS 'المسؤول (ASSIGNEE)';
COMMENT ON COLUMN PRJ_TASK.PLAN_START IS 'بدء مخطط (PLAN_START)';
COMMENT ON COLUMN PRJ_TASK.PLAN_END IS 'انتهاء مخطط (PLAN_END)';
COMMENT ON COLUMN PRJ_TASK.PCT_DONE IS 'نسبة الإنجاز % (PCT_DONE)';
COMMENT ON COLUMN PRJ_TASK.PLAN_HOURS IS 'ساعات مخططة (PLAN_HOURS)';
COMMENT ON TABLE PRJ_TIME IS 'ساعات العمل على المشروع / project timesheet. HOURS بين 0 و24';
COMMENT ON COLUMN PRJ_TIME.TIME_ID IS 'م (TIME_ID)';
COMMENT ON COLUMN PRJ_TIME.TASK_ID IS 'رقم المهمة (TASK_ID) - FK → PRJ_TASK.TASK_ID';
COMMENT ON COLUMN PRJ_TIME.USER_NAME IS 'المستخدم (USER_NAME)';
COMMENT ON COLUMN PRJ_TIME.WORK_DATE IS 'تاريخ العمل (WORK_DATE)';
COMMENT ON COLUMN PRJ_TIME.HOURS IS 'الساعات (HOURS)';
COMMENT ON COLUMN PRJ_TIME.HOUR_COST IS 'تكلفة الساعة (HOUR_COST)';
COMMENT ON COLUMN PRJ_TIME.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE BOM_HEAD IS 'قوائم المواد (رأس): منتج ودفعة وإصدار / bill of materials header. PRODUCT_ITEMID المنتج. الاحتياج في MRP_EXPLODE';
COMMENT ON COLUMN BOM_HEAD.BOM_ID IS 'رقم القائمة (BOM_ID)';
COMMENT ON COLUMN BOM_HEAD.PRODUCT_ITEMID IS 'كود المنتج (PRODUCT_ITEMID)';
COMMENT ON COLUMN BOM_HEAD.BATCH_QTY IS 'كمية الدفعة (BATCH_QTY)';
COMMENT ON COLUMN BOM_HEAD.VERSION_NO IS 'الإصدار (VERSION_NO)';
COMMENT ON COLUMN BOM_HEAD.ACTIVE_FLAG IS 'نشط (Y/N) (ACTIVE_FLAG)';
COMMENT ON COLUMN BOM_HEAD.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE BOM_LINE IS 'مكونات قائمة المواد / BOM components. SCRAP_PCT نسبة الهالك';
COMMENT ON COLUMN BOM_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN BOM_LINE.BOM_ID IS 'رقم القائمة (BOM_ID) - FK → BOM_HEAD.BOM_ID';
COMMENT ON COLUMN BOM_LINE.COMPONENT_ITEMID IS 'كود المكوّن (COMPONENT_ITEMID)';
COMMENT ON COLUMN BOM_LINE.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN BOM_LINE.SCRAP_PCT IS 'هالك % (SCRAP_PCT)';
COMMENT ON TABLE ANOM_FINDING IS 'ملاحظات الفحص الذكي (فواتير مكررة، أسعار شاذة، قيود غير معتادة) / smart-check findings. RULE_KEY القاعدة. STATUS: NEW, REVIEWED... العتبات من SYS_SETTING (ANOM_*)';
COMMENT ON COLUMN ANOM_FINDING.FINDING_ID IS 'Finding Id (FINDING_ID)';
COMMENT ON COLUMN ANOM_FINDING.RULE_KEY IS 'القاعدة (RULE_KEY)';
COMMENT ON COLUMN ANOM_FINDING.REF_KEY IS 'المرجع (REF_KEY)';
COMMENT ON COLUMN ANOM_FINDING.DETAIL IS 'التفاصيل (DETAIL)';
COMMENT ON COLUMN ANOM_FINDING.SEVERITY IS 'الخطورة (SEVERITY) - القيم: LOW=منخفضة، MEDIUM=متوسطة، HIGH=عالية';
COMMENT ON COLUMN ANOM_FINDING.FOUND_DATE IS 'تاريخ الاكتشاف (FOUND_DATE)';
COMMENT ON COLUMN ANOM_FINDING.STATUS IS 'الحالة (STATUS) - القيم: NEW=جديد، CONFIRMED=مؤكد، DISMISSED=DISMISSED';
COMMENT ON COLUMN ANOM_FINDING.REVIEWED_BY IS 'Reviewed By (REVIEWED_BY)';
COMMENT ON COLUMN ANOM_FINDING.REVIEW_NOTE IS 'Review Note (REVIEW_NOTE)';
COMMENT ON TABLE CHEQUE_LINK IS 'ربط الشيك بعميل/مورد/فاتورة/حركة خزينة / cheque links. LINK_TYPE نوع الربط. REF_ID رقم المرجع';
COMMENT ON COLUMN CHEQUE_LINK.LINK_ID IS 'Link Id (LINK_ID)';
COMMENT ON COLUMN CHEQUE_LINK.CHEQUE_ID IS 'رقم الشيك (النظام) (CHEQUE_ID) - FK → CHEQUES.CHEQUE_ID';
COMMENT ON COLUMN CHEQUE_LINK.LINK_TYPE IS 'نوع الربط (LINK_TYPE) - القيم: INVOICE=فاتورة (رقم مفتاح الفاتورة)، PAYMENT=سداد (رقم السداد)، CASH_TRANS=حركة خزينة (رقم الحركة)، CUSTOMER=عميل / مورد (كود)';
COMMENT ON COLUMN CHEQUE_LINK.REF_ID IS 'رقم المرجع (REF_ID)';
COMMENT ON COLUMN CHEQUE_LINK.AMOUNT IS 'المبلغ (AMOUNT)';
COMMENT ON COLUMN CHEQUE_LINK.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN CHEQUE_LINK.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN CHEQUE_LINK.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE INT_GUARD IS 'مفاتيح الحماية (منع السداد الزائد وفحص الائتمان) / integrity guards. GUARD_NAME: OVERPAY منع سداد أكبر من الفاتورة، CREDIT فحص حد الائتمان في شاشة الفاتورة. ENABLED Y/N';
COMMENT ON COLUMN INT_GUARD.GUARD_NAME IS 'Guard Name (GUARD_NAME)';
COMMENT ON COLUMN INT_GUARD.ENABLED IS 'Enabled (ENABLED) - القيم: Y=Y، N=N';
COMMENT ON COLUMN INT_GUARD.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE PUR_REQ IS 'طلبات الشراء الداخلية / purchase requests. STATUS: DRAFT, SUBMITTED, APPROVED, REJECTED, RFQ, CLOSED';
COMMENT ON COLUMN PUR_REQ.REQ_ID IS 'رقم الطلب (REQ_ID)';
COMMENT ON COLUMN PUR_REQ.REQ_DATE IS 'تاريخ الطلب (REQ_DATE)';
COMMENT ON COLUMN PUR_REQ.REQUESTER IS 'مقدم الطلب (REQUESTER)';
COMMENT ON COLUMN PUR_REQ.DEPT_CODE IS 'القسم (DEPT_CODE)';
COMMENT ON COLUMN PUR_REQ.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، SUBMITTED=مقدّم، APPROVED=معتمدة، REJECTED=مرفوض، RFQ=طلب عروض، CLOSED=مغلقة';
COMMENT ON COLUMN PUR_REQ.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN PUR_REQ.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE PUR_REQ_LINE IS 'أصناف طلب الشراء / purchase request lines.';
COMMENT ON COLUMN PUR_REQ_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN PUR_REQ_LINE.REQ_ID IS 'رقم الطلب (REQ_ID) - FK → PUR_REQ.REQ_ID';
COMMENT ON COLUMN PUR_REQ_LINE.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN PUR_REQ_LINE.UNIT_ID IS 'الوحدة (UNIT_ID)';
COMMENT ON COLUMN PUR_REQ_LINE.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN PUR_REQ_LINE.NEEDED_DATE IS 'مطلوب في (NEEDED_DATE)';
COMMENT ON COLUMN PUR_REQ_LINE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE PUR_RFQ IS 'طلبات عروض الأسعار من الموردين / requests for quotation. STATUS: OPEN, CLOSED, AWARDED, CANCELLED';
COMMENT ON COLUMN PUR_RFQ.RFQ_ID IS 'رقم طلب العروض (RFQ_ID)';
COMMENT ON COLUMN PUR_RFQ.REQ_ID IS 'رقم الطلب (REQ_ID) - FK → PUR_REQ.REQ_ID';
COMMENT ON COLUMN PUR_RFQ.RFQ_DATE IS 'تاريخ الطلب (RFQ_DATE)';
COMMENT ON COLUMN PUR_RFQ.DUE_DATE IS 'الموعد (DUE_DATE)';
COMMENT ON COLUMN PUR_RFQ.STATUS IS 'الحالة (STATUS) - القيم: OPEN=مفتوحة، CLOSED=مغلقة، AWARDED=تمت الترسية، CANCELLED=ملغي';
COMMENT ON COLUMN PUR_RFQ.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE PUR_RFQ_LINE IS 'أصناف طلب العروض / RFQ lines.';
COMMENT ON COLUMN PUR_RFQ_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN PUR_RFQ_LINE.RFQ_ID IS 'رقم طلب العروض (RFQ_ID) - FK → PUR_RFQ.RFQ_ID';
COMMENT ON COLUMN PUR_RFQ_LINE.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN PUR_RFQ_LINE.UNIT_ID IS 'الوحدة (UNIT_ID)';
COMMENT ON COLUMN PUR_RFQ_LINE.QTY IS 'الكمية (QTY)';
COMMENT ON TABLE PUR_RFQ_QUOTE IS 'عروض الموردين لكل بند / supplier quotes. SUPPLIER_ID = CUST.CUSTID (مورد CUST_TYPE=1). المقارنة في V_PUR_QUOTE_COMPARE';
COMMENT ON COLUMN PUR_RFQ_QUOTE.QUOTE_ID IS 'رقم عرض السعر (QUOTE_ID)';
COMMENT ON COLUMN PUR_RFQ_QUOTE.RFQ_ID IS 'رقم طلب العروض (RFQ_ID)';
COMMENT ON COLUMN PUR_RFQ_QUOTE.LINE_ID IS 'رقم السطر (LINE_ID) - FK → PUR_RFQ_LINE.LINE_ID';
COMMENT ON COLUMN PUR_RFQ_QUOTE.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID)';
COMMENT ON COLUMN PUR_RFQ_QUOTE.UNIT_PRICE IS 'سعر الوحدة (UNIT_PRICE)';
COMMENT ON COLUMN PUR_RFQ_QUOTE.LEAD_DAYS IS 'مدة التوريد (يوم) (LEAD_DAYS)';
COMMENT ON COLUMN PUR_RFQ_QUOTE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE PUR_PO IS 'أوامر الشراء / purchase orders. STATUS: DRAFT, SUBMITTED مُرسل للاعتماد, APPROVED, REJECTED, SENT, RECEIVED, CLOSED, CANCELLED. INV_KEY فاتورة المشتريات الفعلية. ORD_ID صف ORDERS المرتبط بدورة الاعتماد';
COMMENT ON COLUMN PUR_PO.PO_ID IS 'رقم أمر الشراء (PO_ID)';
COMMENT ON COLUMN PUR_PO.RFQ_ID IS 'رقم طلب العروض (RFQ_ID) - FK → PUR_RFQ.RFQ_ID';
COMMENT ON COLUMN PUR_PO.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID)';
COMMENT ON COLUMN PUR_PO.PO_DATE IS 'تاريخ الأمر (PO_DATE)';
COMMENT ON COLUMN PUR_PO.STATUS IS 'الحالة (STATUS) - القيم: DRAFT=مسودة، SUBMITTED=مقدّم، APPROVED=معتمدة، REJECTED=مرفوض، SENT=مُرسل، RECEIVED=مستلم، CLOSED=مغلقة، CANCELLED=ملغي';
COMMENT ON COLUMN PUR_PO.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON COLUMN PUR_PO.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN PUR_PO.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY)';
COMMENT ON COLUMN PUR_PO.ORD_ID IS 'Ord Id (ORD_ID)';
COMMENT ON TABLE PUR_PO_LINE IS 'أصناف أمر الشراء والكمية المستلمة / PO lines. RECEIVED_QTY مايزيدش عن QTY';
COMMENT ON COLUMN PUR_PO_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN PUR_PO_LINE.PO_ID IS 'رقم أمر الشراء (PO_ID) - FK → PUR_PO.PO_ID';
COMMENT ON COLUMN PUR_PO_LINE.ITEMID IS 'كود الصنف (ITEMID)';
COMMENT ON COLUMN PUR_PO_LINE.UNIT_ID IS 'الوحدة (UNIT_ID)';
COMMENT ON COLUMN PUR_PO_LINE.QTY IS 'الكمية (QTY)';
COMMENT ON COLUMN PUR_PO_LINE.PRICE IS 'السعر (PRICE)';
COMMENT ON COLUMN PUR_PO_LINE.RECEIVED_QTY IS 'المستلم (RECEIVED_QTY)';
COMMENT ON TABLE FX_RATE IS 'أسعار الصرف / exchange rates. CURRENCY_CODE + RATE_DATE';
COMMENT ON COLUMN FX_RATE.CURRENCY_CODE IS 'كود العملة (CURRENCY_CODE)';
COMMENT ON COLUMN FX_RATE.RATE_DATE IS 'تاريخ السعر (RATE_DATE)';
COMMENT ON COLUMN FX_RATE.RATE IS 'سعر التحويل (RATE)';
COMMENT ON TABLE FX_REVAL_RUN IS 'مقترحات إعادة تقييم العملات (مقترح فقط، بدون قيد) / FX revaluation proposals.';
COMMENT ON COLUMN FX_REVAL_RUN.RUN_ID IS 'رقم التشغيل (RUN_ID)';
COMMENT ON COLUMN FX_REVAL_RUN.RATE_DATE IS 'تاريخ السعر (RATE_DATE)';
COMMENT ON COLUMN FX_REVAL_RUN.STATUS IS 'الحالة (STATUS) - القيم: PROPOSED=مقترح، APPROVED=معتمدة، REJECTED=مرفوض';
COMMENT ON COLUMN FX_REVAL_RUN.CREATED_BY IS 'أنشأه (CREATED_BY)';
COMMENT ON COLUMN FX_REVAL_RUN.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE)';
COMMENT ON TABLE FX_REVAL_LINE IS 'أسطر مقترح إعادة التقييم / FX revaluation lines.';
COMMENT ON COLUMN FX_REVAL_LINE.LINE_ID IS 'رقم السطر (LINE_ID)';
COMMENT ON COLUMN FX_REVAL_LINE.RUN_ID IS 'رقم التشغيل (RUN_ID) - FK → FX_REVAL_RUN.RUN_ID';
COMMENT ON COLUMN FX_REVAL_LINE.CHART_CODE IS 'كود الحساب (CHART_CODE)';
COMMENT ON COLUMN FX_REVAL_LINE.CURRENCY_CODE IS 'كود العملة (CURRENCY_CODE)';
COMMENT ON COLUMN FX_REVAL_LINE.FOREIGN_BALANCE IS 'الرصيد بالعملة (FOREIGN_BALANCE)';
COMMENT ON COLUMN FX_REVAL_LINE.BOOK_VALUE IS 'القيمة الدفترية (BOOK_VALUE)';
COMMENT ON COLUMN FX_REVAL_LINE.REVALUED_VALUE IS 'القيمة بعد التقييم (REVALUED_VALUE)';
COMMENT ON COLUMN FX_REVAL_LINE.DIFFERENCE IS 'الفرق (DIFFERENCE)';
COMMENT ON TABLE CLASS_RULE IS 'قواعد تصنيف حركات الخزينة والبنك (كلمة مفتاحية في البيان ← حساب مقترح) / transaction classification rules. PRIORITY الأقل أولاً ثم أطول كلمة. اقتراح فقط، مفيش سطر بيتغير. تُستخدم في V_BANK_LINE_SUGGEST و V_CASH_LINE_SUGGEST';
COMMENT ON COLUMN CLASS_RULE.RULE_ID IS 'رقم القاعدة (RULE_ID)';
COMMENT ON COLUMN CLASS_RULE.RULE_NAME IS 'اسم القاعدة (RULE_NAME)';
COMMENT ON COLUMN CLASS_RULE.KEYWORD IS 'الكلمة المفتاحية في البيان (KEYWORD)';
COMMENT ON COLUMN CLASS_RULE.CHART_CODE IS 'كود الحساب (CHART_CODE)';
COMMENT ON COLUMN CLASS_RULE.COST_CODE IS 'مركز التكلفة (COST_CODE)';
COMMENT ON COLUMN CLASS_RULE.PRIORITY IS 'الأولوية (الأقل أولاً) (PRIORITY)';
COMMENT ON COLUMN CLASS_RULE.ACTIVE IS 'نشط (Y/N) (ACTIVE) - القيم: Y=Y، N=N';
COMMENT ON COLUMN CLASS_RULE.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE COMPANY_COUNTRY IS 'بلد كل شركة (مصر EG / السعودية SA) / company country. IS_MAIN=Y الشركة الأساسية اللي حسابات المرتبات بتمشي بنسب بلدها. بدونها الأصل مصر';
COMMENT ON COLUMN COMPANY_COUNTRY.COMPANY_CODE IS 'كود الشركة (COMPANY_CODE)';
COMMENT ON COLUMN COMPANY_COUNTRY.COUNTRY_CODE IS 'البلد (EG مصر / SA السعودية) (COUNTRY_CODE) - القيم: EG=EG، SA=SA';
COMMENT ON COLUMN COMPANY_COUNTRY.IS_MAIN IS 'الشركة الأساسية للحساب (Y/N) (IS_MAIN) - القيم: Y=Y، N=N';
COMMENT ON COLUMN COMPANY_COUNTRY.NOTES IS 'ملاحظات / المصدر (NOTES)';
COMMENT ON TABLE V_CHARTS_ORPHANS IS 'حسابات فرعية بلا أب ومقترح أبيها / view v_charts_orphans';
COMMENT ON TABLE V_PAYROLL_STATUTORY IS 'تأمينات وضرائب المرتبات لكل موظف من الجداول القانونية / view v_payroll_statutory';
COMMENT ON TABLE V_HR_RECRUIT_FUNNEL IS 'قمع التوظيف: عدد المتقدمين في كل مرحلة / view v_hr_recruit_funnel';
COMMENT ON TABLE V_HR_GOAL_SCORE IS 'نسبة تحقيق أهداف كل موظف / view v_hr_goal_score';
COMMENT ON TABLE V_HR_TRAINING_SUMMARY IS 'ملخص الدورات التدريبية / view v_hr_training_summary';
COMMENT ON TABLE V_HR_TRAINING_BY_EMP IS 'تدريب كل موظف / view v_hr_training_by_emp';
COMMENT ON TABLE V_MFG_OVERLAP IS 'تعارضات جدول تشغيل الماكينات / view v_mfg_overlap';
COMMENT ON TABLE V_MFG_LOAD IS 'حمل الماكينات الأسبوعي مقابل الطاقة / view v_mfg_load';
COMMENT ON TABLE V_QC_PASS_RATE IS 'نسبة نجاح فحوصات الجودة لكل صنف / view v_qc_pass_rate';
COMMENT ON TABLE V_MFG_VARIANCE IS 'التكلفة المعيارية مقابل الفعلية / view v_mfg_variance';
COMMENT ON TABLE V_MNT_DUE IS 'خطط الصيانة المستحقة أو المتأخرة / view v_mnt_due';
COMMENT ON TABLE V_MNT_COST IS 'تكلفة الصيانة لكل أصل / view v_mnt_cost';
COMMENT ON TABLE V_AST_COUNT_DIFF IS 'نتيجة جرد الأصول: موجود / غير موجود / كود غير معروف / view v_ast_count_diff';
COMMENT ON TABLE V_SAL_QUOTE_TOTAL IS 'إجمالي كل عرض سعر وصلاحيته / view v_sal_quote_total';
COMMENT ON TABLE V_SAL_ORDER_STATUS IS 'أوامر البيع: نسبة التسليم والفوترة / view v_sal_order_status. يحتوي CUST_ID وليس CUSTOMER_NAME — للاسم JOIN justclick.CUST c ON c.CUSTID = s.CUST_ID واستخدم c.CUSTNAME';
COMMENT ON TABLE V_SAL_QUOTE_FUNNEL IS 'قمع عروض الأسعار حسب الحالة / view v_sal_quote_funnel';
COMMENT ON TABLE V_REC_JE_STATUS IS 'حالة قوالب القيود الدورية (مستحق/متوقف/غير متزن) / view v_rec_je_status';
COMMENT ON TABLE V_SAL_NOTE_STATUS IS 'الإشعارات الدائنة والمدينة وقيدها الجاهز / view v_sal_note_status';
COMMENT ON TABLE V_CON_STATUS IS 'حالة العقود والمستحق عليها / view v_con_status';
COMMENT ON TABLE V_CON_BILLS_DUE IS 'مطالبات العقود اللي لسه ما اتفوترتش / view v_con_bills_due';
COMMENT ON TABLE V_PUR_PO_INVOICE IS 'أمر الشراء مقابل فاتورة المورد والفرق / view v_pur_po_invoice';
COMMENT ON TABLE V_ALLOC_RULE_STATUS IS 'جاهزية قواعد توزيع التكاليف / view v_alloc_rule_status';
COMMENT ON TABLE V_EXP_CLAIM_STATUS IS 'طلبات المصروفات والسلف وإجماليها / view v_exp_claim_status';
COMMENT ON TABLE V_AUDIT_LOG IS 'سجل التدقيق مقروء / view v_audit_log';
COMMENT ON TABLE V_MY_NOTIFICATIONS IS 'إشعارات المستخدم / view v_my_notifications';
COMMENT ON TABLE V_DMS_CURRENT IS 'أحدث إصدار لكل مستند / view v_dms_current';
COMMENT ON TABLE V_HEALTH_LATEST IS 'آخر لقطة لصحة النظام / view v_health_latest';
COMMENT ON TABLE V_PAGE_ACCESS_COVERAGE IS 'تغطية الصلاحيات للصفحات / view v_page_access_coverage';
COMMENT ON TABLE V_PAGE_FORMS IS 'ربط الصفحات بالشاشات / view v_page_forms';
COMMENT ON TABLE V_PAGE_ACCESS_IMPACT IS 'أثر تفعيل صلاحيات الصفحات / view v_page_access_impact';
COMMENT ON TABLE V_TRANSFER_STATUS IS 'تحويلات المخازن: مستلم / في الطريق / استلام جزئي (نوع حركة 5) / view v_transfer_status. ⚠ لاستعلام غير المستلم استخدم: WHERE STATE != ''تم الاستلام'' — لا تفلتر بقيمة STATE محددة لأن غير المستلم يشمل أكثر من حالة';
COMMENT ON TABLE V_TRANSFER_IN_TRANSIT IS 'المنتظر بين كل فرعين وأقدمه / view v_transfer_in_transit';
COMMENT ON TABLE V_AUTOPOST_PENDING IS 'قيود وسيطة لسه ما اترحلتش للأستاذ وحالتها (جاهز/غير متزن/حساب غير موجود/فترة مقفولة) / view v_autopost_pending';
COMMENT ON TABLE V_CONS_UNMAPPED IS 'حسابات شركات غير مربوطة بحسابات المجموعة / view v_cons_unmapped';
COMMENT ON TABLE V_CONS_TRIAL IS 'ميزان المراجعة الموحد بعد الاستبعاد / view v_cons_trial';
COMMENT ON TABLE V_CONS_CHECK IS 'اتزان ميزان كل شركة / view v_cons_check';
COMMENT ON TABLE V_FLT_DOC_ALERT IS 'رخص وتأمين وصيانة مركبات قاربت أو انتهت / view v_flt_doc_alert';
COMMENT ON TABLE V_FLT_COST IS 'تكلفة المركبة وتكلفة الكيلو واللترات/100كم / view v_flt_cost';
COMMENT ON TABLE V_LOG_TRIP_STATUS IS 'حالة الرحلات ونسبة النجاح / view v_log_trip_status';
COMMENT ON TABLE V_LOG_DRIVER_PERF IS 'أداء السائقين / view v_log_driver_perf';
COMMENT ON TABLE V_QMS_DOC_REVIEW IS 'مستندات جودة مراجعتها متأخرة أو قريبة / view v_qms_doc_review';
COMMENT ON TABLE V_QMS_CAPA_STATUS IS 'الإجراءات التصحيحية والالتزام بالميعاد / view v_qms_capa_status';
COMMENT ON TABLE V_BUD_VS_ACTUAL IS 'الموازنة مقابل الفعلي / view v_bud_vs_actual';
COMMENT ON TABLE V_BANK_BOOK_TRANS IS 'حركات دفتر البنك للمطابقة / view v_bank_book_trans';
COMMENT ON TABLE V_BANK_RECON_SUMMARY IS 'ملخص مطابقة كشوف البنك / view v_bank_recon_summary';
COMMENT ON TABLE V_CLOSE_LAST_RUN IS 'آخر فحص إقفال / view v_close_last_run';
COMMENT ON TABLE V_VAT_MONTHLY IS 'ضريبة القيمة المضافة شهري / view v_vat_monthly';
COMMENT ON TABLE V_VAT_SUMMARY IS 'صافي ضريبة المبيعات والمشتريات / view v_vat_summary';
COMMENT ON TABLE V_CFO_MONTHLY IS 'مبيعات ومشتريات شهرية / view v_cfo_monthly';
COMMENT ON TABLE V_CASH_POSITION IS 'أرصدة الخزائن والبنوك الآن / view v_cash_position';
COMMENT ON TABLE V_INV_OPEN IS 'فواتير بيع أجل مفتوحة (CASH_FLAG=1 أجل، 2 نقدي) / view v_inv_open';
COMMENT ON TABLE V_PARTY_BALANCE IS 'رصيد العميل/المورد الرسمي من دفتر العميل / view v_party_balance';
COMMENT ON TABLE V_AGING IS 'أعمار الديون بالـ FIFO على رصيد الدفتر / view v_aging';
COMMENT ON TABLE V_AR_AGING IS 'أعمار ديون العملاء / view v_ar_aging';
COMMENT ON TABLE V_AP_AGING IS 'أعمار ديون الموردين / view v_ap_aging';
COMMENT ON TABLE V_SALES_BY_DEALER IS 'المبيعات لكل مندوب / view v_sales_by_dealer';
COMMENT ON TABLE V_COMMISSION IS 'العمولات المحسوبة / view v_commission';
COMMENT ON TABLE V_REORDER IS 'أصناف تحت حد الطلب / view v_reorder';
COMMENT ON TABLE V_EXPIRY_ALERT IS 'تنبيهات الصلاحية (الحدود من الإعدادات) / view v_expiry_alert';
COMMENT ON TABLE V_SUPPLIER_EVAL IS 'تقييم الموردين / view v_supplier_eval';
COMMENT ON TABLE V_ORDER_MATCH IS 'مطابقة ثلاثية: مطلوب/مسلّم/مفوتر / view v_order_match';
COMMENT ON TABLE V_PAYSLIP IS 'قسيمة المرتب / view v_payslip';
COMMENT ON TABLE V_PAYROLL_NET IS 'صافي المرتبات / view v_payroll_net';
COMMENT ON TABLE V_PAYROLL_BANK_FILE IS 'ملف تحويل المرتبات للبنك / view v_payroll_bank_file';
COMMENT ON TABLE V_PAYROLL_NO_BANK IS 'موظفون بلا حساب بنك / view v_payroll_no_bank';
COMMENT ON TABLE V_LEAVE_BALANCE IS 'أرصدة الإجازات / view v_leave_balance';
COMMENT ON TABLE V_HEADCOUNT IS 'أعداد الموظفين / view v_headcount';
COMMENT ON TABLE V_EMP_DOC_EXPIRY IS 'مستندات موظفين منتهية / view v_emp_doc_expiry';
COMMENT ON TABLE V_CRM_PIPELINE IS 'مسار الفرص / view v_crm_pipeline';
COMMENT ON TABLE V_CRM_FOLLOWUP IS 'متابعات CRM المستحقة / view v_crm_followup';
COMMENT ON TABLE V_HD_SLA_STATUS IS 'حالة مهلة التذاكر / view v_hd_sla_status';
COMMENT ON TABLE V_PRJ_SUMMARY IS 'ملخص تكلفة وإنجاز المشروع / view v_prj_summary';
COMMENT ON TABLE V_SALES_FORECAST IS 'توقع المبيعات (اتجاه خطي، الشهور من الإعدادات) / view v_sales_forecast';
COMMENT ON TABLE V_EXEC_KPI IS 'المؤشرات التنفيذية / view v_exec_kpi';
COMMENT ON TABLE V_INT_SWITCHES IS 'حالة ربط الأنظمة بالحسابات / view v_int_switches';
COMMENT ON TABLE V_INT_PENDING IS 'مستندات منتظرة الترحيل للحسابات / view v_int_pending';
COMMENT ON TABLE V_CHEQUE_LINK_SUMMARY IS 'الشيكات ومدى ربطها / view v_cheque_link_summary';
COMMENT ON TABLE V_INT_CASH_VS_LEDGER IS 'رصيد الخزينة مقابل الأستاذ / view v_int_cash_vs_ledger';
COMMENT ON TABLE V_INT_CHECKS IS 'فحوصات التكامل بين الأنظمة والحسابات / view v_int_checks';
COMMENT ON TABLE V_INT_CHECK_DETAIL IS 'تفاصيل مشاكل التكامل / view v_int_check_detail';
COMMENT ON TABLE V_PUR_QUOTE_COMPARE IS 'مقارنة عروض الموردين وأقل سعر / view v_pur_quote_compare';
COMMENT ON TABLE V_PUR_RFQ_SUPPLIER_TOTAL IS 'إجمالي عرض كل مورد / view v_pur_rfq_supplier_total';
COMMENT ON TABLE V_PUR_PO_STATUS IS 'أوامر الشراء ونسبة الاستلام / view v_pur_po_status';
COMMENT ON TABLE V_FIN_CHARTS_U IS 'دليل الحسابات بدون تكرار / view v_fin_charts_u';
COMMENT ON TABLE V_FIN_ROLLUP IS 'تجميع الحسابات العامة على فروعها / view v_fin_rollup';
COMMENT ON TABLE V_FIN_LEAF_YEAR IS 'حركة الحسابات الفرعية بالسنة / view v_fin_leaf_year';
COMMENT ON TABLE V_FIN_LAST_YEAR IS 'آخر سنة مالية وسابقتها / view v_fin_last_year';
COMMENT ON TABLE V_FIN_TRIAL_BALANCE IS 'ميزان المراجعة / view v_fin_trial_balance';
COMMENT ON TABLE V_FIN_INCOME_COMPARE IS 'قائمة الدخل المقارنة / view v_fin_income_compare';
COMMENT ON TABLE V_FIN_BALANCE_SHEET IS 'المركز المالي المقارن / view v_fin_balance_sheet';
COMMENT ON TABLE V_FIN_CASHFLOW_MONTHLY IS 'التدفقات النقدية الشهرية / view v_fin_cashflow_monthly';
COMMENT ON TABLE V_FX_REVAL_SUMMARY IS 'ملخص إعادة تقييم العملات / view v_fx_reval_summary';
COMMENT ON TABLE V_CASH_LINE_SUGGEST IS 'أسطر الخزينة بلا حساب والحساب المقترح من قواعد التصنيف / view v_cash_line_suggest';
COMMENT ON TABLE V_ITEM_VALUATION IS 'تقييم المخزون بالسعر المسجل والمتوسط المرجح وآخر سعر شراء (FIFO غير متاح) / view v_item_valuation';
COMMENT ON TABLE V_DB_SIZE IS 'حجم جداول القاعدة بالميجا / view v_db_size';

-- ============================================================
--  Column comments for the views above (generated from the database, 7 Nov 2026)
-- ============================================================
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.VOUCHER_CODE IS 'رقم القيد (VOUCHER_CODE) - رقم';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.VOUCHER_DATE IS 'تاريخ القيد (VOUCHER_DATE) - تاريخ';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.DOC_ID IS 'DOC_ID - رقم';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.VOUCHER_DESC IS 'البيان (VOUCHER_DESC) - نص';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.CURRENCY_CODE IS 'العملة (CURRENCY_CODE) - رقم';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.FACTOR IS 'FACTOR - رقم';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.DOC_NUM IS 'DOC_NUM - رقم';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.INV_TRANS_TYPE IS 'INV_TRANS_TYPE - رقم';
COMMENT ON COLUMN VOUCHERS_SAL_PURCH_TOT.POSTED_VOUCHER_CODE IS 'POSTED_VOUCHER_CODE - رقم';
COMMENT ON COLUMN V_AGING.INVTYPE IS 'INVTYPE - رقم';
COMMENT ON COLUMN V_AGING.PARTY_KIND IS 'الطرف (PARTY_KIND) - نص';
COMMENT ON COLUMN V_AGING.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_AGING.CUST_NAME IS 'الاسم (CUST_NAME) - نص';
COMMENT ON COLUMN V_AGING.CREDIT_LIMIT IS 'حد الائتمان (CREDIT_LIMIT) - رقم';
COMMENT ON COLUMN V_AGING.OPEN_INVOICES IS 'فواتير مفتوحة (OPEN_INVOICES) - رقم';
COMMENT ON COLUMN V_AGING.TOTAL_OPEN IS 'إجمالي المستحق (TOTAL_OPEN) - رقم';
COMMENT ON COLUMN V_AGING.NOT_DUE IS 'غير مستحق (NOT_DUE) - رقم';
COMMENT ON COLUMN V_AGING.D_1_30 IS '1-30 يوم (D_1_30) - رقم';
COMMENT ON COLUMN V_AGING.D_31_60 IS '31-60 يوم (D_31_60) - رقم';
COMMENT ON COLUMN V_AGING.D_61_90 IS '61-90 يوم (D_61_90) - رقم';
COMMENT ON COLUMN V_AGING.D_OVER_90 IS 'أكثر من 90 (D_OVER_90) - رقم';
COMMENT ON COLUMN V_AGING.MAX_DAYS_OVERDUE IS 'أقصى تأخير (MAX_DAYS_OVERDUE) - رقم';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.RULE_ID IS 'رقم القاعدة (RULE_ID) - رقم';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.RULE_NAME IS 'اسم القاعدة (RULE_NAME) - نص';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.SOURCE_CHART_CODE IS 'حساب المصدر (SOURCE_CHART_CODE) - نص';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.SOURCE_COST_CODE IS 'مركز تكلفة المصدر (SOURCE_COST_CODE) - رقم';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.ACTIVE IS 'نشط (ACTIVE) - نص';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.TARGETS_COUNT IS 'عدد الأهداف (TARGETS_COUNT) - رقم';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.PCT_TOTAL IS 'مجموع النسب (PCT_TOTAL) - رقم';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_ALLOC_RULE_STATUS.LAST_ALLOCATED_TO IS 'آخر فترة اتوزعت (LAST_ALLOCATED_TO) - تاريخ';
COMMENT ON COLUMN V_AP_AGING.INVTYPE IS 'INVTYPE - رقم';
COMMENT ON COLUMN V_AP_AGING.PARTY_KIND IS 'الطرف (PARTY_KIND) - نص';
COMMENT ON COLUMN V_AP_AGING.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_AP_AGING.CUST_NAME IS 'الاسم (CUST_NAME) - نص';
COMMENT ON COLUMN V_AP_AGING.CREDIT_LIMIT IS 'حد الائتمان (CREDIT_LIMIT) - رقم';
COMMENT ON COLUMN V_AP_AGING.OPEN_INVOICES IS 'فواتير مفتوحة (OPEN_INVOICES) - رقم';
COMMENT ON COLUMN V_AP_AGING.TOTAL_OPEN IS 'إجمالي المستحق (TOTAL_OPEN) - رقم';
COMMENT ON COLUMN V_AP_AGING.NOT_DUE IS 'غير مستحق (NOT_DUE) - رقم';
COMMENT ON COLUMN V_AP_AGING.D_1_30 IS '1-30 يوم (D_1_30) - رقم';
COMMENT ON COLUMN V_AP_AGING.D_31_60 IS '31-60 يوم (D_31_60) - رقم';
COMMENT ON COLUMN V_AP_AGING.D_61_90 IS '61-90 يوم (D_61_90) - رقم';
COMMENT ON COLUMN V_AP_AGING.D_OVER_90 IS 'أكثر من 90 (D_OVER_90) - رقم';
COMMENT ON COLUMN V_AP_AGING.MAX_DAYS_OVERDUE IS 'أقصى تأخير (MAX_DAYS_OVERDUE) - رقم';
COMMENT ON COLUMN V_AR_AGING.INVTYPE IS 'INVTYPE - رقم';
COMMENT ON COLUMN V_AR_AGING.PARTY_KIND IS 'الطرف (PARTY_KIND) - نص';
COMMENT ON COLUMN V_AR_AGING.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_AR_AGING.CUST_NAME IS 'الاسم (CUST_NAME) - نص';
COMMENT ON COLUMN V_AR_AGING.CREDIT_LIMIT IS 'حد الائتمان (CREDIT_LIMIT) - رقم';
COMMENT ON COLUMN V_AR_AGING.OPEN_INVOICES IS 'فواتير مفتوحة (OPEN_INVOICES) - رقم';
COMMENT ON COLUMN V_AR_AGING.TOTAL_OPEN IS 'إجمالي المستحق (TOTAL_OPEN) - رقم';
COMMENT ON COLUMN V_AR_AGING.NOT_DUE IS 'غير مستحق (NOT_DUE) - رقم';
COMMENT ON COLUMN V_AR_AGING.D_1_30 IS '1-30 يوم (D_1_30) - رقم';
COMMENT ON COLUMN V_AR_AGING.D_31_60 IS '31-60 يوم (D_31_60) - رقم';
COMMENT ON COLUMN V_AR_AGING.D_61_90 IS '61-90 يوم (D_61_90) - رقم';
COMMENT ON COLUMN V_AR_AGING.D_OVER_90 IS 'أكثر من 90 (D_OVER_90) - رقم';
COMMENT ON COLUMN V_AR_AGING.MAX_DAYS_OVERDUE IS 'أقصى تأخير (MAX_DAYS_OVERDUE) - رقم';
COMMENT ON COLUMN V_AST_COUNT_DIFF.COUNT_ID IS 'COUNT_ID - رقم';
COMMENT ON COLUMN V_AST_COUNT_DIFF.ASSETS_ID IS 'الأصل (ASSETS_ID) - رقم';
COMMENT ON COLUMN V_AST_COUNT_DIFF.ASSET_CODE IS 'كود الأصل (ASSET_CODE) - نص';
COMMENT ON COLUMN V_AST_COUNT_DIFF.ASSET_NAME_AR IS 'اسم الأصل (ASSET_NAME_AR) - نص';
COMMENT ON COLUMN V_AST_COUNT_DIFF.EXPECTED_LOC IS 'المكان المتوقع (EXPECTED_LOC) - رقم';
COMMENT ON COLUMN V_AST_COUNT_DIFF.RESULT IS 'النتيجة (RESULT) - نص';
COMMENT ON COLUMN V_AST_COUNT_DIFF.FOUND_LOC_ID IS 'مكان الجرد (FOUND_LOC_ID) - رقم';
COMMENT ON COLUMN V_AST_COUNT_DIFF.LOCATION_NOTE IS 'ملاحظة المكان (LOCATION_NOTE) - نص';
COMMENT ON COLUMN V_AUDIT_LOG.AUDIT_ID IS 'رقم المراجعة (AUDIT_ID) - رقم';
COMMENT ON COLUMN V_AUDIT_LOG.AUDIT_DATE IS 'تاريخ المراجعة (AUDIT_DATE) - نص';
COMMENT ON COLUMN V_AUDIT_LOG.TABLE_NAME IS 'الجدول (TABLE_NAME) - نص';
COMMENT ON COLUMN V_AUDIT_LOG.ACTION IS 'ACTION - نص';
COMMENT ON COLUMN V_AUDIT_LOG.ACTION_LABEL IS 'ACTION_LABEL - نص';
COMMENT ON COLUMN V_AUDIT_LOG.PK_VALUE IS 'PK_VALUE - نص';
COMMENT ON COLUMN V_AUDIT_LOG.CHANGED_COLS IS 'CHANGED_COLS - نص';
COMMENT ON COLUMN V_AUDIT_LOG.APP_USER IS 'APP_USER - نص';
COMMENT ON COLUMN V_AUDIT_LOG.DB_USER IS 'DB_USER - نص';
COMMENT ON COLUMN V_AUDIT_LOG.OLD_DATA IS 'OLD_DATA - نص';
COMMENT ON COLUMN V_AUDIT_LOG.NEW_DATA IS 'NEW_DATA - نص';
COMMENT ON COLUMN V_AUTOPOST_PENDING.SOURCE_KEY IS 'المصدر (SOURCE_KEY) - نص';
COMMENT ON COLUMN V_AUTOPOST_PENDING.SOURCE_NAME IS 'اسم المصدر (SOURCE_NAME) - نص';
COMMENT ON COLUMN V_AUTOPOST_PENDING.VOUCHER_CODE IS 'رقم القيد (VOUCHER_CODE) - رقم';
COMMENT ON COLUMN V_AUTOPOST_PENDING.VOUCHER_DATE IS 'تاريخ القيد (VOUCHER_DATE) - تاريخ';
COMMENT ON COLUMN V_AUTOPOST_PENDING.VOUCHER_DESC IS 'البيان (VOUCHER_DESC) - نص';
COMMENT ON COLUMN V_AUTOPOST_PENDING.IMBALANCE IS 'فرق عدم الاتزان (IMBALANCE) - رقم';
COMMENT ON COLUMN V_AUTOPOST_PENDING.BAD_ACCOUNTS IS 'حسابات غير موجودة (BAD_ACCOUNTS) - رقم';
COMMENT ON COLUMN V_AUTOPOST_PENDING.STATE IS 'حالة القيد الوسيط (STATE) - القيم بالنص بالظبط: ''جاهز للترحيل'' / ''غير متزن'' / ''حساب غير موجود'' / ''فترة مقفولة''. اللي لسه ماترحلش هو كل الصفوف في العرض (العرض أصلًا بيستبعد المترحّل)';
COMMENT ON COLUMN V_BANK_BOOK_TRANS.CASH_ID IS 'CASH_ID - رقم';
COMMENT ON COLUMN V_BANK_BOOK_TRANS.TRANS_ID IS 'TRANS_ID - رقم';
COMMENT ON COLUMN V_BANK_BOOK_TRANS.TRANS_DATE IS 'التاريخ (TRANS_DATE) - تاريخ';
COMMENT ON COLUMN V_BANK_BOOK_TRANS.TRANS_TYPE IS 'TRANS_TYPE - رقم';
COMMENT ON COLUMN V_BANK_BOOK_TRANS.NOTES IS 'NOTES - نص';
COMMENT ON COLUMN V_BANK_BOOK_TRANS.SIGNED_AMOUNT IS 'SIGNED_AMOUNT - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.STMT_ID IS 'رقم الكشف (STMT_ID) - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.CASH_ID IS 'CASH_ID - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.CASH_NAME IS 'الخزينة / البنك (CASH_NAME) - نص';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.STMT_FROM IS 'STMT_FROM - تاريخ';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.STMT_TO IS 'STMT_TO - تاريخ';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.OPENING_BAL IS 'OPENING_BAL - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.CLOSING_BAL IS 'CLOSING_BAL - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.LINES_TOTAL IS 'بنود الطلب (LINES_TOTAL) - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.LINES_MATCHED IS 'المطابق (LINES_MATCHED) - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.LINES_UNMATCHED IS 'غير المطابق (LINES_UNMATCHED) - رقم';
COMMENT ON COLUMN V_BANK_RECON_SUMMARY.UNMATCHED_NET IS 'صافي غير المطابق (UNMATCHED_NET) - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.BUD_ID IS 'BUD_ID - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.BUD_YEAR IS 'BUD_YEAR - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.BUD_NAME IS 'اسم الموازنة (BUD_NAME) - نص';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.LINE_ID IS 'رقم السطر (LINE_ID) - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.COST_CODE IS 'COST_CODE - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.BUD_MONTH IS 'الشهر (BUD_MONTH) - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.SIDE IS 'SIDE - نص';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.BUDGET_AMOUNT IS 'الموازنة (BUDGET_AMOUNT) - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.ACTUAL_AMOUNT IS 'الفعلي (ACTUAL_AMOUNT) - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.VARIANCE IS 'الفرق (VARIANCE) - رقم';
COMMENT ON COLUMN V_BUD_VS_ACTUAL.VARIANCE_PCT IS 'نسبة الفرق % (VARIANCE_PCT) - رقم';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.TRANS_ID IS 'TRANS_ID - رقم';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.SERIAL IS 'SERIAL - رقم';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.NOTES_DETAIL IS 'NOTES_DETAIL - نص';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.RULE_ID IS 'رقم القاعدة (RULE_ID) - رقم';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.RULE_NAME IS 'اسم القاعدة (RULE_NAME) - نص';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.SUGGESTED_CHART IS 'الحساب المقترح (SUGGESTED_CHART) - نص';
COMMENT ON COLUMN V_CASH_LINE_SUGGEST.SUGGESTED_COST IS 'مركز التكلفة المقترح (SUGGESTED_COST) - رقم';
COMMENT ON COLUMN V_CASH_POSITION.CASH_ID IS 'CASH_ID - رقم';
COMMENT ON COLUMN V_CASH_POSITION.CASH_NAME IS 'الخزينة / البنك (CASH_NAME) - نص';
COMMENT ON COLUMN V_CASH_POSITION.BANK_ACC_NO IS 'BANK_ACC_NO - نص';
COMMENT ON COLUMN V_CASH_POSITION.KIND IS 'النوع (KIND) - نص';
COMMENT ON COLUMN V_CASH_POSITION.BALANCE IS 'الرصيد (BALANCE) - رقم';
COMMENT ON COLUMN V_CFO_MONTHLY.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_CFO_MONTHLY.NET_SALES IS 'صافي المبيعات (NET_SALES) - رقم';
COMMENT ON COLUMN V_CFO_MONTHLY.NET_PURCHASES IS 'صافي المشتريات (NET_PURCHASES) - رقم';
COMMENT ON COLUMN V_CFO_MONTHLY.SALES_INVOICES IS 'فواتير بيع (SALES_INVOICES) - رقم';
COMMENT ON COLUMN V_CFO_MONTHLY.PURCHASE_INVOICES IS 'فواتير شراء (PURCHASE_INVOICES) - رقم';
COMMENT ON COLUMN V_CHARTS_ORPHANS.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_CHARTS_ORPHANS.CHART_NAME_A IS 'CHART_NAME_A - نص';
COMMENT ON COLUMN V_CHARTS_ORPHANS.CHART_NATURE IS 'CHART_NATURE - رقم';
COMMENT ON COLUMN V_CHARTS_ORPHANS.CHART_LEVEL IS 'المستوى (CHART_LEVEL) - رقم';
COMMENT ON COLUMN V_CHARTS_ORPHANS.PROPOSED_PARENT IS 'PROPOSED_PARENT - نص';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.CHEQUE_ID IS 'رقم الشيك (النظام) (CHEQUE_ID) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.CHEQUE_CODE IS 'كود الشيك (CHEQUE_CODE) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.CHEQUE_NUMBER IS 'رقم الشيك (CHEQUE_NUMBER) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.BANK_NAME IS 'البنك (BANK_NAME) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.DUE_DATE IS 'تاريخ الاستحقاق (DUE_DATE) - تاريخ';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.CHEQUE_STATUS IS 'حالة الشيك (CHEQUE_STATUS) - نص';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.SETTLED_AMOUNT IS 'المسدد (SETTLED_AMOUNT) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.LINKED_AMOUNT IS 'المربوط (LINKED_AMOUNT) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.LINKS IS 'عدد الروابط (LINKS) - رقم';
COMMENT ON COLUMN V_CHEQUE_LINK_SUMMARY.LINK_STATE IS 'حالة الربط (LINK_STATE) - نص';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.RUN_ID IS 'رقم التشغيل (RUN_ID) - رقم';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.RUN_DATE IS 'وقت التشغيل (RUN_DATE) - تاريخ';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.RUN_BY IS 'RUN_BY - نص';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.PERIOD_FROM IS 'PERIOD_FROM - تاريخ';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.PERIOD_TO IS 'PERIOD_TO - تاريخ';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.CHECK_KEY IS 'كود الفحص (CHECK_KEY) - نص';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.LABEL IS 'الفحص (LABEL) - نص';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.ISSUES IS 'عدد المشاكل (ISSUES) - رقم';
COMMENT ON COLUMN V_CLOSE_LAST_RUN.SEVERITY IS 'الخطورة (SEVERITY) - نص';
COMMENT ON COLUMN V_COMMISSION.DEALER_ID IS 'المندوب (DEALER_ID) - رقم';
COMMENT ON COLUMN V_COMMISSION.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_COMMISSION.INVOICES IS 'عدد الفواتير (INVOICES) - رقم';
COMMENT ON COLUMN V_COMMISSION.NET_SALES IS 'صافي المبيعات (NET_SALES) - رقم';
COMMENT ON COLUMN V_COMMISSION.PCT IS 'النسبة (PCT) - رقم';
COMMENT ON COLUMN V_COMMISSION.COMMISSION IS 'العمولة (COMMISSION) - رقم';
COMMENT ON COLUMN V_CONS_CHECK.CO_NAME IS 'اسم الشركة (CO_NAME) - نص';
COMMENT ON COLUMN V_CONS_CHECK.AS_OF IS 'بتاريخ (AS_OF) - تاريخ';
COMMENT ON COLUMN V_CONS_CHECK.TOTAL_DEBIT IS 'إجمالي المدين (TOTAL_DEBIT) - رقم';
COMMENT ON COLUMN V_CONS_CHECK.TOTAL_CREDIT IS 'إجمالي الدائن (TOTAL_CREDIT) - رقم';
COMMENT ON COLUMN V_CONS_CHECK.DIFF IS 'الفرق (DIFF) - رقم';
COMMENT ON COLUMN V_CONS_CHECK.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_CONS_CHECK.UNMAPPED_ACCOUNTS IS 'حسابات غير مربوطة (UNMAPPED_ACCOUNTS) - رقم';
COMMENT ON COLUMN V_CONS_TRIAL.AS_OF IS 'بتاريخ (AS_OF) - تاريخ';
COMMENT ON COLUMN V_CONS_TRIAL.GROUP_CODE IS 'كود حساب المجموعة (GROUP_CODE) - نص';
COMMENT ON COLUMN V_CONS_TRIAL.GROUP_NAME IS 'اسم حساب المجموعة (GROUP_NAME) - نص';
COMMENT ON COLUMN V_CONS_TRIAL.GROUP_TYPE IS 'النوع (GROUP_TYPE) - نص';
COMMENT ON COLUMN V_CONS_TRIAL.BEFORE_ELIMINATION IS 'قبل الاستبعاد (BEFORE_ELIMINATION) - رقم';
COMMENT ON COLUMN V_CONS_TRIAL.ELIMINATIONS IS 'الاستبعادات (ELIMINATIONS) - رقم';
COMMENT ON COLUMN V_CONS_TRIAL.CONSOLIDATED_NET IS 'الصافي الموحد (CONSOLIDATED_NET) - رقم';
COMMENT ON COLUMN V_CONS_TRIAL.CONSOLIDATED_DEBIT IS 'موحد مدين (CONSOLIDATED_DEBIT) - رقم';
COMMENT ON COLUMN V_CONS_TRIAL.CONSOLIDATED_CREDIT IS 'موحد دائن (CONSOLIDATED_CREDIT) - رقم';
COMMENT ON COLUMN V_CONS_UNMAPPED.CO_ID IS 'رقم الشركة (CO_ID) - رقم';
COMMENT ON COLUMN V_CONS_UNMAPPED.CO_NAME IS 'اسم الشركة (CO_NAME) - نص';
COMMENT ON COLUMN V_CONS_UNMAPPED.AS_OF IS 'بتاريخ (AS_OF) - تاريخ';
COMMENT ON COLUMN V_CONS_UNMAPPED.CO_ACCOUNT IS 'حساب الشركة (CO_ACCOUNT) - نص';
COMMENT ON COLUMN V_CONS_UNMAPPED.ACCOUNT_NAME IS 'الحساب (ACCOUNT_NAME) - نص';
COMMENT ON COLUMN V_CONS_UNMAPPED.NET_AMOUNT IS 'الصافي (NET_AMOUNT) - رقم';
COMMENT ON COLUMN V_CON_BILLS_DUE.BILL_ID IS 'رقم المطالبة (BILL_ID) - رقم';
COMMENT ON COLUMN V_CON_BILLS_DUE.CONTRACT_ID IS 'رقم العقد (CONTRACT_ID) - رقم';
COMMENT ON COLUMN V_CON_BILLS_DUE.CONTRACT_NAME IS 'اسم العقد (CONTRACT_NAME) - نص';
COMMENT ON COLUMN V_CON_BILLS_DUE.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_CON_BILLS_DUE.CUSTOMER_NAME IS 'العميل (CUSTOMER_NAME) - نص';
COMMENT ON COLUMN V_CON_BILLS_DUE.PERIOD_DATE IS 'تاريخ الاستحقاق (PERIOD_DATE) - تاريخ';
COMMENT ON COLUMN V_CON_BILLS_DUE.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_CON_BILLS_DUE.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_CON_BILLS_DUE.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY) - رقم';
COMMENT ON COLUMN V_CON_BILLS_DUE.DAYS_LATE IS 'أيام التأخير (DAYS_LATE) - رقم';
COMMENT ON COLUMN V_CON_STATUS.CONTRACT_ID IS 'رقم العقد (CONTRACT_ID) - رقم';
COMMENT ON COLUMN V_CON_STATUS.CONTRACT_NAME IS 'اسم العقد (CONTRACT_NAME) - نص';
COMMENT ON COLUMN V_CON_STATUS.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_CON_STATUS.CUSTOMER_NAME IS 'العميل (CUSTOMER_NAME) - نص';
COMMENT ON COLUMN V_CON_STATUS.START_DATE IS 'بداية العقد (START_DATE) - تاريخ';
COMMENT ON COLUMN V_CON_STATUS.END_DATE IS 'ينتهي في (END_DATE) - تاريخ';
COMMENT ON COLUMN V_CON_STATUS.FREQ IS 'التكرار (FREQ) - نص';
COMMENT ON COLUMN V_CON_STATUS.NEXT_BILL_DATE IS 'موعد الفاتورة القادم (NEXT_BILL_DATE) - تاريخ';
COMMENT ON COLUMN V_CON_STATUS.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_CON_STATUS.ACTIVE IS 'نشط (ACTIVE) - نص';
COMMENT ON COLUMN V_CON_STATUS.PENDING_BILLS IS 'فواتير مستحقة (PENDING_BILLS) - رقم';
COMMENT ON COLUMN V_CON_STATUS.PENDING_AMOUNT IS 'قيمة المستحق (PENDING_AMOUNT) - رقم';
COMMENT ON COLUMN V_CON_STATUS.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_CRM_FOLLOWUP.LEAD_ID IS 'LEAD_ID - رقم';
COMMENT ON COLUMN V_CRM_FOLLOWUP.LEAD_NAME IS 'LEAD_NAME - نص';
COMMENT ON COLUMN V_CRM_FOLLOWUP.OWNER_USER IS 'المسؤول (OWNER_USER) - نص';
COMMENT ON COLUMN V_CRM_FOLLOWUP.STAGE IS 'المرحلة (STAGE) - نص';
COMMENT ON COLUMN V_CRM_FOLLOWUP.NEXT_ACTION_DATE IS 'NEXT_ACTION_DATE - تاريخ';
COMMENT ON COLUMN V_CRM_FOLLOWUP.DAYS_LATE IS 'أيام التأخير (DAYS_LATE) - رقم';
COMMENT ON COLUMN V_CRM_PIPELINE.STAGE IS 'المرحلة (STAGE) - نص';
COMMENT ON COLUMN V_CRM_PIPELINE.LEADS IS 'العدد (LEADS) - رقم';
COMMENT ON COLUMN V_CRM_PIPELINE.VALUE IS 'القيمة (VALUE) - رقم';
COMMENT ON COLUMN V_DB_SIZE.TABLE_NAME IS 'الجدول (TABLE_NAME) - نص';
COMMENT ON COLUMN V_DB_SIZE.SIZE_MB IS 'الحجم (ميجا) (SIZE_MB) - رقم';
COMMENT ON COLUMN V_DB_SIZE.NUM_ROWS IS 'عدد الصفوف (تقديري) (NUM_ROWS) - رقم';
COMMENT ON COLUMN V_DB_SIZE.LAST_ANALYZED IS 'آخر تحليل (LAST_ANALYZED) - تاريخ';
COMMENT ON COLUMN V_DMS_CURRENT.FILE_ID IS 'FILE_ID - رقم';
COMMENT ON COLUMN V_DMS_CURRENT.ENTITY_TYPE IS 'ENTITY_TYPE - نص';
COMMENT ON COLUMN V_DMS_CURRENT.ENTITY_KEY IS 'ENTITY_KEY - نص';
COMMENT ON COLUMN V_DMS_CURRENT.FILE_NAME IS 'FILE_NAME - نص';
COMMENT ON COLUMN V_DMS_CURRENT.MIME_TYPE IS 'MIME_TYPE - نص';
COMMENT ON COLUMN V_DMS_CURRENT.FILE_SIZE IS 'FILE_SIZE - رقم';
COMMENT ON COLUMN V_DMS_CURRENT.NOTES IS 'NOTES - نص';
COMMENT ON COLUMN V_DMS_CURRENT.TAGS IS 'TAGS - نص';
COMMENT ON COLUMN V_DMS_CURRENT.VERSION_NO IS 'الإصدار (VERSION_NO) - رقم';
COMMENT ON COLUMN V_DMS_CURRENT.UPLOADED_BY IS 'UPLOADED_BY - نص';
COMMENT ON COLUMN V_DMS_CURRENT.UPLOAD_DATE IS 'UPLOAD_DATE - تاريخ';
COMMENT ON COLUMN V_DMS_CURRENT.FILE_CONTENT IS 'FILE_CONTENT - نص';
COMMENT ON COLUMN V_EMP_DOC_EXPIRY.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_EMP_DOC_EXPIRY.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_EMP_DOC_EXPIRY.DOC_KIND IS 'المستند (DOC_KIND) - نص';
COMMENT ON COLUMN V_EMP_DOC_EXPIRY.EXPIRY_DATE IS 'تاريخ الانتهاء (EXPIRY_DATE) - تاريخ';
COMMENT ON COLUMN V_EMP_DOC_EXPIRY.DAYS_LEFT IS 'الأيام المتبقية (DAYS_LEFT) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.SALES_THIS_MONTH IS 'مبيعات الشهر (SALES_THIS_MONTH) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.SALES_LAST_MONTH IS 'مبيعات الشهر السابق (SALES_LAST_MONTH) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.RECEIVABLES IS 'مديونية العملاء (RECEIVABLES) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.RECEIVABLES_OVER_90 IS 'متأخرات +90 (RECEIVABLES_OVER_90) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.PAYABLES IS 'مستحقات الموردين (PAYABLES) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.CASH_AND_BANK IS 'النقدية والبنوك (CASH_AND_BANK) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.PENDING_APPROVALS_ALL IS 'اعتمادات معلقة (PENDING_APPROVALS_ALL) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.NEW_FINDINGS IS 'ملاحظات جديدة (NEW_FINDINGS) - رقم';
COMMENT ON COLUMN V_EXEC_KPI.EXPIRING_BATCHES IS 'تشغيلات قاربت الانتهاء (EXPIRING_BATCHES) - رقم';
COMMENT ON COLUMN V_EXPIRY_ALERT.STORE_CODE IS 'المخزن (STORE_CODE) - رقم';
COMMENT ON COLUMN V_EXPIRY_ALERT.ITEM_ID IS 'ITEM_ID - رقم';
COMMENT ON COLUMN V_EXPIRY_ALERT.ITEMNAME IS 'الصنف (ITEMNAME) - نص';
COMMENT ON COLUMN V_EXPIRY_ALERT.BATCH_NO IS 'التشغيلة (BATCH_NO) - رقم';
COMMENT ON COLUMN V_EXPIRY_ALERT.EXPIRE_DATE IS 'تاريخ الانتهاء (EXPIRE_DATE) - تاريخ';
COMMENT ON COLUMN V_EXPIRY_ALERT.DAYS_LEFT IS 'الأيام المتبقية (DAYS_LEFT) - رقم';
COMMENT ON COLUMN V_EXPIRY_ALERT.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_EXPIRY_ALERT.QTY IS 'الكمية (QTY) - رقم';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.CLAIM_ID IS 'رقم الطلب (CLAIM_ID) - رقم';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.CLAIM_DATE IS 'تاريخ الطلب (CLAIM_DATE) - تاريخ';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.CLAIM_KIND IS 'النوع (CLAIM_KIND) - نص';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.CREDIT_CHART_CODE IS 'حساب الدائن (CREDIT_CHART_CODE) - نص';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.READY_VOUCHER_CODE IS 'رقم القيد الجاهز (READY_VOUCHER_CODE) - رقم';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.APPROVED_BY IS 'اعتمده (APPROVED_BY) - نص';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.LINES_COUNT IS 'عدد الأصناف (LINES_COUNT) - رقم';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.CLAIM_TOTAL IS 'إجمالي الطلب (CLAIM_TOTAL) - رقم';
COMMENT ON COLUMN V_EXP_CLAIM_STATUS.NOTES IS 'NOTES - نص';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.ACCOUNT_NAME IS 'الحساب (ACCOUNT_NAME) - نص';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.CHART_LEVEL IS 'المستوى (CHART_LEVEL) - رقم';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.CUR_YEAR IS 'السنة الحالية (CUR_YEAR) - رقم';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.PREV_YEAR IS 'السنة السابقة (PREV_YEAR) - رقم';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.BALANCE_CUR IS 'رصيد السنة الحالية (BALANCE_CUR) - رقم';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.BALANCE_PREV IS 'رصيد السنة السابقة (BALANCE_PREV) - رقم';
COMMENT ON COLUMN V_FIN_BALANCE_SHEET.CHANGE_AMOUNT IS 'التغير (CHANGE_AMOUNT) - رقم';
COMMENT ON COLUMN V_FIN_CASHFLOW_MONTHLY.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_FIN_CASHFLOW_MONTHLY.CASH_IN IS 'وارد (CASH_IN) - رقم';
COMMENT ON COLUMN V_FIN_CASHFLOW_MONTHLY.CASH_OUT IS 'منصرف (CASH_OUT) - رقم';
COMMENT ON COLUMN V_FIN_CASHFLOW_MONTHLY.NET_CASH IS 'صافي (NET_CASH) - رقم';
COMMENT ON COLUMN V_FIN_CASHFLOW_MONTHLY.CUMULATIVE_NET IS 'التراكمي (CUMULATIVE_NET) - رقم';
COMMENT ON COLUMN V_FIN_CHARTS_U.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_CHARTS_U.CHART_NAME_A IS 'CHART_NAME_A - نص';
COMMENT ON COLUMN V_FIN_CHARTS_U.CHART_NATURE IS 'CHART_NATURE - رقم';
COMMENT ON COLUMN V_FIN_CHARTS_U.CHART_TYPE IS 'CHART_TYPE - رقم';
COMMENT ON COLUMN V_FIN_CHARTS_U.CHART_LEVEL IS 'المستوى (CHART_LEVEL) - رقم';
COMMENT ON COLUMN V_FIN_CHARTS_U.PARENT_CHART_CODE IS 'الحساب الأب (PARENT_CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.ACCOUNT_NAME IS 'الحساب (ACCOUNT_NAME) - نص';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.CHART_LEVEL IS 'المستوى (CHART_LEVEL) - رقم';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.CUR_YEAR IS 'السنة الحالية (CUR_YEAR) - رقم';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.PREV_YEAR IS 'السنة السابقة (PREV_YEAR) - رقم';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.AMOUNT_CUR IS 'السنة الحالية (AMOUNT_CUR) - رقم';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.AMOUNT_PREV IS 'السنة السابقة (AMOUNT_PREV) - رقم';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.CHANGE_AMOUNT IS 'التغير (CHANGE_AMOUNT) - رقم';
COMMENT ON COLUMN V_FIN_INCOME_COMPARE.CHANGE_PCT IS 'نسبة التغير % (CHANGE_PCT) - رقم';
COMMENT ON COLUMN V_FIN_LAST_YEAR.CUR_YEAR IS 'السنة الحالية (CUR_YEAR) - رقم';
COMMENT ON COLUMN V_FIN_LAST_YEAR.PREV_YEAR IS 'السنة السابقة (PREV_YEAR) - رقم';
COMMENT ON COLUMN V_FIN_LEAF_YEAR.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_LEAF_YEAR.FIN_YEAR IS 'FIN_YEAR - رقم';
COMMENT ON COLUMN V_FIN_LEAF_YEAR.DEBIT_TOTAL IS 'إجمالي المدين (DEBIT_TOTAL) - رقم';
COMMENT ON COLUMN V_FIN_LEAF_YEAR.CREDIT_TOTAL IS 'CREDIT_TOTAL - رقم';
COMMENT ON COLUMN V_FIN_LEAF_YEAR.NET IS 'NET - رقم';
COMMENT ON COLUMN V_FIN_ROLLUP.ANC_CODE IS 'ANC_CODE - نص';
COMMENT ON COLUMN V_FIN_ROLLUP.LEAF_CODE IS 'LEAF_CODE - نص';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.ACCOUNT_NAME IS 'الحساب (ACCOUNT_NAME) - نص';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.PARENT_CHART_CODE IS 'الحساب الأب (PARENT_CHART_CODE) - نص';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.OPENING_BALANCE IS 'رصيد أول (OPENING_BALANCE) - رقم';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.DEBIT_MOVEMENT IS 'حركة مدينة (DEBIT_MOVEMENT) - رقم';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.CREDIT_MOVEMENT IS 'حركة دائنة (CREDIT_MOVEMENT) - رقم';
COMMENT ON COLUMN V_FIN_TRIAL_BALANCE.CLOSING_BALANCE IS 'رصيد آخر (CLOSING_BALANCE) - رقم';
COMMENT ON COLUMN V_FLT_COST.VEHICLE_ID IS 'رقم المركبة (VEHICLE_ID) - رقم';
COMMENT ON COLUMN V_FLT_COST.PLATE_NO IS 'رقم اللوحة (PLATE_NO) - نص';
COMMENT ON COLUMN V_FLT_COST.DRIVER_NAME IS 'السائق (DRIVER_NAME) - نص';
COMMENT ON COLUMN V_FLT_COST.FUEL_COST IS 'تكلفة الوقود (FUEL_COST) - رقم';
COMMENT ON COLUMN V_FLT_COST.FUEL_LITERS IS 'لترات الوقود (FUEL_LITERS) - رقم';
COMMENT ON COLUMN V_FLT_COST.MAINT_COST IS 'تكلفة الصيانة (MAINT_COST) - رقم';
COMMENT ON COLUMN V_FLT_COST.TOTAL_COST IS 'إجمالي التكلفة (TOTAL_COST) - رقم';
COMMENT ON COLUMN V_FLT_COST.LAST_ODOMETER IS 'آخر عداد (LAST_ODOMETER) - رقم';
COMMENT ON COLUMN V_FLT_COST.KM_DRIVEN IS 'كم مقطوع (KM_DRIVEN) - رقم';
COMMENT ON COLUMN V_FLT_COST.COST_PER_KM IS 'تكلفة الكم (COST_PER_KM) - رقم';
COMMENT ON COLUMN V_FLT_COST.LITERS_PER_100KM IS 'لتر/100كم (LITERS_PER_100KM) - رقم';
COMMENT ON COLUMN V_FLT_DOC_ALERT.VEHICLE_ID IS 'رقم المركبة (VEHICLE_ID) - رقم';
COMMENT ON COLUMN V_FLT_DOC_ALERT.PLATE_NO IS 'رقم اللوحة (PLATE_NO) - نص';
COMMENT ON COLUMN V_FLT_DOC_ALERT.DRIVER_NAME IS 'السائق (DRIVER_NAME) - نص';
COMMENT ON COLUMN V_FLT_DOC_ALERT.DOC_KIND IS 'المستند (DOC_KIND) - نص';
COMMENT ON COLUMN V_FLT_DOC_ALERT.EXPIRY IS 'تاريخ الانتهاء (EXPIRY) - تاريخ';
COMMENT ON COLUMN V_FLT_DOC_ALERT.DAYS_LEFT IS 'الأيام المتبقية (DAYS_LEFT) - رقم';
COMMENT ON COLUMN V_FLT_DOC_ALERT.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.RUN_ID IS 'رقم التشغيل (RUN_ID) - رقم';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.RATE_DATE IS 'تاريخ السعر (RATE_DATE) - تاريخ';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.ACCOUNT_NAME IS 'الحساب (ACCOUNT_NAME) - نص';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.CURRENCY_CODE IS 'العملة (CURRENCY_CODE) - رقم';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.FOREIGN_BALANCE IS 'الرصيد بالعملة (FOREIGN_BALANCE) - رقم';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.BOOK_VALUE IS 'القيمة الدفترية (BOOK_VALUE) - رقم';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.REVALUED_VALUE IS 'القيمة بعد التقييم (REVALUED_VALUE) - رقم';
COMMENT ON COLUMN V_FX_REVAL_SUMMARY.DIFFERENCE IS 'الفرق (DIFFERENCE) - رقم';
COMMENT ON COLUMN V_HD_SLA_STATUS.TICKET_ID IS 'TICKET_ID - رقم';
COMMENT ON COLUMN V_HD_SLA_STATUS.TITLE IS 'العنوان (TITLE) - نص';
COMMENT ON COLUMN V_HD_SLA_STATUS.PRIORITY IS 'الأولوية (PRIORITY) - نص';
COMMENT ON COLUMN V_HD_SLA_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_HD_SLA_STATUS.ASSIGNEE IS 'المسؤول (ASSIGNEE) - نص';
COMMENT ON COLUMN V_HD_SLA_STATUS.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE) - تاريخ';
COMMENT ON COLUMN V_HD_SLA_STATUS.RESOLVE_DUE IS 'موعد الحل (RESOLVE_DUE) - تاريخ';
COMMENT ON COLUMN V_HD_SLA_STATUS.SLA_STATE IS 'حالة SLA (SLA_STATE) - نص';
COMMENT ON COLUMN V_HD_SLA_STATUS.RESPONSE_STATE IS 'حالة الرد (RESPONSE_STATE) - نص';
COMMENT ON COLUMN V_HEADCOUNT.DEPT_CODE IS 'القسم (DEPT_CODE) - رقم';
COMMENT ON COLUMN V_HEADCOUNT.EMPLOYEES IS 'عدد الموظفين (EMPLOYEES) - رقم';
COMMENT ON COLUMN V_HEADCOUNT.WITHOUT_BANK_ACCOUNT IS 'WITHOUT_BANK_ACCOUNT - رقم';
COMMENT ON COLUMN V_HEADCOUNT.WITHOUT_ID_NO IS 'WITHOUT_ID_NO - رقم';
COMMENT ON COLUMN V_HEADCOUNT.WITHOUT_HIRE_DATE IS 'WITHOUT_HIRE_DATE - رقم';
COMMENT ON COLUMN V_HEALTH_LATEST.KPI_KEY IS 'KPI_KEY - نص';
COMMENT ON COLUMN V_HEALTH_LATEST.LABEL IS 'الفحص (LABEL) - نص';
COMMENT ON COLUMN V_HEALTH_LATEST.TARGET_TXT IS 'TARGET_TXT - نص';
COMMENT ON COLUMN V_HEALTH_LATEST.KPI_VALUE IS 'KPI_VALUE - رقم';
COMMENT ON COLUMN V_HEALTH_LATEST.SNAP_DATE IS 'SNAP_DATE - تاريخ';
COMMENT ON COLUMN V_HEALTH_LATEST.ERROR_TEXT IS 'ERROR_TEXT - نص';
COMMENT ON COLUMN V_HR_GOAL_SCORE.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_HR_GOAL_SCORE.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_HR_GOAL_SCORE.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_HR_GOAL_SCORE.GOALS IS 'عدد الأهداف (GOALS) - رقم';
COMMENT ON COLUMN V_HR_GOAL_SCORE.ACHIEVEMENT_PCT IS 'نسبة التحقيق % (ACHIEVEMENT_PCT) - رقم';
COMMENT ON COLUMN V_HR_GOAL_SCORE.AVG_RATING IS 'متوسط التقييم (AVG_RATING) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.VACANCY_ID IS 'VACANCY_ID - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.TITLE IS 'العنوان (TITLE) - نص';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.POSITIONS IS 'عدد الوظائف (POSITIONS) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.CANDIDATES IS 'المتقدمون (CANDIDATES) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.IN_SCREENING IS 'فرز (IN_SCREENING) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.IN_INTERVIEW IS 'مقابلة (IN_INTERVIEW) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.OFFERS IS 'عروض (OFFERS) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.HIRED IS 'تم التعيين (HIRED) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.REJECTED IS 'مرفوض (REJECTED) - رقم';
COMMENT ON COLUMN V_HR_RECRUIT_FUNNEL.AVG_INTERVIEW_SCORE IS 'متوسط المقابلة (AVG_INTERVIEW_SCORE) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_BY_EMP.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_BY_EMP.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_HR_TRAINING_BY_EMP.COURSES IS 'COURSES - رقم';
COMMENT ON COLUMN V_HR_TRAINING_BY_EMP.TRAINING_HOURS IS 'TRAINING_HOURS - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.COURSE_ID IS 'COURSE_ID - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.TITLE IS 'العنوان (TITLE) - نص';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.PROVIDER IS 'الجهة (PROVIDER) - نص';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.START_DATE IS 'بداية العقد (START_DATE) - تاريخ';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.HOURS IS 'الساعات (HOURS) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.COST IS 'التكلفة (COST) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.ENROLLED IS 'المسجلون (ENROLLED) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.ATTENDED IS 'الحاضرون (ATTENDED) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.COST_PER_PARTICIPANT IS 'تكلفة الفرد (COST_PER_PARTICIPANT) - رقم';
COMMENT ON COLUMN V_HR_TRAINING_SUMMARY.AVG_SCORE IS 'متوسط الدرجة (AVG_SCORE) - رقم';
COMMENT ON COLUMN V_INT_CASH_VS_LEDGER.CASH_ID IS 'CASH_ID - رقم';
COMMENT ON COLUMN V_INT_CASH_VS_LEDGER.CASH_NAME IS 'الخزينة / البنك (CASH_NAME) - نص';
COMMENT ON COLUMN V_INT_CASH_VS_LEDGER.CHART_CODE IS 'الحساب (CHART_CODE) - نص';
COMMENT ON COLUMN V_INT_CASH_VS_LEDGER.CASH_MODULE_BALANCE IS 'رصيد الخزينة (CASH_MODULE_BALANCE) - رقم';
COMMENT ON COLUMN V_INT_CASH_VS_LEDGER.LEDGER_BALANCE IS 'رصيد الأستاذ (LEDGER_BALANCE) - رقم';
COMMENT ON COLUMN V_INT_CASH_VS_LEDGER.DIFFERENCE IS 'الفرق (DIFFERENCE) - رقم';
COMMENT ON COLUMN V_INT_CHECKS.RELATION_NAME IS 'العلاقة (RELATION_NAME) - نص';
COMMENT ON COLUMN V_INT_CHECKS.CHECK_KEY IS 'كود الفحص (CHECK_KEY) - نص';
COMMENT ON COLUMN V_INT_CHECKS.CHECK_LABEL IS 'المشكلة (CHECK_LABEL) - نص';
COMMENT ON COLUMN V_INT_CHECKS.SEVERITY IS 'الخطورة (SEVERITY) - نص';
COMMENT ON COLUMN V_INT_CHECKS.ISSUES IS 'عدد المشاكل (ISSUES) - رقم';
COMMENT ON COLUMN V_INT_CHECK_DETAIL.CHECK_KEY IS 'كود الفحص (CHECK_KEY) - نص';
COMMENT ON COLUMN V_INT_CHECK_DETAIL.REF_NO IS 'رقم المستند (REF_NO) - رقم';
COMMENT ON COLUMN V_INT_CHECK_DETAIL.REF_DATE IS 'التاريخ (REF_DATE) - تاريخ';
COMMENT ON COLUMN V_INT_CHECK_DETAIL.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_INT_CHECK_DETAIL.DESCRIPTION IS 'الوصف (DESCRIPTION) - نص';
COMMENT ON COLUMN V_INT_CHECK_DETAIL.RN IS 'م (RN) - رقم';
COMMENT ON COLUMN V_INT_PENDING.MODULE_NAME IS 'النظام (MODULE_NAME) - نص';
COMMENT ON COLUMN V_INT_PENDING.WAITING_DOCUMENTS IS 'مستندات منتظرة (WAITING_DOCUMENTS) - رقم';
COMMENT ON COLUMN V_INT_PENDING.WAITING_AMOUNT IS 'إجمالي المنتظر (WAITING_AMOUNT) - رقم';
COMMENT ON COLUMN V_INT_PENDING.OLDEST_DATE IS 'أقدم مستند (OLDEST_DATE) - تاريخ';
COMMENT ON COLUMN V_INT_PENDING.OLDEST_AGE_DAYS IS 'عمره بالأيام (OLDEST_AGE_DAYS) - رقم';
COMMENT ON COLUMN V_INT_SWITCHES.LINK_NAME IS 'الربط (LINK_NAME) - نص';
COMMENT ON COLUMN V_INT_SWITCHES.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_INV_OPEN.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY) - رقم';
COMMENT ON COLUMN V_INV_OPEN.INVID IS 'INVID - رقم';
COMMENT ON COLUMN V_INV_OPEN.INVTYPE IS 'INVTYPE - رقم';
COMMENT ON COLUMN V_INV_OPEN.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_INV_OPEN.CUST_TYPE IS 'CUST_TYPE - رقم';
COMMENT ON COLUMN V_INV_OPEN.INVDATE IS 'INVDATE - تاريخ';
COMMENT ON COLUMN V_INV_OPEN.DUE_DATE IS 'تاريخ الاستحقاق (DUE_DATE) - تاريخ';
COMMENT ON COLUMN V_INV_OPEN.FINALTOTAL IS 'FINALTOTAL - رقم';
COMMENT ON COLUMN V_INV_OPEN.PAID IS 'PAID - رقم';
COMMENT ON COLUMN V_INV_OPEN.REMAINING IS 'REMAINING - رقم';
COMMENT ON COLUMN V_INV_OPEN.DAYS_OVERDUE IS 'DAYS_OVERDUE - رقم';
COMMENT ON COLUMN V_INV_OPEN.DEALER_ID IS 'المندوب (DEALER_ID) - رقم';
COMMENT ON COLUMN V_INV_OPEN.COST_CODE IS 'COST_CODE - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.ITEMID IS 'كود الصنف (ITEMID) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.ITEMNAME IS 'الصنف (ITEMNAME) - نص';
COMMENT ON COLUMN V_ITEM_VALUATION.BALANCE_QTY IS 'الرصيد (BALANCE_QTY) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.REGISTERED_BUY_PRICE IS 'سعر الشراء المسجل (REGISTERED_BUY_PRICE) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.WEIGHTED_AVG_PRICE IS 'متوسط سعر الشراء المرجح (WEIGHTED_AVG_PRICE) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.LAST_PURCHASE_PRICE IS 'آخر سعر شراء (LAST_PURCHASE_PRICE) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.VALUE_REGISTERED IS 'القيمة بالسعر المسجل (VALUE_REGISTERED) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.VALUE_WEIGHTED_AVG IS 'القيمة بالمتوسط المرجح (VALUE_WEIGHTED_AVG) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.VALUE_LAST_PURCHASE IS 'القيمة بآخر سعر شراء (VALUE_LAST_PURCHASE) - رقم';
COMMENT ON COLUMN V_ITEM_VALUATION.LAST_VS_AVG_DIFF IS 'الفرق (آخر سعر - المتوسط) (LAST_VS_AVG_DIFF) - رقم';
COMMENT ON COLUMN V_LEAVE_BALANCE.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_LEAVE_BALANCE.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_LEAVE_BALANCE.VAC_TYPE_ID IS 'VAC_TYPE_ID - رقم';
COMMENT ON COLUMN V_LEAVE_BALANCE.VAC_TYPE_NAME_AR IS 'VAC_TYPE_NAME_AR - نص';
COMMENT ON COLUMN V_LEAVE_BALANCE.OPEN_BALANCE IS 'OPEN_BALANCE - رقم';
COMMENT ON COLUMN V_LEAVE_BALANCE.DAYS_TAKEN_THIS_YEAR IS 'DAYS_TAKEN_THIS_YEAR - رقم';
COMMENT ON COLUMN V_LEAVE_BALANCE.REMAINING IS 'REMAINING - رقم';
COMMENT ON COLUMN V_LOG_DRIVER_PERF.DRIVER_NAME IS 'السائق (DRIVER_NAME) - نص';
COMMENT ON COLUMN V_LOG_DRIVER_PERF.TRIPS IS 'عدد الرحلات (TRIPS) - رقم';
COMMENT ON COLUMN V_LOG_DRIVER_PERF.STOPS IS 'عدد المحطات (STOPS) - رقم';
COMMENT ON COLUMN V_LOG_DRIVER_PERF.DELIVERED IS 'تم التسليم (DELIVERED) - رقم';
COMMENT ON COLUMN V_LOG_DRIVER_PERF.FAILED IS 'راسب (FAILED) - رقم';
COMMENT ON COLUMN V_LOG_DRIVER_PERF.SUCCESS_PCT IS 'نسبة النجاح % (SUCCESS_PCT) - رقم';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.TRIP_ID IS 'رقم الرحلة (TRIP_ID) - رقم';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.TRIP_DATE IS 'تاريخ الرحلة (TRIP_DATE) - تاريخ';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.DRIVER_NAME IS 'السائق (DRIVER_NAME) - نص';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.PLATE_NO IS 'رقم اللوحة (PLATE_NO) - نص';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.STOPS_TOTAL IS 'عدد المحطات (STOPS_TOTAL) - رقم';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.DELIVERED IS 'تم التسليم (DELIVERED) - رقم';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.FAILED IS 'راسب (FAILED) - رقم';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.PENDING IS 'منتظر (PENDING) - رقم';
COMMENT ON COLUMN V_LOG_TRIP_STATUS.SUCCESS_PCT IS 'نسبة النجاح % (SUCCESS_PCT) - رقم';
COMMENT ON COLUMN V_MFG_LOAD.MACHINE_ID IS 'الماكينة (MACHINE_ID) - رقم';
COMMENT ON COLUMN V_MFG_LOAD.MACHINE_NAME IS 'اسم الماكينة (MACHINE_NAME) - نص';
COMMENT ON COLUMN V_MFG_LOAD.WEEK_NO IS 'الأسبوع (WEEK_NO) - نص';
COMMENT ON COLUMN V_MFG_LOAD.JOBS IS 'عدد المهام (JOBS) - رقم';
COMMENT ON COLUMN V_MFG_LOAD.PLANNED_HOURS IS 'ساعات مخططة (PLANNED_HOURS) - رقم';
COMMENT ON COLUMN V_MFG_LOAD.WEEK_CAPACITY_HOURS IS 'سعة الأسبوع (WEEK_CAPACITY_HOURS) - رقم';
COMMENT ON COLUMN V_MFG_LOAD.LOAD_PCT IS 'نسبة الحمل % (LOAD_PCT) - رقم';
COMMENT ON COLUMN V_MFG_OVERLAP.MACHINE_ID IS 'الماكينة (MACHINE_ID) - رقم';
COMMENT ON COLUMN V_MFG_OVERLAP.MACHINE_NAME IS 'اسم الماكينة (MACHINE_NAME) - نص';
COMMENT ON COLUMN V_MFG_OVERLAP.SCHED_A IS 'مهمة 1 (SCHED_A) - رقم';
COMMENT ON COLUMN V_MFG_OVERLAP.SCHED_B IS 'مهمة 2 (SCHED_B) - رقم';
COMMENT ON COLUMN V_MFG_OVERLAP.OVERLAP_FROM IS 'من (OVERLAP_FROM) - تاريخ';
COMMENT ON COLUMN V_MFG_OVERLAP.OVERLAP_TO IS 'إلى (OVERLAP_TO) - تاريخ';
COMMENT ON COLUMN V_MFG_VARIANCE.ITEMID IS 'كود الصنف (ITEMID) - رقم';
COMMENT ON COLUMN V_MFG_VARIANCE.ITEMNAME IS 'الصنف (ITEMNAME) - نص';
COMMENT ON COLUMN V_MFG_VARIANCE.STANDARD_COST IS 'التكلفة المعيارية (STANDARD_COST) - رقم';
COMMENT ON COLUMN V_MFG_VARIANCE.ACTUAL_COST IS 'التكلفة الفعلية (ACTUAL_COST) - رقم';
COMMENT ON COLUMN V_MFG_VARIANCE.VARIANCE IS 'الفرق (VARIANCE) - رقم';
COMMENT ON COLUMN V_MFG_VARIANCE.VARIANCE_PCT IS 'نسبة الفرق % (VARIANCE_PCT) - رقم';
COMMENT ON COLUMN V_MFG_VARIANCE.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_MNT_COST.ASSETS_ID IS 'الأصل (ASSETS_ID) - رقم';
COMMENT ON COLUMN V_MNT_COST.ASSET_NAME_AR IS 'اسم الأصل (ASSET_NAME_AR) - نص';
COMMENT ON COLUMN V_MNT_COST.WORK_ORDERS IS 'أوامر الصيانة (WORK_ORDERS) - رقم';
COMMENT ON COLUMN V_MNT_COST.BREAKDOWNS IS 'أعطال (BREAKDOWNS) - رقم';
COMMENT ON COLUMN V_MNT_COST.LABOUR_COST IS 'تكلفة العمالة (LABOUR_COST) - رقم';
COMMENT ON COLUMN V_MNT_COST.PARTS_COST IS 'تكلفة القطع (PARTS_COST) - رقم';
COMMENT ON COLUMN V_MNT_DUE.PLAN_ID IS 'PLAN_ID - رقم';
COMMENT ON COLUMN V_MNT_DUE.ASSETS_ID IS 'الأصل (ASSETS_ID) - رقم';
COMMENT ON COLUMN V_MNT_DUE.ASSET_NAME_AR IS 'اسم الأصل (ASSET_NAME_AR) - نص';
COMMENT ON COLUMN V_MNT_DUE.TASK IS 'المهمة (TASK) - نص';
COMMENT ON COLUMN V_MNT_DUE.EVERY_DAYS IS 'كل (يوم) (EVERY_DAYS) - رقم';
COMMENT ON COLUMN V_MNT_DUE.LAST_DONE IS 'آخر تنفيذ (LAST_DONE) - تاريخ';
COMMENT ON COLUMN V_MNT_DUE.NEXT_DUE IS 'الاستحقاق القادم (NEXT_DUE) - تاريخ';
COMMENT ON COLUMN V_MNT_DUE.DAYS_LATE IS 'أيام التأخير (DAYS_LATE) - رقم';
COMMENT ON COLUMN V_MNT_DUE.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.NOTIF_ID IS 'NOTIF_ID - رقم';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.USER_NAME IS 'USER_NAME - نص';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.TITLE IS 'العنوان (TITLE) - نص';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.BODY IS 'BODY - نص';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.LINK_URL IS 'LINK_URL - نص';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.NOTIF_TYPE IS 'NOTIF_TYPE - نص';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.CREATED_DATE IS 'تاريخ الإنشاء (CREATED_DATE) - تاريخ';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.READ_DATE IS 'READ_DATE - تاريخ';
COMMENT ON COLUMN V_MY_NOTIFICATIONS.IS_READ IS 'IS_READ - نص';
COMMENT ON COLUMN V_ORDER_MATCH.ORD_ID IS 'ORD_ID - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.ORD_NO IS 'رقم الطلب (ORD_NO) - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.ORD_TYPE IS 'ORD_TYPE - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.ORD_DATE IS 'ORD_DATE - تاريخ';
COMMENT ON COLUMN V_ORDER_MATCH.CUSTID IS 'CUSTID - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.ITEMID IS 'كود الصنف (ITEMID) - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.ORDERED_QTY IS 'المطلوب (ORDERED_QTY) - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.DELIVERED_QTY IS 'المسلّم (DELIVERED_QTY) - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.INVOICED_QTY IS 'المفوتر (INVOICED_QTY) - رقم';
COMMENT ON COLUMN V_ORDER_MATCH.REMAINING_TO_INVOICE IS 'المتبقي للفوترة (REMAINING_TO_INVOICE) - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_COVERAGE.PAGE_ID IS 'PAGE_ID - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_COVERAGE.PAGE_NAME IS 'PAGE_NAME - نص';
COMMENT ON COLUMN V_PAGE_ACCESS_COVERAGE.PAGE_MODE IS 'PAGE_MODE - نص';
COMMENT ON COLUMN V_PAGE_ACCESS_COVERAGE.MAPPED_FORMS IS 'MAPPED_FORMS - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_COVERAGE.ROLES_ALLOWED IS 'ROLES_ALLOWED - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_IMPACT.USER_NAME IS 'USER_NAME - نص';
COMMENT ON COLUMN V_PAGE_ACCESS_IMPACT.ROLE_ID IS 'ROLE_ID - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_IMPACT.IS_ADMIN IS 'IS_ADMIN - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_IMPACT.PAGE_ID IS 'PAGE_ID - رقم';
COMMENT ON COLUMN V_PAGE_ACCESS_IMPACT.ALLOWED IS 'ALLOWED - نص';
COMMENT ON COLUMN V_PAGE_FORMS.PAGE_ID IS 'PAGE_ID - رقم';
COMMENT ON COLUMN V_PAGE_FORMS.FORM_ID IS 'FORM_ID - رقم';
COMMENT ON COLUMN V_PARTY_BALANCE.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_PARTY_BALANCE.CUST_TYPE IS 'CUST_TYPE - رقم';
COMMENT ON COLUMN V_PARTY_BALANCE.BALANCE IS 'الرصيد (BALANCE) - رقم';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.SAL_YEAR IS 'السنة (SAL_YEAR) - رقم';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.SAL_MONTH IS 'الشهر (SAL_MONTH) - رقم';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.BANK_ACCOUNT IS 'BANK_ACCOUNT - نص';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.NET_PAY IS 'NET_PAY - رقم';
COMMENT ON COLUMN V_PAYROLL_BANK_FILE.CSV_LINE IS 'CSV_LINE - نص';
COMMENT ON COLUMN V_PAYROLL_NET.SAL_YEAR IS 'السنة (SAL_YEAR) - رقم';
COMMENT ON COLUMN V_PAYROLL_NET.SAL_MONTH IS 'الشهر (SAL_MONTH) - رقم';
COMMENT ON COLUMN V_PAYROLL_NET.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_PAYROLL_NET.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_PAYROLL_NET.DEPT_CODE IS 'القسم (DEPT_CODE) - رقم';
COMMENT ON COLUMN V_PAYROLL_NET.TOTAL_EARNINGS IS 'TOTAL_EARNINGS - رقم';
COMMENT ON COLUMN V_PAYROLL_NET.TOTAL_DEDUCTIONS IS 'TOTAL_DEDUCTIONS - رقم';
COMMENT ON COLUMN V_PAYROLL_NET.NET_PAY IS 'NET_PAY - رقم';
COMMENT ON COLUMN V_PAYROLL_NO_BANK.SAL_YEAR IS 'السنة (SAL_YEAR) - رقم';
COMMENT ON COLUMN V_PAYROLL_NO_BANK.SAL_MONTH IS 'الشهر (SAL_MONTH) - رقم';
COMMENT ON COLUMN V_PAYROLL_NO_BANK.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_PAYROLL_NO_BANK.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_PAYROLL_NO_BANK.NET_PAY IS 'NET_PAY - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.SAL_YEAR IS 'السنة (SAL_YEAR) - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.SAL_MONTH IS 'الشهر (SAL_MONTH) - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.GROSS IS 'الإجمالي (GROSS) - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.INSURANCE_EMPLOYEE IS 'تأمين الموظف (INSURANCE_EMPLOYEE) - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.INSURANCE_EMPLOYER IS 'تأمين صاحب العمل (INSURANCE_EMPLOYER) - رقم';
COMMENT ON COLUMN V_PAYROLL_STATUTORY.INCOME_TAX IS 'ضريبة الدخل (INCOME_TAX) - رقم';
COMMENT ON COLUMN V_PAYSLIP.SAL_YEAR IS 'السنة (SAL_YEAR) - رقم';
COMMENT ON COLUMN V_PAYSLIP.SAL_MONTH IS 'الشهر (SAL_MONTH) - رقم';
COMMENT ON COLUMN V_PAYSLIP.EMP_ID IS 'كود الموظف (EMP_ID) - رقم';
COMMENT ON COLUMN V_PAYSLIP.EMP_NAME_AR IS 'الموظف (EMP_NAME_AR) - نص';
COMMENT ON COLUMN V_PAYSLIP.DEPT_CODE IS 'القسم (DEPT_CODE) - رقم';
COMMENT ON COLUMN V_PAYSLIP.JOB_CODE IS 'JOB_CODE - رقم';
COMMENT ON COLUMN V_PAYSLIP.ELEMENT_CODE IS 'ELEMENT_CODE - رقم';
COMMENT ON COLUMN V_PAYSLIP.ELEMENT_NAME_AR IS 'ELEMENT_NAME_AR - نص';
COMMENT ON COLUMN V_PAYSLIP.IN_OUT IS 'IN_OUT - نص';
COMMENT ON COLUMN V_PAYSLIP.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_PAYSLIP.SIGNED_AMOUNT IS 'SIGNED_AMOUNT - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.PROJECT_ID IS 'PROJECT_ID - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.PROJECT_NAME IS 'المشروع (PROJECT_NAME) - نص';
COMMENT ON COLUMN V_PRJ_SUMMARY.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_PRJ_SUMMARY.BUDGET IS 'الموازنة (BUDGET) - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.START_DATE IS 'بداية العقد (START_DATE) - تاريخ';
COMMENT ON COLUMN V_PRJ_SUMMARY.END_DATE IS 'ينتهي في (END_DATE) - تاريخ';
COMMENT ON COLUMN V_PRJ_SUMMARY.TASKS IS 'TASKS - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.PCT_DONE IS 'نسبة الإنجاز (PCT_DONE) - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.HOURS_LOGGED IS 'HOURS_LOGGED - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.LABOUR_COST IS 'تكلفة العمالة (LABOUR_COST) - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.LEDGER_COST IS 'LEDGER_COST - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.TOTAL_COST IS 'إجمالي التكلفة (TOTAL_COST) - رقم';
COMMENT ON COLUMN V_PRJ_SUMMARY.BUDGET_LEFT IS 'المتبقي (BUDGET_LEFT) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.PO_ID IS 'أمر الشراء (PO_ID) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.PO_DATE IS 'التاريخ (PO_DATE) - تاريخ';
COMMENT ON COLUMN V_PUR_PO_INVOICE.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_PUR_PO_INVOICE.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.SUPPLIER_NAME IS 'المورد (SUPPLIER_NAME) - نص';
COMMENT ON COLUMN V_PUR_PO_INVOICE.PO_TOTAL IS 'قيمة الأمر (PO_TOTAL) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.RECEIVED_VALUE IS 'قيمة المستلم (RECEIVED_VALUE) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.INVOICE_TOTAL IS 'إجمالي الفاتورة (INVOICE_TOTAL) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.DIFF_VS_ORDER IS 'الفرق عن الأمر (DIFF_VS_ORDER) - رقم';
COMMENT ON COLUMN V_PUR_PO_INVOICE.INVOICE_STATE IS 'حالة الفوترة (INVOICE_STATE) - نص';
COMMENT ON COLUMN V_PUR_PO_STATUS.PO_ID IS 'أمر الشراء (PO_ID) - رقم';
COMMENT ON COLUMN V_PUR_PO_STATUS.PO_DATE IS 'التاريخ (PO_DATE) - تاريخ';
COMMENT ON COLUMN V_PUR_PO_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_PUR_PO_STATUS.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID) - رقم';
COMMENT ON COLUMN V_PUR_PO_STATUS.SUPPLIER_NAME IS 'المورد (SUPPLIER_NAME) - نص';
COMMENT ON COLUMN V_PUR_PO_STATUS.PO_TOTAL IS 'قيمة الأمر (PO_TOTAL) - رقم';
COMMENT ON COLUMN V_PUR_PO_STATUS.QTY_ORDERED IS 'المطلوب (QTY_ORDERED) - رقم';
COMMENT ON COLUMN V_PUR_PO_STATUS.QTY_RECEIVED IS 'المستلم (QTY_RECEIVED) - رقم';
COMMENT ON COLUMN V_PUR_PO_STATUS.RECEIVED_PCT IS 'نسبة الاستلام % (RECEIVED_PCT) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.RFQ_ID IS 'RFQ_ID - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.LINE_ID IS 'رقم السطر (LINE_ID) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.ITEMID IS 'كود الصنف (ITEMID) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.ITEMNAME IS 'الصنف (ITEMNAME) - نص';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.QTY IS 'الكمية (QTY) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.SUPPLIER_NAME IS 'المورد (SUPPLIER_NAME) - نص';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.UNIT_PRICE IS 'سعر الوحدة (UNIT_PRICE) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.LINE_TOTAL IS 'إجمالي البند (LINE_TOTAL) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.LEAD_DAYS IS 'مدة التوريد (يوم) (LEAD_DAYS) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.PRICE_RANK IS 'الترتيب (PRICE_RANK) - رقم';
COMMENT ON COLUMN V_PUR_QUOTE_COMPARE.BEST_PRICE IS 'أفضل سعر (BEST_PRICE) - نص';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.RFQ_ID IS 'RFQ_ID - رقم';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID) - رقم';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.SUPPLIER_NAME IS 'المورد (SUPPLIER_NAME) - نص';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.LINES_QUOTED IS 'بنود مسعّرة (LINES_QUOTED) - رقم';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.LINES_TOTAL IS 'بنود الطلب (LINES_TOTAL) - رقم';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.TOTAL_PRICE IS 'الإجمالي (TOTAL_PRICE) - رقم';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.MAX_LEAD_DAYS IS 'أطول مدة توريد (MAX_LEAD_DAYS) - رقم';
COMMENT ON COLUMN V_PUR_RFQ_SUPPLIER_TOTAL.COMPLETENESS IS 'الاكتمال (COMPLETENESS) - نص';
COMMENT ON COLUMN V_QC_PASS_RATE.ITEMID IS 'كود الصنف (ITEMID) - رقم';
COMMENT ON COLUMN V_QC_PASS_RATE.ITEMNAME IS 'الصنف (ITEMNAME) - نص';
COMMENT ON COLUMN V_QC_PASS_RATE.INSPECTIONS IS 'الفحوصات (INSPECTIONS) - رقم';
COMMENT ON COLUMN V_QC_PASS_RATE.PASSED IS 'ناجح (PASSED) - رقم';
COMMENT ON COLUMN V_QC_PASS_RATE.FAILED IS 'راسب (FAILED) - رقم';
COMMENT ON COLUMN V_QC_PASS_RATE.PASS_PCT IS 'نسبة النجاح % (PASS_PCT) - رقم';
COMMENT ON COLUMN V_QC_PASS_RATE.OPEN_NCR IS 'عدم مطابقة مفتوح (OPEN_NCR) - رقم';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.CAPA_ID IS 'رقم الإجراء (CAPA_ID) - رقم';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.SOURCE_KIND IS 'المصدر (SOURCE_KIND) - نص';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.AUDIT_ID IS 'رقم المراجعة (AUDIT_ID) - رقم';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.AUDIT_AREA IS 'مجال المراجعة (AUDIT_AREA) - نص';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.NCR_ID IS 'رقم عدم المطابقة (NCR_ID) - رقم';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.DESCRIPTION IS 'الوصف (DESCRIPTION) - نص';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.OWNER_USER IS 'المسؤول (OWNER_USER) - نص';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.DUE_DATE IS 'تاريخ الاستحقاق (DUE_DATE) - تاريخ';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.DONE_DATE IS 'تاريخ الإنجاز (DONE_DATE) - تاريخ';
COMMENT ON COLUMN V_QMS_CAPA_STATUS.TIMELINESS IS 'الالتزام بالميعاد (TIMELINESS) - نص';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.DOC_ID IS 'DOC_ID - رقم';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.DOC_NAME IS 'اسم المستند (DOC_NAME) - نص';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.DOC_TYPE IS 'نوع المستند (DOC_TYPE) - نص';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.VERSION_NO IS 'الإصدار (VERSION_NO) - نص';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.OWNER_USER IS 'المسؤول (OWNER_USER) - نص';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.NEXT_REVIEW IS 'المراجعة القادمة (NEXT_REVIEW) - تاريخ';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.DAYS_LEFT IS 'الأيام المتبقية (DAYS_LEFT) - رقم';
COMMENT ON COLUMN V_QMS_DOC_REVIEW.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_REC_JE_STATUS.JE_ID IS 'رقم القالب (JE_ID) - رقم';
COMMENT ON COLUMN V_REC_JE_STATUS.JE_NAME IS 'اسم القيد (JE_NAME) - نص';
COMMENT ON COLUMN V_REC_JE_STATUS.FREQ IS 'التكرار (FREQ) - نص';
COMMENT ON COLUMN V_REC_JE_STATUS.NEXT_DATE IS 'الموعد القادم (NEXT_DATE) - تاريخ';
COMMENT ON COLUMN V_REC_JE_STATUS.END_DATE IS 'ينتهي في (END_DATE) - تاريخ';
COMMENT ON COLUMN V_REC_JE_STATUS.ACTIVE IS 'نشط (ACTIVE) - نص';
COMMENT ON COLUMN V_REC_JE_STATUS.REVERSE_NEXT IS 'يُعكس في الفترة التالية (REVERSE_NEXT) - نص';
COMMENT ON COLUMN V_REC_JE_STATUS.LINES_COUNT IS 'عدد الأصناف (LINES_COUNT) - رقم';
COMMENT ON COLUMN V_REC_JE_STATUS.DEBIT_TOTAL IS 'إجمالي المدين (DEBIT_TOTAL) - رقم';
COMMENT ON COLUMN V_REC_JE_STATUS.IMBALANCE IS 'فرق عدم الاتزان (IMBALANCE) - رقم';
COMMENT ON COLUMN V_REC_JE_STATUS.STATE IS 'الحالة (STATE) - نص';
COMMENT ON COLUMN V_REC_JE_STATUS.LAST_GENERATED IS 'آخر توليد (LAST_GENERATED) - تاريخ';
COMMENT ON COLUMN V_REORDER.ITEMID IS 'كود الصنف (ITEMID) - رقم';
COMMENT ON COLUMN V_REORDER.ITEMNAME IS 'الصنف (ITEMNAME) - نص';
COMMENT ON COLUMN V_REORDER.MIN_LIMIT IS 'الحد الأدنى (MIN_LIMIT) - رقم';
COMMENT ON COLUMN V_REORDER.MAX_LIMIT IS 'الحد الأقصى (MAX_LIMIT) - رقم';
COMMENT ON COLUMN V_REORDER.REORDER_LIMIT IS 'حد الطلب (REORDER_LIMIT) - رقم';
COMMENT ON COLUMN V_REORDER.BALANCE IS 'الرصيد (BALANCE) - رقم';
COMMENT ON COLUMN V_REORDER.SUGGESTED_ORDER_QTY IS 'الكمية المقترحة (SUGGESTED_ORDER_QTY) - رقم';
COMMENT ON COLUMN V_SALES_BY_DEALER.DEALER_ID IS 'المندوب (DEALER_ID) - رقم';
COMMENT ON COLUMN V_SALES_BY_DEALER.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_SALES_BY_DEALER.INVOICES IS 'عدد الفواتير (INVOICES) - رقم';
COMMENT ON COLUMN V_SALES_BY_DEALER.NET_SALES IS 'صافي المبيعات (NET_SALES) - رقم';
COMMENT ON COLUMN V_SALES_FORECAST.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_SALES_FORECAST.FORECAST_SALES IS 'المبيعات المتوقعة (FORECAST_SALES) - رقم';
COMMENT ON COLUMN V_SALES_FORECAST.MONTHS_USED IS 'شهور الاحتساب (MONTHS_USED) - رقم';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.NOTE_ID IS 'رقم الإشعار (NOTE_ID) - رقم';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.NOTE_DATE IS 'تاريخ الإشعار (NOTE_DATE) - تاريخ';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.NOTE_TYPE IS 'النوع (NOTE_TYPE) - نص';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.PARTY_KIND IS 'الطرف (PARTY_KIND) - نص';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.PARTY_ID IS 'كود الطرف (PARTY_ID) - رقم';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.PARTY_NAME IS 'اسم الطرف (PARTY_NAME) - نص';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.AMOUNT IS 'AMOUNT - رقم';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.CONTRA_CHART_CODE IS 'الحساب المقابل (CONTRA_CHART_CODE) - نص';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY) - رقم';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.READY_VOUCHER_CODE IS 'رقم القيد الجاهز (READY_VOUCHER_CODE) - رقم';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.REASON IS 'السبب (REASON) - نص';
COMMENT ON COLUMN V_SAL_NOTE_STATUS.APPROVED_BY IS 'اعتمده (APPROVED_BY) - نص';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.ORDER_ID IS 'رقم أمر البيع (ORDER_ID) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.QUOTE_ID IS 'رقم عرض السعر (QUOTE_ID) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.ORDER_DATE IS 'تاريخ الأمر (ORDER_DATE) - تاريخ';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.DELIVERY_DATE IS 'تاريخ التسليم (DELIVERY_DATE) - تاريخ';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.CUSTOMER_NAME IS 'العميل (CUSTOMER_NAME) - نص';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.INV_KEY IS 'رقم الفاتورة (المفتاح) (INV_KEY) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.ORDER_TOTAL IS 'إجمالي الأمر (ORDER_TOTAL) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.QTY_ORDERED IS 'المطلوب (QTY_ORDERED) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.QTY_DELIVERED IS 'الكمية المسلّمة (QTY_DELIVERED) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.DELIVERED_PCT IS 'نسبة التسليم % (DELIVERED_PCT) - رقم';
COMMENT ON COLUMN V_SAL_ORDER_STATUS.INVOICE_NOTE IS 'الفاتورة (INVOICE_NOTE) - نص';
COMMENT ON COLUMN V_SAL_QUOTE_FUNNEL.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_SAL_QUOTE_FUNNEL.QUOTES IS 'عدد العروض (QUOTES) - رقم';
COMMENT ON COLUMN V_SAL_QUOTE_FUNNEL.TOTAL_VALUE IS 'القيمة (TOTAL_VALUE) - رقم';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.QUOTE_ID IS 'رقم عرض السعر (QUOTE_ID) - رقم';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.QUOTE_DATE IS 'تاريخ العرض (QUOTE_DATE) - تاريخ';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.VALID_UNTIL IS 'ساري حتى (VALID_UNTIL) - تاريخ';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.STATUS IS 'الحالة (STATUS) - نص';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.CUST_ID IS 'الكود (CUST_ID) - رقم';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.CUSTOMER_NAME IS 'العميل (CUSTOMER_NAME) - نص';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.SALES_USER IS 'مندوب البيع (SALES_USER) - نص';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.LINES_COUNT IS 'عدد الأصناف (LINES_COUNT) - رقم';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.QUOTE_TOTAL IS 'إجمالي العرض (QUOTE_TOTAL) - رقم';
COMMENT ON COLUMN V_SAL_QUOTE_TOTAL.VALIDITY IS 'الصلاحية (VALIDITY) - نص';
COMMENT ON COLUMN V_SUPPLIER_EVAL.SUPPLIER_ID IS 'كود المورد (SUPPLIER_ID) - رقم';
COMMENT ON COLUMN V_SUPPLIER_EVAL.CUST_NAME IS 'الاسم (CUST_NAME) - نص';
COMMENT ON COLUMN V_SUPPLIER_EVAL.PURCHASE_INVOICES IS 'فواتير شراء (PURCHASE_INVOICES) - رقم';
COMMENT ON COLUMN V_SUPPLIER_EVAL.PURCHASES_VALUE IS 'قيمة المشتريات (PURCHASES_VALUE) - رقم';
COMMENT ON COLUMN V_SUPPLIER_EVAL.RETURNS_VALUE IS 'قيمة المرتجعات (RETURNS_VALUE) - رقم';
COMMENT ON COLUMN V_SUPPLIER_EVAL.RETURN_PCT IS 'نسبة المرتجع % (RETURN_PCT) - رقم';
COMMENT ON COLUMN V_SUPPLIER_EVAL.LAST_PURCHASE IS 'آخر شراء (LAST_PURCHASE) - تاريخ';
COMMENT ON COLUMN V_SUPPLIER_EVAL.OPEN_PAYABLE IS 'مستحق للمورد (OPEN_PAYABLE) - رقم';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.FROM_STORE IS 'من مخزن (FROM_STORE) - رقم';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.FROM_STORE_NAME IS 'من (FROM_STORE_NAME) - نص';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.TO_STORE IS 'إلى مخزن (TO_STORE) - رقم';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.TO_STORE_NAME IS 'إلى (TO_STORE_NAME) - نص';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.TRANSFERS_WAITING IS 'تحويلات منتظرة (TRANSFERS_WAITING) - رقم';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.QTY_WAITING IS 'كمية منتظرة (QTY_WAITING) - رقم';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.OLDEST_DAYS IS 'أقدم (يوم) (OLDEST_DAYS) - رقم';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.OLDEST_DATE IS 'أقدم مستند (OLDEST_DATE) - تاريخ';
COMMENT ON COLUMN V_TRANSFER_IN_TRANSIT.RECEIPT_APPROVAL_ON IS 'اعتماد الاستلام مفعّل (1 نعم) (RECEIPT_APPROVAL_ON) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.TRANS_SER IS 'رقم الحركة (TRANS_SER) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.TRANS_CODE IS 'رقم التحويل (TRANS_CODE) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.TRANS_DATE IS 'التاريخ (TRANS_DATE) - تاريخ';
COMMENT ON COLUMN V_TRANSFER_STATUS.FROM_STORE IS 'من مخزن (FROM_STORE) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.FROM_STORE_NAME IS 'من (FROM_STORE_NAME) - نص';
COMMENT ON COLUMN V_TRANSFER_STATUS.TO_STORE IS 'إلى مخزن (TO_STORE) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.TO_STORE_NAME IS 'إلى (TO_STORE_NAME) - نص';
COMMENT ON COLUMN V_TRANSFER_STATUS.LINES_COUNT IS 'عدد الأصناف (LINES_COUNT) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.TOTAL_QTY IS 'إجمالي الكمية (TOTAL_QTY) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.RECEIVED_LINES IS 'أصناف مستلمة (RECEIVED_LINES) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.STATE IS 'حالة التحويل (STATE) - القيم بالنص بالظبط: ''تم الاستلام'' / ''في الطريق - لم يُستلم'' / ''استلام جزئي'' / ''قديم - قبل التفعيل'' (غير مستلم قبل تاريخ بداية التتبع TRANSFER_TRACK_FROM) / ''بدون أصناف''. غير المستلم = كل القيم غير ''تم الاستلام''';
COMMENT ON COLUMN V_TRANSFER_STATUS.DAYS_WAITING IS 'أيام الانتظار (DAYS_WAITING) - رقم';
COMMENT ON COLUMN V_TRANSFER_STATUS.RECEIPT_APPROVAL_ON IS 'اعتماد الاستلام مفعّل (1 نعم) (RECEIPT_APPROVAL_ON) - رقم';
COMMENT ON COLUMN V_VAT_MONTHLY.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_VAT_MONTHLY.INV_KIND IS 'INV_KIND - نص';
COMMENT ON COLUMN V_VAT_MONTHLY.INVOICES IS 'عدد الفواتير (INVOICES) - رقم';
COMMENT ON COLUMN V_VAT_MONTHLY.TAXABLE_BASE IS 'TAXABLE_BASE - رقم';
COMMENT ON COLUMN V_VAT_MONTHLY.TAX_AMOUNT IS 'قيمة الضريبة (TAX_AMOUNT) - رقم';
COMMENT ON COLUMN V_VAT_MONTHLY.TOTAL_WITH_TAX IS 'TOTAL_WITH_TAX - رقم';
COMMENT ON COLUMN V_VAT_MONTHLY.INVOICES_WITHOUT_TAX_VALUE IS 'INVOICES_WITHOUT_TAX_VALUE - رقم';
COMMENT ON COLUMN V_VAT_SUMMARY.PERIOD IS 'الفترة (PERIOD) - نص';
COMMENT ON COLUMN V_VAT_SUMMARY.OUTPUT_TAX IS 'ضريبة المبيعات (OUTPUT_TAX) - رقم';
COMMENT ON COLUMN V_VAT_SUMMARY.INPUT_TAX IS 'ضريبة المشتريات (INPUT_TAX) - رقم';
COMMENT ON COLUMN V_VAT_SUMMARY.NET_TAX_DUE IS 'صافي الضريبة المستحقة (NET_TAX_DUE) - رقم';
