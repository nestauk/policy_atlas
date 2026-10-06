Let me check my understanding of the pipeline.

The steps are, in order:

1. The Planner reformulates the user's query and determines what steps the pipeline will take (within constraints). Input: raw query. Output: user intent; a Plan
2. ACQUIRE. User intent gets turned into OpenAlex and Overton queries. These are run, the results merged and deduplicated, and the top results are kept.
3. SCREEN. The title + abstract are screened for relevance. Three LLM calls and 2 votes = a win. **The following steps only apply to articles that pass this step**
4. CLASSIFY. A LLM determines the type of study, e.g. expert opinion, RCT, systematic review etc.
5. APPRAISE. Based on the results of CLASSIFY, an evidence strength score from 1-5 is assigned.
6. INGEST. The full text of every article that passed step 4 is ingested.
7. SCREEN FULL. This is a repeat of step 4, but using full text??
8. CHARACTERISE. A LLM groups the articles into a set of themes - kind of LLM-driven topic modelling.
9. SELECT. For the synthesis, a representative set of articles from each theme is selected.
10. EXTRACT. Structured info is extracted **only from the documents selected at the SELECT step**. There are two **finding vetter** judges that check the findings.
11. GROUP. The sections of the synthesis and the texts/claims that underpin them are determined.
12. SYNTHESISE. The final report is written. There is a **grounding judge** that checks each claim against the source.

Rapid:
Steps 1-6
8
12

Standard:
Steps 1-9
12

Detailed:
All 12 steps