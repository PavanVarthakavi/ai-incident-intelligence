import { createContext, useContext } from "react";
import type { Evidence } from "../../api/client";
import type { CitationSource } from "../../lib/exhibits";

export type ExhibitState = {
  evidence: Evidence[];
  numbers: Map<string, number>;
  citedBy: Map<string, CitationSource[]>;
  /** Evidence under the pointer or keyboard focus, highlighted while it lasts. */
  active: string | null;
  /** Evidence opened by a click, expanded until closed. */
  pinned: string | null;
  setActive: (id: string | null) => void;
  /** Opens or closes an exhibit; `from` is the citation that opened it, to return to. */
  togglePin: (id: string, from?: HTMLElement) => void;
  /** Scrolls back to and focuses the citation that opened the pinned exhibit. */
  returnToCitation: () => void;
  hasOrigin: boolean;
};

export const ExhibitContext = createContext<ExhibitState | null>(null);

export function useExhibits(): ExhibitState {
  const state = useContext(ExhibitContext);
  if (state === null) throw new Error("useExhibits needs an ExhibitProvider");
  return state;
}

export const exhibitRowId = (evidenceId: string) => `exhibit-${evidenceId}`;
