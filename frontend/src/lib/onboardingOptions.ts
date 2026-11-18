/**
 * Onboarding profile: every list of answers, in one file.
 *
 * The API stores the codes, not the labels, so a label can change here with
 * no change to stored data. The J1 to J7 labels will be revised after user
 * testing. The type check fails if a team type or a use has no label.
 *
 * The departments and the email-domain map are held only here: the API takes
 * any department code. Change the two lists together when a department is
 * renamed.
 */
import type { components } from "../api/gen/types";

type ProfileAnswers = components["schemas"]["UserProfileIn"];
export type TeamType = ProfileAnswers["team_type"];
export type ProfileJob = ProfileAnswers["primary_job"];

/** The department code for a department that is not in the list. */
export const OTHER_DEPARTMENT = "other";

/** "Where do you work?": the departments in the select, in A to Z order. */
export const DEPARTMENTS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "ago", label: "Attorney General's Office" },
  { value: "co", label: "Cabinet Office" },
  { value: "dbt", label: "Department for Business and Trade" },
  { value: "dcms", label: "Department for Culture, Media and Sport" },
  { value: "dfe", label: "Department for Education" },
  { value: "desnz", label: "Department for Energy Security and Net Zero" },
  { value: "defra", label: "Department for Environment, Food and Rural Affairs" },
  { value: "dsit", label: "Department for Science, Innovation and Technology" },
  { value: "dft", label: "Department for Transport" },
  { value: "dwp", label: "Department for Work and Pensions" },
  { value: "dhsc", label: "Department of Health and Social Care" },
  { value: "fcdo", label: "Foreign, Commonwealth and Development Office" },
  { value: "hmrc", label: "HM Revenue and Customs" },
  { value: "hmt", label: "HM Treasury" },
  { value: "ho", label: "Home Office" },
  { value: "mod", label: "Ministry of Defence" },
  { value: "mhclg", label: "Ministry of Housing, Communities and Local Government" },
  { value: "moj", label: "Ministry of Justice" },
  { value: "no10", label: "Prime Minister's Office, 10 Downing Street" },
  { value: "scottish_government", label: "Scottish Government" },
  { value: "welsh_government", label: "Welsh Government" },
  { value: OTHER_DEPARTMENT, label: "Other…" },
];

/** Email domain to department code. A subdomain of a listed domain also matches. */
const EMAIL_DOMAIN_DEPARTMENT: Readonly<Record<string, string>> = {
  "attorneygeneral.gov.uk": "ago",
  "cabinetoffice.gov.uk": "co",
  "businessandtrade.gov.uk": "dbt",
  "dcms.gov.uk": "dcms",
  "education.gov.uk": "dfe",
  "energysecurity.gov.uk": "desnz",
  "defra.gov.uk": "defra",
  "dsit.gov.uk": "dsit",
  "dft.gov.uk": "dft",
  "dwp.gov.uk": "dwp",
  "dhsc.gov.uk": "dhsc",
  "fcdo.gov.uk": "fcdo",
  "hmrc.gov.uk": "hmrc",
  "hmtreasury.gov.uk": "hmt",
  "homeoffice.gov.uk": "ho",
  "mod.gov.uk": "mod",
  "mod.uk": "mod",
  "communities.gov.uk": "mhclg",
  "justice.gov.uk": "moj",
  "no10.gov.uk": "no10",
  "gov.scot": "scottish_government",
  "gov.wales": "welsh_government",
};

/**
 * The department to prefill from a user's email address.
 *
 * Args:
 *   email: The user's email address, or null when the app does not know it.
 *
 * Returns:
 *   The department code for a known domain, `"other"` for an unknown domain,
 *   and `""` (no prefill) when there is no email address.
 */
export function departmentForEmail(email: string | null | undefined): string {
  const domain = email?.split("@")[1]?.trim().toLowerCase();
  if (domain === undefined || domain === "") return "";
  const known = Object.keys(EMAIL_DOMAIN_DEPARTMENT).find(
    (listed) => domain === listed || domain.endsWith(`.${listed}`),
  );
  return known === undefined ? OTHER_DEPARTMENT : EMAIL_DOMAIN_DEPARTMENT[known];
}

/** "Where do you work?": the team-type chips, in display order. */
export const TEAM_TYPE_LABELS: Readonly<Record<TeamType, string>> = {
  policy: "Policy",
  analysis_evidence: "Analysis / evidence",
  strategy_finance: "Strategy & finance",
  private_office: "Private office / No.10",
  other: "Other",
};

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
