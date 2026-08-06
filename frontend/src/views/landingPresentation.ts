/** The precise local-state reset used when a project rename is cancelled. */
export function cancelledRenameState(projectName: string): { editing: false; draftName: string } {
  return { editing: false, draftName: projectName };
}
