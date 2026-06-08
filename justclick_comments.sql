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
