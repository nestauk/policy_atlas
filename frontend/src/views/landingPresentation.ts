/** The precise local-state reset used when a task rename is cancelled. */
export function cancelledRenameState(taskName: string): { editing: false; draftName: string } {
  return { editing: false, draftName: taskName };
}
