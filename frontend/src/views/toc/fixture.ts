import type {
  LinkState,
  TocBox,
  TocBoxEvidence,
  TocDocument,
  TocEvidence,
  TocFigure,
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
    seen_in: null,
    seen_in_cites: [],
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
  box(7, "outcome_long", "Households buy fewer calories from less healthy food", {
    seen_in: "Seen on London transport after its 2019 advertising restriction.",
    seen_in_cites: [docId(9)],
  }),
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
    title: `Link ${n} title`,
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
    evidence_cites: [],
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
    evidence_cites: [docId(1), docId(2)],
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
    grade_rules: [
      { label: "Confident", rule: "enough evidence, and on average it supports the step." },
      { label: "Mixed", rule: "enough evidence, but it neither clearly supports nor refutes the step." },
      { label: "Not enough evidence", rule: "the documents add up to less than one strong, relevant study." },
      { label: "Not confident: evidence against", rule: "enough evidence, and on average it is against the step." },
    ],
    confidence: "not_sure_mixed",
    report: {
      title: "Food advert limits and childhood obesity",
      summary_text: "Removing adverts should cut snacking, but whether children see fewer adverts overall is the weakest step.",
      summary: {
        goal: "Fewer children in England living with obesity within five years",
        if_then_because:
          "If adverts for less healthy food are removed before 9pm, then children will see fewer of them and eat fewer snacks, because food adverts prompt eating.",
        population: "children under 18 in England",
        time_horizon: "five years",
        directly_influenced: "outputs",
        context: "Children watch most television outside children's programmes.",
        weakest_links: "Whether fewer covered adverts mean children see fewer adverts overall (#3: not sure, mixed).",
      },
      pathways: [
        { title: "Fewer adverts, less snacking", paragraph: "Removing covered adverts (A1 → P1) should cut children's exposure (S1) [1][2]." },
        { title: "How it could fail", paragraph: "Advertising may move to spaces the rules do not cover (F1) [3]." },
      ],
      assumptions: [
        {
          code: "#3",
          statement: "Brands do not move their spend to brand-only ads",
          kind: "assumption",
          verdict: "Mixed",
          why: "Chile cut exposure; brands moved to brand-only ads",
          sources: [1, 3],
        },
        { code: "F1", statement: "Marketing moves to unrestricted spaces", kind: "risk", verdict: "Mixed", why: "Seen after Chile's rules", sources: [3] },
      ],
      tests: [
        {
          link: "#3",
          question: "Do children see fewer less healthy food adverts overall?",
          indicator: "Children's impacts per week (BARB)",
          test_and_learn: "Compare exposure before and after January 2026",
        },
      ],
      sources: [
        { n: 1, authors: ["Ann Smith", "Bo Lee"], year: 2020, venue: "Obesity Reviews", citation: "Smith et al. (2020) Children's exposure after Chile's Law 20.606. Obesity Reviews.", url: "https://example.org/doc-1", title: "Source 1", evidence_id: "00000000-0000-4000-8000-0000000e0001", quote: "Exposure fell by about half." },
        { n: 2, authors: ["Ann Smith", "Bo Lee"], year: 2020, venue: "Obesity Reviews", citation: "Smith et al. (2022) Household purchases after the TfL restriction.", url: null, title: "Source 2", evidence_id: "00000000-0000-4000-8000-0000000e0002", quote: "Exposure fell by about half." },
        { n: 3, authors: ["Ann Smith", "Bo Lee"], year: 2020, venue: "Obesity Reviews", citation: "Smith et al. (2023) Food brand advertising after Chile's restrictions.", url: null, title: "Source 3", evidence_id: "00000000-0000-4000-8000-0000000e0003", quote: "Exposure fell by about half." },
      ],
      method:
        "Generated by Policy Atlas with AI on 28 October 2026 from OpenAlex and Overton searches for each step; evidence judged by gpt-6.1-terra; not yet reviewed by a person. 'Too little evidence' means none was found in this search, not that none exists.",
    },
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

function figure(n: number, doc: number, measure: string, value: number, extra: Partial<TocFigure> = {}): TocFigure {
  return {
    figure_id: `00000000-0000-4000-8000-0000000f${String(n).padStart(4, "0")}`,
    box: "link",
    measure,
    value_text: String(value),
    value,
    ci_lower_text: null,
    ci_lower: null,
    ci_upper_text: null,
    ci_upper: null,
    unit: "%",
    effect_size_type: "relative_change",
    population: "children",
    place: null,
    year: null,
    n: null,
    k: null,
    quote: `Exposure fell ${value}% after the rules.`,
    statement: `Children saw ${value}% fewer adverts for less healthy food after the rules.`,
    evidence_id: `00000000-0000-4000-8000-0000000e${String(doc).padStart(4, "0")}`,
    task_source_snapshot_id: docId(doc),
    source_title: `Study ${doc}`,
    source_authors: ["Smith", "Jones"],
    source_year: 2020,
    source_venue: "Obesity Reviews",
    source_type: "academic",
    evidence_type: "quasi-experiment",
    url: null,
    ...extra,
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
          evidence_id: "00000000-0000-4000-8000-0000000e0009",
          task_source_snapshot_id: docId(9),
          authors: ["Transport for London"],
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
      figures: [
        figure(4, 9, "excess calories a day eaten by children", 140, {
          box: "target",
          unit: "kcal",
          effect_size_type: "level",
          quote: "children overall eat 140 excess kcal per day",
          source_authors: [],
          source_type: "policy",
          source_venue: "Public Health England",
          evidence_type: "government evidence review",
        }),
      ],
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
        figures: [
          // Two studies, the same measure: one line with the range.
          figure(1, 1, "fewer adverts for less healthy food seen by children", 44),
          figure(2, 2, "Fewer adverts for less healthy food seen by children.", 58),
          // One number with its range.
          figure(3, 2, "odds of children's exposure, no change", 1.05, {
            value_text: "1·05",
            unit: null,
            effect_size_type: "ratio",
            ci_lower_text: "0·99",
            ci_lower: 0.99,
            ci_upper_text: "1·12",
            ci_upper: 1.12,
            quote: "odds ratio 1·05 (0·99 to 1·12)",
          }),
        ],
      },
      { link_id: linkId(1), documents: [doc(4, "Ofcom review of TV rules", "weak", "Broadcasters blocked most ads.", 3, 3, "UK television")], figures: [] },
    ],
    boxes,
  };
}
