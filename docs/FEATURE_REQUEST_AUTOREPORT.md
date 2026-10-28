# Unsupported capability → ETA estimate + automatic feature request
# قابلیت پشتیبانی‌نشده ← تخمین زمان + درخواست خودکار قابلیت

**Status:** implemented, **OFF by default** (`FEATURE_REQUEST_AUTOREPORT_ENABLED=false`). Nothing changes on a server until the flag is set.
**Never** deploys or changes code by itself: it records a request and tells the user an *estimate*. The dev team (Grok Bot's routine, then a human review/merge) decides what ships.

## English

### Flow
```
user message (no attachment)
  └─ conversation_service._maybe_feature_request   (flag off → skipped, zero cost)
       ├─ pre-filter: command-like engineering message; NOT a question/explain, greeting, bug report, "how do I", bare yes/no
       ├─ known-gap catalogue (deterministic, no model): time-history, nonlinear, pushover, Mabhas-10 steel,
       │   pile foundation, steel connections, retaining wall   (Persian / Finglish / English patterns, negation aware)
       ├─ otherwise: if an existing deterministic engine / chat command handles it → not ours (normal pipeline)
       └─ otherwise: ONE bounded Gemini call (JSON verdict: unsupported | supported | unclear | not_a_request)
            ├─ unclear (confidence ≥ 0.5) → a clarifying question, nothing filed
            ├─ unsupported (confidence ≥ FEATURE_REQUEST_MIN_CONFIDENCE) → below
            └─ anything else / model down → normal pipeline untouched
  user reply (platform-rendered template, fa/en, RTL for Persian):
       "not available yet" + ESTIMATED time + "not a commitment, activates after review and approval"
       + "forwarded to the dev team automatically" + closest thing that works today (+ a working example)
  filing: IssueService.report(category="feature_request") → dedupe by capability key → webhook platform_issue.created
```
The model only classifies and picks a size from the rubric. All user-facing text comes from fixed templates, the "closest alternative" must be an id of the platform's own `EXAMPLES` table, and the model cannot name a capability that the matrix marks as working. So it cannot invent a date, a feature or a promise.

### ETA rubric (an estimate, never a promise)
| size | shown to the user | hours | typical work |
|---|---|---|---|
| `small` | a few hours (about 2-8 working hours) / چند ساعت | 2–8 | text/config/UI tweak, one more export/option on an existing engine |
| `medium` | 1-2 days / یک تا دو روز | 24–48 | new check/calculation on existing data and engines, known formulas |
| `large` | several days (about 3-7 days) / چند روز | 72–168 | new analysis/design module or code clause set with its own validation tests |
| `xlarge` | weeks (about 2-6 weeks) / چند هفته | 336–1008 | new solver class (nonlinear/time-domain), new product area, external data/licences |

**Timeout and retry.** Each model attempt gets `FEATURE_REQUEST_LLM_TIMEOUT_SECONDS` (default **25 s**; the thinking-style Gemini models regularly need 5-17 s). A *transient* failure (timeout, network error, HTTP 5xx, "all providers failed" with at least one non-4xx cause) is retried **once** after about 1 s. Auth/quota/bad-request errors (4xx: 400/401/403/404/429), "no provider configured" and unparsable answers are **not** retried. Every attempt runs in a worker thread with a wall-clock limit (timeout + 2 s grace) because the provider client has its own internal retries/fallbacks, and all attempts together are capped by `FEATURE_REQUEST_LLM_TOTAL_SECONDS` (default **60 s**). Worst case for one user message is about 2 x 27 s + 1 s = 55 s. The retry does **not** count against `FEATURE_REQUEST_LLM_MAX_PER_HOUR`: that budget is charged once per classification.

If Gemini is down, rate-limited, slow (> `FEATURE_REQUEST_LLM_TIMEOUT_SECONDS`, after the one retry) or answers outside the rubric, the catalogue's fixed size is used (unknown capabilities fall back to a keyword rubric, default `large`). The user still gets the message and the issue is still filed (`details.estimate.source = "rubric_fallback"`). An *unknown* request with the model down is left to the normal pipeline (nothing to say honestly).

### Dedupe, counters, rate limits
* Capability key = ascii slug, generic words dropped, plurals stripped, tokens sorted (`Wind_CFD_Simulations` = `simulation cfd wind`). Catalogue entries have fixed keys. Issue `dedupe_key = sha256("feature_request|<key>")[:24]`.
* One **open** issue per capability. Another user asking → `occurrences` +1 (also `details.request_count`), up to 3 redacted `details.sample_requests`, **no** new `created` webhook; at demand milestones **3, 5, 10, 25, 50, 100** one `platform_issue.updated` is sent.
* The same user asking the same capability again within `FEATURE_REQUEST_USER_DEDUPE_SECONDS` is told it was already sent and is **not** counted again.
* Per user: at most `FEATURE_REQUEST_MAX_PER_HOUR` filings/hour and `FEATURE_REQUEST_LLM_MAX_PER_HOUR` model calls/hour. Over the limit the user is told, nothing is filed. (In-process counters, as the helper's own auto-report limiter.)
* If storing fails the user still gets the estimate plus a note that automatic filing failed (and a manual "report a problem" hint).

### Environment flags
| name | default | meaning |
|---|---|---|
| `FEATURE_REQUEST_AUTOREPORT_ENABLED` | `false` | master switch |
| `FEATURE_REQUEST_LLM_ENABLED` | `true` | `false` = catalogue + fixed rubric only (no Gemini call at all) |
| `FEATURE_REQUEST_MAX_PER_HOUR` | `5` | per user, filings counted per hour (1–100) |
| `FEATURE_REQUEST_USER_DEDUPE_SECONDS` | `86400` | same user + same capability counted once per this window |
| `FEATURE_REQUEST_LLM_MAX_PER_HOUR` | `30` | per user, model calls per hour |
| `FEATURE_REQUEST_MIN_CONFIDENCE` | `0.6` | model confidence required to treat a message as unsupported |
| `FEATURE_REQUEST_LLM_TIMEOUT_SECONDS` | `25` | per-attempt cap on the model call (1 retry on transient failure) |
| `FEATURE_REQUEST_LLM_TOTAL_SECONDS` | `60` | overall cap for all attempts of one user message |

The model goes through the helper's existing provider chain (`LLM_GEMINI_API_KEY`, `LLM_PROVIDER` …, see PLATFORM_HELPER.md). The webhook uses the existing `PLATFORM_ISSUE_WEBHOOK_URL`, `PLATFORM_ISSUE_WEBHOOK_SECRET`, `PLATFORM_ISSUE_WEBHOOK_AUTH_TOKEN`; without a URL the request is still stored and listed for admins and the user is told it was "recorded" instead of "forwarded".

### Webhook payload (schema v1, additive)
Same envelope and headers as bug reports (`X-Platform-Event`, HMAC `X-Platform-Signature`, optional Bearer). New optional keys inside `issue`: `kind` and `details` (bugs: `"kind":"bug","details":{}`).
```json
{"schema_version":1,"event":"platform_issue.created","delivery_id":"…","sent_at":"…","product":"structuralai",
 "issue":{"id":"…","title":"Feature request: Pushover analysis","category":"feature_request","severity":"low","source":"auto_detected",
  "status":"open","summary":"A user asked for “Pushover analysis”, which the platform does not support. Estimated size: xlarge (weeks (about 2-6 weeks)). …",
  "user_message":"please run a pushover analysis on my frame","locale":"en","occurrences":1,"dedupe_key":"…",
  "kind":"feature_request",
  "details":{"schema":1,"capability_key":"pushover_analysis","capability_title_en":"Pushover analysis","capability_title_fa":"تحلیل پوش‌اور",
   "matrix_id":"pushover","matrix_status":"no",
   "estimate":{"size":"xlarge","hours_min":336,"hours_max":1008,"eta_en":"weeks (about 2-6 weeks)","eta_fa":"چند هفته (حدود ۲ تا ۶ هفته)",
               "source":"model|rubric_fallback","confidence":1.0,"note":"estimate, not a commitment; activation needs review and approval"},
   "closest_alternative":{"id":"define_frame","text_en":"linear 3D frame analysis with P-Δ, modal and Standard 2800 seismic loads","text_fa":"…","example_en":"…","example_fa":"…"},
   "project_context":{"plan_id":"free","has_project":true,"has_model":true,"storeys":5,"bays_x":3,"bays_y":3},
   "request_count":1,"sample_requests":["please run a pushover analysis on my frame"],"language":"en","user_informed":true}}}
```
`project_context` is a whitelist (plan id, booleans, frame storeys/bays). Never a project name, file name, e-mail or id.

### Admin visibility
`GET /api/v1/admin/platform-issues?kind=feature_request` (machine token or admin account; `kind=bug` for the rest; default list unchanged). Feature requests are sorted by demand counter, then newest. The admin UI `/workspace/admin/platform-issues` shows a "feature" badge and a line `capability · ETA · ×count`. `GET /api/v1/platform-issues/mine` shows the user their own filed requests like any issue.

### Storage / migration
`031_platform_issues_details.sql` (additive, idempotent): `platform_issues.details JSONB NOT NULL DEFAULT '{}'` + index on `(category, created_at)`. `category` is free text, so no enum change. The repository tolerates the column being absent (rolling deploys: code first, migration second still works; `details` is then simply not persisted). Migrations run on startup when `RUN_MIGRATIONS_ON_STARTUP=true`.

### Privacy
The user text is redacted (keys/tokens/passwords, e-mails, phone numbers, IBAN, card/national-id-like digit runs, URLs) before it goes to Gemini and before it is stored or sent. The classifier prompt wraps it in `<user>` tags and states it is data. No project content, only the whitelisted context above.

### Rollout (recommended)
1. Merge, deploy (flag stays `false`; migration 031 applied; behaviour identical to today).
2. Staging/live with `FEATURE_REQUEST_AUTOREPORT_ENABLED=true` and `FEATURE_REQUEST_LLM_ENABLED=false` first: only the 7 known gaps react, no model cost, easy to review.
3. Then `FEATURE_REQUEST_LLM_ENABLED=true` (needs `LLM_GEMINI_API_KEY`); watch `GET …?kind=feature_request` for false positives for a few days; tune `FEATURE_REQUEST_MIN_CONFIDENCE`.
4. Point `PLATFORM_ISSUE_WEBHOOK_URL` at the Grok Bot routine so a new request triggers it immediately.

### Rollback
Set `FEATURE_REQUEST_AUTOREPORT_ENABLED=false` and restart: the chat is exactly as before (the hook returns immediately). Already-filed issues stay as ordinary issues (close with post-back `wontfix`). The migration is additive and can stay. Full revert = revert the PR; the extra column is harmless.

### Limitations
Detection of *unknown* gaps depends on the model's judgement (confidence threshold, "not a request" default); the catalogue is hand-maintained (add a `KnownGap` + matrix row for a new known gap). The estimate is a size class, not planning. Attachments (PDF/photo/CAD) are never intercepted.

## فارسی

### جریان
اگر کاربر در چت چیزی بخواهد که پلتفرم هنوز ندارد (مثلاً «تحلیل تاریخچهٔ زمانی غیرخطی» یا «طراحی پی عمیق شمع»)، پلتفرم: (۱) صادقانه می‌گوید «هنوز فعال نیست»؛ (۲) **تخمین** زمان افزودن را از جدول ثابت (چند ساعت / یک تا دو روز / چند روز / چند هفته) می‌دهد و صریح می‌گوید «نه تعهد؛ فعال‌شدن بعد از بررسی و تأیید»؛ (۳) می‌گوید به‌طور خودکار برای تیم توسعه ارسال شد؛ (۴) نزدیک‌ترین کار فعلی را با مثال پیشنهاد می‌دهد؛ (۵) درخواست را یک‌بار (با شمارندهٔ تقاضا) به‌صورت `feature_request` از مسیر وب‌هوک موجود ثبت می‌کند تا روتین Grok Bot فوراً خبردار شود.
متن را همیشه پلتفرم از قالب ثابت می‌سازد؛ مدل فقط تشخیص و اندازه (small/medium/large/xlarge) را انتخاب می‌کند، پس نمی‌تواند تاریخ یا قابلیت اختراع کند. اگر Gemini در دسترس نباشد، اندازهٔ ثابت جدول استفاده می‌شود و پیام و ثبت همچنان انجام می‌شود.
سؤال‌ها («پوش‌اور چیست؟»)، درخواست‌های پشتیبانی‌شده، گزارش خطا، درخواست مبهم (فقط سؤال شفاف‌کننده) و محدودیت‌های پلن هرگز درخواست قابلیت ثبت نمی‌کنند. هر کاربر در ساعت حداکثر `FEATURE_REQUEST_MAX_PER_HOUR` درخواست؛ تکرار همان درخواست از همان کاربر شمرده نمی‌شود.

### فعال‌سازی و بازگشت
پرچم `FEATURE_REQUEST_AUTOREPORT_ENABLED` به‌طور پیش‌فرض `false` است و تا تأیید مه‌یسام هیچ چیز روی سرور زنده تغییر نمی‌کند. پیشنهاد: اول با `FEATURE_REQUEST_LLM_ENABLED=false` (فقط ۷ مورد شناخته‌شده، بدون هزینهٔ مدل)، بعد روشن‌کردن مدل. بازگشت: پرچم را `false` کنید و سرویس را ری‌استارت کنید. مایگریشن `031` فقط ستون `details` را اضافه می‌کند و بی‌خطر است.
