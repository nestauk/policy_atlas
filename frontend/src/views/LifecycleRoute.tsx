import type { ReactNode } from "react";
import { Navigate, useParams } from "react-router";

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

/** Send a retired path to its new home, keeping the project in the URL. */
export function RedirectToPath({ suffix }: { suffix: string }) {
  const { projectId } = useParams();
  return <Navigate to={`/projects/${projectId}${suffix}`} replace />;
}
