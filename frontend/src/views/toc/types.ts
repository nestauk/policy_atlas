// The theory-of-change read contract, re-exported from the generated OpenAPI
// types (backend api/contract/toc.py; `make openapi-sync` regenerates them).
import type { components } from "../../api/gen/types";

type Schemas = components["schemas"];

export type TocResultCriteria = Schemas["TocResultCriteriaOut"];
export type TocBox = Schemas["TocBoxOut"];
export type TocWeights = Schemas["TocWeightsOut"];
export type TocLink = Schemas["TocLinkOut"];
export type TocPathway = Schemas["TocPathwayOut"];
export type TocSummary = Schemas["TocSummaryOut"];
export type TocGradeRule = Schemas["TocGradeRuleOut"];
export type TocGraph = Schemas["TocGraphOut"];
export type TocDocument = Schemas["TocDocumentOut"];
export type TocLinkEvidence = Schemas["TocLinkEvidenceOut"];
export type TocCaseStudy = Schemas["TocCaseStudyOut"];
export type TocBoxEvidence = Schemas["TocBoxEvidenceOut"];
export type TocEvidence = Schemas["TocEvidenceOut"];

export type Verdict = TocLink["verdict"];
export type LinkState = TocLink["state"];
export type Origin = TocBox["origin"];
export type CheckStatus = TocGraph["check_status"];
export type Support = TocDocument["support"];
export type BoxLayer = TocBox["layer"];
export type SourceType = TocDocument["source_type"];
