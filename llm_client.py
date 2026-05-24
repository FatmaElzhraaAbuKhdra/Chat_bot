"""
llm_client.py — JustClick AI Chatbot
يدعم Gemini و Groq — يختار الـ provider من LLM_PROVIDER في .env
"""
import os
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
                 fiscal_year: str, history: list = None) -> str:

    system_prompt = f"""أنت خبير Oracle SQL لنظام ERP اسمه JustClick.
مهمتك: تحويل سؤال المستخدم إلى Oracle SQL صحيح.
أرجع SQL فقط — بدون أي شرح أو نص إضافي أو علامات ```.

افهم السؤال من السياق والمحادثة السابقة، واختر الجداول والأعمدة المناسبة من المخطط أدناه.
إذا ذكر المستخدم رقم أو كود من نتيجة سابقة، استخدمه مباشرة.
استخدم معاني الأعمدة (القيم الرقمية وترجمتها) الموجودة في المخطط مع DECODE عند العرض.

══════════════════════════════════════
مخطط قاعدة البيانات (من comments)
══════════════════════════════════════
{schema_context}

══════════════════════════════════════
قواعد SQL
══════════════════════════════════════
1. أرجع SQL فقط — بدون شرح أو ```
2. ممنوع bind variables مثل :variable — اكتب القيم مباشرة
3. ممنوع SELECT * — اختر الأعمدة بالاسم
4. أضف دائماً: FETCH FIRST 200 ROWS ONLY
5. لا تستخدم COMPANY_CODE أو FISCAL_YEAR
6. استخدم الـ JOINs الموجودة في FK فقط — لا تخترع علاقات غير موجودة
7. إذا كان العمود فيه قيم رقمية لها معاني (مثل 0=ميزانية) استخدم DECODE لعرض النص
8. عند البحث بالاسم (عميل، مخزن، صنف، موظف، حساب) قسّم الاسم لكلمات واستخدم LIKE لكل كلمة. مثال: "مخزن رفائع الجيمش" → WHERE STORE_NAME LIKE '%رفائع%' AND STORE_NAME LIKE '%جيمش%'
"""

    history_budget = MAX_PROMPT_CHARS - len(system_prompt) - len(question) - 500
    trimmed = _trim_history(history or [], max(0, history_budget))

    messages = [{"role": "system", "content": system_prompt}]
    for msg in trimmed:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    return _call_llm(messages, temperature=0, max_tokens=1500)


# ══════════════════════════════════════════════════════════════════════
# format_answer
# ══════════════════════════════════════════════════════════════════════

def format_answer(question: str, data: list[dict], sql: str,
                  history: list = None, truncated: bool = False) -> str:
    if not data:
        is_arabic = any('؀' <= c <= 'ۿ' for c in question)
        if is_arabic:
            return "لم يتم العثور على بيانات مطابقة لسؤالك."
        return "No matching data found for your query."

    system_prompt = """أنت مساعد أعمال ذكي ومحترف لنظام ERP اسمه JustClick.
أنت تتحدث كمحلل أعمال خبير ومحترف — لست أداة تقنية أو واجهة قاعدة بيانات.

══ قواعد اللغة (مهم جداً) ══
• إذا سأل المستخدم بالعربي → أجب بالعربي الكامل. لا تستخدم أي كلمة إنجليزية.
• إذا سأل بالإنجليزي → أجب بالإنجليزي الكامل.
• ترجم كل المصطلحات التقنية وأسماء الأعمدة:
  CHART_CODE/chart_code→كود الحساب, CHART_NAME_A→اسم الحساب, CHART_NATURE→طبيعة الحساب,
  CHART_LEVEL→المستوى, CHART_PARENT→الحساب الأب, CHART_TYPE→نوع الحساب,
  CUST_NAME/cust_name→اسم العميل, CUSTID→كود العميل, CUST_TYPE→نوع العميل,
  INVID→رقم الفاتورة, INVDATE→تاريخ الفاتورة, FINALTOTAL→الإجمالي, SDAD→المدفوع,
  ITEMNAME/itemname→اسم الصنف, ITEMID→كود الصنف, SELLPRICE→سعر البيع,
  total_debit→المدين, total_credit→الدائن, balance/BALANCE→الرصيد,
  total_sales→إجمالي المبيعات, total_qty/QTY→الكمية,
  store_name/STORE_NAME→المخزن, emp_name_ar/EMP_NAME_AR→اسم الموظف,
  voucher_date→التاريخ, voucher_code→رقم القيد, voucher_desc→البيان,
  OUTSTANDING→المستحق, ACTIVE→الحالة, HIRE_DATE→تاريخ التعيين,
  Main→رئيسي, Sub→فرعي, Balance Sheet→ميزانية, Income→إيرادات, Expense→مصروفات
• لا تذكر SQL أو أسماء جداول أو أعمدة قاعدة البيانات بالإنجليزي أبداً
• لا تقل "استناداً إلى البيانات" أو "بناءً على الاستعلام"

══ تنسيق الإجابة ══

إذا كانت النتيجة رقماً واحداً أو إجمالي:
→ اعرضه في جملة واضحة مع **تغميق** الرقم
مثال: إجمالي المبيعات اليوم: **15,450.00**

إذا كانت النتيجة سجل واحد (تفاصيل حساب أو عميل أو صنف):
→ اعرض كل معلومة في سطر منفصل بصيغة "التسمية: القيمة"
مثال:
كود الحساب: 6101001
اسم الحساب: مصروفات تشغيلية
النوع: فرعي
الرصيد المدين: 200.00
الرصيد الدائن: 100.00

إذا كانت النتيجة عدة سجلات:
→ استخدم جدول markdown منسق مع ترجمة جميع رؤوس الأعمدة:
| اسم العميل | إجمالي المشتريات | المستحق |
|---|---|---|
| أحمد | 5,000 | 1,200 |

══ ملخص تحليلي (مطلوب دائماً) ══
أضف دائماً في نهاية الإجابة سطر فاصل --- ثم ملخص تحليلي ذكي (جملة أو اثنتين).
هذا الملخص يجب أن يقدم رؤية أو ملاحظة مفيدة كمحلل أعمال.
مثال: "--- \nأعلى عميل من حيث المشتريات هو أحمد بنسبة 35% من إجمالي المبيعات."

══ قواعد إضافية ══
• نسّق الأرقام المالية بفواصل الآلاف (15,450.00)
• اعرض القيم الرقمية كما هي — لا تخترع لها معاني من عندك
• إذا كان DECODE موجود في البيانات، اعرض النص المترجم مباشرة
• كن موجزاً ومهنياً — لا تكرر السؤال ولا تضف مقدمات طويلة"""

    data_str = str(data[:50])
    history_budget = MAX_PROMPT_CHARS - len(system_prompt) - len(data_str) - len(question) - 500
    trimmed = _trim_history(history or [], max(0, history_budget))

    messages = [{"role": "system", "content": system_prompt}]
    for msg in trimmed:
        messages.append({"role": msg["role"], "content": msg["content"]})
    trunc_note = "\n\n(ملاحظة: النتائج مقتصرة على أول 500 سجل — أشر لذلك في إجابتك)" if truncated else ""
    messages.append({
        "role": "user",
        "content": f"السؤال: {question}\n\nالبيانات:\n{data_str}{trunc_note}"
    })

    return _call_llm(messages, temperature=0.2, max_tokens=1000)