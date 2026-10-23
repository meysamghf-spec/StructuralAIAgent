"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; label?: string; fallback?: ReactNode };
type State = { error: Error | null };

/** Keeps one broken card/section from taking down the whole page ("Application error"). */
export class SectionErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn(`[section-error] ${this.props.label ?? "section"}:`, error?.message, info?.componentStack?.slice(0, 400));
  }

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback !== undefined) return this.props.fallback;
    return (
      <div className="alert error" role="alert" data-testid="section-error">
        <p>
          {this.props.label ? `${this.props.label}: ` : ""}this section could not be shown. / نمایش این بخش ممکن نشد.
        </p>
        <button className="button secondary small" type="button" onClick={() => this.setState({ error: null })}>
          Retry / تلاش دوباره
        </button>
      </div>
    );
  }
}
