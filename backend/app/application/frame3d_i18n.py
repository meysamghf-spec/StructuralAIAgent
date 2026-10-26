"""Persian (fa) text for the chat 3D-frame results.

The analysis builds English text with numbers embedded. For a Persian prompt the same strings are passed through
``fa()`` which replaces known English phrases (longest first) by Persian ones and leaves numbers, units, symbols and
identifiers untouched, so the output stays correct for mixed RTL/LTR text. ``tests/test_frame3d_i18n.py`` checks that
no known phrase is left untranslated in a Persian result.
"""

from __future__ import annotations

import re
from typing import Any

_ARABIC = re.compile(r"[\u0600-\u06FF]")


def detect_lang(text: str) -> str:
    return "fa" if _ARABIC.search(text or "") else "en"


# (English phrase, Persian). Matching is case-sensitive; longer phrases are applied first.
PHRASES: list[tuple[str, str]] = [
    # --- headings / markdown
    ("### 3D frame analysis", "### تحلیل قاب سه‌بعدی"),
    ("**Status:** Completed", "**وضعیت:** تکمیل شد"),
    ("**Status:**", "**وضعیت:**"),
    ("3D frame analysis completed", "تحلیل قاب سه‌بعدی انجام شد"),
    ("3D frame analysis failed:", "تحلیل قاب سه‌بعدی ناموفق بود:"),
    ("3D FRAME ANALYSIS", "تحلیل قاب سه‌بعدی"),
    ("- Model:", "- مدل:"),
    ("- Standard 2800:", "- استاندارد ۲۸۰۰:"),
    ("- Base shear:", "- برش پایه:"),
    ("- Max storey drift", "- حداکثر دریفت طبقه"),
    ("- Modal:", "- مودال:"),
    ("- Response spectrum", "- طیف پاسخ"),
    ("- Beam max", "- بیشینهٔ تیر"),
    ("- Column max axial", "- بیشینهٔ نیروی محوری ستون"),
    ("Mabhas 9 RC design", "طراحی بتن‌آرمهٔ مبحث نهم"),
    ("Foundation design (isolated footings)", "طراحی فونداسیون (پی منفرد)"),
    ("Implemented clauses:", "بندهای پیاده‌سازی‌شده:"),
    ("Simplified / not checked:", "بندهای ساده‌شده / کنترل‌نشده:"),
    ("Strong column / weak beam", "ستون قوی – تیر ضعیف"),
    ("Assumptions:", "فرضیات:"),
    ("Warnings:", "هشدارها:"),
    ("**Exports ready** (download from the result card):", "**خروجی‌ها آماده است** (از کارت نتیجه دانلود کنید):"),
    ("Exports available on the result card:", "خروجی‌های قابل دانلود در کارت نتیجه:"),
    ("Model re-analysed from the last 3D frame stored in this project.", "مدل از آخرین قاب سه‌بعدی ذخیره‌شده در این پروژه دوباره تحلیل شد."),
    ("intermediate ductility", "شکل‌پذیری متوسط"), ("special ductility", "شکل‌پذیری ویژه"), ("ordinary ductility", "شکل‌پذیری معمولی"),
    ("ductility", "شکل‌پذیری"),
    ("Storey | Dir | Δ elastic (mm) | Δ/h elastic %", "طبقه | جهت | Δ ارتجاعی (mm) | Δ/h ارتجاعی %"),
    ("| Beam group |", "| گروه تیر |"), ("| Column group |", "| گروه ستون |"),
    ("| Footing group |", "| گروه پی |"),
    ("| Mode |", "| مود |"), ("| Storey |", "| طبقه |"),
    ("| Top | Bottom | Stirrups |", "| بالا | پایین | خاموت |"),
    ("| Bars |", "| آرماتور |"), ("| Ties |", "| تنگ |"),
    ("| Bars | Mu |", "| آرماتور | Mu |"),
    # --- status words in markdown
    ("Foundation status", "وضعیت فونداسیون"),
    # --- model/result phrases
    ("storeys", "طبقه"), ("bays", "دهانه"), ("columns", "ستون"), ("beams", "تیر"), ("nodes", "گره"),
    ("direction", "جهت"), ("at storey", "در طبقهٔ"), ("limit", "حد مجاز"),
    ("reactions X", "عکس‌العمل X"), ("reactions", "عکس‌العمل‌ها"),
    ("modes for 90% mass X/Y:", "مودهای لازم برای ۹۰٪ جرم X/Y:"),
    ("max scaled drift", "حداکثر دریفت مقیاس‌شده"), ("→ scale", "← ضریب مقیاس"),
    ("vs V_static", "در برابر V_static"),
    ("soil type", "نوع خاک"), ("soil", "خاک"), ("hazard zone", "پهنهٔ خطر"),
    ("very high", "بسیار زیاد"), ("high", "زیاد"), ("moderate", "متوسط"), ("low", "کم"),
    ("importance", "اهمیت"),
    ("RC special moment frame", "قاب خمشی بتنی ویژه"), ("RC intermediate moment frame", "قاب خمشی بتنی متوسط"),
    ("RC ordinary moment frame", "قاب خمشی بتنی معمولی"), ("Steel special moment frame", "قاب خمشی فولادی ویژه"),
    ("Steel intermediate moment frame", "قاب خمشی فولادی متوسط"), ("Steel ordinary moment frame", "قاب خمشی فولادی معمولی"),
    ("regular (assumed)", "منظم (فرض شده)"), ("irregular", "نامنظم"), ("regular", "منظم"),
    # --- field labels
    ("Model and results", "مدل و نتایج"), ("Model", "مدل"), ("Elements", "اجزا"), ("Sections", "مقاطع"),
    ("Seismic weight W", "وزن لرزه‌ای W"), ("2800 parameters", "پارامترهای ۲۸۰۰"),
    ("T (empirical) / B1·N", "T (تجربی) / B1·N"), ("C = ABI/R (≥ 0.12AI)", "C = ABI/R (≥ 0.12AI)"),
    ("Base shear V = C·W", "برش پایه V = C·W"), ("T1 (modal)", "T1 (مودال)"), ("V dynamic / static", "V دینامیکی / استاتیکی"),
    ("Max drift", "حداکثر دریفت"), ("Mabhas 9 design", "طراحی مبحث نهم"),
    ("Beam max M⁻", "بیشینهٔ M⁻ تیر"), ("Beam max M⁺", "بیشینهٔ M⁺ تیر"), ("Beam max V", "بیشینهٔ V تیر"),
    ("Column max P", "بیشینهٔ P ستون"), ("Foundation", "فونداسیون"),
    ("max D/C", "بیشینهٔ D/C"), ("groups failing", "گروه ناموفق"), ("groups", "گروه"), ("footings", "پی"),
    ("allowable bearing", "تنش مجاز خاک"), ("(assumed)", "(فرضی)"),
    # --- disclaimers
    ("Linear elastic 3D frame analysis with the internal SAIA solver. Seismic load uses the user-supplied coefficient C (equivalent static); no Iranian Standard 2800 or Mabhas 9 checks are performed yet. Final engineering decisions require verification by a qualified engineer.",
     "تحلیل خطی ارتجاعی قاب سه‌بعدی با حل‌گر داخلی SAIA. بار زلزله با ضریب C واردشده توسط کاربر (استاتیکی معادل) اعمال شده و هنوز کنترل‌های استاندارد ۲۸۰۰ و مبحث نهم انجام نمی‌شود. تصمیم نهایی مهندسی نیازمند تأیید مهندس مسئول است."),
    ("Linear elastic 3D frame analysis with the internal SAIA solver. Seismic loads follow Standard 2800 (4th ed.) as implemented here (equivalent static + response spectrum, simplifications listed under Assumptions). Not a certified code check; final engineering decisions require verification by a qualified engineer.",
     "تحلیل خطی ارتجاعی قاب سه‌بعدی با حل‌گر داخلی SAIA. بارهای زلزله طبق استاندارد ۲۸۰۰ (ویرایش چهارم) به شکل پیاده‌شده در این برنامه (استاتیکی معادل + طیف پاسخ، با ساده‌سازی‌های فهرست‌شده در فرضیات) اعمال شده است. این یک کنترل آیین‌نامه‌ای معتبر نیست و تصمیم نهایی مهندسی نیازمند تأیید مهندس مسئول است."),
    ("Analysis with Standard 2800 (4th ed.) seismic loads;", "تحلیل با بارهای زلزلهٔ استاندارد ۲۸۰۰ (ویرایش چهارم)؛"),
    ("Analysis with user-supplied seismic C (no Standard 2800);", "تحلیل با ضریب زلزلهٔ C واردشده توسط کاربر (بدون استاندارد ۲۸۰۰)؛"),
    ("Analysis with", "تحلیل با"),
    ("Mabhas 9 RC design (simplified, see clauses)", "طراحی بتن‌آرمهٔ مبحث نهم (ساده‌شده، بندها را ببینید)"),
    ("no member design (no Mabhas 9 checks)", "بدون طراحی اعضا (بدون کنترل مبحث نهم)"),
    # --- assumptions
    ("Regular orthogonal grid, fixed column bases, rigid floor diaphragms", "شبکهٔ منظم متعامد، پای ستون‌ها گیردار، سقف‌ها دیافراگم صلب"),
    ("Cracked stiffness: beams 0.35·Ig, columns 0.70·Ig; torsion 0.15·J; Ec = 4700√f'c", "سختی ترک‌خورده: تیرها 0.35·Ig، ستون‌ها 0.70·Ig؛ پیچش 0.15·J؛ Ec = 4700√f'c"),
    ("Two-way slab loads to beams by equivalent triangular/trapezoidal UDL; slab self-weight is part of the dead load", "بار دال دوطرفه با بار گستردهٔ معادل مثلثی/ذوزنقه‌ای به تیرها منتقل شده؛ وزن دال جزو بار مرده است"),
    ("Perimeter wall", "دیوار پیرامونی"), ("kN/m on edge beams, roof parapet", "kN/m روی تیرهای کناری، جان‌پناه بام"),
    ("kN/m; roof live load", "kN/m؛ بار زندهٔ بام"),
    ("Combinations: 1.4D, 1.2D+1.6L, 1.2D+1.0L±E, 0.9D±E (Mabhas 6 / ACI form; no 30% orthogonal combination)", "ترکیب بارها: 1.4D، 1.2D+1.6L، 1.2D+1.0L±E، 0.9D±E (شکل مبحث ششم / ACI؛ بدون ترکیب ۳۰٪ متعامد)"),
    ("No P-Δ", "بدون اثر P-Δ"),
    ("Standard 2800 (4th ed.) equivalent static with the empirical period", "استاتیکی معادل استاندارد ۲۸۰۰ (ویرایش چهارم) با زمان تناوب تجربی"),
    ("(analytical period not used for C)", "(زمان تناوب تحلیلی برای C استفاده نشده)"),
    ("Inelastic drift Δm = Cd·Δe/I", "دریفت غیرارتجاعی Δm = Cd·Δe/I"),
    ("drift from the design-force analysis (conservative)", "دریفت از تحلیل با نیروی طراحی (محافظه‌کارانه)"),
    ("Modal analysis on rigid-diaphragm DOFs with storey masses (D+0.2L)/g and uniform-plate polar inertia; mass centre at plan centre", "تحلیل مودال روی درجات آزادی دیافراگم صلب با جرم طبقات (D+0.2L)/g و اینرسی قطبی صفحهٔ یکنواخت؛ مرکز جرم در مرکز پلان"),
    ("Response spectrum: 2800 design spectrum A·B1·N·I/R, CQC 5% damping, no accidental torsion in the dynamic cases", "طیف پاسخ: طیف طرح ۲۸۰۰ برابر A·B1·N·I/R، ترکیب CQC با میرایی ۵٪، بدون پیچش اتفاقی در حالت‌های دینامیکی"),
    ("Drift amplified by 0.7R with R=", "دریفت با ضریب 0.7R و R="), ("the 2.5% value shown is only a reference, not a 2800 check", "مقدار ۲٫۵٪ فقط مرجع است و کنترل ۲۸۰۰ نیست"),
    ("No member design / code compliance checks requested (add 'design per Mabhas 9')", "طراحی اعضا / کنترل آیین‌نامه‌ای درخواست نشده (عبارت «طبق مبحث نهم طراحی کن» را اضافه کنید)"),
    ("Foundation: isolated square footings under every base column; reactions of the analysis combinations; allowable bearing", "فونداسیون: پی منفرد مربعی زیر هر ستون پایه؛ با عکس‌العمل‌های ترکیب‌های تحلیل؛ تنش مجاز خاک"),
    # --- warnings
    ("Standard 2800 parameters not given and assumed:", "پارامترهای استاندارد ۲۸۰۰ داده نشده و فرض شد:"),
    ("A user C was given but Standard 2800 parameters take precedence; C was computed from A·B·I/R.", "ضریب C از کاربر داده شده ولی پارامترهای استاندارد ۲۸۰۰ اولویت دارد؛ C از A·B·I/R محاسبه شد."),
    ("No seismic coefficient C given (e.g. `C=0.165`): only gravity load cases were analysed; drift and base shear are not reported.", "ضریب زلزلهٔ C داده نشد (مثلاً `C=0.165`): فقط بارهای ثقلی تحلیل شد و دریفت و برش پایه گزارش نمی‌شود."),
    ("Behaviour factor R not given; assumed R=", "ضریب رفتار R داده نشد؛ فرض شد R="), ("for amplified drift (0.7R·Δ).", "برای دریفت بزرگ‌نمایی‌شده (0.7R·Δ)."),
    ("Equilibrium residual", "باقیماندهٔ تعادل"),
    ("Strong column / weak beam ratio below 1.2 at some joints (see design table): consider larger columns or less beam steel.", "نسبت ستون قوی – تیر ضعیف در برخی گره‌ها کمتر از ۱٫۲ است (جدول طراحی را ببینید): ستون بزرگ‌تر یا آرماتور کمتر در تیر در نظر بگیرید."),
    ("Special-frame detailing (capacity shear, joint shear, Ash confinement) not implemented", "جزئیات قاب ویژه (برش ظرفیتی، برش گره، Ash محصورشدگی) پیاده‌سازی نشده است"),
    ("Mabhas 9 design uses the user-supplied seismic C; add Standard 2800 parameters for code-based seismic forces.", "طراحی مبحث نهم با ضریب C واردشده توسط کاربر انجام شده؛ برای نیروی زلزلهٔ آیین‌نامه‌ای پارامترهای ۲۸۰۰ را اضافه کنید."),
    ("Mabhas 9 RC design applies to RC systems only (steel / Mabhas 10 not implemented).", "طراحی مبحث نهم فقط برای سیستم‌های بتن‌آرمه است (فولاد / مبحث دهم پیاده‌سازی نشده)."),
    ("Allowable soil bearing was not given and 150 kPa is assumed (add e.g. 'allowable bearing 200 kPa' / 'تنش مجاز خاک 200 kPa').", "تنش مجاز خاک داده نشد و ۱۵۰ kPa فرض شد (مثلاً «تنش مجاز خاک 200 kPa» را اضافه کنید)."),
    ("Foundation footings overlap:", "پی‌ها با هم تداخل دارند:"),
    ("Please specify:", "لطفاً مشخص کنید:"), ("number of storeys", "تعداد طبقات"), ("number of bays in X", "تعداد دهانه در X"), ("number of bays in Y", "تعداد دهانه در Y"),
    ("Example:", "مثال:"),
    ("This chat solver currently supports", "این حل‌گر چت فعلاً پشتیبانی می‌کند از"), ("at most", "حداکثر"), ("per direction", "در هر جهت"),
    ("No 3D frame analysis was found in this project (needed for the export / foundation design).", "در این پروژه تحلیل قاب سه‌بعدی‌ای (لازم برای خروجی / طراحی فونداسیون) پیدا نشد."),
    ("Describe the frame first, e.g.", "ابتدا قاب را توصیف کنید، مثلاً"),
    (", then ask for the foundation design or the ETABS/SAFE/AutoCAD export.", "، سپس طراحی فونداسیون یا خروجی ایتبس/سیف/اتوکد را بخواهید."),
    # --- design notes / clauses (mabhas9)
    ("Section too small: compression block cannot develop Mu", "مقطع خیلی کوچک است: بلوک فشاری نمی‌تواند Mu را تأمین کند"),
    ("Required bars do not fit in one layer", "آرماتورهای لازم در یک ردیف جا نمی‌شوند"),
    ("(ductile-frame limit)", "(حد قاب شکل‌پذیر)"),
    ("tension steel does not yield", "فولاد کششی تسلیم نمی‌شود"),
    ("Shear exceeds the section limit Vs ≤ 4Vc: enlarge the section", "برش از حد مقطع Vs ≤ 4Vc بیشتر است: مقطع را بزرگ کنید"),
    ("No bar arrangement fits", "هیچ چیدمان آرماتوری جا نمی‌شود"),
    ("D/C > 1 even at ρ = 6 %: enlarge the column", "حتی با ρ = ۶٪ نسبت D/C بزرگ‌تر از ۱ است: ستون را بزرگ کنید"),
    ("Material factors φc = 0.65, φs = 0.85; εcu = 0.0035; α1, β1 stress block", "ضرایب مصالح φc = 0.65 و φs = 0.85؛ εcu = 0.0035؛ بلوک تنش α1 و β1"),
    ("Beam flexure: required As, As,min = max(0.25√f'c, 1.4)·b·d/fy, ρ ≤ 0.025, c/d ≤ 700/(700+fy)", "خمش تیر: As لازم، As,min = max(0.25√f'c, 1.4)·b·d/fy، ρ ≤ 0.025، c/d ≤ 700/(700+fy)"),
    ("Beam M⁺ ≥ M⁻/3 at the face (intermediate) / ≥ M⁻/2 (special)", "M⁺ تیر در بر تکیه‌گاه ≥ M⁻/3 (متوسط) / ≥ M⁻/2 (ویژه)"),
    ("Beam shear: Vc = 0.2·φc·√f'c·b·d, Vs = φs·Av·fy·d/s, Av,min, spacing limits incl. end zones 2h", "برش تیر: Vc = 0.2·φc·√f'c·b·d، Vs = φs·Av·fy·d/s، Av,min، محدودیت فاصله شامل ناحیهٔ انتهایی 2h"),
    ("Column P–M interaction by strain compatibility, Pr,max = 0.8·Pr0, ρ between 1 % and 6 %", "اندرکنش P–M ستون با سازگاری کرنش، Pr,max = 0.8·Pr0، ρ بین ۱٪ و ۶٪"),
    ("Column ties: s0 = min(8db, 24dt, b/2, 300) over l0 = max(h, Ln/6, 450); elsewhere min(16db, 48dt, b)", "تنگ ستون: s0 = min(8db, 24dt, b/2, 300) در طول l0 = max(h, Ln/6, 450)؛ در بقیه min(16db, 48dt, b)"),
    ("Strong column / weak beam: ΣMnc ≥ 1.2·ΣMnb (nominal capacities)", "ستون قوی – تیر ضعیف: ΣMnc ≥ 1.2·ΣMnb (ظرفیت‌های اسمی)"),
    ("Practical detailing rule: longitudinal column bars at ≤ 200 mm, bars in one layer with clear spacing ≥ max(db, 25 mm)", "قاعدهٔ اجرایی: میلگردهای طولی ستون با فاصلهٔ ≤ ۲۰۰ mm، در یک ردیف با فاصلهٔ آزاد ≥ max(db, 25 mm)"),
    ("Biaxial bending by linear load contour Mux/Mrx + Muy/Mry ≤ 1 (conservative Bresler α = 1)", "خمش دومحوره با منحنی بار خطی Mux/Mrx + Muy/Mry ≤ 1 (برسلر محافظه‌کارانه با α = 1)"),
    ("Beam/column shear from the analysis envelope; capacity-design shear (Mpr / 2E) not applied", "برش تیر/ستون از پوش تحلیل؛ برش طراحی ظرفیتی (Mpr / 2E) اعمال نشده"),
    ("Section limit Vs ≤ 4·Vc used for the maximum shear reinforcement", "حد مقطع Vs ≤ 4·Vc برای بیشینهٔ آرماتور برشی"),
    ("Moments at member centre-lines (not at support faces); no redistribution", "لنگرها در محور اعضا (نه بر تکیه‌گاه)؛ بدون باز توزیع"),
    ("Not checked: column shear, slenderness/second-order effects, beam-column joint shear, confinement Ash, development/splices, crack/deflection", "کنترل نشده: برش ستون، لاغری/اثرات مرتبهٔ دوم، برش گرهٔ تیر-ستون، محصورشدگی Ash، طول مهاری/وصله، ترک/خیز"),
    ("mandatory for special frames", "برای قاب‌های ویژه الزامی است"), ("reported as a check; verify applicability for this ductility level", "به‌صورت کنترل گزارش شده؛ کاربرد آن برای این سطح شکل‌پذیری بررسی شود"),
    ("Member forces from the equivalent static load cases (response spectrum used for checks only)", "نیروی اعضا از حالت‌های بار استاتیکی معادل (طیف پاسخ فقط برای کنترل‌ها)"),
    # --- foundation clauses / notes
    ("Service bearing: q = P/A·(1 + 6ex/B + 6ey/B) ≤ qa,net, kern check ex + ey ≤ B/6 (no uplift)", "تنش زیر پی در بار بهره‌برداری: q = P/A·(1 + 6ex/B + 6ey/B) ≤ qa,net و کنترل هسته ex + ey ≤ B/6 (بدون بلندشدگی)"),
    ("Net allowable pressure qa,net = qa − γ·Df with Df = 1.5 m, γ = 18 kN/m³; qa × 1.33 for combinations with earthquake", "تنش مجاز خالص qa,net = qa − γ·Df با Df = 1.5 m و γ = 18 kN/m³؛ برای ترکیب‌های با زلزله qa × 1.33"),
    ("One-way shear at d from the column face: Vc = 0.2·φc·√f'c·b·d", "برش یک‌طرفه در فاصلهٔ d از بر ستون: Vc = 0.2·φc·√f'c·b·d"),
    ("Punching shear on bo at d/2: vc = φc·√f'c·min(0.2(1+2/βc), 0.2(αs·d/bo + 2), 0.4)", "برش پانچ روی محیط bo در d/2: vc = φc·√f'c·min(0.2(1+2/βc), 0.2(αs·d/bo + 2), 0.4)"),
    ("Flexure at the column face with the Mabhas 9 stress block (φc = 0.65, φs = 0.85), As,min = 0.0018·b·h", "خمش در بر ستون با بلوک تنش مبحث نهم (φc = 0.65، φs = 0.85) و As,min = 0.0018·b·h"),
    ("Square pad footings, one per base column, centred under the column; uniform soil, rigid footing", "پی‌های منفرد مربعی، یکی برای هر ستون پایه، همبر با ستون؛ خاک یکنواخت و پی صلب"),
    ("Eccentricity from the base reactions (M + V·h); footing self-weight and soil are deducted from qa through Df", "خروج از مرکزیت از عکس‌العمل‌های پایه (M + V·h)؛ وزن پی و خاک روی آن با Df از qa کسر شده است"),
    ("Group size = envelope of the columns of the same position (corner / edge / interior) at the base", "ابعاد گروه = پوش ستون‌های هم‌موقعیت (گوشه / کناری / میانی) در پایه"),
    ("Not checked: settlement, sliding, overturning, bearing capacity from soil data, development length, column dowels, bearing on the column base", "کنترل نشده: نشست، لغزش، واژگونی، ظرفیت باربری از داده‌های خاک، طول مهاری، میلگرد انتظار، فشار زیر ستون"),
    ("Allowable pressure too small after deducting the overburden", "تنش مجاز پس از کسر سربار خیلی کم است"),
    ("No square footing up to 8 m satisfies bearing / kern: use a mat or combined footing", "هیچ پی مربعی تا ۸ متر تنش زیر پی/هسته را برآورده نمی‌کند: از پی گسترده یا ترکیبی استفاده کنید"),
    ("Shear governs beyond h = 2.5 m", "برش بیش از h = 2.5 m را لازم می‌کند"),
    ("Section too thin for the flexural demand", "مقطع برای خمش لازم خیلی نازک است"),
    ("Minimum steel governs", "آرماتور حداقل کنترل‌کننده است"),
    ("Net uplift in", "بلندشدگی خالص در"), ("those combinations are ignored for footing design (check overturning/anchorage)", "این ترکیب‌ها در طراحی پی نادیده گرفته شدند (واژگونی/مهار را کنترل کنید)"),
    ("Isolated footings do not overlap.", "پی‌های منفرد با هم تداخل ندارند."),
    ("Footings overlap and cover more than 50 % of the plan: use a mat foundation (SAFE mat).", "پی‌ها تداخل دارند و بیش از ۵۰٪ پلان را می‌پوشانند: از پی گسترده (مت) استفاده کنید."),
    ("Footings overlap: use combined (strip) footings along the overlapping grid lines; a strap beam is an alternative for edge columns at the property line.", "پی‌ها تداخل دارند: از پی ترکیبی (نواری) در امتداد محورهای دارای تداخل استفاده کنید؛ برای ستون‌های کناریِ کنار مرز ملک، تیر تراز (strap) گزینهٔ دیگری است."),
    ("each way", "در هر دو جهت"),
    # --- exports
    ("ETABS model (.e2k)", "مدل ایتبس (.e2k)"), ("SAFE foundation loads (.f2k)", "بارهای فونداسیون سیف (.f2k)"), ("SAP2000 model (.s2k)", "مدل SAP2000 (.s2k)"),
    ("AutoCAD plans per storey (.dxf)", "پلان هر طبقه برای اتوکد (.dxf)"), ("AutoCAD 3D wireframe (.dxf)", "قاب سه‌بعدی سیمی برای اتوکد (.dxf)"),
    ("Not yet opened in a licensed ETABS: syntax copied from public ETABS 2016/21 exports, import not confirmed.", "هنوز در ایتبس اصل باز نشده: دستور فایل از خروجی‌های عمومی ایتبس ۲۰۱۶/۲۱ برداشته شده و ایمپورت تأیید نشده است."),
    ("Seismic EX/EY use DIR \"X\"/\"Y\" without the ±5% accidental eccentricity (our analysis includes it); set 'X + Ecc. Y' in ETABS if you need it.", "بار زلزلهٔ EX/EY بدون خروج از مرکزیت اتفاقی ±۵٪ نوشته شده (تحلیل ما آن را دارد)؛ در صورت نیاز در ایتبس «X + Ecc. Y» را تنظیم کنید."),
    ("Mass source = element self mass (columns only; beam MMOD=0 because beam weight is in the line loads) + 1.0·Dead + 0.2·Live loads — check Define > Mass Source after import.", "منبع جرم = جرم اجزا (فقط ستون‌ها؛ برای تیرها MMOD=0 چون وزن تیر در بارهای خطی است) + 1.0·مرده + 0.2·زنده — پس از ایمپورت Define > Mass Source را کنترل کنید."),
    ("Slabs are not modelled as shells: floor loads are already distributed to beams as line loads (tributary areas).", "دال‌ها به‌صورت پوسته مدل نشده‌اند: بار طبقات از قبل به‌صورت بار خطی (سطح بارگیر) روی تیرها آمده است."),
    ("Point table, load patterns/cases/combinations and point loads follow an ETABS→SAFE 2014 export (SAFE v12–2016 table names).", "جدول نقاط، الگوها/حالت‌ها/ترکیب‌های بار و بارهای نقطه‌ای از خروجی ETABS→SAFE 2014 پیروی می‌کند."),
    ("The mat outline tables", "جدول‌های طرح پی گسترده"),
    ("are written from memory of the SAFE 12 format and are a PLACEHOLDER — delete them if SAFE rejects the file and draw the mat/footings in SAFE.", "از حافظهٔ قالب SAFE 12 نوشته شده و فقط «جایگزین موقت» است — اگر SAFE فایل را نپذیرفت آن‌ها را حذف کنید و پی را در SAFE بکشید."),
    ("DXF R12 ASCII; layers GRID, COLUMNS, BEAMS, SECTION_TEXT, DESIGN_TEXT, FOUNDATION; one plan per storey side by side, then the foundation plan.", "DXF نسخهٔ R12 متنی؛ لایه‌ها GRID، COLUMNS، BEAMS، SECTION_TEXT، DESIGN_TEXT، FOUNDATION؛ پلان طبقات کنار هم و سپس پلان فونداسیون."),
    ("DXF R12 ASCII; LINE entities with Z plus one 3D POLYLINE per column stack (use 3D Orbit).", "DXF نسخهٔ R12 متنی؛ خط‌هایی با مختصات Z به‌علاوهٔ یک پلی‌لاین سه‌بعدی برای هر ستون (از 3D Orbit استفاده کنید)."),
    ("When a foundation design exists the placeholder mat is replaced by one footing area per column (sizes/thickness from the design); soil spring ks is still a placeholder.", "وقتی طراحی فونداسیون وجود دارد، مت موقت با یک پی برای هر ستون (ابعاد و ضخامت از طراحی) جایگزین می‌شود؛ فنر خاک ks هنوز مقدار موقت است."),
]
_PHRASES = sorted(PHRASES, key=lambda p: -len(p[0]))
_STATUS = {"PASS": "قبول", "FAIL": "رد", "CHECK": "بررسی", "OVERLAP": "تداخل", "NOT_APPLICABLE": "نامربوط"}
_ASCII_WORD = re.compile(r"^[A-Za-z]+$")


def fa(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    out = text
    for en, per in _PHRASES:
        if en in out:
            if _ASCII_WORD.match(en):
                out = re.sub(rf"(?<![A-Za-z_]){re.escape(en)}(?![A-Za-z_])", per, out)
            else:
                out = out.replace(en, per)
    return out


def fa_markdown(text: str) -> str:
    out = fa(text)
    return re.sub(r"\b(PASS|FAIL|CHECK|OVERLAP|NOT_APPLICABLE)\b", lambda m: _STATUS[m.group(1)], out)


_SKIP = {"kind", "status", "format", "filename", "spec", "seismic_code", "design_code", "inputs", "group", "node", "column", "position",
         "direction", "joint", "governing_combo", "bearing_combo", "id", "mime", "lang", "unit", "a", "b", "ductility", "code_enum",
         "parsed_from_request", "defaulted_inputs", "missing_inputs", "export_requested", "load_combinations", "combos", "zone", "soil",
         "system", "T_formula", "vertical_distribution", "method", "viewer"}


def translate_payload(value: Any, key: str | None = None) -> Any:
    if key in _SKIP:
        return value
    if isinstance(value, str):
        return fa(value)
    if isinstance(value, list):
        return [translate_payload(v, key) for v in value]
    if isinstance(value, dict):
        return {k: translate_payload(v, k) for k, v in value.items()}
    return value
