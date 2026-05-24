import os
from groq import Groq

_client = None

MAX_PROMPT_CHARS = 28000


def _get_model():
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def _trim_history(history: list, budget: int) -> list:
    if not history:
        return []
    trimmed = []
    used = 0
    for msg in reversed(history):
        msg_len = len(msg["content"])
        if used + msg_len > budget:
            break
        trimmed.insert(0, msg)
        used += msg_len
    return trimmed


def _call_groq(messages: list, temperature: float, max_tokens: int) -> str:
    try:
        response = get_client().chat.completions.create(
            model=_get_model(),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        err = str(e)
        if ("413" in err or "too large" in err.lower()) and len(messages) > 2:
            return get_client().chat.completions.create(
                model=_get_model(),
                messages=[messages[0], messages[-1]],
                temperature=temperature,
                max_tokens=max_tokens
            ).choices[0].message.content.strip()
        raise


def generate_sql(schema_context: str, question: str, company_code: str,
                 fiscal_year: str, history: list = None) -> str:

    system_prompt = f"""أنت خبير Oracle SQL لنظام ERP اسمه JustClick.
لديك الوصف الكامل لمخطط قاعدة البيانات أدناه — اقرأه جيداً قبل كتابة أي SQL.

{schema_context}

=== مفاهيم محاسبية ===
- تفاصيل/حركات/كشف حساب = بيانات من VOUCHERS_DET (وليس CHARTS)
- CHARTS = تعريف الحساب فقط (اسم، طبيعة، مستوى)
- VOUCHERS_DET = كل الحركات المالية على الحسابات (مدين/دائن)

=== قواعد ===
- اختر الأعمدة المناسبة (لا تستخدم SELECT *)
- اعمل JOIN مع الجداول المرتبطة لإرجاع تواريخ وأسماء وأوصاف كاملة
- لا تستخدم bind variables مثل :variable — اكتب القيم مباشرة
- أرجع SQL فقط بدون شرح ولا ```
"""

    history_budget = MAX_PROMPT_CHARS - len(system_prompt) - len(question) - 500
    trimmed = _trim_history(history, max(0, history_budget))

    messages = [{"role": "system", "content": system_prompt}]
    for msg in trimmed:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    return _call_groq(messages, temperature=0, max_tokens=1000)


def format_answer(question: str, data: list[dict], sql: str, history: list = None) -> str:
    if not data:
        return "لم يتم العثور على بيانات مطابقة لسؤالك. / No matching data found."

    system_prompt = """أنت مساعد ذكي لنظام ERP اسمه JustClick.
- أجب بنفس لغة السؤال (عربي أو إنجليزي)
- إذا كانت البيانات تفاصيل حركات: اعرضها كجدول نصي منظم (تاريخ | رقم | وصف | مدين | دائن)
- إذا كانت البيانات إجماليات (total_debit, total_credit, balance): اعرضها مباشرة كأرقام واضحة
- أسماء الأعمدة: total_debit=المدين، total_credit=الدائن، balance=الرصيد
- لا تكتب عمليات جمع أو تعداد للأرقام الفردية — أعطِ النتيجة النهائية مباشرة
- لا تذكر SQL"""

    data_str = str(data[:50])
    history_budget = MAX_PROMPT_CHARS - len(system_prompt) - len(data_str) - 500
    trimmed = _trim_history(history, max(0, history_budget))

    messages = [{"role": "system", "content": system_prompt}]
    for msg in trimmed:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({
        "role": "user",
        "content": f"السؤال: {question}\nالبيانات: {data_str}"
    })

    return _call_groq(messages, temperature=0.3, max_tokens=800)
