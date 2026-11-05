# Design annex: 058-perceived-latency

The lead's script for this slice: every state, transition and line of copy the build must
produce. The contract cites this file by version; looks live here, not in the contract.
Owner feedback rounds (mock and polish) edit this file first, then the mock or the app.
Voice: a short label, then one plain sentence; no mannered prose.

> **Version:** 5 (2026-11-04; v5 corrects the round copy after the deferred-list scan; v1 = the frozen mock script; v2 and v3 added the contract-gate rulings as notes; v4 folds them into the scenes and removes the superseded text, per the contract-stage review) · Mock: https://claude.ai/artifact/Xse3bLcA6XhQqxQJFVEwtH
> version 7, fifteen scenes; source `research/mock-v7.html` · Frozen: 2026-11-04 (the owner:
> "broadly looks okay", more judgement expected on the live app) · Polish rounds: log at the
> end.

The body below is the mock script as it stood when the mock was frozen. Section names follow
the script; the template's "Surfaces and states" are the running card section, the block
rules and the scenes.

---

# Task 058 mock script (lead design annex, 2026-11-04)

Published mock: https://claude.ai/artifact/Xse3bLcA6XhQqxQJFVEwtH (private; scenes `#scene-1` to `#scene-8`). Owner feedback on the mock is applied here first, then to the page.

What the interactive mock shows, scene by scene, with the exact copy and states. The builder constructs the page from this; the lead owns every word and state here. Source of the current look: `frontend/src/index.css` (tokens), `frontend/src/views/workspace/RunningCard.tsx`, `frontend/src/views/workspace/runProgress.ts`, `frontend/src/ui/brand/LifecycleBar.tsx`, `frontend/src/views/ArtefactView.tsx` (`LiveArtefactBody`), `frontend/src/views/TaskListRow.tsx`, `frontend/src/ui/feedback/ReconnectingBanner.tsx`.

## Voice rules (owner, 2026-11-04)
Short label, then one plain sentence. No sentence fragments for effect, no triads, no flourishes. Counts only where the total is known before the loop; otherwise "so far". Elapsed time only; never a countdown or a percent. Nothing animates unless real data is arriving.

## Fixed example run (same data in every scene)
Question: "What works to raise take-up of free childcare places among low-income families?"
Evidence search, standard effort, standard depth. Stages in order with the plan-panel labels: Searching, Screening, Sorting by evidence type, Appraising, Reading the full texts, Mapping, Shortlisting, Writing.
Counts: 312 sources found over 2 search rounds; 435 abstracts checked (second looks included); 118 relevant; 118 sorted; 118 appraised; 38 read in full; 7 themes; 24 shortlisted; 7 report sections.
Section titles (report order): Key findings (written last, shown first); 1 Why take-up matters; 2 Who is missing out; 3 Costs and funding; 4 Information and outreach; 5 Administrative burden; 6 Supply and local capacity; 7 Conclusions.

## Owner feedback round 1 (2026-11-04) and the lead's answers
1. Card clean-up; rounds produced repeated Searching / Screening rows. → One merged row "Searching and screening"; round detail in the activity line. Completed rows are one-liners with the key count and a link; upcoming rows are names only; the duplicate card title goes.
2. Better navigation between the Agent tab and the task. → Every finished row links to its output; the Result tab carries the run strip with "Follow in the Agent tab →"; signposts stay.
3. Stall counter is noisy for short pauses. → No counter. Short pauses show nothing. After 2 minutes of silence the action line reads "Still working on this step" (no timer, count stays). Drop entirely if the owner prefers.
4. Writing: show the section, then what it is doing in that section. → Two lines: section line persistent, action line changes under it.
5. Early Result tab needs refining. → Report-shaped page: title, run strip, landed outputs as rows. Section titles cannot appear before writing starts (the writer proposes them); moving the proposal to after Mapping is a backend option for the owner.
6. Proposed sections should display in the report with subtly pulsing lines. → At the skeleton every section shows 2 to 3 pulsing placeholder lines until its prose arrives.
7. How are the writer's tool-call turns shown in the Result tab? → The active section shows the action line ("Looking for: …") above its pulsing lines; prose replaces it when streaming starts.

## Owner feedback round 2 (2026-11-04) and the lead's answers
1. Show which claims have been sent for repair. → When the check returns, the sentences it failed get a dotted underline and a small grey "being revised" at the end; when the repair lands the text is replaced, the underline becomes a thin solid one and the word becomes "revised" with the old wording on hover or tap. Sentences that passed get nothing.
2. The "Checked" / "Writing" pills look busy and generated. → No pills anywhere. Section state is carried by one breathing dot after the heading while the section is being written or checked, and by nothing once it is done. The "Written last" note on Key findings becomes a plain grey sentence under the heading. The run strip and the signpost bubbles use words, not chips.
3. Early Result tab: the links to other tabs are redundant with the strip and vanish once writing starts. → Dropped. Early Result tab = the run strip, the question as the title, and one grey sentence: "The report's sections are set out when writing begins." Nothing else.
4. General polish: a design review with the frontend design skills, against DESIGN.md, applied to the mock.

## The running card (revised)
- Top line: dot, "RUNNING", elapsed "6 min 12 s" right-aligned in tabular figures, "Minimise" link. No second title.
- Rows, one per plan step in order. **Owner 2026-11-04: "Sorting by evidence type" is renamed "Classifying" and absorbs Appraising (a one-second deterministic step); Shortlisting has no view in the app and gets no link (the selection shows through citations and the read-in-full status).** Evidence search rows: Searching and screening; Classifying; Reading the full texts; Mapping; Shortlisting; Writing (six). Three looks:
  - Done: label in navy, then on the same line in grey the key count, then the link. Examples: "Searching and screening · 312 found · 118 relevant · Sources →"; "Classifying · 118 classified · Landscape →" (link appears once Mapping is done; before that no link); "Reading the full texts · 38 read" (no link; owner round 4: nowhere relevant to point); "Mapping · 7 themes · Landscape →"; "Shortlisting · 24 selected" (no link); "Writing · 7 sections · Report →". In-progress line for Classifying: "40 of 118 classified".
  - In progress: label in navy with the breathing dot at the right; under it the action line in grey (and, for Writing, the section line above the action line). No "In progress" word; the dot is the state.
  - Upcoming: name only, grey, smaller, no status word.
- Rules between rows stay. Row order is the plan order; Searching and screening is one row even when the search runs several rounds.

## Scenes

### 1. Agent tab · searching and screening (the activity line)
Running card as revised. Rows: "Searching and screening" in progress with the action line "searching · 184 found so far" rising to 312, then "screening 87 new abstracts · 104 relevant so far"; the 87 counts down to 0 as abstracts are checked (show "screening 61 new abstracts", "screening 23 new abstracts") and "relevant so far" rises slowly (104, 107, 112, 118). There are no rounds (task 051: one search and one screen per scope). Then the row completes as "Searching and screening · 312 found · 118 relevant · Sources →" and the next row "Classifying" becomes in progress with "40 of 118 classified". (The run's fixed figure is 118 relevant; the rounds build up to it.) Upcoming rows below as names only. Elapsed ticks.
Caption: "One row per step. The round and the counts live in the line under it."

### 2. A quiet pause
Same card during "Reading the full texts · 14 of 38 read". The count stops at 21. Nothing changes for what stands for 2 minutes (compress to 4 s at 1x): the dot stops breathing, the count stays. Then the action line becomes "Still working on this step". When updates resume the line returns to "27 of 38 read" and the dot breathes again.
Caption: "Short pauses show nothing. After two minutes the line says it is still working. No timer."

### 3. Reading the full texts
Rows up to Appraising done as one-liners. Reading the full texts in progress with "14 of 38 read", rising to 38. Then Mapping in progress with "Assigning themes · batch 1 of 3" counting up, then Shortlisting with "Ranking 118 sources · batch 1 of 5" counting up.
Caption: "Batch stages show the batch, not a fake per-item count."

### 4. Writing (the model's own words)
Writing in progress. Two lines under the label. Section line (persistent, navy-grey, slightly larger than the action line): "Section 3 of 7 · Costs and funding". Action line under it cycles, each 2 to 4 s:
1. "Looking for: evidence on subsidy uptake among low-income households" (verbatim, no quotation marks)
2. "Reading findings"
3. "Looking for: childcare cost as a barrier to take-up"
4. "Writing"
5. "Checking claims"
6. "Revising 1 claim"
Then the section line becomes "Section 4 of 7 · Information and outreach" and the action line cycles faster: "Looking for: awareness of the free childcare entitlement among eligible parents", "Reading findings", "Looking for: outreach that raised applications", "Writing", "Checking claims". The signpost bubble under the card appears when section 3 completes: "Section 3 is written. Read it in the Result tab →". Rows above Writing are done one-liners with their links.
Caption: "During writing: the section first, then what the model is doing in it."

### 5. Result tab, early in the run
Result selected. Under the tabs, the run strip (same as scene 7): "● Searching and screening · 184 found so far · 6 min", status only, its text advancing through the stages as in the Agent card. The page is the report-to-be: the question as the title, then one grey sentence: "The report's sections are set out when writing begins." Nothing else. (Round 2 feedback: the output links were redundant with the strip.)
Caption: "The Result tab is the report before it exists. The strip says where the run is."

### 6. Result tab, streaming
Run strip under the tabs: "● Writing · Section 3 of 7 · 14 min", status only. Skeleton of 8 headers in report order, each with 2 to 3 placeholder lines of varying width that pulse softly (1.6 s opacity, same as the dot) until that section's prose arrives. No pills or chips anywhere (round 2 feedback). Key findings at the top with a plain grey sentence under the heading, "Written last, after the sections are checked.", and its pulsing lines. Sections 1 and 2 are done: heading, then a short line of real prose each, no marker ("Take-up of the free entitlement is lowest among the families it was designed for." and "Lone parents and families on Universal Credit are the least likely to hold a place."). Section 3 is the active one:
- A breathing dot after the heading text (the only state signal). Under the heading, before any prose, the action line in grey, the same text as the Agent card: "Looking for: evidence on subsidy uptake among low-income households" (3 s), "Reading findings" (2 s), "Looking for: childcare cost as a barrier to take-up" (3 s), above the pulsing lines.
- Then the action line and the pulsing lines go and prose arrives in chunks of 2 to 6 words every 80 to 160 ms, plain text, no Markdown. Use this text (three short paragraphs; the builder may shorten but not change register):
  "Cost is the barrier families name most often. Across the 12 studies that asked parents directly, between a third and a half said the remaining charges for meals, hours outside the funded entitlement, or deposits stopped them taking a place. The effect is strongest for families on Universal Credit and for lone parents.
  Subsidy design matters more than its size. Where the entitlement was paid directly to the provider, take-up rose by 8 to 14 percentage points; where parents had to claim it back, the gain was under 4 points. Two studies found no effect where providers passed on higher top-up fees.
  Funding rates set below provider costs reduce the number of places offered to funded children. Three local-authority evaluations link a shortfall of 10% or more to providers capping funded hours."
- When the prose finishes, the action line returns under the heading reading "Checking claims", the dot keeps breathing, the text stays as is.
- When the check returns (3 s), the action line reads "Revising 1 claim" and the failed sentence "Two studies found no effect where providers passed on higher top-up fees." softly blurs in place (a 2 px blur and reduced opacity, eased in over 300 ms); nothing else changes and no words are added. Sentences that passed get nothing.
- When the repair lands (2 s), the blurred sentence resolves smoothly into "One study found no effect where providers passed on higher top-up fees." (cross-fade over 400 ms, the blur clearing as the new text fades in; the paragraph does not jump). No underline, no label, no popover. The dot after the heading goes, the action line goes, and citation markers [1] [2] appear on two sentences. A done section has no marker of any kind. Under reduce motion the sentence dims instead of blurring and the swap is instant. (Owner, 2026-11-04 round 3: no "revised" text post hoc; a subtle blur while fixing and a smooth update.)
- Section 4's heading then gets the breathing dot, shows the action line "Looking for: awareness of the free childcare entitlement among eligible parents" (2 s) then "Reading findings" (1.5 s) above its pulsing lines, and then streams this paragraph: "Many eligible families do not know the entitlement exists or assume they do not qualify. In the six studies that tested outreach, a letter or text message from the local authority raised applications by 5 to 9 percentage points. A home visit did more, at about ten times the cost." Then the action line "Checking claims" (2 s), then the dot and line go; no revision.
- Sections 5 to 7 then each get the dot with "Reading findings" for about a second, then the dot goes and their pulsing lines are replaced by one short grey line "Written." (the mock does not need their prose).
- Footer line after section 7: "Checking claims and attaching citations" with a breathing dot. While it shows, Key findings gets the dot after its heading and its grey sentence goes. Then the footer becomes "Report ready" in green with "Read the full report" as a button, the Key findings dot goes and two short lines appear under it: "Cost and the way the subsidy is claimed decide take-up more than its size." and "Outreach works when it comes from the local authority and names the family's own eligibility."
Caption: "Prose streams as it is written. A sentence being fixed blurs, then settles into its new wording."

### 7. Elsewhere in the app
Three panels:
- Sources tab with the lifecycle bar. Under the tabs the run strip: "● Writing · Section 4 of 7 · 14 min", status only, no link and no mark. When the run finishes it becomes "Report ready · Read it →" in green, the one link it ever carries.
- A browser tab strip mock showing the title change from "Childcare take-up · Policy Atlas" to "● Report ready · Policy Atlas".
- Task list row: status dot, "Writing · Section 4 of 7 · 14 min" instead of "Analysing the evidence…", then "Complete" with the green dot.
Caption: "The run is visible from every tab, and you are told when it finishes."

### 8. Re-run and reconnect
- Result tab with an existing report and one plain line above it: "This report is from 3 November. A new run started 2 min ago." (The strip above reads "Searching and screening · 112 found so far · 2 min".) No button: the strip above it carries the stage, and the sidebar rail and the Agent tab are the routes to the run.

## Design review round 2 (lead decisions, 2026-11-04)
Review note: `design-review-round2.md`. Card directions A (tinted, refined), B (paper ledger, recommended), C (step spine) are in the mock behind a "Card: A | B | C" control; the owner chooses. Accepted from the review: paper instead of the green fill in B and C; yellow for running everywhere; counts right-aligned; no pills; repair treatment as in round 2; skeleton bars on the prose pitch; the two copy changes above. Not applied: duration band (owner: out), stop button (owner: cancel deferred), pulsing only the active section (owner asked for all proposed sections to pulse), rewriting the middot data lines as sentences (meta lines keep middots; the voice rule is about prose). For the build: the Result-tab, strip and task-row dots must stop 1.5 s after the last update like the card dot; consider a 0.5 trough for the yellow dot on white.
- The reconnecting banner (existing component, now mounted): "Reconnecting to live updates… Updates may be stale." shown for 3 s then gone.
Caption: "An old report is never mistaken for the new one. A dropped connection says so."

### 9. Options Scoping run (added after round 2; owner: scoping is in scope)
Agent tab, a scoping task "Reducing youth unemployment" (capability label "Options scoping"). Same card design as the chosen direction. Rows in the scoping plan order with the plan-panel labels: Reading the linked search (done, "1 report · Report →"), Suggesting options (done, "12 suggested"), Searching for each option (in progress), Reading the abstracts, Clustering into options, Writing what each option would take, Applying your constraints, Grouping into themes, Shortlisting (upcoming, names only). The in-progress action line: "4 of 12 searches done · 1,180 sources so far", the done count rising one at a time every 2 to 5 s with the sources figure rising in steps of 60 to 200. Then the row completes as "12 searches · 2,410 sources" and Reading the abstracts starts with "Reading 180 of 2,410 abstracts" rising. Elapsed "22 min 40 s" ticking.
Caption: "Options scoping uses the same card. The fan-out shows how many of the option searches are done."

### 10. Planning turn streaming (added after round 2; owner: block G)
Agent tab before any run. The user's question bubble, then the agent's reply appears word by word (chunks of 2 to 6 words every 80 to 160 ms), plain text: "I would search academic and policy sources for evaluations of outreach, subsidy design and provider funding, screen on relevance to low-income families in England, and read the strongest 30 to 40 in full. The report would cover who misses out, cost and funding, information and outreach, administrative burden, and local supply." Under the reply, while the rest of the turn is arriving, a grey action line with a breathing dot: "Drafting the plan". After 3 s the plan card appears below ("Evidence search · standard · ~20 to 40 min" with the "Start the search" cut-corner button) and the action line goes. Today the whole reply appears at once after 3 to 12 s with "Planning…".
Caption: "The planner's reply streams as it is written. The plan follows it."

## Blocks H, I, J (owner widened scope 2026-11-04): the planning conversation, the sidebar, navigation
Grounding: `grounding-planning-conversation.md` (27 friction points). Design rules for these scenes, all on card C and in the plain voice:
- **A real stepper.** The "Plan · 1 of 3" line is computed by the client from the parts the capability has (evidence search: Question, Scope, Thoroughness; options scoping: Question, Settings, Constraints, Depth, Risk appetite), not written by the model. It renders as one small line above the active card: "Plan · step 2 of 3 · Scope", with the settled steps named before it in grey ("Question ✓"). Friction 4.
- **One shape for a choice.** Every choice is a radio list: label, then one plain sentence. The planner's existing primary option (and a check-in's existing suggested option) sits first and its reason sits under that option, not under the list. **No "Recommended" word and no pre-selection (owner, 2026-11-04 round 4: the planner does not exercise that judgement; the mock surfaces only the primary/suggested data it already sends).** Friction 6, 14.
- **Nothing that only pre-fills.** An option that needs words ("Refine it", "Add or change a constraint", "Change") opens a short input inside the card with its own Send. The composer is for free conversation. Friction 5, 15.
- **The question is visible.** The clarifying question the model wrote is shown above its chips (the API gains the field; additive). Chips come from the stored turn, so they survive a reload. Friction 2, 3.
- **Quiet settled state.** A confirmed part collapses to one line: "Scope · Looks right · Change". No tick glyphs, no "Confirmed" word. Friction 7.
- **The plan card starts the run for both capabilities.** Evidence search: "Start the search". Options scoping: "Confirm and build the baseline". Friction 12.
- **Streaming (block G) runs through all of it.** The reply streams; "Drafting the plan" holds the place; the opening turn streams in the Agent tab instead of blocking on /new. Friction 1.
- **The sidebar is the same agent.** On any other tab the open sidebar shows the compact progress line, the thread tail, a pending check-in, and the composer locked with the same placeholder as the Agent tab. Its header reads "Task Agent" with no link (the Agent tab in the lifecycle bar is the full view); plan links open the plan document. Friction 17, 18.
- **Two routes to the agent, never three (owner, rounds 4 and 5).** On any non-Agent tab the sidebar rail's own blue diamond opens the sidebar in place, and the Agent tab is the full view. Nothing else links to the agent: the run strip is status only; the re-run notice has no button; there is no separate paused banner. While a check-in waits, the strip turns orange, "Paused · a check-in is waiting on you", and opening the sidebar from its rail lands on the check-in, which glows once; on the Agent tab the card glows in place.
- **New content marks its tab.** When a stage lands something the user has not seen (sources, the landscape, findings, a report section, the report), the lifecycle tab gets a small dot; it clears when the tab is visited. The check-in keeps its orange dot. Friction 21.
- **Plan is one click away everywhere.** A "Plan" control sits in the task nav beside the tabs and opens the plan document; Escape closes it. Friction 25.
- **One stop.** The check-in card has one "Stop the run" link, bottom right; no duplicate option. Friction 13.
- **"Go to the check-in" lands on the card.** Friction 20. Wording per capability: "The search is paused" / "The scoping is paused".
- Not in the mock, for the contract: fix the two rejected scoping parts (friction 11), align the preset and plan-document time bands (8), persist "You chose" server-side (16), render the longlist replies without asterisks (22), keep ES plan edits when leaving the tab (9), mock parts and real check-in kinds (27).

### 11. Planning conversation (block H)
Agent tab, evidence search, before any run. The question bubble. The agent's reply streams (block G): "I can search for this. First, is the question as you want it, or do you want to narrow it?" Then the stepper line "Plan · step 1 of 3 · Question" and a part card on paper (card C material: hairline, no fill):
- Title line: "Your question", then the question text as the user wrote it.
- Radio list: "That's my question" (Recommended, grey; reason under it: "It names the outcome, the group and the setting."), "Narrow it" (sentence: "Tell me what to add or leave out.").
- Choosing "That's my question" collapses the card to the line "Question · That's my question · Change" and the stepper advances. The next reply streams: "Here is the scope I would use. Change any chip, or add one." Then "Plan · step 2 of 3 · Scope" and the scope card: chips "Since 2016", "UK", "Low-income families" each with ✎ and ×, "+ add", and the radio list "Looks right" (Recommended; reason "These match your question and the usual evidence base.") and "Add or change a constraint" (sentence: "Opens a line to type the change."). Choosing the second shows an input inside the card with placeholder "What should change?" and a Send; the mock types "Exclude pre-2010 studies" and sends; a chip "Since 2010" replaces "Since 2016" and the card collapses to "Scope · Since 2010 · UK · Low-income families · Change".
- Reply streams: "How thorough should the search be?" then "Plan · step 3 of 3 · Thoroughness" with three radio options, the recommended one first as the block rule says, each with its sentence and the plan document's time band: "Standard report · ~20 to 40 min" (Recommended; "Reads the strongest sources in full."), "Rapid overview · ~10 to 15 min" ("Abstracts only. Good for a first look."), "Detailed report · ~90 to 100 min" ("Reads widely and extracts findings."). Choosing Standard collapses it to "Thoroughness · Standard report · ~20 to 40 min · Change".
- Then "Drafting the plan" with the dot for 2 s, then the plan card: "Search plan · standard · ~20 to 40 min", a quiet "Review the plan" link and the green cut-corner "Start the search".
Caption: "Three steps, one shape for every choice, and the plan starts from the card."

### 12. A check-in (block H, during a run)
Agent tab, card C with Searching and screening done ("312 found · 118 relevant · Sources →") and the run paused: the card's top line reads "PAUSED" with an orange dot and the elapsed time. Below the card, the check-in on paper with a 2px orange rule on the left:
- Title: "Does this look right before I assess the sources?" (no eyebrow; the question is the title).
- One line of facts: "312 sources · 118 relevant · 2 rounds · Sources →".
- Radio list: "Looks right, assess these" (Recommended; reason: "Coverage matches the plan and the second round added little."), "Search deeper" ("One more round on the thin themes."), "Change the search scope" ("Opens a line to say what to change."), "Guide the queries" ("Tell me what to search for.").
- Under the list, a grey disclosure "Or steer in your own words", closed. Bottom right, one grey link "Stop the run".
- Choosing the first option collapses the check-in to the line "You chose: Looks right, assess these · after searching" and the card's top line returns to "RUNNING" with Sorting by evidence type in progress.
Caption: "A check-in reads like a question. The recommended answer is first, with its reason."

### 13. The same agent in the sidebar (block I)
Sources tab at 1100 wide with the sidebar open on the right (320 px). The run strip under the tabs reads "Searching and screening · screening 61 new abstracts · 6 min", status only. The sidebar opens from the rail's diamond. In the sidebar, top to bottom: header "Task Agent"; a compact run line (dot, "Searching and screening · 6 min"); the thread tail, which is the card's current line ("Searching and screening" in navy-grey with "screening 61 new abstracts · 107 relevant so far" under it); the composer locked with the placeholder "Replanning unlocks when this run finishes." Then, at 4 s, the run pauses: the compact line becomes orange "Paused · check-in after searching" and the check-in card from scene 12 appears in the sidebar at reduced width (radio list, no facts line), answerable there. Answering returns the line to "Classifying · 40 of 118 classified · 7 min". (Aligned 2026-11-04 after the builder flagged the writing/searching mismatch.)
Caption: "The sidebar shows the same run and the same check-in. Nothing is only on the Agent tab."

### 14. Finding your way (block J)
Three panels, as in scene 7:
- The task nav with a new "Plan" control to the left of the lifecycle tabs (grey text, underline on hover). The lifecycle tabs during a run, the user on Sources: when a section lands, a small navy dot appears beside "Result"; the mock shows it appear, then the user clicks Result (the tab underlines) and the dot goes. The Agent tab shows an orange dot when a check-in is pending.
- The plan document open as a side panel (not centred) over the Result tab with the hint line "Esc closes" at its top right; the mock closes it after 3 s.
- The History tab with the run strip in its paused state: orange dot, "Paused · a check-in is waiting on you", no link. The sidebar rail's diamond opens the sidebar with the check-in in view and its orange rule briefly brighter (one 900 ms glow, honouring reduce-motion).
Caption: "New content marks its tab. The plan is one click from anywhere. Opening the sidebar lands on the check-in."

## Block K (owner 2026-11-04): the Options Scoping Result tab during the longlist build
Grounding: `grounding-scoping-result-tab.md`. What the pipeline can honestly show, and what the scene therefore does:
- The suggested options are real rows seconds in, but no read lists them before the longlist stage. Block K adds an additive read (a provisional longlist shape instead of 404, or an options list) and an `option_id` on each child run so the client can map a child search to its row. Both are public-interface additions (Tier 3, additive).
- Child searches run acquire only, so a row's line is "Searching" while its child runs and "Searched · N found" when it completes. No per-option reading or counts exist before clustering, so "Reading the abstracts" and "Clustering into options" are stage-level lines at the top of the list.
- Clustering keeps the suggested ids; a suggestion may be folded into a wider option (the row stays, marked folded) and new clustered rows may appear. Never split.
- Profiles, constraint checks and themes each land for every option in one commit, so the list fills in three waves, not row by row. The scene shows waves.
- The list carries no qualifier word: the stage line and the moving rows say it is being built. The view knows it is building because the longlist does not exist yet while a walk runs; no API flag.

### 15. The scoping Result tab during the build (block K)
Scoping task "Reducing youth unemployment", Result tab, card C elsewhere. Run strip under the tabs: "● Suggesting options · 1 min" then advancing. The page is the longlist-to-be:
- Title: "Longlist". Under it one stage line in the activity style, changing with the run: "Searching for each option · 4 of 12 done", "Reading the abstracts · 1,180 of 2,410", "Clustering into options · options may be folded together or added", "Writing what each option would take", "Applying your constraints", "Grouping into themes", "Shortlisting".
- Rows appear as soon as suggest completes (2 s): 12 rows, each a paper row with the option name, a small grey origin word ("from your report", "suggested", "added by you") and, on the right, a per-row line. Use these names: Youth guarantee with a job or training offer within four months; Wage subsidies for employers hiring under-25s; Expanded apprenticeship incentives; Careers advice in every secondary school; Sector-based work academies; Mental health support in job centres; Transport subsidies for young job seekers; Intermediate labour market programmes; Digital skills bootcamps; Youth hubs co-located with Jobcentre Plus; Enterprise allowance for young founders (added by you); Conditionality reform for under-25s (added by you).
- Per-row line while the fan-out runs: a breathing dot and "Searching" on rows whose child is running (up to 10 at once), "Searched · 312 found" when a child completes (vary the counts 140 to 410), "Queued" in grey for the two waiting. The stage line counts up "4 of 12 done" to "12 of 12".
- Then the stage line reads "Reading the abstracts · 1,180 of 2,410" rising; rows are unchanged (no per-row count yet).
- Then "Clustering into options · options may be folded together or added" with the dot; after 3 s the list changes once: "Transport subsidies for young job seekers" folds into "Youth hubs co-located with Jobcentre Plus" (the row slides under it as a grey line "Folded into Youth hubs"), and two new rows appear at the end with the origin word "found in the evidence": "Employer-led pre-apprenticeship traineeships" and "Benefit run-ons when a young person starts work". Every remaining row's right-hand line becomes a count: "38 documents", "12 documents" and so on.
- Then "Writing what each option would take" with the dot for 3 s; then, in one wave, every row gains a lever line in grey under its name (for example "Supply-side · Standard ambition"); the stage line moves to "Applying your constraints" for 2 s; then in one wave two rows move to a collapsed "Excluded · 2" group at the bottom with a one-line reason each ("Out of scope: not a youth measure"); then "Grouping into themes" for 2 s; then the rows regroup under three theme headings ("Getting into work", "Staying in work", "Advice and support") with a 300 ms rise; then "Shortlisting" for 2 s; then four rows gain a small navy "Shortlist" word, the stage line goes, and the strip reads "The longlist is ready · Read it →" in green.
- Reduce motion: no slides; each wave appears at once.
Caption: "The longlist exists from the first minute. Rows search, fold, fill and group as the build moves."

## Mock frozen (2026-11-04, version 6; scene 15 added after)
The owner accepted the mock as the direction ("broadly looks okay") and expects further judgement once the real changes are in the app. Rule for the build: the contract carries behaviours, states, interfaces and invariants from this script, not looks; a named polish loop after the build on the live app takes the owner's remaining notes, and each round's rulings are recorded here. Polish notes so far: none recorded; the owner will add them when the live app is in front of them.

## Decisions taken on the first build (lead, 2026-11-04)
- Batch stages count the batch up (1 of 3, 2 of 3, 3 of 3); they never hold one number.
- The in-progress row's label is navy; only upcoming rows are muted grey. The running dot sits beside "In progress".
- The task-list status needs room for "Writing · Section 4 of 7 · 14 min"; in the real app the column widens, and below the `md` breakpoint the row shows the short form "Writing · 14 min".
- The stall counter runs in real seconds even when the scene is compressed.

## Page controls
- Scene tabs across the top (1 to 8) with the scene names; the page opens on scene 1; a plain `#scene-3` style hash selects a scene.
- Play / Pause, Speed 1x / 4x, Restart scene, and a "Reduce motion" toggle that stops breathing dots and chunked typing (prose appears paragraph by paragraph) and also honours `prefers-reduced-motion`.
- Each scene has its one-line caption under the frame.
- The frame is a 1100 px wide app mock scaled to fit the viewport; at phone width it shows the mobile layout of the running card and the bottom tab bar instead.

## Look
Nesta palette from `index.css`: navy `#0f294a` structural text, grey `#646363` secondary, ground `#f4f4f5`, paper `#ffffff`, line `#e4e4e7`, green `#18a48c` with tint `#e7f5f2` (running card uses `#17A88D` on `#DDF2EE`), yellow `#fdb633` for running status dots, orange `#ff6e47` for paused. Radius 0 everywhere. Uppercase labels with 0.06 em tracking. Fonts: the app's Averta and Zosia are self-hosted and cannot load in the artifact; use a system sans stack and say so in a footnote. Dark theme: provide tokens, do not invert the running card's green.

---

## Rulings at the contract gate (folded into the scenes in version 4)

- Two routes to the agent, never three; the strip is status only; no paused banner; no
  button on the re-run notice (owner, 2026-11-04). Folded into the block rules and scenes 5,
  6, 7, 8, 13 and 14.
- Per-stage timings on the card: each done row carries its wall time after its count,
  before the link ("Searching and screening · 312 found · 118 relevant · 1 min 4 s · Sources
  →"); the in-progress row shows its own elapsed time in the count column; the top line keeps
  the run's total; tabular figures; no band, no estimate. Applies to every card scene.
- No label that states what the page already shows (owner, 2026-11-04): unnecessary labels,
  eyebrow text and pills are hallmarks of generated frontends. Folded into scenes 12, 13 and
  15 (no eyebrow, no "provisional"). Rule for the build and the polish passes: before adding
  any word, chip or label, ask what on the page already says it.
- No round cap (deferred-list scan, 2026-11-04): task 051 removed the round loop, so no line
  says "Round n of M"; a second search pass (a coverage steer or a retried attempt) shows as
  "Search 2" on the same row; scenes 1, 5, 8 and 13 corrected. The duplicate "Screening" row
  on staging and production is a mapping bug (`stage_for_payload`'s `screen_full` guard tests
  the wrong field); fixed in this slice, and the full-text screen shows as a line on the one
  merged row.
- The mock (version 7) predates these rulings and still shows round counts, the strip's
  diamond, the eyebrow and "provisional"; the annex, not the mock, is the authority.

## Rulings during the build (lead, 2026-11-05)

- The sidebar's header keeps its existing link to the Agent tab (the name with the expand icon); no
  second text link is added. The Agent tab is the full view, so this is not a third route.
- The paused run line in the sidebar colours the dot orange and keeps the text dark: orange text on
  white fails the contrast rule.
- The sidebar's thread tail shows the activity line only; the run line above already names the row.
- The Result tab after a run that ended before any section was proposed reads "This run ended before
  writing began." The re-run line under one minute reads "A new run started just now."
- The blur eases with the product's strong ease-out, not the mock's ease-in; the settle fades over 400 ms.
- The check-in's place in the sidebar reads "after <row label>" with the server's row label
  ("after searching and screening").

- The running card has no title line (the top line is the state word, the elapsed time and
  Minimise); "See plan" leaves the card (the Plan control is one click from anywhere).
- The strip's finish wording per walk: "Report ready", "The baseline is ready", "The longlist is
  ready", "The option's search is done", "The shortlist is proposed", each then "· Read it →", the
  whole line in green. A colleague who cannot answer a check-in sees "Paused · <row> · <elapsed>".
- Failed and skipped rows read "Stopped" and "Skipped".
- The breathing dot's lowest opacity is 0.5 (0.35 nearly vanished on white).
- The strip shows the writer's whole section line while writing; shortening it to "Section n of M"
  is a polish item for the owner pass.
- The done row's counts and nouns come on the `stage.completed` frame from the server; the client
  keeps no table.

- The longlist's stage line shows the server's activity words after the stage label
  ("Searching for each option · 4 of 12 searches done · 1,180 sources so far"; "Reading the
  abstracts · 1,180 of 2,410 abstracts read"); scene 15's shorter forms are superseded. The
  clustering note comes from the server too.
- A shortlisted row reads "Shortlist · 38 documents"; a folded row shows its name, then "Folded
  into <the parent's full name>".
- When the walk ends the built longlist view takes over (its own header, themes collapsed);
  keeping the watched rows in place and linking row names to the option card during the build
  are polish items for the owner pass.
- While paused, the longlist's stage line shows the orange dot and the stage label only.

- The check-in's question is the first line of the server's render (`runtime/steering.py`
  `CHECK_IN_QUESTIONS`, one per component: "Does this look right before I assess the sources?"
  after searching and screening, "Does the categorising look right before I read the full
  texts?", "Does the map look right before I shortlist?", "Does the shortlist look right before
  I write?"); the client never writes one.
- "Go to the check-in" has no home: the rail's diamond and the Agent tab are the two routes and
  both land on the card. No "The search is paused" line is shown anywhere.
- Plan card summary: "Search plan · Standard report · ~20 to 40 min" (the preset's label);
  scoping: "Scoping plan · <time band>". A settled thoroughness line carries the band. The
  in-card input's placeholder is "What should change?" for every words option. Decisions the
  user did not take read "The Agent decided: <label> · after <stage>" and "Your standing rule
  decided: …". A dropped connection mid-reply keeps "Drafting the plan" with a still dot.
- A turn that carries a part card shows no question or chips beside it.

- Polish round 1 (agent) follow-ups by the lead: "A new run started just now" under one minute
  (the minute count may be zero); no re-run line over the baseline while a longlist walk runs
  (it does not rewrite the report); the strip's writing state keeps "Section n of M" and drops
  the title. A check-in option shows the server's sentence and the planner's reason on two
  lines; the annex's reason-only form is the mock's shape. The mid-write failure banner's copy
  and the plan panel's arrival motion are deferred to the owner pass.

## Owner pass, round 2 (2026-11-05): the owner's notes on the live app and what was done

1. "Your Task Agent conversation couldn't be loaded" on a completed search, and the History tab
   likewise: a bug, not polish. Turns stored before this slice carry plan steps without the new
   `row` key, so re-reading the transcript failed validation. The transcript read now re-stamps
   every stored plan step with the server's current label, blurb and row (one source of copy on
   every read).
2. The "Plan" control leaves the task nav. "See plan" is back on the running card's top line, and
   the Result tab carries a small "See the plan" link under its title (before and after the
   report exists). Both open the plan side panel.
3. "Esc closes" is removed from the plan view (Escape still closes it).
4. The sidebar's pane shows no running card: the strip and the sidebar's run line already say
   where the run is.
5. "Categorising" becomes "Classifying" everywhere (the row label for classify and appraise, the
   activity line "n of M classified", the step verb). The row key `categorise` is unchanged.
6. The plan card with "Start the search" under a completed search's conversation was the same
   bug as item 1: with the transcript unreadable the pane saw no run block after the plan card.
   To confirm on the live app after restarting `make dev`.

Noted by the lead on the live check for the next owner round: on a completed task, a past
turn's part card (for example "Plan · step 2 of 3 · Scope" with "Looks right" and "Add or change
a constraint") still shows its unsettled radio list in the conversation history; the settled
one-line form, or a read-only look, would read better once the plan has run. The sidebar's run
block lists every run event ("Executed a search query × 50"); it predates this slice.

## Owner pass, round 3 (2026-11-05): "uncompleted 'N of 3' cards on completed searches"

A part card whose turn has a later turn after it is answered: it collapses to one line
carrying what the user wrote, "<Part> · <the user's reply>" (no radio list, no Change), and
the stepper counts it as settled. A card answered by a recorded choice keeps
"<Part> · <choice> · Change" while it is the newest proposal. Only the newest, unanswered card
is open. Both settled lines use the conversation's text size (Lead), the part name in navy
bold, the rest in grey (owner: consistent text sizes). The settled line names the outcome the
plan settled on, not the user's words (owner: "I would have expected 'standard'"): a recorded
choice names itself; otherwise the question's text, the scope's chips, the thoroughness preset
with its band ("Standard report · ~10-20 min"), the scoping depth and risk appetite labels; the
user's reply only where the plan names nothing.

Also in this round (owner): the two stage signposts under the running card ("Searching has
finished. Sources are ready →", "Mapping has finished. The landscape is ready →") go; the card's
own row links point at the outputs. The run-finished line stays. The Mapping row links to the
Themes view (the Sources tab's first view), not the Landscape.

## Owner pass, round 4 (2026-11-05, the last of the build's three owner rounds)

1. The thoroughness options read fastest to slowest, in the order the planner gives them; the
   primary option is no longer moved to the front (D10's "primary first" is withdrawn by the
   owner for this card; no option is pre-selected and no "Recommended" word appears).
2. Each option shows its label and its one sentence, as before this slice; the planner's reason
   line under the primary option goes (owner: too verbose).
3. A settled question line shows the question's text; a settled scope line shows the screening
   and search chips; "That's my question" and "Looks right" are fallbacks only when the plan
   names nothing.
4. The cards take a moment to arrive, so settled lines rise in like the open card and the plan
   card (the existing 300 ms rise; off under reduced motion).

## Polish log

| Round | Phase | Date | Notes applied | Sign-off |
|---|---|---|---|---|
| 1 | build, agent pass | 2026-11-05 | Plan side panel lies over the page instead of squeezing the report; task nav keeps a gutter before Plan; the card's step in progress keeps its clock on the label line on phones; the strip's elapsed time never truncates; in-card inputs span the card on phones | lead |
| 2 | build, owner pass | 2026-11-05 | six notes applied (above); the transcript-read bug fixed; Classifying | owner (round 1 of 3) |
| 3 | build, owner pass (round 2 of 3) | 2026-11-05 | settled part cards name the plan's outcome at the conversation's text size; stage signposts under the card removed; Mapping links to Themes | owner |
| 4 | build, owner pass (round 3 of 3) | 2026-11-05 | option order as the planner gives it; no reason line; settled lines show the question and the chips; settled lines rise in | owner |
| 5 | review, agent pass | | | lead |
| 6 | review, owner pass | | | owner |

## Deferred polish

Notes the owner gave that this slice does not take, with where they go (`docs/deferred.md`).
None yet; the owner will add them on the live app.
