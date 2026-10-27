import type {
  Grade,
  LinkState,
  TocBox,
  TocBoxEvidence,
  TocDocument,
  TocEvidence,
  TocGraph,
  TocLink,
  TocPathway,
} from "./types";

/*
 * A realistic theory of change for tests, from the wireframe example: the
 * obesity option "Restrictions on unhealthy food advertising to children".
 * Two success pathways, one failure pathway, one set-aside pathway; nine
 * links with mixed grades and states, one critical link (L3), one merged link
 * (L6), and one document (TfL) that answers both questions on L3.
 */

export const TASK_ID = "11111111-1111-4111-8111-111111111111";
const id = (kind: string, n: number) => `${kind}0000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const boxId = (n: number) => id("b", n);
export const linkId = (n: number) => id("c", n);
export const pathwayId = (n: number) => id("d", n);
export const docId = (n: number) => id("e", n);

function box(n: number, layer: TocBox["layer"], text: string, extra: Partial<TocBox> = {}): TocBox {
  return {
    box_id: boxId(n),
    layer,
    text,
    dosage: null,
    result_criteria: { definition: `Definition of: ${text}`, indicator: `Indicator for: ${text}`, timing: "Within a year" },
    description: `${text}, described in a short paragraph.`,
    origin: "drafted",
    revision: 1,
    ...extra,
  };
}

export const BOXES: TocBox[] = [
  box(1, "input", "Ban on less healthy food ads", { origin: "imported" }),
  box(2, "input", "Nutrient profiling rules, enforced by Ofcom"),
  box(3, "output", "Fewer less healthy food ads shown"),
  box(4, "output", "Some products reformulated to pass the rules"),
  box(5, "outcome", "Children see fewer ads for less healthy food"),
  box(6, "outcome", "Children ask for and pick healthier food"),
  box(7, "outcome", "Households buy fewer calories from less healthy food"),
  box(8, "impact", "Fewer children living with obesity at age 10 to 11"),
  box(9, "failure_outcome", "Brands shift spend to brand ads and influencers", { origin: "found_in_evidence" }),
  box(10, "failure_outcome", "Children's exposure barely falls", { origin: "found_in_evidence" }),
];

function link(
  n: number,
  source: number,
  target: number,
  type: string,
  elsewhere: Grade,
  here: Grade,
  extra: Partial<TocLink> = {},
): TocLink {
  const rank = { strong: 3, medium: 2, weak: 1, none: 0 };
  return {
    link_id: linkId(n),
    source_box_id: boxId(source),
    target_box_id: boxId(target),
    sentence: `Link ${n} says the step works.`,
    if_text: `if step ${source}`,
    for_text: "children aged 4 to 15 in England",
    then_text: `then step ${target}`,
    because_text: `reason ${n}`,
    conditions: [`Condition for link ${n}`],
    assumption_type: type,
    critical: false,
    origin: "drafted",
    revision: 1,
    state: "checked",
    elsewhere: { grade: elsewhere, supports: 1, against: 0 },
    here: { grade: here, supports: 1, against: 0 },
    lower_grade: rank[here] < rank[elsewhere] ? here : elsewhere,
    elsewhere_sentence: `Elsewhere evidence for link ${n}.`,
    here_sentence: `Here evidence for link ${n}.`,
    merged: false,
    ...extra,
  };
}

export const LINKS: TocLink[] = [
  link(1, 1, 3, "delivery", "strong", "medium"),
  link(2, 2, 4, "delivery", "weak", "none"),
  link(3, 3, 5, "take-up", "medium", "weak", {
    critical: true,
    conditions: ["Brands do not move their spend to brand-only ads, sponsorship and influencers"],
  }),
  link(4, 5, 6, "behaviour change", "strong", "weak", { conditions: ["The effect seen in short trials lasts in everyday life"] }),
  link(5, 6, 7, "behaviour change", "medium", "weak"),
  link(6, 4, 7, "take-up", "medium", "medium", { merged: true, here_sentence: null }),
  link(7, 7, 8, "benefits and side effects", "medium", "weak"),
  link(8, 3, 9, "if it goes wrong", "medium", "weak"),
  link(9, 9, 10, "if it goes wrong", "none", "none", { state: "checking" as LinkState }),
];

const pathway = (
  n: number,
  kind: TocPathway["kind"],
  label: string,
  links: number[],
  extra: Partial<TocPathway> = {},
): TocPathway => ({
  pathway_id: pathwayId(n),
  kind,
  status: "kept",
  label,
  reason: null,
  origin: "drafted",
  link_ids: links.map(linkId),
  broken: false,
  ...extra,
});

export const PATHWAYS: TocPathway[] = [
  pathway(1, "success", "Fewer ads, healthier choices", [1, 3, 4, 5, 7]),
  pathway(2, "success", "Reformulation", [2, 6, 7]),
  pathway(3, "failure", "Spend moves elsewhere", [1, 8, 9]),
  pathway(4, "success", "Children ask parents less", [], {
    status: "set_aside",
    reason: "Merged into pathway 1, because it is the same step as healthier choices.",
  }),
];

export function tocGraphFixture(overrides: Partial<TocGraph> = {}): TocGraph {
  return {
    task_id: TASK_ID,
    check_status: "checked",
    boxes: BOXES,
    links: LINKS,
    pathways: PATHWAYS,
    context: ["Rules in force since January 2026.", "Children's viewing is moving to YouTube and TikTok."],
    supporting_activities: ["Ofcom monitoring", "Industry guidance on nutrient profiling"],
    summary: {
      about: "How restricting ads for less healthy food could mean fewer children living with obesity.",
      evidence_says: "Most steps worked where they were tried, but few have been shown to hold in England.",
      evaluation_questions: ["Did children's exposure fall across all channels?", "Are the calories cut made up from other food?"],
    },
    grade_rules: [
      { label: "Strong", rule: "two or more good studies support it, and none of that quality challenges it." },
      { label: "Medium", rule: "at least one fair study supports it." },
      { label: "Weak", rule: "only poor support, or the challenges outweigh the support." },
      { label: "No evidence found", rule: "the search ran and found nothing on it." },
    ],
    links_left_out: 0,
    ...overrides,
  };
}

function doc(n: number, title: string, elsewhere: TocDocument["elsewhere"], here: TocDocument["here"]): TocDocument {
  return {
    task_source_snapshot_id: docId(n),
    evidence_id: `00000000-0000-4000-8000-0000000e${String(n).padStart(4, "0")}`,
    authors: ["Smith", "Jones"],
    title,
    year: 2020 + (n % 5),
    url: `https://example.org/doc-${n}`,
    source_type: "academic",
    evidence_type: "quasi-experiment",
    appraisal_score: 3,
    elsewhere,
    here,
    condition: null,
    previous_wording: false,
  };
}

/** The TfL study answers both questions on L3: listed once, with both quotes. */
export const SHARED_DOC_TITLE = "Household purchases after the Transport for London advertising restriction";

export function tocEvidenceFixture(): TocEvidence {
  const boxes: TocBoxEvidence[] = [
    {
      box_id: boxId(7),
      case_studies: [
        {
          task_source_snapshot_id: docId(9),
          programme: "Transport for London advertising restriction",
          place: "London",
          note: "Weekly calories fell against a comparison area.",
          quote: "Calories bought fell by about 7%.",
          title: "TfL restriction study",
          year: 2022,
          url: "https://example.org/tfl",
          source_type: "academic",
        },
      ],
      indicators: ["Calories bought per household per week"],
    },
  ];
  return {
    links: [
      {
        link_id: linkId(3),
        documents: [
          doc(1, "Children's exposure after Chile's Law 20.606", { stance: "supports", quote: "Exposure fell by about half." }, { stance: "not_about", quote: null }),
          doc(2, SHARED_DOC_TITLE, { stance: "supports", quote: "Ads fell to almost none." }, { stance: "supports", quote: "This is England, so it counts here." }),
          doc(3, "Food brand advertising after Chile's restrictions", { stance: "not_about", quote: null }, { stance: "challenges", quote: "Companies moved to brand-only advertising." }),
        ],
      },
      { link_id: linkId(1), documents: [doc(4, "Ofcom review of TV rules", { stance: "supports", quote: "Broadcasters blocked most ads." }, { stance: "supports", quote: "UK TV." })] },
    ],
    boxes,
  };
}
