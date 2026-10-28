"use client";

import { useState } from "react";

import { GeometryField, validateGeometry } from "@/components/frame3d/GeometryField";
import { DEFAULT_FRAME_INPUTS, FRAME_FORM_FIELDS, formToInputs, inputsToForm } from "@/lib/frame3d-store";
import { REQUIRED_GEOMETRY, SPAN_KEYS } from "@/lib/input-labels";
import type { LengthUnit } from "@/lib/length-units";
import { useUiLang } from "@/hooks/useUiLang";

type Props = {
  values: Record<string, string>;
  setValues: (v: Record<string, string>) => void;
  busy: boolean;
  onRun: (inputs: Record<string, unknown>) => void;
  onImport: () => void;
};

const isRequired = (k: string) => (REQUIRED_GEOMETRY as readonly string[]).includes(k);

/** Model page form. The five geometry fields are required (placeholders only, no hidden defaults); spans take a unit (m/cm/mm/ft). */
export function FrameModelForm({ values, setValues, busy, onRun, onImport }: Props) {
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
        const errs = validateGeometry(values, units, lang, REQUIRED_GEOMETRY);
        setErrors(errs);
        if (Object.keys(errs).length) return;
        onRun(formToInputs(values, lang, units));
      }}
    >
      <p className="muted geo-hint" data-testid="geo-required-hint">
        {tx(
          "Required: number of storeys, bays and span lengths in X and Y — nothing is pre-filled or guessed. Spans accept m, cm, mm or ft.",
          "لازم: تعداد طبقات، تعداد دهانه‌ها و طول دهانه در جهت x و y — هیچ مقداری از قبل پر یا حدس زده نمی‌شود. طول دهانه با واحد m، cm، mm یا ft وارد می‌شود.",
        )}
      </p>
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
