import { createContext, useContext, useState, type ReactNode } from "react";

interface PlanPanel {
  open: boolean;
  openPlan: () => void;
  closePlan: () => void;
}

const PlanPanelContext = createContext<PlanPanel | null>(null);

/**
 * Whether the plan document is open, shared by the task shell so the "Plan"
 * control in the task nav, the Agent tab's "Review the plan" and the
 * sidebar's plan links all open the same side panel (task 058, N15).
 */
export function PlanPanelProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <PlanPanelContext.Provider
      value={{ open, openPlan: () => setOpen(true), closePlan: () => setOpen(false) }}
    >
      {children}
    </PlanPanelContext.Provider>
  );
}

/**
 * Read the shared plan-panel state. Outside a provider (a view rendered on
 * its own, as in a unit test) it falls back to state of its own.
 *
 * Returns:
 *   `open`, plus `openPlan` and `closePlan` to change it.
 */
export function usePlanPanel(): PlanPanel {
  const shared = useContext(PlanPanelContext);
  const [open, setOpen] = useState(false);
  return shared ?? { open, openPlan: () => setOpen(true), closePlan: () => setOpen(false) };
}
