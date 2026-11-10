import { useTask } from "../../api/queries";
import { usePublicView } from "../publicView";
import { ownerWord } from "./longlistPresentation";

/** `ownerWord` for the task on this page: "you", the owner's short name, or "the owner". */
export function useOwnerWord(taskId: string): string {
  const task = useTask(taskId);
  return ownerWord(task.data, usePublicView());
}
