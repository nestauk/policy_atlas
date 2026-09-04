import type { ReactNode } from "react";
import { Navigate, useLocation, useParams } from "react-router";

import { useProject } from "../api/queries";
import { PUBLIC_TABS, isTabOpen } from "./lifecycle";
import type { LifecycleTab } from "./lifecycle";

/**
 * Gate one lifecycle route on the task's run state.
 *
 * A locked tab must not be reachable by typing its URL either — otherwise the
 * lock is decoration and the page it guards renders empty. A locked route
 * redirects to Plan, which is open at every state.
 *
 * The redirect waits for the project to load: before the query settles the
 * run state is unknown, and treating unknown as "no run" would bounce every
 * deep link back to Plan on a cold page load.
 */
export function LifecycleRoute({ tab, children }: { tab: LifecycleTab; children: ReactNode }) {
  const { projectId } = useParams();
  const project = useProject(projectId ?? "");

  if (project.isPending || project.data === undefined) return null;
  // Public-leg access (task 037): a signed-in outsider reading a public Task
  // gets Results and Sources only — every other tab's URL lands on Results,
  // mirroring the anonymous public view. The run-state locks below never
  // apply on this leg: they are an owner-side affordance, and the public
  // pages render their own shaped absence when a run has not finished.
  if (project.data.access === "public") {
    if (PUBLIC_TABS.includes(tab)) return <>{children}</>;
    return <Navigate to={`/projects/${projectId}/results`} replace />;
  }
  if (!isTabOpen(tab, project.data.latest_run?.status)) {
    return <Navigate to={`/projects/${projectId}`} replace />;
  }
  return <>{children}</>;
}

/**
 * Send a retired path to its new home, keeping the project AND the query.
 *
 * The search string carries the filter, the open dossier and the selected
 * theme. Dropping it makes a redirect look like it worked — the page loads,
 * nothing 404s — while quietly landing the reader on an unfiltered view. That
 * is a worse failure than a broken link, because nothing announces it.
 */
export function RedirectToPath({
  suffix,
  preserveOriginal = false,
}: {
  suffix: string;
  /**
   * Carry the pre-redirect location as router state under `from` (task
   * 037's public wildcard leg). This redirect can fire on project data that
   * was public when read but has since been unshared before a stashed
   * `useProject` refetch settles; when `PublicTaskShell` then discovers the
   * Task isn't public after all, `StashAndSplashRedirect` prefers this over
   * the already-rewritten URL, so a signed-out visitor's original deep link
   * (e.g. `/share`) still survives to be restored after sign-in.
   */
  preserveOriginal?: boolean;
}) {
  const { projectId } = useParams();
  const location = useLocation();
  const { search } = location;
  return (
    <Navigate
      to={`/projects/${projectId}${suffix}${search}`}
      replace
      state={
        preserveOriginal
          ? { from: `${location.pathname}${location.search}${location.hash}` }
          : undefined
      }
    />
  );
}
