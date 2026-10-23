import { scrollBehavior } from "../../lib/motion";
import { useMemo, useRef, useState, type ReactNode } from "react";
import type { Evidence, SourceError } from "../../api/client";
import { exhibitNumbers, type CitationSource } from "../../lib/exhibits";
import { ExhibitContext, type ExhibitState, type SourceGap } from "./exhibitState";

export function ExhibitProvider({
  evidence,
  sourceErrors = [],
  emptySources = [],
  citedBy,
  children,
}: {
  evidence: Evidence[];
  sourceErrors?: SourceError[];
  emptySources?: string[];
  citedBy: Map<string, CitationSource[]>;
  children: ReactNode;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const [hasOrigin, setHasOrigin] = useState(false);
  const origin = useRef<HTMLElement | null>(null);
  const value = useMemo<ExhibitState>(
    () => ({
      evidence,
      sourceGaps: new Map<string, SourceGap>([
        ...sourceErrors.map((e) => [`src-${e.source}`, { kind: "failed" as const, ...e }] as const),
        ...emptySources.map(
          (source) => [`src-${source}`, { kind: "empty" as const, source }] as const,
        ),
      ]),
      numbers: exhibitNumbers(evidence),
      citedBy,
      active,
      pinned,
      setActive,
      togglePin: (id, from) => {
        origin.current = from ?? null;
        setHasOrigin(from !== undefined);
        setPinned((current) => (current === id ? null : id));
      },
      returnToCitation: () => {
        origin.current?.scrollIntoView({ block: "center", behavior: scrollBehavior() });
        origin.current?.focus({ preventScroll: true });
      },
      hasOrigin,
    }),
    [evidence, sourceErrors, emptySources, citedBy, active, pinned, hasOrigin],
  );
  return <ExhibitContext.Provider value={value}>{children}</ExhibitContext.Provider>;
}
