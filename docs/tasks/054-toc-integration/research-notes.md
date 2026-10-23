# Task 054 — research notes (2026-10-23)

Background research for the theory of change spec
(`docs/specs/capabilities/theory-of-change/`). Three questions: what the guidance says, which
datasets could support evals, and whether imports and exports fit the infrastructure. Quotes
were read from the PDFs unless marked *summarised* (read through a fetch tool, not in full).

## 1. What the guidance says

Sources:
- Magenta Book 2026 (HM Treasury, updated 15 May 2026, 160 pages):
  https://assets.publishing.service.gov.uk/media/6a3157a0141f0690ad5fa438/CCS0126982978-001_PN10541411_Magenta_Book_Update_V2_Accessible_2__1_.pdf
- Magenta Book Annex A 2026:
  https://assets.publishing.service.gov.uk/media/6a049bf75f39105e0848a21e/CCS0126982978-004_PN10640792_Magenta_Book_Annex_A_WEB_ACCESSIBLE__4_.pdf
- Handling Complexity supplementary guide:
  https://assets.publishing.service.gov.uk/media/5e96c98ed3bf7f412d7f7bb0/Magenta_Book_supplementary_guide._Handling_Complexity_in_policy_evaluation.pdf
- Mayne 2015, "Useful Theory of Change Models", CJPE 30.2: https://ces.journals.uvic.ca/index.php/cjpe/article/download/529/468
- Mayne 2017, "Theory of change analysis: building robust theories of change", CJPE 32.2: https://ces.journals.uvic.ca/index.php/cjpe/article/download/408/350
- Vogel 2012, DFID review of theory of change use: https://assets.publishing.service.gov.uk/media/57a08a5ded915d3cfd00071a/DFID_ToC_Review_VogelV7.pdf

**Layers.** Magenta Book Figure 2.2 (p.46, "based on Mayne 2017") has four columns:
Inputs ("the resources committed and activities undertaken"), Outputs ("what is delivered or
produced"), Outcomes ("the early or medium term results"), Impact ("the long term results").
The Government Analysis Function toolkit (*summarised*) splits Activities from Inputs and allows
short- and medium-term outcomes.

**Assumptions.** Figure 2.2 puts a row of assumption boxes under the chain, one per stage
change: "Assumptions around the individuals who take up the intervention" (outputs to
outcomes), "…the early changes in behaviour brought about by the intervention" (within
outcomes), "…the benefits produced and possible unintended effects" (outcomes to impact). Two
full-width bands frame the chain: "Contextual factors and external influencers" and "Supporting
activities to help bring about the changes (assumptions) required". Mayne 2015 (pp.124–125):
"Only when we add the assumptions to the causal links in the impact pathway do we get a theory
of change." He names five link types (reach, capacity change, behaviour change, direct
benefits, well-being change). Vogel 2012 (p.35): "links and arrows are labelled with key
assumptions", and (on logframes) the assumptions column became "a 'too hard' column".

Visual patterns found: (1) a band of assumption boxes under the chain, one per stage change;
(2) numbered labels on the arrows with a separate list; (3) an assumptions column (criticised);
(4) typed, colour-coded assumptions; (5) a context band kept apart from link assumptions.

**Evidence strength.** The Magenta Book asks for "the strength or weakness of the evidence
supporting these assumptions" (p.44) but defines **no rating scale**. Mayne 2017 (pp.162–165)
asks for each link "the strength or current status of evidence", "classified as strong,
medium, or weak". No source cleanly separates "no evidence", "evidence against" and "mixed".
Nearest wording: Foundations (*summarised*): "mixed findings i.e., studies suggesting positive
impact alongside studies, which on balance, indicate no effect or negative impact"; Mayne 2015
(p.133): evidence "weak or not existing".

**Evidence for boxes.** Mayne 2017 Table 1 gives criteria for each result box: well-defined,
plausible timing, logical coherence, and "Measurable — … How can the results be measured?
What is the likely strength or status of evidence for the result being realized?". The Magenta
Book asks for indicators "at each stage of the Theory of Change" (Figure 4.1, p.103). Neither
asks for a literature search per box.

**Failure and alternatives.** Magenta Book p.47: "explore the negative programme theory – all
the reasons why the causal steps might not happen in practice and why the desired outcome is
likely not to occur." p.60: include "alternative theories of how the outcome could come
about". Mayne 2017 p.162: "if you have more than 13 result 'boxes,' you may have a mess instead
of a ToC". Unintended effects sit in Figure 2.2's last assumption box.

## 2. Datasets and prior work for evals

**No public machine-readable dataset of real theories of change exists.** They are figures in
PDFs. Usable sources for hand-built reference sets: Youth Endowment Fund feasibility and trial
reports (logic model plus intervention text); GOV.UK evaluation plans (Open Government Licence);
Campbell systematic reviews (logic model figures; licence to check per article); FCDO business
cases (via DevTracker); 3ie reports; USAID evaluations archived by AidData. EEF and 3ie licences
not checked.

**No paper evaluates LLM-made theories of change against human ones.** Nearest work:
- Giabbanelli & Witkowicz, HICSS 2024: GPT causal maps from policy text; nodes good, edge
  direction sometimes reversed. Score direction separately.
- "Soft measures for extracting causal collective intelligence" (arXiv 2409.18911): soft F1 for
  graph comparison when the same idea is worded differently.
- System Dynamics Conference 2026 abstract 1250: sample many diagrams, score link stability.
- Evidence-ablation fact-checking (arXiv 2609.08943): remove the evidence, check the verdict
  changes.

**Stance datasets read at abstract level** (all biomedical; none has a "conditional" label):
SciFact (CC-BY 4.0), SciFact-Open, HealthVer, Check-COVID, PubMedQA, Evidence Inference 2.0
(intervention, comparator, outcome prompts; the closest match to a link).

**Image to graph:** FlowVQA (2,272 flowcharts with Mermaid ground truth), FlowLearn (simulated
part has ground truth). None are theories of change.

## 3. Feasibility in this repo

- **Image and PDF import.** No upload endpoint, storage or vision call exists today. The GPT-5.6
  models accept images on both model routes (AWS model card for GPT-5.6 Sol). Minimal design:
  the file as base64 in a JSON request, PDF pages rasterised with `pymupdf` (already a
  dependency), sent as image parts through the existing `chat.completions.parse` path, nothing
  stored. `docs/deferred.md` "Upload audit-event seam" asks for an audit event and a trace span.
  A one-call smoke test per route is still needed.
- **Web search.** None today. OpenAI's hosted web search works on the OpenAI route. On Bedrock,
  the `bedrock-runtime` endpoint (and so every global profile) does not support server-side
  tools; only `bedrock-mantle` offers hosted web search, in-region in us-east-1 and us-east-2
  only (AWS model card for GPT-5.6 Sol; OpenAI's Bedrock guide; checked 2026-10-23). A search API (Brave about $5 per 1,000
  queries; Exa about $7 per 1,000 with page text; prices from third-party summaries) works on
  both routes. Open-web search is a deferred seam that the specs say needs injection screening
  (`docs/specs/system/execution-orchestration.md`, `docs/deferred.md`), so it needs an ADR.
- **Slides.** `python-pptx` (new dependency) makes native boxes with attached connectors,
  editable in PowerPoint; arrowheads need a small XML addition. Whether Google Slides keeps
  connectors on import is **not verified**; test by hand first. Google Slides API needs OAuth;
  not recommended.
- **Miro.** The Miro REST API supports shapes and connectors but needs an OAuth app and per-user
  tokens. Miro, Lucidchart and diagrams.net all import **draw.io XML**, which the standard
  library can write. Use draw.io XML first.
- **Canvas.** React Flow (`@xyflow/react`, MIT licence) with `html-to-image` pinned to 1.11.11
  for PNG export. Neither is installed. The repo's `triggerTextDownload` helper covers text
  downloads.
