import { createContext, useContext, useEffect } from "react";
import type { ReactNode } from "react";

import { scrub } from "./scrub";

/**
 * What the browser tab title should flag, read by every view's
 * `useDocumentTitle` call via `TitleMarkerProvider`, so the marker and the
 * view's own title segments land in one `document.title` write — no
 * two-effect race between "set the title" and "prefix it".
 *
 * `active`: a check-in is waiting (contract strand 14, "pending check-in
 * visibility outside the workspace"). `ready`: the run finished and the user
 * has not looked yet; it carries the words ("Report ready") and wins over
 * `active` (task 058, N14).
 */
interface TitleMarker {
  active: boolean;
  ready: string | null;
}

const TitleMarkerContext = createContext<TitleMarker>({ active: false, ready: null });

/** Wrap the router outlet with the app-wide title signals. A nested
 *  provider overrides only the props it is given. */
export function TitleMarkerProvider({
  active,
  ready,
  children,
}: {
  active?: boolean;
  ready?: string | null;
  children: ReactNode;
}) {
  const parent = useContext(TitleMarkerContext);
  const value = { active: active ?? parent.active, ready: ready === undefined ? parent.ready : ready };
  return <TitleMarkerContext.Provider value={value}>{children}</TitleMarkerContext.Provider>;
}

/**
 * Set `document.title` for the life of the calling view: `parts` join with
 * " · ", empty/absent parts are skipped (e.g. a task name still loading),
 * and "Policy Atlas" is always the last segment. Landing calls this with
 * just the Projects label (`PROJECT.many`, `lib/vocabulary.ts`); task-scoped
 * views pass the task name and the view name, e.g.
 * `useDocumentTitle(task?.name, "Workspace")` ->
 * "Acme task · Workspace · Policy Atlas". A finished run the user has not
 * seen reads "● Report ready · Acme task · Policy Atlas".
 */
export function useDocumentTitle(...parts: Array<string | null | undefined>): void {
  const { active, ready } = useContext(TitleMarkerContext);
  const segments = parts
    .filter((part): part is string => typeof part === "string" && part.trim().length > 0)
    .map(scrub);
  const title =
    ready !== null
      ? `● ${[ready, ...segments.slice(0, 1), "Policy Atlas"].join(" · ")}`
      : `${active ? "● " : ""}${[...segments, "Policy Atlas"].join(" · ")}`;
  useEffect(() => {
    document.title = title;
  }, [title]);
}
