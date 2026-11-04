"use client";

import { largeModelNotice } from "@/lib/frame3d-limits";
import { useState } from "react";

import { GeometryField, validateGeometry } from "@/components/frame3d/GeometryField";
import { DEFAULT_FRAME_INPUTS, FRAME_FORM_FIELDS, formToInputs, inputsToForm } from "@/lib/frame3d-store";
import { prefillGeometry, type PrefillInfo } from "@/lib/frame3d-prefill";
import { inputLabels, REQUIRED_GEOMETRY, SPAN_KEYS } from "@/lib/input-labels";
import type { LengthUnit } from "@/lib/length-units";
import { useUiLang } from "@/hooks/useUiLang";

type Props = {
  values: Record<string, string>;
  setValues: (v: Record<string, string>) => void;
  busy: boolean;
  onRun: (inputs: Record<string, unknown>) => void;
  onImport: () => void;
  /** What was pre-filled from the project's chats and what was assumed (shown as a note above the fields). */
  prefill?: PrefillInfo | null;
  onPrefill?: (p: PrefillInfo) => void;
};

const isRequired = (k: string) => (REQUIRED_GEOMETRY as readonly string[]).includes(k);

/**
 * Model page form. Geometry is pre-filled from the project's chat history; anything still blank is filled with defaults
 * (never a blocking "Required") and the note lists what came from the chat and what was assumed. Spans take a unit.
 */
export function FrameModelForm({ values, setValues, busy, onRun, onImport, prefill, onPrefill }: Props) {
  const { lang, t } = useUiLang();
  const [units, setUnits] = useState<Partial<Record<string, LengthUnit>>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const groups = Array.from(new Set(FRAME_FORM_FIELDS.map((f) => f.group)));
  const tx = (en: string, fa: string) => (lang === "fa" ? fa : en);

  return (
    <form
      className="frame3d-form"
      noValidate
      data-testid="frame-model-form"
      onSubmit={(e) => {
        e.preventDefault();
        // Blank geometry is assumed (defaults), not blocked; only invalid typed values are errors.
        const filled = prefillGeometry(values, null);
        if (filled.assumed.length) {
          setValues(filled.values);
          for (const k of filled.assumed) if (units[k] && units[k] !== "m") setUnits((u) => ({ ...u, [k]: "m" }));
          onPrefill?.({
            fromChat: (prefill?.fromChat ?? []).filter((k) => !filled.assumed.includes(k)),
            assumed: Array.from(new Set([...(prefill?.assumed ?? []), ...filled.assumed])),
            chatTitle: prefill?.chatTitle ?? null,
            sourceLabel: prefill?.sourceLabel,
          });
        }
        const assumedUnits = { ...units };
        for (const k of filled.assumed) assumedUnits[k] = "m";
        const errs = validateGeometry(filled.values, assumedUnits, lang, REQUIRED_GEOMETRY);
        setErrors(errs);
        if (Object.keys(errs).length) return;
        onRun(formToInputs(filled.values, lang, assumedUnits));
      }}
    >
      <p className="muted geo-hint" data-testid="geo-required-hint">
        {tx(
          "Storeys, bays and spans in X and Y are taken from this project's chat; anything not found there is assumed and listed below. Spans accept m, cm, mm or ft.",
          "تعداد طبقات، تعداد دهانه‌ها و طول دهانه در جهت x و y از چت همین پروژه خوانده می‌شود؛ هر چه آنجا نباشد فرض می‌شود و در زیر آمده است. طول دهانه با واحد m، cm، mm یا ft وارد می‌شود.",
        )}
      </p>
      {prefill && (prefill.fromChat.length || prefill.assumed.length) ? (
        <div className="muted geo-hint" data-testid="geo-prefill-note" role="status">
          {prefill.fromChat.length ? (
            <div data-testid="geo-prefill-from-chat">
              {tx("From the chat", "از چت")}
              {prefill.chatTitle ? ` «${prefill.chatTitle}»` : prefill.sourceLabel ? ` (${prefill.sourceLabel[lang]})` : ""}:{" "}
              {inputLabels(prefill.fromChat, lang)}
            </div>
          ) : null}
          {prefill.assumed.length ? (
            <div data-testid="geo-prefill-assumed">
              {tx("Assumed (not found in the chat): ", "فرض شده (در چت پیدا نشد): ")}
              {prefill.assumed
                .map((k) => `${inputLabels([k], lang)} = ${values[k] || ""}`)
                .join(lang === "fa" ? "، " : ", ")}
            </div>
          ) : null}
        </div>
      ) : null}
      {groups.map((g) => (
        <fieldset key={g}>
          <legend>{t(g)}</legend>
          {FRAME_FORM_FIELDS.filter((f) => f.group === g).map((f) =>
            isRequired(f.key) ? (
              <GeometryField
                key={f.key}
                fieldKey={f.key}
                lang={lang}
                idPrefix="model"
                value={values[f.key] ?? ""}
                unit={(SPAN_KEYS as readonly string[]).includes(f.key) ? units[f.key] ?? "m" : undefined}
                error={errors[f.key]}
                onValue={(v) => setValues({ ...values, [f.key]: v })}
                onUnit={(SPAN_KEYS as readonly string[]).includes(f.key) ? (u) => setUnits({ ...units, [f.key]: u }) : undefined}
              />
            ) : (
              <label key={f.key}>
                <span>
                  {t(f.label)}
                  {f.unit ? ` (${f.unit})` : ""}
                </span>
                {f.kind === "select" ? (
                  <select value={values[f.key] ?? ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}>
                    {f.options!.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input dir="ltr" inputMode="decimal" value={values[f.key] ?? ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
                )}
              </label>
            ),
          )}
        </fieldset>
      ))}
      {(() => {
        const note = largeModelNotice(Number(values.storeys), Number(values.bays_x), Number(values.bays_y), lang === "fa" ? "fa" : "en");
        return note ? <p className="muted" role="status" data-testid="large-model-notice">⏳ {note}</p> : null;
      })()}
      <div className="frame3d-actions">
        <button className="button" type="submit" disabled={busy}>
          {busy ? t("Running…") : t("Run analysis + design")}
        </button>
        <button className="button secondary" type="button" onClick={onImport}>
          {t("Import from last chat frame")}
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={() => {
            setErrors({});
            setUnits({});
            setValues(inputsToForm(DEFAULT_FRAME_INPUTS));
          }}
        >
          {tx("Reset form", "پاک‌سازی فرم")}
        </button>
      </div>
    </form>
  );
}
