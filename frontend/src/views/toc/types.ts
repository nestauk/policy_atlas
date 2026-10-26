// Mirrors backend api/contract/toc.py; replace with generated types after make openapi-sync.

export type Grade = "strong" | "medium" | "weak" | "none";
export type LinkState = "unchecked" | "checking" | "checked" | "pending" | "kept" | "no_change";
export type Origin = "drafted" | "found_in_evidence" | "imported" | "user" | "options_scoping";
export type CheckStatus = "none" | "drafting" | "checking" | "checked" | "failed";
export type Stance = "supports" | "challenges" | "not_about";
export type BoxLayer = "input" | "output" | "outcome" | "impact" | "failure_outcome";
export type SourceType = "academic" | "policy" | "web";

export interface TocResultCriteria {
  definition: string | null;
  indicator: string | null;
  timing: string | null;
}

export interface TocBox {
  box_id: string;
  layer: BoxLayer;
  text: string;
  dosage: string | null;
  result_criteria: TocResultCriteria;
  description: string | null;
  origin: Origin;
  revision: number;
}

export interface TocGrade {
  grade: Grade;
  against: number;
  supports: number;
}

export interface TocLink {
  link_id: string;
  source_box_id: string;
  target_box_id: string;
  sentence: string;
  if_text: string;
  for_text: string;
  then_text: string;
  because_text: string;
  conditions: string[];
  assumption_type: string;
  critical: boolean;
  origin: Origin;
  revision: number;
  state: LinkState;
  elsewhere: TocGrade;
  here: TocGrade;
  lower_grade: Grade;
  elsewhere_sentence: string | null;
  here_sentence: string | null;
  merged: boolean;
}

export interface TocPathway {
  pathway_id: string;
  kind: "success" | "failure";
  status: "kept" | "set_aside";
  label: string;
  reason: string | null;
  origin: Origin;
  link_ids: string[];
  broken: boolean;
}

export interface TocSummary {
  about: string;
  evidence_says: string;
  evaluation_questions: string[];
}

export interface TocGradeRule {
  label: string;
  rule: string;
}

export interface TocGraph {
  task_id: string;
  check_status: CheckStatus;
  boxes: TocBox[];
  links: TocLink[];
  pathways: TocPathway[];
  context: string[];
  supporting_activities: string[];
  summary: TocSummary | null;
  grade_rules: TocGradeRule[];
  links_left_out: number;
}

export interface TocStance {
  stance: Stance;
  quote: string | null;
}

export interface TocDocument {
  task_source_snapshot_id: string;
  title: string;
  year: number | null;
  url: string | null;
  source_type: SourceType;
  evidence_type: string | null;
  appraisal_score: number | null;
  elsewhere: TocStance;
  here: TocStance;
  condition: string | null;
  previous_wording: boolean;
}

export interface TocLinkEvidence {
  link_id: string;
  documents: TocDocument[];
}

export interface TocCaseStudy {
  task_source_snapshot_id: string;
  programme: string;
  place: string | null;
  note: string;
  quote: string;
  title: string;
  year: number | null;
  url: string | null;
  source_type: SourceType;
}

export interface TocBoxEvidence {
  box_id: string;
  case_studies: TocCaseStudy[];
  indicators: string[];
}

export interface TocEvidence {
  links: TocLinkEvidence[];
  boxes: TocBoxEvidence[];
}
