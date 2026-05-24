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
    'جدول الأصناف المخزنية - يُعرِّف كل صنف وخصائصه';

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


-- =============================================================================
-- End of Comments Script - Page 20 (STORE_TRANSACTION_FORM)
-- =============================================================================
