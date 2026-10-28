import type {
  LinkState,
  TocBox,
  TocBoxEvidence,
  TocDocument,
  TocEvidence,
  TocGraph,
  TocLink,
  TocPathway,
  Verdict,
} from "./types";

/*
 * A realistic theory of change for tests, from the wireframe example: the
 * obesity option "Restrictions on unhealthy food advertising to children".
 * Two success pathways, one failure pathway, one set-aside pathway; nine
 * links with every verdict and state, one critical link (#3, close to the
 * threshold), and three documents on #3: two support it, one refutes it.
 */

export const TASK_ID = "11111111-1111-4111-8111-111111111111";
const id = (kind: string, n: number) => `${kind}0000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const boxId = (n: number) => id("b", n);
export const linkId = (n: number) => id("c", n);
export const pathwayId = (n: number) => id("d", n);
export const docId = (n: number) => id("e", n);

const PREFIX: Record<TocBox["layer"], string> = {
  input: "A",
  output: "P",
  outcome_short: "S",
  outcome_long: "L",
  impact: "I",
  failure_outcome: "F",
};
const used: Partial<Record<TocBox["layer"], number>> = {};

function box(n: number, layer: TocBox["layer"], text: string, extra: Partial<TocBox> = {}): TocBox {
  used[layer] = (used[layer] ?? 0) + 1;
  return {
    box_id: boxId(n),
    layer,
    code: `${PREFIX[layer]}${used[layer]}`,
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
  box(5, "outcome_short", "Children see fewer ads for less healthy food"),
  box(6, "outcome_short", "Children ask for and pick healthier food"),
  box(7, "outcome_long", "Households buy fewer calories from less healthy food"),
  box(8, "impact", "Fewer children living with obesity at age 10 to 11"),
  box(9, "failure_outcome", "Brands shift spend to brand ads and influencers", { origin: "found_in_evidence" }),
  box(10, "failure_outcome", "Children's exposure barely falls", { origin: "found_in_evidence" }),
];

function link(n: number, source: number, target: number, type: string, verdict: Verdict, extra: Partial<TocLink> = {}): TocLink {
  return {
    link_id: linkId(n),
    code: `#${n}`,
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
    verdict,
    near_threshold: false,
    weights: { total_weight: 1.2, mean_support: 1.1, refute_share: 0, n_documents: 2 },
    evidence_sentence: `Evidence sentence for link ${n}.`,
    ...extra,
  };
}

export const LINKS: TocLink[] = [
  link(1, 1, 3, "delivery", "confident"),
  link(2, 2, 4, "delivery", "not_sure_insufficient", { evidence_sentence: "No evidence was found in the documents read." }),
  link(3, 3, 5, "take-up", "not_sure_mixed", {
    critical: true,
    near_threshold: true,
    conditions: ["Brands do not move their spend to brand-only ads, sponsorship and influencers"],
    evidence_sentence: "Exposure fell under Chile's rules and on London transport, but brands moved to brand-only adverts.",
  }),
  link(4, 5, 6, "behaviour change", "confident", { conditions: ["The effect seen in short trials lasts in everyday life"] }),
  link(5, 6, 7, "behaviour change", "not_sure_mixed"),
  link(6, 4, 6, "take-up", "confident"),
  link(7, 7, 8, "benefits and side effects", "not_confident"),
  link(8, 3, 9, "if it goes wrong", "not_sure_mixed"),
  link(9, 9, 10, "if it goes wrong", "not_sure_insufficient", { state: "checking" as LinkState }),
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
  pathway(2, "success", "Reformulation", [2, 6, 5, 7]),
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
      { label: "Confident", rule: "enough evidence, and on average it supports the step." },
      { label: "Not sure: mixed", rule: "enough evidence, but it neither clearly supports nor refutes the step." },
      { label: "Not sure: too little evidence", rule: "the documents add up to less than one strong, relevant study." },
      { label: "Not confident: evidence against", rule: "enough evidence, and on average it is against the step." },
    ],
    confidence: "not_sure_mixed",
    links_left_out: 0,
    ...overrides,
  };
}

function doc(n: number, title: string, support: TocDocument["support"], quote: string, quality: number, relevance: number, reason: string): TocDocument {
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
    support,
    quote,
    relevance,
    relevance_reason: reason,
    quality,
    weight: Math.round(((quality * relevance) / 9) * 1000) / 1000,
    condition: null,
    previous_wording: false,
  };
}

/** The heaviest document on #3: the London study, in England. */
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
          doc(1, "Children's exposure after Chile's Law 20.606", "strong", "Exposure fell by about half.", 2, 1, "Chile, a different country and media market"),
          doc(2, SHARED_DOC_TITLE, "strong", "Ads fell to almost none.", 2, 3, "London, so it applies in England"),
          doc(3, "Food brand advertising after Chile's restrictions", "refutes", "Companies moved to brand-only advertising.", 2, 2, "Chile, similar advertisers"),
        ],
      },
      { link_id: linkId(1), documents: [doc(4, "Ofcom review of TV rules", "weak", "Broadcasters blocked most ads.", 3, 3, "UK television")] },
    ],
    boxes,
  };
}
