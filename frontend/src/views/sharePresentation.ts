import { conflictSentences, isConflictCode } from "../lib/errors";
import { PROJECT, TASK } from "../lib/vocabulary";

/**
 * The Share tab's words (task 058 round 10; lead rulings S1 to S8 and the
 * review's proposals P2 to P5, `research/share-history-polish.md`). Kept with
 * the view that says them; entity names still come from `vocabulary.ts`.
 */
export const SHARE_COPY = {
  publicHeading: "Public link",
  /** What the section is for, one plain line under its heading, said as
   *  the effect of the choice, not as if it were made (owner, round 13). */
  publicExplain: `Making this ${TASK.lower} public creates a link that anyone can open to read the report, without a Policy Atlas account.`,
  publicOn: "Public. Anyone with the link can read it.",
  publicOff: "Not public.",
  makePublic: "Make public",
  /** The second step before the task goes public (lead ruling S3). */
  confirmPublic: "Anyone with the link can read the report, the source list and the quoted excerpts, without signing in.",
  keepPrivate: "Keep private",
  stopPublic: "Stop sharing publicly",
  linkField: "Public link",
  copyLink: "Copy link",
  copied: "Copied",
  copyFailed: "Couldn't copy. The link is selected.",
  publicFailed: "Public sharing couldn't be changed. Try again.",
  orgHeading: "Organisation",
  /** What the section is for (owner, round 13). */
  orgExplain: `Sharing with your organisation lets everyone in it open this ${TASK.lower} from their ${TASK.many} list.`,
  orgShared: "Shared with your organisation",
  orgPrivate: "Private",
  shareWithOrg: "Share with organisation",
  makePrivate: "Make private",
  orgFailed: `The ${TASK.lower}'s visibility couldn't be changed. Try again.`,
  /** In a project the task follows the project's visibility (P3). */
  followsProject: (count: number) => `Follows its ${count === 1 ? PROJECT.lower : PROJECT.lowerMany}: `,
  projectsHeading: PROJECT.many,
  notInProject: `Not in a ${PROJECT.lower}.`,
  addToProject: `Add to a ${PROJECT.lower}`,
  selectProject: `Select a ${PROJECT.lower}`,
  remove: "Remove",
  projectsFailed: `The ${PROJECT.lowerMany} couldn't be changed. Try again.`,
} as const;

/** The 403 message the server sends when it has nothing more to say. */
const GENERIC_FORBIDDEN = "action is not permitted";

/**
 * What a refused change says (lead ruling S8): the server's own message for a
 * refusal when it sends one, the conflict's sentence for a known conflict,
 * else the action's fallback.
 *
 * Args:
 *   error: The mutation's thrown error (`{ code, message }` from `raise`).
 *   fallback: The action's own sentence.
 *
 * Returns:
 *   One plain sentence.
 */
export function refusalSentence(error: unknown, fallback: string): string {
  const { code, message } = (error ?? {}) as { code?: string; message?: string };
  if (isConflictCode(code)) return conflictSentences[code];
  if (code === "forbidden" && typeof message === "string" && message.trim() !== "" && message !== GENERIC_FORBIDDEN) {
    return message;
  }
  return fallback;
}
