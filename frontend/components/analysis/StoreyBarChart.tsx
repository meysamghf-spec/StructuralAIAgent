"use client";

// Horizontal per-storey bar chart (top storey first). Plain HTML/CSS so it follows RTL and wraps on small screens.
export type BarSeries = { key: string; label: string; values: Array<number | null> };

export function StoreyBarChart({
  title,
  unit,
  storeys,
  series,
  limit,
  limitLabel,
  digits = 2,
  storeyLabel,
  topFirst = true,
}: {
  title: string;
  unit: string;
  storeys: number[];
  series: BarSeries[];
  limit?: number | null;
  limitLabel?: string;
  digits?: number;
  storeyLabel: string;
  /** storeys: highest first; modes: ascending */
  topFirst?: boolean;
}) {
  const all = series.flatMap((s) => s.values).filter((v): v is number => v !== null && Number.isFinite(v));
  const max = Math.max(...all.map((v) => Math.abs(v)), limit ?? 0, 0);
  if (!all.length || max <= 0) return null;
  const scale = max * 1.08;
  const order = storeys.map((_, i) => i);
  if (topFirst) order.reverse();
  return (
    <figure className="an-chart" aria-label={title}>
      <figcaption>
        <span>{title}</span>
        <span className="an-chart-unit" dir="ltr">{unit}</span>
      </figcaption>
      <ul className="an-chart-rows">
        {order.map((i) => (
          <li key={storeys[i]} className="an-chart-row">
            <span className="an-chart-label">{storeyLabel} {storeys[i]}</span>
            <span className="an-chart-track" dir="ltr">
              {limit != null && limit > 0 ? <i className="an-chart-limit" style={{ left: `${(limit / scale) * 100}%` }} title={limitLabel} /> : null}
              {series.map((s, si) => {
                const v = s.values[i];
                if (v === null || v === undefined) return null;
                const over = limit != null && v > limit;
                return (
                  <span key={s.key} className="an-chart-barwrap">
                    <b className={`an-chart-bar an-s${si}${over ? " over" : ""}`} style={{ width: `${Math.max(1, (Math.abs(v) / scale) * 100)}%` }} />
                    <em>{v.toLocaleString("en-US", { maximumFractionDigits: digits, useGrouping: false })}</em>
                  </span>
                );
              })}
            </span>
          </li>
        ))}
      </ul>
      <div className="an-chart-legend" dir="ltr">
        {series.length > 1 ? series.map((s, si) => <span key={s.key}><b className={`an-dot an-s${si}`} />{s.label}</span>) : null}
        {limit != null && limit > 0 ? <span><b className="an-dot-limit" />{limitLabel}</span> : null}
      </div>
    </figure>
  );
}
