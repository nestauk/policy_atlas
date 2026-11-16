import { createContext, useContext, useEffect, useMemo, useRef, useState, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "../brand/cn";

/**
 * Arrivals (task 058, round 9; the animation sweep's entry 2): in a view
 * that grows as things arrive (the Task Agent thread), only a block that
 * appears after the view's first paint rises in. Opening the view, the
 * sidebar or a reload shows the history still, because motion on opening a
 * view marks navigation, not data arriving.
 *
 * Each block names itself with a stable id; a block whose id has already
 * been on screen in this view does not rise again, so the durable turn that
 * replaces a streamed one (same client turn id) appears in place.
 */
interface ArrivalScope {
  /** True once the view's first paint with its content is done. */
  ready: boolean;
  has: (id: string) => boolean;
  add: (id: string) => void;
}

const ArrivalContext = createContext<ArrivalScope | null>(null);

/**
 * Whether a view's first paint with its content is done: true from the commit
 * after `ready` first holds for this `key`, so blocks mounted with the
 * content hold still and later ones arrive. A new `key` starts afresh.
 *
 * Args:
 *   ready: True once the view's content has loaded.
 *   key: The view's identity (the task id).
 */
export function useFirstPaintDone(ready: boolean, key: string): boolean {
  const [readyKey, setReadyKey] = useState<string | null>(null);
  useEffect(() => {
    if (!ready) return undefined;
    // Once this commit has painted.
    const id = window.setTimeout(() => setReadyKey(key), 0);
    return () => window.clearTimeout(id);
  }, [ready, key]);
  return ready && readyKey === key;
}

/**
 * The scope a view's arrivals are judged in.
 *
 * Args:
 *   settled: The view's first paint is done (`useFirstPaintDone`).
 *   scopeKey: The view's identity (the task id): a change starts afresh.
 */
export function ArrivalProvider({
  settled,
  scopeKey,
  children,
}: {
  settled: boolean;
  scopeKey: string;
  children: ReactNode;
}) {
  const seen = useRef(new Map<string, Set<string>>());
  const value = useMemo<ArrivalScope>(() => {
    const ids = () => {
      let set = seen.current.get(scopeKey);
      if (set === undefined) {
        set = new Set();
        seen.current = new Map([[scopeKey, set]]);
      }
      return set;
    };
    return { ready: settled, has: (id) => ids().has(id), add: (id) => void ids().add(id) };
  }, [settled, scopeKey]);
  return <ArrivalContext.Provider value={value}>{children}</ArrivalContext.Provider>;
}

/** Whether the view's first paint is done (outside a scope: false). */
export function useArrivalsReady(): boolean {
  return useContext(ArrivalContext)?.ready ?? false;
}

/**
 * Whether this block is arriving now: it mounted after the view's first
 * paint and its id has not been on screen in this view. Decided once, at
 * mount. Outside an arrival scope nothing arrives.
 */
export function useArrives(id: string): boolean {
  const scope = useContext(ArrivalContext);
  const [arrives] = useState(() => scope !== null && scope.ready && !scope.has(id));
  useEffect(() => {
    scope?.add(id);
  }, [scope, id]);
  return arrives;
}

/** A block that rises in (`anim-rise`) when it arrives after the view's
 *  first paint, and holds still otherwise. */
export function Arrival({
  arrivalId,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { arrivalId: string; children: ReactNode }) {
  const arrives = useArrives(arrivalId);
  return (
    <div className={cn(arrives && "anim-rise", className)} {...props}>
      {children}
    </div>
  );
}
