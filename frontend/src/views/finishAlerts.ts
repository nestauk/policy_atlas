import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";

import { useApiClient, useTasks } from "../api/queries";
import { activeRun } from "./scopingActivity";
import type { CheckStatus } from "./toc/types";

/**
 * Browser alerts when a task's work finishes (owner, 2026-11-04): a theory
 * drafted, an evidence check finished, an evidence search ready, or a walk
 * waiting for an answer. They show while any Policy Atlas tab is open, when
 * that task is not the page in view. Uses the browser's own notifications;
 * nothing is sent from the server.
 */

const TOC_ALERT: Partial<Record<CheckStatus, string>> = {
  drafted: "Your theory of change is drafted. Review it, then check the evidence.",
  checked: "The evidence check is finished.",
  stopped: "The evidence check was stopped.",
  failed: "The evidence check failed.",
};

/** What a theory-of-change alert says, by the theory's state; null while the walks go on. */
export function tocAlertText(status: CheckStatus | undefined): string | null {
  return status === undefined ? null : (TOC_ALERT[status] ?? null);
}

/** Watch every task's walks and alert when one finishes or waits for the user. Mount once, in the app shell. */
export function useFinishAlerts(): void {
  const tasks = useTasks(undefined, { background: true });
  const client = useApiClient();
  const navigate = useNavigate();
  // The last status seen per task: a running or paused walk's, or null when none runs.
  const seen = useRef(new Map<string, string | null>());

  useEffect(() => {
    const list = tasks.data?.data;
    if (list === undefined) return;
    for (const task of list) {
      const now = activeRun(task)?.status ?? null;
      const before = seen.current.get(task.task_id);
      seen.current.set(task.task_id, now);
      // The first sighting only records; an alert needs a change seen in this session.
      if (before === undefined || before === now || before === null) continue;
      const inView = document.visibilityState === "visible" && window.location.pathname.startsWith(`/tasks/${task.task_id}`);
      if (inView || typeof Notification === "undefined" || Notification.permission !== "granted") continue;
      const show = (body: string) => {
        const alert = new Notification(task.name, { body, tag: `pa-${task.task_id}` });
        alert.onclick = () => {
          window.focus();
          void navigate(`/tasks/${task.task_id}/result`);
          alert.close();
        };
      };
      if (now === "paused") {
        show("Policy Atlas has a question for you.");
        continue;
      }
      if (now !== null) continue;
      if (task.capability === "theory_of_change") {
        void client
          .GET("/api/v1/tasks/{task_id}/toc", { params: { path: { task_id: task.task_id } } })
          .then(({ data }) => {
            const text = tocAlertText(data?.check_status);
            if (text !== null) show(text);
          });
        continue;
      }
      const status = task.latest_run?.status;
      show(status === "succeeded" || status === "degraded" ? "Your results are ready." : "The run stopped before finishing.");
    }
  }, [tasks.data, client, navigate]);
}
