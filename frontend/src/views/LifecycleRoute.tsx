import type { ReactNode } from "react";
import { Navigate, useLocation, useParams } from "react-router";

import { useProject } from "../api/queries";
import { isTabOpen } from "./lifecycle";
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
export function RedirectToPath({ suffix }: { suffix: string }) {
  const { projectId } = useParams();
  const { search } = useLocation();
  return <Navigate to={`/projects/${projectId}${suffix}${search}`} replace />;
}
