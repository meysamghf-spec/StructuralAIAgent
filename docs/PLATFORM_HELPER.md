# Platform helper — AI assistant that knows the platform and reports bugs
# دستیار هوشمند پلتفرم — آشنا با پلتفرم و گزارش‌دهندهٔ خطا

Languages: [English](#english) · [فارسی](#فارسی) · [Finglish](#finglish)

---

## English

### What it is
A provider-agnostic chat helper (`backend/app/platform_helper/`) that:
* answers greetings, "how do I…", and platform questions using a maintained knowledge file (`knowledge/structuralai.md`);
* optionally answers free-form chat through any OpenAI-compatible LLM, streaming tokens (`agent_run.token` SSE events);
* detects bug reports ("this button doesn't work") and failures, and stores a **redacted, de-duplicated** record in the `platform_issues` table;
* lets an admin post a status / fix note back, which the user sees in chat ("issue status").

Engineering numbers are **never** produced by the LLM — rule-based engines run first; the LLM only converses, explains, and routes.

### Provider setup (no code changes)
| Env var | Meaning |
|---|---|
| `LLM_PROVIDER` | `auto` (default), `stub`, `none`, a preset name, or `custom` |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | primary OpenAI-compatible endpoint |
| `LLM_FALLBACKS` | e.g. `groq,openrouter,pollinations` |
| `LLM_<NAME>_API_KEY / _MODEL / _BASE_URL` | per preset (`GEMINI`, `GROQ`, `OPENROUTER`, `NVIDIA`, `SAMBANOVA`, `MISTRAL`, `CLOUDFLARE`, `CEREBRAS`, `OPENAI`) |
| `LLM_KEYLESS_FALLBACK` | `0` disables anonymous Pollinations |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`, `LLM_MAX_HISTORY` | tuning |

`auto` = every preset that has a key, in quality order, then key-less Pollinations. A 429 puts that provider on cooldown (Retry-After, default 60 s) and the next one is used; streaming falls back only before the first token. With nothing available a stub gives a useful capability message.

**Recommendation:** get one free key (Gemini or Groq, plus OpenRouter) and keep Pollinations as the key-less safety net. Pollinations is anonymous, has no SLA, and prompts are sent to a third party — do not rely on it for confidential data.

### Generated platform knowledge (no hand-maintained page/plan/export lists)

The product facts the assistant answers from are **generated at runtime** by `backend/app/application/platform_knowledge.py` and injected next to the hand-written rules in `knowledge/structuralai.md` (the `HelperService(knowledge_provider=…, faq_provider=…)` hooks wired in `platform_helper_factory.knowledge_hooks()`; the `platform_helper` package itself stays product-agnostic):

- pages (checked against `frontend/lib/nav.ts` by a test), plans/limits/durations (`billing/plans.json`), crypto payment (`billing/crypto.py`), export kinds and plan gates (`chat_actions`), the agent capability catalog, and Validation / Approval / Memory (from their enums);
- the **live per-user context** (plan + limits, project selected, model exists) is added to the system prompt every turn;
- when the LLM is unreachable, platform questions get a **static FAQ built from the same knowledge** (`provider: "faq"`) instead of the generic stub;
- "how do I / چطور / چیست / explain" questions are answered (with an offer to run the action) and never executed; direct commands still run as before;
- `tests/test_platform_knowledge.py` fails if a page, plan or export kind is missing;
- optional: `PLATFORM_HELP_LLM_PROVIDER` (+ `PLATFORM_HELP_LLM_MODEL`) pins a stronger provider first for the helper; it is ignored when that provider has no key, defaults unchanged.

**Maintained sources the assistant is told about (edit these when the product changes):**
- `platform_knowledge.py`: `CAPABILITY_MATRIX` (honest yes / in progress / no / partial / unconfirmed per capability: update a row's status when a feature ships), `EXAMPLES` (one example chat command per capability), `LOGIN_OPTIONS`, `PUBLIC_PAGES`, `RELATED_PRODUCTS`, `DIAGNOSE` (error-code table: cause + next step).
- `platform_whats_new.py`: `WHATS_NEW`, newest first, one entry per user-visible feature that is **merged and live** (never list work in progress). Tests fail if a ref is unknown or an entry is missing from the prompt.
- **Per-question sections:** `build_platform_knowledge(fa, message)` always sends the core (identity, matrix, limits, what's new) plus only the sections the question is about (billing, exports, login, diagnose ...), keeping prompts compact.
- **Error diagnosis (honest):** an error the user describes is classified `diagnose`: the assistant explains the probable cause from `DIAGNOSE` and the error text and *offers* to file an issue (`report a problem: ...` or `report it`). Nothing is filed silently, and the assistant never claims it can change code or fix the site; filed issues follow the safety design below (records only; fixes need a human admin).

### Safety design
* Issues are **records only**. A proposed fix is a stored *draft* (diff or PR text) and is never applied.
* `approve-fix` needs a signed-in **human** admin (`PLATFORM_ADMIN_ACCOUNTS`); the machine token gets 403. Even approval does not merge or deploy — a person does that in GitHub.
* No auto-deploy, no auto-merge.
* Keys, tokens, e-mails and long hex strings are redacted before storage / webhook.
* Dedupe by key with an occurrence counter, so a loop cannot flood the list.
* Every helper call is wrapped: an LLM/provider/DB failure can never break normal chat.
* Webhook is off by default.

### API
* `GET /api/v1/admin/platform-issues?open_only=true&status=&limit=`
* `GET /api/v1/admin/platform-issues/{id}`
* `POST /api/v1/admin/platform-issues/{id}/post-back` `{status?, fix_note?, fix_pr_url?, proposed_fix?}`
* `POST /api/v1/admin/platform-issues/{id}/propose-fix` `{kind: diff|pr_draft, title, body, diff}`
* `POST /api/v1/admin/platform-issues/{id}/approve-fix` (human admin only)
* `GET /api/v1/platform-issues/mine`, `GET /api/v1/platform-helper/status`, `GET /api/v1/platform-helper/admin-check`

Auth: `Authorization: Bearer <PLATFORM_ISSUE_ADMIN_TOKEN>` (machine) or a signed-in admin account.
UI: `/workspace/admin/platform-issues`.

### Webhook (optional)
Set `PLATFORM_ISSUE_WEBHOOK_URL` (+ `PLATFORM_ISSUE_WEBHOOK_SECRET`, `PLATFORM_ISSUE_WEBHOOK_RETRIES`).
```json
{"schema_version":1,"event":"platform_issue.created|platform_issue.updated","delivery_id":"uuid","sent_at":"ISO-8601",
 "product":"structuralai",
 "issue":{"id":"","title":"","summary":"","category":"","severity":"low|medium|high|critical",
  "source":"user_report|auto_detected|admin","status":"open|triaged|fix_in_progress|fix_ready|awaiting_approval|resolved|rejected|wontfix",
  "page":"","conversation_id":"","project_id":"","user_message":"","assistant_excerpt":"","error_text":"",
  "steps_to_reproduce":"","expected":"","actual":"","suspected_files":[],"app_version":"","locale":"fa|en",
  "occurrences":1,"dedupe_key":"","fix_note":"","fix_pr_url":"","proposed_fix":null,"created_at":"","updated_at":""}}
```
Headers: `X-Platform-Event`, `X-Platform-Delivery`, `X-Platform-Timestamp`, `X-Platform-Signature: sha256=<hex>` where hex = HMAC-SHA256(secret, `"{timestamp}." + raw_body`).
Retries: exponential backoff up to 30 s; 4xx other than 408/429 are not retried.

Verify (Python):
```python
import hmac, hashlib
def ok(secret, ts, body, sig):
    exp = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(exp, sig)
```

### Porting to TrafficLens (Traffic Urban)
The package has **no imports from the host app**; the issue store and knowledge file are injected.
1. Copy `backend/app/platform_helper/` (config, llm, issues, intents, prompt, service) and `tests/test_platform_helper.py`.
2. Write `knowledge/trafficlens.md` (pages, features, codes, known issues, chat commands) and point `prompt.py`'s loader at it; adjust the product name in `issues.py`/webhook payload.
3. Add migration `030_platform_issues.sql` and a repository implementing `IssueStore` (`add/get/list/update/find_open_by_dedupe/delete`) — see `postgres_platform_issue_repository.py`.
4. Add a factory (`platform_helper_factory.py`) and routes (`platform_issues.py`); register in the router.
5. In the chat service call `helper.handle(...)` *after* the domain engines and *before* the generic fallback (see `_helper_reply` and the `_run_general_chat` branch); emit `agent_run.token` when a progress sink exists.
6. Frontend: copy `lib/platform-issues.ts`, the admin page, the token handling in `useChat`, and the chat-UI components.
7. Set the same env vars; keep intents for TrafficLens engines (traffic counts, signals, etc.) on the rule-based side.

---

## فارسی

### این چیست؟
یک دستیار گفتگوی مستقل از ارائه‌دهنده (`backend/app/platform_helper/`) که:
* سلام و «چطور…؟» و پرسش دربارهٔ پلتفرم را با فایل دانش (`knowledge/structuralai.md`) پاسخ می‌دهد؛
* در صورت تنظیم، با هر LLM سازگار با OpenAI گفتگوی آزاد می‌کند (استریم توکن‌به‌توکن)؛
* گزارش خطا را تشخیص می‌دهد و یک رکورد **پاک‌سازی‌شده و بدون تکرار** در جدول `platform_issues` می‌گذارد؛
* مدیر می‌تواند وضعیت/یادداشت رفع را برگرداند و کاربر آن را در چت می‌بیند.

اعداد مهندسی **هرگز** از LLM نمی‌آیند؛ موتورهای قاعده‌محور اول اجرا می‌شوند.

### راه‌اندازی
بدون هیچ کلیدی با Pollinations (ناشناس) کار می‌کند. برای کیفیت و پایداری یک کلید رایگان بگیرید: `LLM_GEMINI_API_KEY` یا `LLM_GROQ_API_KEY` (و `LLM_OPENROUTER_API_KEY`). متغیرها: `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_FALLBACKS`, `LLM_KEYLESS_FALLBACK=0` (خاموش کردن Pollinations). هشدار: Pollinations ناشناس و بدون SLA است و متن به سرویس ثالث می‌رود؛ برای داده‌های محرمانه استفاده نکنید.

### طراحی ایمنی
* خطاها فقط **رکورد** هستند؛ اصلاح پیشنهادی فقط **پیش‌نویس** است و خودکار اعمال نمی‌شود.
* تأیید اصلاح فقط با ادمین انسانی واردشده (`PLATFORM_ADMIN_ACCOUNTS`)؛ توکن ماشینی ۴۰۳ می‌گیرد. حتی تأیید هم merge/deploy نمی‌کند.
* بدون deploy و merge خودکار؛ کلید/توکن/ایمیل قبل از ذخیره پاک می‌شود؛ تکرارها یکی می‌شوند؛ خطای دستیار هرگز چت را خراب نمی‌کند؛ وب‌هوک پیش‌فرض خاموش است.

### وب‌هوک و API
ساختار payload، هدرهای امضا (`X-Platform-Signature` = HMAC-SHA256 روی `"{timestamp}." + body`) و endpointها همان بخش انگلیسی است. صفحهٔ ادمین: `/workspace/admin/platform-issues`.

### انتقال به TrafficLens
۱) پوشهٔ `platform_helper` و تست‌ها را کپی کنید. ۲) فایل دانش `trafficlens.md` را بنویسید. ۳) مایگریشن `030` و ریپازیتوری `IssueStore` را اضافه کنید. ۴) factory و routeها را ثبت کنید. ۵) در سرویس چت بعد از موتورهای دامنه و قبل از پاسخ عمومی `helper` را صدا بزنید. ۶) فرانت: `lib/platform-issues.ts`، صفحهٔ ادمین، و مدیریت رویداد `agent_run.token`. ۷) همان متغیرهای محیطی را تنظیم کنید.

---

## Finglish

### In chiye?
Yek dastyar-e chat ke be hich provider-i vabaste nist (`backend/app/platform_helper/`). Salam va "chetor…?" va soalat dar mored-e platform ro ba file-e danesh javab mide, agar LLM tanzim shode bashe chat-e azad ham mikone (token be token), va gozaresh-e khata ro be sorat-e **pak-sazi-shode va bedun-e tekrar** dar jadval-e `platform_issues` zakhire mikone. Admin mitune vaziat/yaddasht-e raf-e khata ro bargardune va karbar dar chat mibine.

Adad-e mohandesi hargez az LLM nemiad; engine-haye ghaede-mahvar avval ejra mishan.

### Rah-andazi
Bedun-e kelid ba Pollinations (nashenas) kar mikone. Baraye keyfiyat yek kelid-e rayegan begirid: `LLM_GEMINI_API_KEY` ya `LLM_GROQ_API_KEY` (va `LLM_OPENROUTER_API_KEY`). Pollinations bedun-e SLA-e va matn be service-e sevom miravad; baraye dade-ye mahramane estefade nakonid.

### Tarrahi-ye imeni
Khata-ha faghat **record** hastan; eslah-e pishnahadi faghat **pishnevis**-e va khodkar emal nemishe. Taeid-e eslah faghat ba admin-e ensani (`PLATFORM_ADMIN_ACCOUNTS`); token-e mashini 403 migire. Hata taeid ham merge ya deploy nemikone. Webhook pishfarz khamoosh-e.

### Enteghal be TrafficLens
1) Pooshe-ye `platform_helper` va test-ha ro copy konid. 2) File-e danesh `trafficlens.md` ro benevisid. 3) Migration `030` va repository-ye `IssueStore` ro ezafe konid. 4) factory va route-ha ro register konid. 5) Dar chat service bad az engine-haye domain va ghabl az pasokh-e omumi `helper` ro seda bezanid. 6) Frontend: `lib/platform-issues.ts`, safhe-ye admin, va event-e `agent_run.token`. 7) Hamin env-ha ro set konid.
