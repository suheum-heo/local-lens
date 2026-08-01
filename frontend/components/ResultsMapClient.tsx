"use client";

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";

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

export function ResultsMapClient(
  props: ComponentProps<typeof ResultsMapInner>,
) {
  return <ResultsMapInner {...props} />;
}
