/** Public legal / landing copy (EN + FA). Plain data so it renders on the server and is unit-tested. */
export const CONTACT_EMAIL = "meysam.ghf@gmail.com";
export const LEGAL_UPDATED = { en: "October 27, 2026", fa: "۵ آبان ۱۴۰۵" };

export type Section = { h: string; p?: string[]; ul?: string[] };
export type PageCopy = { title: string; intro: string; sections: Section[] };
export type Bilingual = { en: PageCopy; fa: PageCopy };

export const PRIVACY: Bilingual = {
  en: {
    title: "Privacy Policy",
    intro:
      "SAIA is a chat-first structural engineering assistant operated by Meysam Farahani (Arak, Iran). This page explains, in plain words, what we collect and what we do with it.",
    sections: [
      {
        h: "What we collect",
        ul: [
          "Account data: your email address, a display name (optional) and your password, which is stored only as a salted hash.",
          "Sign-in with Google (if you use it): only your verified email address and name, using the openid, email and profile scopes. We do not access your Gmail, Drive, contacts or anything else in your Google account.",
          "Your work: projects, model inputs, chat messages, uploaded files, analysis and design results, approvals and the project memory you create while using SAIA.",
          "Technical data: IP address and basic request logs, used for security (for example limiting repeated failed sign-ins) and for keeping the service running.",
          "Payment records: only that a cryptocurrency payment was made and for which plan. We never receive or store bank-card details.",
        ],
      },
      {
        h: "How we use it",
        ul: [
          "To sign you in, keep your session (a secure, httpOnly cookie if you tick “Remember me”) and show you your projects.",
          "To answer your chat requests and run the engineering calculations you ask for. Chat text may be sent to a third-party AI model provider only to generate the reply.",
          "To protect the service from abuse, fix problems and improve SAIA.",
        ],
      },
      {
        h: "What we do not do",
        ul: [
          "We do not sell your data and we do not share it for advertising.",
          "We do not use your project data to train public models.",
          "We share data only with service providers needed to run SAIA (hosting, AI model, email, crypto payment processing) or when the law requires it.",
        ],
      },
      {
        h: "Payments",
        p: ["Payments are accepted in cryptocurrency only, through a payment processor. Card payments are not offered."],
      },
      {
        h: "Cookies and local storage",
        p: [
          "We use a session cookie and your browser’s local storage to keep you signed in and to remember your language. We do not use advertising or tracking cookies.",
        ],
      },
      {
        h: "Retention and your rights",
        p: [
          "We keep your data while your account exists. You can ask us to export or delete your account and project data at any time by writing to the address below; we will respond within a reasonable time.",
        ],
      },
      { h: "Contact", p: [`Questions or requests: ${CONTACT_EMAIL}`] },
    ],
  },
  fa: {
    title: "سیاست حریم خصوصی",
    intro:
      "سایا (SAIA) دستیار مهندسی سازهٔ گفتگومحور است که توسط میثم فرهی (اراک، ایران) اداره می‌شود. در این صفحه ساده توضیح می‌دهیم چه اطلاعاتی گرفته می‌شود و چگونه از آن استفاده می‌کنیم.",
    sections: [
      {
        h: "چه اطلاعاتی گرفته می‌شود",
        ul: [
          "اطلاعات حساب: نشانی ایمیل، نام نمایشی (اختیاری) و رمز عبور که فقط به‌صورت هش و نمک‌دار ذخیره می‌شود.",
          "ورود با گوگل (در صورت استفاده): فقط ایمیل تأییدشده و نام شما با سطوح دسترسی openid، email و profile. به جیمیل، درایو، مخاطبین یا هیچ بخش دیگری از حساب گوگل شما دسترسی نداریم.",
          "کار شما: پروژه‌ها، ورودی‌های مدل، پیام‌های گفتگو، فایل‌های بارگذاری‌شده، نتایج تحلیل و طراحی، تأییدها و حافظهٔ پروژه که هنگام استفاده می‌سازید.",
          "داده‌های فنی: نشانی IP و گزارش‌های ساده درخواست‌ها برای امنیت (مثلاً محدود کردن ورودهای ناموفق مکرر) و پایداری سرویس.",
          "سوابق پرداخت: فقط اینکه یک پرداخت رمزارزی برای چه طرحی انجام شده است. اطلاعات کارت بانکی هرگز دریافت یا ذخیره نمی‌شود.",
        ],
      },
      {
        h: "استفاده از اطلاعات",
        ul: [
          "برای ورود، نگه‌داشتن نشست (کوکی امن و httpOnly در صورت انتخاب «مرا به خاطر بسپار») و نمایش پروژه‌های شما.",
          "برای پاسخ به گفتگو و اجرای محاسبات مهندسی که درخواست می‌کنید. متن گفتگو فقط برای تولید پاسخ ممکن است به یک ارائه‌دهندهٔ مدل هوش مصنوعی ارسال شود.",
          "برای جلوگیری از سوءاستفاده، رفع مشکلات و بهبود سایا.",
        ],
      },
      {
        h: "آنچه انجام نمی‌دهیم",
        ul: [
          "داده‌های شما را نمی‌فروشیم و برای تبلیغات به اشتراک نمی‌گذاریم.",
          "از داده‌های پروژهٔ شما برای آموزش مدل‌های عمومی استفاده نمی‌کنیم.",
          "داده‌ها فقط با ارائه‌دهندگان لازم برای اجرای سایا (میزبانی، مدل هوش مصنوعی، ایمیل، پردازش پرداخت رمزارزی) یا در صورت الزام قانونی به اشتراک گذاشته می‌شود.",
        ],
      },
      {
        h: "پرداخت",
        p: ["پرداخت‌ها فقط با رمزارز و از طریق یک پردازشگر پرداخت انجام می‌شود. پرداخت با کارت بانکی ارائه نمی‌شود."],
      },
      {
        h: "کوکی و حافظهٔ مرورگر",
        p: ["از یک کوکی نشست و حافظهٔ محلی مرورگر برای نگه‌داشتن ورود و زبان شما استفاده می‌کنیم. از کوکی تبلیغاتی یا ردیابی استفاده نمی‌کنیم."],
      },
      {
        h: "نگهداری و حقوق شما",
        p: ["تا زمانی که حساب شما وجود دارد داده‌ها نگهداری می‌شود. می‌توانید هر زمان با ایمیل زیر درخواست دریافت یا حذف حساب و داده‌های پروژه را بدهید؛ در زمان معقول پاسخ می‌دهیم."],
      },
      { h: "تماس", p: [`پرسش‌ها و درخواست‌ها: ${CONTACT_EMAIL}`] },
    ],
  },
};

export const TERMS: Bilingual = {
  en: {
    title: "Terms of Service",
    intro: "By creating an account or using SAIA you agree to these terms. They are short on purpose.",
    sections: [
      {
        h: "The service",
        p: ["SAIA is a chat-first, AI-driven assistant for structural engineering: analysis, design, validation, approval and project memory. Calculations come from deterministic engineering engines; chat is the way you drive them."],
      },
      {
        h: "Professional responsibility",
        ul: [
          "SAIA supports engineers; it does not replace them. Results must be reviewed, checked against the applicable codes and approved by a qualified, licensed engineer before use in any design, drawing, permit or construction.",
          "You are responsible for the inputs and assumptions you provide and for how you use the outputs.",
          "The service and its results are provided “as is”, without warranty. To the extent the law allows, we are not liable for indirect or consequential losses.",
        ],
      },
      {
        h: "Your account",
        ul: [
          "Provide a real email address and keep your password secret. You are responsible for activity under your account.",
          "You may stop using SAIA and ask us to delete your account at any time.",
        ],
      },
      {
        h: "Your content",
        p: ["Your projects, files and chat content remain yours. You give us permission to store and process them only to provide the service to you, as described in the Privacy Policy."],
      },
      {
        h: "Acceptable use",
        p: ["Do not attack, overload or reverse-engineer the service, try to access other users’ data, or use SAIA for anything unlawful."],
      },
      {
        h: "Payments",
        p: ["Paid plans are paid in cryptocurrency only. Plan prices and limits are shown before you pay. Questions about a payment: contact us."],
      },
      {
        h: "Changes",
        p: ["We may update these terms or the service. Material changes will be announced in the product or by email. Continued use means you accept them."],
      },
      { h: "Contact", p: [`${CONTACT_EMAIL}`] },
    ],
  },
  fa: {
    title: "شرایط استفاده از خدمات",
    intro: "با ساخت حساب یا استفاده از سایا (SAIA) این شرایط را می‌پذیرید. عمداً کوتاه نوشته شده است.",
    sections: [
      {
        h: "خدمت",
        p: ["سایا دستیار گفتگومحور و مبتنی بر هوش مصنوعی برای مهندسی سازه است: تحلیل، طراحی، اعتبارسنجی، تأیید و حافظهٔ پروژه. محاسبات از موتورهای مهندسی قطعی می‌آیند و گفتگو راه کنترل آن‌هاست."],
      },
      {
        h: "مسئولیت حرفه‌ای",
        ul: [
          "سایا ابزار کمک به مهندس است و جای او را نمی‌گیرد. نتایج باید پیش از استفاده در هر طراحی، نقشه، مجوز یا ساخت‌وساز توسط مهندس دارای صلاحیت بررسی، با آیین‌نامه‌های مربوط کنترل و تأیید شود.",
          "مسئولیت ورودی‌ها و فرضیاتی که وارد می‌کنید و نحوهٔ استفاده از خروجی‌ها با شماست.",
          "خدمت و نتایج آن «همان‌گونه که هست» و بدون ضمانت ارائه می‌شود. تا حدی که قانون اجازه دهد، مسئولیتی در قبال خسارت‌های غیرمستقیم نداریم.",
        ],
      },
      {
        h: "حساب کاربری",
        ul: [
          "ایمیل واقعی وارد کنید و رمز عبور خود را محرمانه نگه دارید. مسئولیت فعالیت‌های حساب با شماست.",
          "هر زمان می‌توانید استفاده را متوقف کنید و درخواست حذف حساب بدهید.",
        ],
      },
      {
        h: "محتوای شما",
        p: ["پروژه‌ها، فایل‌ها و گفتگوهای شما متعلق به خودتان است. فقط برای ارائهٔ خدمت به شما و مطابق سیاست حریم خصوصی اجازهٔ ذخیره و پردازش آن‌ها را می‌دهید."],
      },
      {
        h: "استفادهٔ مجاز",
        p: ["به سرویس حمله نکنید، آن را بیش از حد تحت فشار نگذارید یا مهندسی معکوس نکنید، به داده‌های دیگران دسترسی نگیرید و از سایا برای کار غیرقانونی استفاده نکنید."],
      },
      {
        h: "پرداخت",
        p: ["طرح‌های پولی فقط با رمزارز پرداخت می‌شوند. قیمت و محدودیت‌های هر طرح پیش از پرداخت نمایش داده می‌شود. برای پرسش دربارهٔ پرداخت با ما تماس بگیرید."],
      },
      {
        h: "تغییرات",
        p: ["ممکن است این شرایط یا خدمت را به‌روزرسانی کنیم. تغییرات مهم در محصول یا با ایمیل اعلام می‌شود. ادامهٔ استفاده به معنی پذیرش آن‌هاست."],
      },
      { h: "تماس", p: [`${CONTACT_EMAIL}`] },
    ],
  },
};

export const ABOUT = {
  en: {
    title: "SAIA — Chat with your structural AI",
    intro: "Chat-first, AI-driven structural engineering. Describe what you need in conversation and SAIA does the work.",
    features: [
      ["Analysis", "Structural analysis driven from the chat."],
      ["Design", "Member design and detailing with deterministic engines."],
      ["Validation", "Independent checks on every result."],
      ["Approval", "Engineer sign-off before anything is final."],
      ["Memory", "Your project’s decisions and assumptions are remembered."],
    ],
    signIn: "Sign in",
    create: "Create account",
  },
  fa: {
    title: "سایا — با هوش مصنوعی سازه‌ات گفتگو کن",
    intro: "مهندسی سازهٔ گفتگومحور و مبتنی بر هوش مصنوعی. نیازتان را در گفتگو بگویید و سایا انجام می‌دهد.",
    features: [
      ["تحلیل", "تحلیل سازه‌ای که از گفتگو هدایت می‌شود."],
      ["طراحی", "طراحی و جزئیات اعضا با موتورهای قطعی."],
      ["اعتبارسنجی", "کنترل مستقل هر نتیجه."],
      ["تأیید", "تأیید مهندس پیش از نهایی شدن هر چیز."],
      ["حافظه", "تصمیم‌ها و فرضیات پروژه به خاطر سپرده می‌شود."],
    ],
    signIn: "ورود",
    create: "ساخت حساب",
  },
} as const;

export const PUBLIC_PATHS = ["/about", "/privacy", "/terms"] as const;
