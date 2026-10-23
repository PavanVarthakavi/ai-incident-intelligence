import { scrollBehavior } from "../../lib/motion";
import { useMemo, useRef, useState, type ReactNode } from "react";
import type { Evidence } from "../../api/client";
import { exhibitNumbers, type CitationSource } from "../../lib/exhibits";
import { ExhibitContext, type ExhibitState } from "./exhibitState";

export function ExhibitProvider({
  evidence,
  citedBy,
  children,
}: {
  evidence: Evidence[];
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
    [evidence, citedBy, active, pinned, hasOrigin],
  );
  return <ExhibitContext.Provider value={value}>{children}</ExhibitContext.Provider>;
}
