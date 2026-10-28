// Generated from backend/app/application/assistant_chat.py (keep in sync).
export type AssistantContext = { title: { en: string; fa: string }; starters: { en: string[]; fa: string[] } };

export const ASSISTANT_CONTEXTS: Record<string, AssistantContext> = {
  "STRUCTURAL_MODELING_AGENT": {
    "title": {
      "en": "Structural Modeling Assistant",
      "fa": "دستیار مدل‌سازی سازه"
    },
    "starters": {
      "en": [
        "Summarize the structural model",
        "4-storey RC frame, 3x3 bays of 5 m, storey height 3.2 m"
      ],
      "fa": [
        "مدل سازه را خلاصه کن",
        "قاب بتنی ۴ طبقه با ۳x۳ دهانه ۵ متر"
      ]
    }
  },
  "LOAD_ASSESSMENT_AGENT": {
    "title": {
      "en": "Load Assessment Assistant",
      "fa": "دستیار ارزیابی بار"
    },
    "starters": {
      "en": [
        "Summarize the load combinations",
        "Show the loading summary per Mabhas 6 / 2800",
        "3-storey RC frame, 3x3 bays of 5 m, storey height 3.2 m, high hazard, soil II"
      ],
      "fa": [
        "ترکیب بارها را خلاصه کن",
        "خلاصه بارگذاری طبق مبحث ۶ و ۲۸۰۰",
        "قاب بتنی ۳ طبقه با ۳x۳ دهانه ۵ متر، ارتفاع طبقه ۳.۲، خطر زیاد، خاک ۲"
      ]
    }
  },
  "ANALYSIS_AGENT": {
    "title": {
      "en": "Structural Analysis Assistant",
      "fa": "دستیار تحلیل سازه"
    },
    "starters": {
      "en": [
        "Review the analysis results",
        "Check drift and stability",
        "Summarize results and member maxima"
      ],
      "fa": [
        "نتایج تحلیل را بررسی کن",
        "دریفت و پایداری را کنترل کن",
        "خلاصه نتایج و بیشینه نیروها"
      ]
    }
  },
  "CONCRETE_DESIGN_AGENT": {
    "title": {
      "en": "Concrete Design Assistant",
      "fa": "دستیار طراحی بتن"
    },
    "starters": {
      "en": [
        "Summarize the Mabhas 9 concrete design",
        "Which groups fail and why?"
      ],
      "fa": [
        "خلاصه طراحی بتن طبق مبحث نهم",
        "کدام گروه‌ها رد می‌شوند و چرا؟"
      ]
    }
  },
  "STEEL_DESIGN_AGENT": {
    "title": {
      "en": "Steel Design Assistant",
      "fa": "دستیار طراحی فولاد"
    },
    "starters": {
      "en": [
        "Analyze a simply supported steel beam, span 6 m, 20 kN/m",
        "What can and can't the steel assistant do?"
      ],
      "fa": [
        "تیر فولادی ساده با دهانه ۶ متر و بار ۲۰ kN/m را تحلیل کن",
        "دستیار فولاد چه کارهایی می‌کند و چه کارهایی نمی‌کند؟"
      ]
    }
  },
  "SEISMIC_AGENT": {
    "title": {
      "en": "Seismic Design Assistant",
      "fa": "دستیار طراحی لرزه‌ای"
    },
    "starters": {
      "en": [
        "Show the Standard 2800 seismic parameters",
        "Base shear and storey forces",
        "Drift check"
      ],
      "fa": [
        "پارامترهای لرزه‌ای استاندارد ۲۸۰۰",
        "برش پایه و نیروی طبقات",
        "کنترل دریفت"
      ]
    }
  },
  "VALIDATION_AGENT": {
    "title": {
      "en": "Design Validation Assistant",
      "fa": "دستیار اعتبارسنجی طرح"
    },
    "starters": {
      "en": [
        "Validate this design",
        "List all warnings and failed checks"
      ],
      "fa": [
        "این طرح را اعتبارسنجی کن",
        "همه هشدارها و کنترل‌های رد شده را فهرست کن"
      ]
    }
  },
  "CAD_AGENT": {
    "title": {
      "en": "CAD Coordination Assistant",
      "fa": "دستیار نقشه‌کشی"
    },
    "starters": {
      "en": [
        "What drawings can be produced from this model?",
        "Generate the structural drawing set"
      ],
      "fa": [
        "از این مدل چه نقشه‌هایی ساخته می‌شود؟",
        "مجموعه نقشه‌های سازه را تولید کن"
      ]
    }
  },
  "REPORTING_AGENT": {
    "title": {
      "en": "Engineering Report Assistant",
      "fa": "دستیار گزارش مهندسی"
    },
    "starters": {
      "en": [
        "Write the engineering report summary",
        "List the runs available for a report"
      ],
      "fa": [
        "خلاصه گزارش مهندسی را بنویس",
        "اجراهای آماده گزارش را فهرست کن"
      ]
    }
  },
  "DOCUMENT_INTERPRETATION_AGENT": {
    "title": {
      "en": "Document Interpretation Assistant",
      "fa": "دستیار تفسیر مدارک"
    },
    "starters": {
      "en": [
        "Attach a PDF/Excel/DXF/image and I will interpret it",
        "What file types are supported?"
      ],
      "fa": [
        "یک PDF/اکسل/DXF/تصویر پیوست کنید تا تفسیر کنم",
        "چه فرمت‌هایی پشتیبانی می‌شود؟"
      ]
    }
  },
  "OPTIMIZATION_AGENT": {
    "title": {
      "en": "Optimization Assistant",
      "fa": "دستیار بهینه‌سازی"
    },
    "starters": {
      "en": [
        "What is missing before optimization can run?",
        "Optimize the frame sections for cost"
      ],
      "fa": [
        "قبل از بهینه‌سازی چه چیزهایی کم است؟",
        "مقاطع قاب را برای کاهش هزینه بهینه کن"
      ]
    }
  },
  "STRUCTURAL_ENGINEERING_AGENT": {
    "title": {
      "en": "Structural Engineering Agent",
      "fa": "عامل مهندسی سازه"
    },
    "starters": {
      "en": [
        "3-storey RC frame, 2x2 bays of 5 m, analyze and design",
        "Explain the platform to me"
      ],
      "fa": [
        "قاب بتنی ۳ طبقه ۲x۲ دهانه ۵ متر را تحلیل و طراحی کن",
        "پلتفرم را به من توضیح بده"
      ]
    }
  }
};

export function assistantContext(agentType: string | null | undefined): AssistantContext | null {
  return agentType ? ASSISTANT_CONTEXTS[agentType.toUpperCase()] ?? null : null;
}
