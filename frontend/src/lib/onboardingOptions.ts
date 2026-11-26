/**
 * Onboarding profile: the list of uses, in one file.
 *
 * The API stores the codes, not the labels, so a label can change here with
 * no change to stored data. The J1 to J7 labels will be revised after user
 * testing. The type check fails if a use has no label.
 */
import type { components } from "../api/gen/types";

export type ProfileJob = components["schemas"]["UserProfileIn"]["jobs"][number];

/** "What will you mainly use Policy Atlas for?": the uses, in display order. */
export const JOB_LABELS: Readonly<Record<ProfileJob, string>> = {
  j1: "Build or defend a spending bid",
  j2: "Pressure-test someone else's bid or numbers",
  j3: "Test claims in a policy proposal",
  j4: "Turn evidence into briefing, fast",
  j5: "Bring in international evidence and ideas",
  j6: "Compare interventions across countries",
  j7: "Get up to speed on a new policy area",
  other: "Something else",
};
