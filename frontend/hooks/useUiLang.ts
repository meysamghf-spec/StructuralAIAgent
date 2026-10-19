"use client";

import { useEffect, useMemo, useState } from "react";

import type { Frame3dLang } from "@/lib/frame3d-i18n";
import { getUiLang, makeUiT, setUiLang, UI_LANG_EVENT } from "@/lib/ui-i18n";

export function useUiLang() {
  const [lang, setLang] = useState<Frame3dLang>("en");
  useEffect(() => {
    const sync = () => setLang(getUiLang());
    sync();
    window.addEventListener(UI_LANG_EVENT, sync);
    return () => window.removeEventListener(UI_LANG_EVENT, sync);
  }, []);
  const t = useMemo(() => makeUiT(lang), [lang]);
  return { lang, t, setLang: setUiLang };
}
