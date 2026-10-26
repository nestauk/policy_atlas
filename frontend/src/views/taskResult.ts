import { useArtefact, useTask, useToc } from "../api/queries";
import { useRunStream } from "../store";
import { hasResult, type TabOptions } from "./lifecycle";
import { hasLonglist, hasTaskResult, isBaselineArtefact, isScoping, isToc } from "./scopingActivity";

/**
 * The results a task's lifecycle tabs open on (task 044, A17; task 045):
 * a scoping task's baseline and longlist. Only a scoping task pays for the
 * artefact read — the empty task id disables the query.
 *
 * Returns:
 *   The tab options, and whether a scoping task's baseline read is still in
 *   flight (its existence is then unknown).
 */
export function useTabOptions(taskId: string): { options: TabOptions; baselineLoading: boolean } {
  const task = useTask(taskId);
  const scoping = isScoping(task.data);
  const artefact = useArtefact(scoping ? taskId : "");
  const toc = useToc(isToc(task.data) ? taskId : "");
  return {
    options: {
      hasBaseline: isBaselineArtefact(artefact.data),
      hasLonglist: hasLonglist(task.data),
      hasToc: (toc.data?.boxes.length ?? 0) > 0,
    },
    baselineLoading: scoping && artefact.isLoading,
  };
}

/**
 * Whether chats are open: they need a result to ask about (038 V8). Either
 * source may be behind — the task read model until its next refetch, the run
 * stream until its replay reaches the final status frame. A scoping task has
 * a result once a baseline or a longlist exists (task 045, S15).
 */
export function useChatsEnabled(taskId: string): boolean {
  const task = useTask(taskId);
  const artefact = useArtefact(taskId);
  const toc = useToc(isToc(task.data) ? taskId : "");
  const stream = useRunStream(taskId);
  return (
    hasTaskResult(task.data, { hasBaseline: isBaselineArtefact(artefact.data), hasToc: (toc.data?.boxes.length ?? 0) > 0 }) ||
    hasResult(stream.run?.status)
  );
}
