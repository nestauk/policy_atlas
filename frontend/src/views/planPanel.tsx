import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { exitRuns } from "../ui/motion/motion";

interface PlanPanel {
  open: boolean;
  /** True while the plan plays its exit; it unmounts when that ends. */
  closing: boolean;
  openPlan: () => void;
  closePlan: () => void;
}

/** How long the plan document takes to leave: as a sheet, faster than it
 *  came (260 ms). */
export const PLAN_EXIT_MS = 200;

const PlanPanelContext = createContext<PlanPanel | null>(null);

/** The plan panel's state: open, and leaving the way it came (owner,
 *  2026-11-09: the plan opened with motion and closed with a cut, unlike the
 *  citation and document sheets). Asked to close, it stays mounted with
 *  `closing` set for `PLAN_EXIT_MS` so the document and the scrim over a tab
 *  can play their exits, then closes. Under reduced motion it closes at
 *  once. An open during the exit cancels it. */
function usePlanPanelState(): PlanPanel {
  const [open, setOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  useEffect(() => {
    if (!closing) return undefined;
    const id = window.setTimeout(() => {
      setClosing(false);
      setOpen(false);
    }, PLAN_EXIT_MS);
    return () => window.clearTimeout(id);
  }, [closing]);
  return {
    open,
    closing,
    openPlan: () => {
      setClosing(false);
      setOpen(true);
    },
    closePlan: () => {
      if (exitRuns()) setClosing(true);
      else setOpen(false);
    },
  };
}

/**
 * Whether the plan document is open, shared by the task shell so the "Plan"
 * control in the task nav, the Agent tab's "Review the plan" and the
 * sidebar's plan links all open the same side panel (task 058, N15).
 */
export function PlanPanelProvider({ children }: { children: ReactNode }) {
  const panel = usePlanPanelState();
  return <PlanPanelContext.Provider value={panel}>{children}</PlanPanelContext.Provider>;
}

/**
 * Read the shared plan-panel state. Outside a provider (a view rendered on
 * its own, as in a unit test) it falls back to state of its own.
 *
 * Returns:
 *   `open` and `closing`, plus `openPlan` and `closePlan` to change them.
 */
export function usePlanPanel(): PlanPanel {
  const shared = useContext(PlanPanelContext);
  const own = usePlanPanelState();
  return shared ?? own;
}
