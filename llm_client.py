"""
llm_client.py — JustClick AI Chatbot
يدعم Gemini و Groq — يختار الـ provider من LLM_PROVIDER في .env
"""
import os
import re
import time
import logging

log = logging.getLogger("llm")

MAX_PROMPT_CHARS = 28000
_provider = None

# ── Token usage tracking ───────────────────────────────────────────
_usage = {
    "total_prompt": 0,
    "total_completion": 0,
    "total_tokens": 0,
    "request_count": 0,
    "last_prompt": 0,
    "last_completion": 0,
}


def get_usage() -> dict:
    return dict(_usage)


def _track_usage(prompt_tokens: int, completion_tokens: int):
    _usage["last_prompt"] = prompt_tokens
    _usage["last_completion"] = completion_tokens
    _usage["total_prompt"] += prompt_tokens
    _usage["total_completion"] += completion_tokens
    _usage["total_tokens"] = _usage["total_prompt"] + _usage["total_completion"]
    _usage["request_count"] += 1


def _get_provider() -> str:
    global _provider
    if _provider is None:
        _provider = os.getenv("LLM_PROVIDER", "groq").lower()
        log.info(f"[LLM] provider={_provider}")
    return _provider


def set_provider(name: str):
    global _provider
    name = name.lower()
    if name not in ("groq", "gemini"):
        raise ValueError(f"Unknown provider: {name}")
    _provider = name
    log.info(f"[LLM] provider switched to {name}")


# ── Gemini ──────────────────────────────────────────────────────────

_gemini_model = None


def _get_gemini_model():
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        _gemini_model = genai.GenerativeModel(model_name)
        log.info(f"[LLM] Gemini model={model_name}")
    return _gemini_model


def _call_gemini(messages: list, temperature: float, max_tokens: int) -> str:
    system_text = ""
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            system_text += msg["content"] + "\n"
        elif msg["role"] == "user":
            contents.append({"role": "user",  "parts": [msg["content"]]})
        elif msg["role"] == "assistant":
            contents.append({"role": "model", "parts": [msg["content"]]})

    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(
        model_name,
        system_instruction=system_text.strip() if system_text else None
    )
    cfg = genai.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
    resp = model.generate_content(contents, generation_config=cfg)
    if resp.usage_metadata:
        _track_usage(
            resp.usage_metadata.prompt_token_count or 0,
            resp.usage_metadata.candidates_token_count or 0
        )
    return resp.text.strip()


# ── Groq ────────────────────────────────────────────────────────────

_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


def _get_groq_model():
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _call_groq(messages: list, temperature: float, max_tokens: int) -> str:
    try:
        resp = _get_groq_client().chat.completions.create(
            model=_get_groq_model(),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=25.0,
        )
        if resp.usage:
            _track_usage(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        err = str(e)
        if ("413" in err or "too large" in err.lower()) and len(messages) > 2:
            resp = _get_groq_client().chat.completions.create(
                model=_get_groq_model(),
                messages=[messages[0], messages[-1]],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=25.0,
            )
            if resp.usage:
                _track_usage(resp.usage.prompt_tokens, resp.usage.completion_tokens)
            return resp.choices[0].message.content.strip()
        raise


# ── Unified call ────────────────────────────────────────────────────

def _call_llm(messages: list, temperature: float, max_tokens: int) -> str:
    p = _get_provider()
    providers = ["groq", "gemini"] if p == "groq" else ["gemini", "groq"]
    last_err = None
    for prov in providers:
        try:
            if prov == "gemini":
                return _call_gemini(messages, temperature, max_tokens)
            if prov == "groq":
                return _call_groq(messages, temperature, max_tokens)
        except Exception as e:
            err = str(e).lower()
            if "429" in str(e) or "rate_limit" in err or "resourceexhausted" in err:
                log.warning(f"[LLM] {prov} rate-limited, trying fallback...")
                last_err = e
                continue
            raise
    raise last_err


def _trim_history(history: list, budget: int) -> list:
    if not history:
        return []
    trimmed, used = [], 0
    for msg in reversed(history):
        msg_len = len(msg.get("content", ""))
        if used + msg_len > budget:
            break
        trimmed.insert(0, msg)
        used += msg_len
    while trimmed and trimmed[0].get("role") == "assistant":
        trimmed.pop(0)
    return trimmed


# ══════════════════════════════════════════════════════════════════════
# generate_sql
# ══════════════════════════════════════════════════════════════════════

def generate_sql(schema_context: str, question: str, company_code: str,
                 fiscal_year: str, history: list = None,
                 extra_context: str = "") -> str:

    system_prompt = f"""أنت خبير Oracle SQL لنظام ERP اسمه JustClick.
مهمتك: تحويل سؤال المستخدم إلى Oracle SQL صحيح.
أرجع SQL فقط — بدون أي شرح أو نص إضافي أو علامات ```.

══ تعليمات مهمة جداً ══
- استخدم الجداول والأعمدة الموجودة في المخطط أدناه فقط — لا تخترع جداول غير موجودة.
- لا تستخدم جدول INST أبداً — هو جدول إعدادات وليس بيانات.
- افهم السؤال من السياق والمحادثة السابقة.
- استخدم معاني الأعمدة (القيم الرقمية وترجمتها) الموجودة في المخطط مع DECODE عند العرض.

══ مخطط قاعدة البيانات ══
{schema_context}

══ قواعد SQL ══
1. أرجع SQL فقط — بدون شرح أو ```
2. ممنوع bind variables مثل :variable — اكتب القيم مباشرة
3. ممنوع SELECT * — اختر الأعمدة بالاسم
4. أضف دائماً: FETCH FIRST 200 ROWS ONLY
5. ⛔ ممنوع تماماً استخدام COMPANY_CODE أو FISCAL_YEAR في أي مكان في الـ SQL — لا في WHERE ولا في JOIN ولا في أي مكان آخر
6. استخدم الـ JOINs الموجودة في FK فقط — لا تخترع علاقات غير موجودة
7. إذا كان العمود فيه قيم رقمية لها معاني (مثل 0=ميزانية) استخدم DECODE لعرض النص
8. عند البحث بالاسم قسّم الكلمات واستخدم LIKE لكل كلمة

══ قواعد المحاسبة (مهم جداً) ══
- CHARTS.CHART_TYPE: 0=ميزانية (أصول/خصوم)، 1=قائمة الدخل (إيرادات ومصروفات)
- الإيرادات والمصروفات = حسابات قائمة الدخل (CHART_TYPE = 1)
- VOUCHERS_DET.AMOUNT: موجب (+) = مدين، سالب (-) = دائن
  → المدين = SUM(CASE WHEN AMOUNT > 0 THEN AMOUNT ELSE 0 END)
  → الدائن = SUM(CASE WHEN AMOUNT < 0 THEN ABS(AMOUNT) ELSE 0 END)
- ⚠ JOIN بين VOUCHERS و VOUCHERS_DET لازم على العمودين معاً:
  JOIN VOUCHERS v ON v.VOUCHER_CODE = vd.VOUCHER_CODE AND v.VOUCHER_MONTH = vd.VOUCHER_MONTH
- للفترات الزمنية استخدم ADD_MONTHS:
  → آخر 3 شهور: v.VOUCHER_DATE >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -3)
  → آخر سنة: v.VOUCHER_DATE >= ADD_MONTHS(TRUNC(SYSDATE), -12)

══ أمثلة ══
سؤال: "اعرض كل المخازن"
SQL: SELECT STORE_CODE, STORE_NAME FROM STORE ORDER BY STORE_NAME FETCH FIRST 200 ROWS ONLY

سؤال: "كم عدد الموظفين"
SQL: SELECT COUNT(*) AS employee_count FROM EMPLOYEES WHERE EMP_ACTIVE = '1' AND END_SERVICE_FLG = 'N' FETCH FIRST 200 ROWS ONLY

سؤال: "أعلى 5 عملاء في المبيعات"
SQL: SELECT cu.CUST_NAME, COUNT(m.INV_KEY) AS invoice_count, SUM(m.FINALTOTAL) AS total_sales FROM MAIN_INV m JOIN CUST cu ON cu.CUSTID = m.CUST_ID AND cu.CUST_TYPE = m.CUST_TYPE WHERE m.INVTYPE = 0 AND m.RETURN_FLAG = 0 AND cu.CUST_TYPE = 0 GROUP BY cu.CUST_NAME ORDER BY total_sales DESC FETCH FIRST 5 ROWS ONLY

سؤال: "حسابات تبدا ب 6"
SQL: SELECT CHART_CODE, CHART_NAME_A, DECODE(CHART_TYPE, 0, 'ميزانية', 1, 'قائمة الدخل') AS CHART_TYPE, DECODE(CHART_NATURE, 0, 'رئيسي', 1, 'فرعي') AS CHART_NATURE FROM CHARTS WHERE CHART_CODE LIKE '6%' ORDER BY CHART_CODE FETCH FIRST 200 ROWS ONLY

سؤال: "إجمالي المبيعات اليوم"
SQL: SELECT COUNT(*) AS invoice_count, NVL(SUM(FINALTOTAL), 0) AS total_sales FROM MAIN_INV WHERE INVTYPE = 0 AND RETURN_FLAG = 0 AND TRUNC(INVDATE) = TRUNC(SYSDATE) FETCH FIRST 200 ROWS ONLY

سؤال: "رصيد مخزن الأدوات"
SQL: SELECT s.STORE_NAME, i.ITEMNAME, t.QTY FROM TRANSACTION_TOT t JOIN ITEMS i ON i.ITEMID = t.ITEMID JOIN STORE s ON s.STORE_CODE = t.STORE_CODE WHERE s.STORE_NAME LIKE '%أدوات%' AND t.QTY <> 0 ORDER BY i.ITEMNAME FETCH FIRST 200 ROWS ONLY

سؤال: "الإيرادات والمصروفات خلال آخر 6 شهور"
SQL: SELECT TO_CHAR(v.VOUCHER_DATE, 'YYYY-MM') AS الشهر, SUM(CASE WHEN vd.AMOUNT > 0 THEN vd.AMOUNT ELSE 0 END) AS المصروفات, SUM(CASE WHEN vd.AMOUNT < 0 THEN ABS(vd.AMOUNT) ELSE 0 END) AS الايرادات, SUM(vd.AMOUNT) AS الصافي FROM VOUCHERS_DET vd JOIN VOUCHERS v ON v.VOUCHER_CODE = vd.VOUCHER_CODE AND v.VOUCHER_MONTH = vd.VOUCHER_MONTH JOIN CHARTS c ON c.CHART_CODE = vd.CHART_CODE WHERE c.CHART_TYPE = 1 AND v.VOUCHER_DATE >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -6) GROUP BY TO_CHAR(v.VOUCHER_DATE, 'YYYY-MM') ORDER BY الشهر FETCH FIRST 200 ROWS ONLY

سؤال: "كشف حساب 1101 خلال آخر 3 شهور"
SQL: SELECT v.VOUCHER_DATE, v.VOUCHER_CODE, v.VOUCHER_DESC, CASE WHEN vd.AMOUNT > 0 THEN vd.AMOUNT ELSE 0 END AS مدين, CASE WHEN vd.AMOUNT < 0 THEN ABS(vd.AMOUNT) ELSE 0 END AS دائن, vd.AMOUNT FROM VOUCHERS_DET vd JOIN VOUCHERS v ON v.VOUCHER_CODE = vd.VOUCHER_CODE AND v.VOUCHER_MONTH = vd.VOUCHER_MONTH WHERE vd.CHART_CODE = '1101' AND v.VOUCHER_DATE >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -3) ORDER BY v.VOUCHER_DATE, v.VOUCHER_CODE FETCH FIRST 200 ROWS ONLY
"""

    # Phase 3/4/5: Inject learned context, JOIN hints, followup context
    if extra_context:
        system_prompt += f"\n{extra_context}"

    history_budget = MAX_PROMPT_CHARS - len(system_prompt) - len(question) - 500
    trimmed = _trim_history(history or [], max(0, history_budget))

    messages = [{"role": "system", "content": system_prompt}]
    for msg in trimmed:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    # Prompt versioning: track which version was used
    _version_id = "v1_default"
    try:
        from prompt_manager import select_prompt, record_result
        _selected = select_prompt()
        _version_id = _selected.version_id
    except Exception:
        pass

    start_t = time.time()
    result = _call_llm(messages, temperature=0, max_tokens=1500)
    elapsed_ms = int((time.time() - start_t) * 1000)

    # Record result for A/B tracking
    try:
        from prompt_manager import record_result
        # Success = non-empty SQL-like response
        success = bool(result and result.strip().upper().startswith("SELECT"))
        record_result(_version_id, success, elapsed_ms)
    except Exception:
        pass

    return _strip_tenant_filters(result)


def _strip_tenant_filters(sql: str) -> str:
    """Remove COMPANY_CODE / FISCAL_YEAR conditions the LLM may generate."""
    pattern = r"\s+AND\s+(?:\w+\.)?(?:COMPANY_CODE|FISCAL_YEAR)\s*=\s*(?:\d+|'[^']*')"
    return re.sub(pattern, "", sql, flags=re.IGNORECASE)


# ══════════════════════════════════════════════════════════════════════
# format_answer
# ══════════════════════════════════════════════════════════════════════

def format_answer(question: str, data: list[dict], sql: str,
                  history: list = None, truncated: bool = False) -> str:

    if not data:
        is_arabic = any('؀' <= c <= 'ۿ' for c in question)
        if is_arabic:
            return "لم أجد بيانات مطابقة لسؤالك. جرّب إعادة صياغة السؤال أو توسيع نطاق البحث."
        return "No matching data found. Try rephrasing your question or broadening the search criteria."

    system_prompt = """أنت مساعد مالي احترافي لنظام JustClick ERP.
لست أداة استعلام أو واجهة قاعدة بيانات. أنت مستشار أعمال تنفيذي يفكر ويحلل ويقدم رؤى مالية دقيقة.

══ هويتك وشخصيتك ══
• مستشار مالي تنفيذي واثق وهادئ ودقيق
• تملك خبرة عميقة في التحليل المالي والمحاسبة وإدارة الأعمال
• تتحدث بنبرة مهنية راقية، كمدير مالي يشرح لمجلس إدارة
• لا تتردد ولا تستخدم لغة ضعيفة ("ربما"، "قد يكون"، "يبدو أن")
• تقدم استنتاجات واضحة وتوصيات عملية

══ قواعد اللغة ══
• سؤال بالعربي → إجابة عربية كاملة. ممنوع أي كلمة إنجليزية.
• سؤال بالإنجليزي → إجابة إنجليزية كاملة.
• ترجم كل أسماء الأعمدة التقنية:
  CHART_CODE→كود الحساب, CHART_NAME_A→اسم الحساب, CHART_NATURE→طبيعة الحساب,
  CHART_LEVEL→المستوى, CHART_PARENT→الحساب الأب, CHART_TYPE→نوع الحساب,
  CUST_NAME→العميل, CUSTID→كود العميل, CUST_TYPE→نوع العميل,
  INVID→رقم الفاتورة, INVDATE→التاريخ, FINALTOTAL→الإجمالي, SDAD→المدفوع,
  ITEMNAME→الصنف, ITEMID→كود الصنف, SELLPRICE→سعر البيع,
  total_debit/DEBIT→المدين, total_credit/CREDIT→الدائن, BALANCE→الرصيد,
  total_sales/TOTAL_SALES→إجمالي المبيعات, QTY→الكمية,
  STORE_NAME→المخزن, EMP_NAME_AR→الموظف,
  VOUCHER_DATE→التاريخ, VOUCHER_CODE→رقم القيد, VOUCHER_DESC→البيان,
  OUTSTANDING→المستحق, HIRE_DATE→تاريخ التعيين
• ممنوع تماماً: SQL، أسماء جداول، أسماء أعمدة تقنية — إلا إذا طلب المستخدم صراحةً
• ممنوع تماماً: "بناءً على البيانات"، "استناداً للاستعلام"، "وفقاً للنتائج"
• ممنوع تماماً: تكرار السؤال أو بدء الإجابة بمقدمة عامة

══ هيكل الإجابة الاحترافية ══

【القاعدة الأولى】 ابدأ دائماً بملخص مباشر (سطر أو سطرين) يجيب على السؤال فوراً:
   ✓ "المبيعات اليوم **15,450** بـ **8 فواتير** — أداء يتجاوز المعدل اليومي."
   ✓ "**12 عميل** متأخر في السداد بإجمالي **284,500** — تحتاج متابعة عاجلة."
   ✗ لا تبدأ بـ "بناءً على البيانات..." أو "إليك النتائج..."

【القاعدة الثانية】 إذا كانت البيانات تحتوي على سجلات متعددة، استخدم هذا القالب الاحترافي:

### النتيجة

[ملخص قصير يجيب مباشرة على السؤال]

| [عنوان 1] | [عنوان 2] | [عنوان 3] | ... |
| --------- | --------- | --------- | --- |
| ...       | ...       | ...       | ... |

### ملاحظات

* ملاحظة مهمة أو تنبيه 1
* ملاحظة مهمة أو تنبيه 2

【القاعدة الثالثة】 لا تكرر المعلومات الموجودة في الجدول داخل النص.

【القاعدة الرابعة — شجرة الحسابات】
إذا كانت البيانات تمثل شجرة حسابات أو حسابات محاسبية:
• استخدم أعمدة: كود الحساب | اسم الحساب | نوع الحساب | طبيعة الحساب | المستوى
• بعد الجدول أضف قسم "### تحليل الهيكل" يوضح التسلسل الهرمي:
  مثال:
  1
  └── 11
      └── 1101
          ├── 1101001
          └── 1101002
• اشرح الحساب الجذر وعدد المستويات وعدد الحسابات التفصيلية.

【القاعدة الخامسة — المؤشرات المالية】
إذا كانت النتيجة تحتوي على أرقام مالية أو مؤشرات:
• اعرض أهم رقم أولاً مع **تغميق**.
• ثم الجدول.
• ثم الاستنتاج والتوصية في ### ملاحظات.

【القاعدة السادسة — البيانات البسيطة】
• رقم واحد → جملة واضحة مع **تغميق** الرقم
• سجل واحد → بطاقة معلومات (التسمية: القيمة)

══ نبرة التحليل ══
• أداء إيجابي (نمو/ارتفاع) → واثقة تؤكد النتيجة مع التحفيز
• مخاطر (تأخر/انخفاض/تركّز) → حازمة تنبّه وتقترح حلول
• بيانات محايدة (قوائم/كشوف) → مهنية هادئة مع ملاحظات ذكية
• قيمة صفرية → إيجابية تقترح بدائل وتفسيرات

══ قواعد التنسيق ══
• الأرقام المالية بفواصل الآلاف: 15,450.00
• عرض القيم كما هي — لا اختراع أرقام
• الإيجاز قوة — لا حشو ولا تكرار
• الإجابة تبدو كأنها مكتوبة بواسطة مستشار مالي تنفيذي وليس تقرير قاعدة بيانات خام"""

    data_str = str(data[:50])
    history_budget = MAX_PROMPT_CHARS - len(system_prompt) - len(data_str) - len(question) - 500
    trimmed = _trim_history(history or [], max(0, history_budget))

    messages = [{"role": "system", "content": system_prompt}]
    for msg in trimmed:
        messages.append({"role": msg["role"], "content": msg["content"]})
    trunc_note = "\n\n(ملاحظة: النتائج مقتصرة على أول 500 سجل — أشر لذلك باختصار)" if truncated else ""
    messages.append({
        "role": "user",
        "content": f"السؤال: {question}\n\nالبيانات:\n{data_str}{trunc_note}"
    })

    return _call_llm(messages, temperature=0.25, max_tokens=1500)