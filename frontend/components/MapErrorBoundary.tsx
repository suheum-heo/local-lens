"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = { error: Error | null };

/**
 * Leaflet / WebKit can throw during map init (especially after display:none
 * or with many markers on iOS Safari). Keep the rest of the app alive.
 */
export class MapErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ResultsMap crashed", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="flex h-full min-h-[16rem] w-full flex-col items-center justify-center gap-2 rounded-card border border-line bg-mist/50 px-4 text-center">
            <p className="text-sm font-medium text-ink">
              지도를 불러오지 못했어요
            </p>
            <button
              type="button"
              className="text-sm font-semibold text-brand-dark underline"
              onClick={() => this.setState({ error: null })}
            >
              다시 시도
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
