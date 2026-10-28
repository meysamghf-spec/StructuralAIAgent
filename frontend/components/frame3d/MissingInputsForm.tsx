"use client";

import { useState } from "react";

import { GeometryField, validateGeometry } from "@/components/frame3d/GeometryField";
import { FRAME3D_EVENT, saveFrame3dInputs, saveFrame3dPayload } from "@/lib/frame3d-store";
import { runFrame3d } from "@/lib/frame3d-run";
import { inputLabels, missingGeometry } from "@/lib/input-labels";
import { parseNumber, typedToMetres, type LengthUnit } from "@/lib/length-units";
import { useUiLang } from "@/hooks/useUiLang";

type Props = {
  /** Inputs stored with the run/model (may have null or absent geometry). */
  inputs: Record<string, unknown> | null | undefined;
  projectId?: string | null;
  /** Called with the new payload + merged inputs after a successful rerun. */
  onDone?: (payload: unknown, merged: Record<string, unknown>) => void;
  /** Optionally restrict which keys are asked (defaults to everything missing). */
  keys?: string[];
  compact?: boolean;
};

/**
 * Inline "enter the missing values and rerun" form: friendly fa/en labels, unit selector for spans,
 * reruns the existing /frame3d/run endpoint with the stored inputs + the entered values (no silent guessing).
 */
export function MissingInputsForm({ inputs, projectId = null, onDone, keys, compact }: Props) {
  const { lang } = useUiLang();
  const stored = (inputs ?? {}) as Record<string, unknown>;
  const missing = keys ?? missingGeometry(stored);
  const [values, setValues] = useState<Record<string, string>>({});
  const [units, setUnits] = useState<Partial<Record<string, LengthUnit>>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);

  if (!missing.length && !done) return null;
  if (done) {
    return (
      <p className="muted" role="status" data-testid="missing-inputs-done" dir={lang === "fa" ? "rtl" : "ltr"}>
        {tx("Saved to this project and re-run with your values.", "ذخیره شد و با مقادیر شما دوباره اجرا شد.")}
      </p>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateGeometry(values, units, lang, missing);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const entered: Record<string, unknown> = {};
    for (const k of missing) {
      const raw = values[k];
      entered[k] = k.startsWith("bay_") ? typedToMetres(raw, units[k] ?? "m") : Math.round(parseNumber(raw) ?? 0);
    }
    const base = Object.fromEntries(Object.entries(stored).filter(([k, v]) => !k.startsWith("_") && v !== null && v !== undefined && v !== ""));
    const merged = { ...base, ...entered, lang };
    setBusy(true);
    setErr(null);
    try {
      const payload = await runFrame3d(merged);
      const st = (payload as { status?: string } | null)?.status;
      if (st === "MISSING_REQUIRED_INPUT") {
        setErr(tx("Some inputs are still missing — please check the fields.", "هنوز برخی ورودی‌ها کم است — فیلدها را بررسی کنید."));
        return;
      }
      saveFrame3dInputs(projectId, merged);
      saveFrame3dPayload(projectId, payload);
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(FRAME3D_EVENT));
      setDone(true);
      onDone?.(payload, merged);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className={compact ? "missing-inputs-form compact" : "missing-inputs-form"}
      data-testid="missing-inputs-form"
      dir={lang === "fa" ? "rtl" : "ltr"}
      lang={lang}
      onSubmit={(e) => void submit(e)}
      noValidate
    >
      <p className="alert" role="note">
        {tx(
          `Missing: ${inputLabels(missing, "en")}. Enter the values below and re-run — nothing is assumed.`,
          `ورودی‌های ناقص: ${inputLabels(missing, "fa")}. مقادیر را اینجا وارد کنید و دوباره اجرا کنید — چیزی فرض نمی‌شود.`,
        )}
      </p>
      <div className="geo-grid">
        {missing.map((k) => (
          <GeometryField
            key={k}
            fieldKey={k}
            idPrefix="miss"
            lang={lang}
            value={values[k] ?? ""}
            unit={units[k] ?? "m"}
            error={errors[k]}
            onValue={(v) => setValues((s) => ({ ...s, [k]: v }))}
            onUnit={(u) => setUnits((s) => ({ ...s, [k]: u }))}
          />
        ))}
      </div>
      {err ? <p className="alert error" role="alert">{err}</p> : null}
      <button className="button" type="submit" disabled={busy}>
        {busy ? tx("Running…", "در حال اجرا…") : tx("Save values and re-run", "ذخیره مقادیر و اجرای دوباره")}
      </button>
    </form>
  );
}
