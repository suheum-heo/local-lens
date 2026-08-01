"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, type ComponentProps } from "react";
import { MapErrorBoundary } from "./MapErrorBoundary";

const ResultsMapInner = dynamic(
  () => import("./ResultsMap").then((m) => m.ResultsMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full min-h-[16rem] w-full items-center justify-center rounded-card border border-line bg-mist/50 text-sm text-mute">
        지도 불러오는 중…
      </div>
    ),
  },
);

type Props = ComponentProps<typeof ResultsMapInner> & {
  /** When false, unmount Leaflet entirely (required for iOS Safari). */
  active?: boolean;
};

/**
 * Only mount the Leaflet map after the host is visible and laid out.
 * Mounting into display:none (or immediately on tab switch) crashes WebKit.
 */
export function ResultsMapClient({ active = true, ...props }: Props) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!active) {
      setReady(false);
      return;
    }
    let cancelled = false;
    // Two frames + short timeout: wait for the map pane height to resolve.
    const id = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        window.setTimeout(() => {
          if (!cancelled) setReady(true);
        }, 50);
      });
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(id);
    };
  }, [active]);

  if (!active || !ready) {
    return (
      <div className="flex h-full min-h-[16rem] w-full items-center justify-center rounded-card border border-line bg-mist/50 text-sm text-mute">
        지도 불러오는 중…
      </div>
    );
  }

  return (
    <MapErrorBoundary>
      <ResultsMapInner {...props} />
    </MapErrorBoundary>
  );
}
