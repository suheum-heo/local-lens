"use client";

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";

const ResultsMapInner = dynamic(
  () => import("./ResultsMap").then((m) => m.ResultsMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-64 items-center justify-center border border-ink/10 bg-mist/40 text-sm text-ink/45 sm:h-80">
        지도 불러오는 중…
      </div>
    ),
  },
);

export function ResultsMapClient(
  props: ComponentProps<typeof ResultsMapInner>,
) {
  return <ResultsMapInner {...props} />;
}
