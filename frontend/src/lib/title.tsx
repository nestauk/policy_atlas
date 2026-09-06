import { createContext, useContext, useEffect } from "react";
import type { ReactNode } from "react";

import { scrub } from "./scrub";

/**
 * Whether a pending check-in should mark the browser tab title (contract
 * strand 14 — "pending check-in visibility outside the workspace"). Read by
 * every view's `useDocumentTitle` call via `TitleMarkerProvider`, so the
 * marker and the view's own title segments land in one `document.title`
 * write — no two-effect race between "set the title" and "prefix it".
 */
const TitleMarkerContext = createContext(false);

/** Wrap the router outlet with the app-wide "a check-in is pending"
 *  signal so every view's title carries the "● " marker honestly. */
export function TitleMarkerProvider({ active, children }: { active: boolean; children: ReactNode }) {
  return <TitleMarkerContext.Provider value={active}>{children}</TitleMarkerContext.Provider>;
}

/**
 * Set `document.title` for the life of the calling view: `parts` join with
 * " · ", empty/absent parts are skipped (e.g. a task name still loading),
 * and "Policy Atlas" is always the last segment. Landing calls this with
 * just the Projects label (`PROJECT.many`, `lib/vocabulary.ts`); task-scoped
 * views pass the task name and the view name, e.g.
 * `useDocumentTitle(task?.name, "Workspace")` ->
 * "Acme task · Workspace · Policy Atlas".
 */
export function useDocumentTitle(...parts: Array<string | null | undefined>): void {
  const markerActive = useContext(TitleMarkerContext);
  const segments = parts
    .filter((part): part is string => typeof part === "string" && part.trim().length > 0)
    .map(scrub);
  const title = `${markerActive ? "● " : ""}${[...segments, "Policy Atlas"].join(" · ")}`;
  useEffect(() => {
    document.title = title;
  }, [title]);
}
