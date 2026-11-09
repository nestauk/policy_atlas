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
2. Better navigation between the Agent tab and the task. → Every finished row links to its output; the Result tab carries the run status bar with "Follow in the Agent tab →"; signposts stay.
3. Stall counter is noisy for short pauses. → No counter. Short pauses show nothing. After 2 minutes of silence the action line reads "Still working on this step" (no timer, count stays). Drop entirely if the owner prefers.
4. Writing: show the section, then what it is doing in that section. → Two lines: section line persistent, action line changes under it.
5. Early Result tab needs refining. → Report-shaped page: title, run status bar, landed outputs as rows. Section titles cannot appear before writing starts (the writer proposes them); moving the proposal to after Mapping is a backend option for the owner.
6. Proposed sections should display in the report with subtly pulsing lines. → At the skeleton every section shows 2 to 3 pulsing placeholder lines until its prose arrives.
7. How are the writer's tool-call turns shown in the Result tab? → The active section shows the action line ("Looking for: …") above its pulsing lines; prose replaces it when streaming starts.

## Owner feedback round 2 (2026-11-04) and the lead's answers
1. Show which claims have been sent for repair. → When the check returns, the sentences it failed get a dotted underline and a small grey "being revised" at the end; when the repair lands the text is replaced, the underline becomes a thin solid one and the word becomes "revised" with the old wording on hover or tap. Sentences that passed get nothing.
2. The "Checked" / "Writing" pills look busy and generated. → No pills anywhere. Section state is carried by one breathing dot after the heading while the section is being written or checked, and by nothing once it is done. The "Written last" note on Key findings becomes a plain grey sentence under the heading. The run status bar and the signpost bubbles use words, not chips.
3. Early Result tab: the links to other tabs are redundant with the status bar and vanish once writing starts. → Dropped. Early Result tab = the run status bar, the question as the title, and one grey sentence: "The report's sections are set out when writing begins." Nothing else.
4. General polish: a design review with the frontend design skills, against DESIGN.md, applied to the mock.

## The running card (revised)
- Top line: dot, "RUNNING", elapsed "6 min 12 s" right-aligned in tabular figures, "Minimise" link. No second title.
- Rows, one per plan step in order. **Owner 2026-11-04: "Sorting by evidence type" is renamed "Classifying" and absorbs Appraising (a one-second deterministic step); Shortlisting has no view in the app and gets no link (the selection shows through citations and the read-in-full status).** Evidence search rows: Searching and screening; Classifying; Reading the full texts; Mapping; Shortlisting; Writing (six). Three looks:
  - Done: label in navy, then on the same line in grey the key count, then the link. Examples: "Searching and screening · 312 found · 118 relevant · Sources →"; "Classifying · 118 classified · Landscape →" (link appears once Mapping is done; before that no link; superseded by the lead, round 8: the link shows at once); "Reading the full texts · 38 read" (no link; owner round 4: nowhere relevant to point); "Mapping · 7 themes · Landscape →"; "Shortlisting · 24 selected" (no link); "Writing · 7 sections · Report →". In-progress line for Classifying: "40 of 118 classified".
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
Result selected. Under the tabs, the run status bar (same as scene 7): "● Searching and screening · 184 found so far · 6 min", status only, its text advancing through the stages as in the Agent card. The page is the report-to-be: the question as the title, then one grey sentence: "The report's sections are set out when writing begins." Nothing else. (Round 2 feedback: the output links were redundant with the status bar.)
Caption: "The Result tab is the report before it exists. The status bar says where the run is."

### 6. Result tab, streaming
Run status bar under the tabs: "● Writing · Section 3 of 7 · 14 min", status only. Skeleton of 8 headers in report order, each with 2 to 3 placeholder lines of varying width that pulse softly (1.6 s opacity, same as the dot) until that section's prose arrives. No pills or chips anywhere (round 2 feedback). Key findings at the top with a plain grey sentence under the heading, "Written last, after the sections are checked.", and its pulsing lines. Sections 1 and 2 are done: heading, then a short line of real prose each, no marker ("Take-up of the free entitlement is lowest among the families it was designed for." and "Lone parents and families on Universal Credit are the least likely to hold a place."). Section 3 is the active one:
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
- Sources tab with the lifecycle bar. Under the tabs the run status bar: "● Writing · Section 4 of 7 · 14 min", status only, no link and no mark. When the run finishes it becomes "Report ready · Read it →" in green, the one link it ever carries.
- A browser tab strip mock showing the title change from "Childcare take-up · Policy Atlas" to "● Report ready · Policy Atlas".
- Task list row: status dot, "Writing · Section 4 of 7 · 14 min" instead of "Analysing the evidence…", then "Complete" with the green dot.
Caption: "The run is visible from every tab, and you are told when it finishes."

### 8. Re-run and reconnect
- Result tab with an existing report and one plain line above it: "This report is from 3 November. A new run started 2 min ago." (The status bar above reads "Searching and screening · 112 found so far · 2 min".) No button: the status bar above it carries the stage, and the sidebar rail and the Agent tab are the routes to the run.

## Design review round 2 (lead decisions, 2026-11-04)
Review note: `design-review-round2.md`. Card directions A (tinted, refined), B (paper ledger, recommended), C (step spine) are in the mock behind a "Card: A | B | C" control; the owner chooses. Accepted from the review: paper instead of the green fill in B and C; yellow for running everywhere; counts right-aligned; no pills; repair treatment as in round 2; skeleton bars on the prose pitch; the two copy changes above. Not applied: duration band (owner: out), stop button (owner: cancel deferred), pulsing only the active section (owner asked for all proposed sections to pulse), rewriting the middot data lines as sentences (meta lines keep middots; the voice rule is about prose). For the build: the Result-tab, status bar and task-row dots must stop 1.5 s after the last update like the card dot; consider a 0.5 trough for the yellow dot on white.
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
- **Two routes to the agent, never three (owner, rounds 4 and 5).** On any non-Agent tab the sidebar rail's own blue diamond opens the sidebar in place, and the Agent tab is the full view. Nothing else links to the agent: the run status bar is status only; the re-run notice has no button; there is no separate paused banner. While a check-in waits, the status bar turns orange, "Paused · a check-in is waiting on you", and opening the sidebar from its rail lands on the check-in, which glows once; on the Agent tab the card glows in place.
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
Sources tab at 1100 wide with the sidebar open on the right (320 px). The run status bar under the tabs reads "Searching and screening · screening 61 new abstracts · 6 min", status only. The sidebar opens from the rail's diamond. In the sidebar, top to bottom: header "Task Agent"; a compact run line (dot, "Searching and screening · 6 min"); the thread tail, which is the card's current line ("Searching and screening" in navy-grey with "screening 61 new abstracts · 107 relevant so far" under it); the composer locked with the placeholder "Replanning unlocks when this run finishes." Then, at 4 s, the run pauses: the compact line becomes orange "Paused · check-in after searching" and the check-in card from scene 12 appears in the sidebar at reduced width (radio list, no facts line), answerable there. Answering returns the line to "Classifying · 40 of 118 classified · 7 min". (Aligned 2026-11-04 after the builder flagged the writing/searching mismatch.)
Caption: "The sidebar shows the same run and the same check-in. Nothing is only on the Agent tab."

### 14. Finding your way (block J)
Three panels, as in scene 7:
- The task nav with a new "Plan" control to the left of the lifecycle tabs (grey text, underline on hover). The lifecycle tabs during a run, the user on Sources: when a section lands, a small navy dot appears beside "Result"; the mock shows it appear, then the user clicks Result (the tab underlines) and the dot goes. The Agent tab shows an orange dot when a check-in is pending.
- The plan document open as a side panel (not centred) over the Result tab with the hint line "Esc closes" at its top right; the mock closes it after 3 s.
- The History tab with the run status bar in its paused state: orange dot, "Paused · a check-in is waiting on you", no link. The sidebar rail's diamond opens the sidebar with the check-in in view and its orange rule briefly brighter (one 900 ms glow, honouring reduce-motion).
Caption: "New content marks its tab. The plan is one click from anywhere. Opening the sidebar lands on the check-in."

## Block K (owner 2026-11-04): the Options Scoping Result tab during the longlist build
Grounding: `grounding-scoping-result-tab.md`. What the pipeline can honestly show, and what the scene therefore does:
- The suggested options are real rows seconds in, but no read lists them before the longlist stage. Block K adds an additive read (a provisional longlist shape instead of 404, or an options list) and an `option_id` on each child run so the client can map a child search to its row. Both are public-interface additions (Tier 3, additive).
- Child searches run acquire only, so a row's line is "Searching" while its child runs and "Searched · N found" when it completes. No per-option reading or counts exist before clustering, so "Reading the abstracts" and "Clustering into options" are stage-level lines at the top of the list.
- Clustering keeps the suggested ids; a suggestion may be folded into a wider option (the row stays, marked folded) and new clustered rows may appear. Never split.
- Profiles, constraint checks and themes each land for every option in one commit, so the list fills in three waves, not row by row. The scene shows waves.
- The list carries no qualifier word: the stage line and the moving rows say it is being built. The view knows it is building because the longlist does not exist yet while a walk runs; no API flag.

### 15. The scoping Result tab during the build (block K)
Scoping task "Reducing youth unemployment", Result tab, card C elsewhere. Run status bar under the tabs: "● Suggesting options · 1 min" then advancing. The page is the longlist-to-be:
- Title: "Longlist". Under it one stage line in the activity style, changing with the run: "Searching for each option · 4 of 12 done", "Reading the abstracts · 1,180 of 2,410", "Clustering into options · options may be folded together or added", "Writing what each option would take", "Applying your constraints", "Grouping into themes", "Shortlisting".
- Rows appear as soon as suggest completes (2 s): 12 rows, each a paper row with the option name, a small grey origin word ("from your report", "suggested", "added by you") and, on the right, a per-row line. Use these names: Youth guarantee with a job or training offer within four months; Wage subsidies for employers hiring under-25s; Expanded apprenticeship incentives; Careers advice in every secondary school; Sector-based work academies; Mental health support in job centres; Transport subsidies for young job seekers; Intermediate labour market programmes; Digital skills bootcamps; Youth hubs co-located with Jobcentre Plus; Enterprise allowance for young founders (added by you); Conditionality reform for under-25s (added by you).
- Per-row line while the fan-out runs: a breathing dot and "Searching" on rows whose child is running (up to 10 at once), "Searched · 312 found" when a child completes (vary the counts 140 to 410), "Queued" in grey for the two waiting. The stage line counts up "4 of 12 done" to "12 of 12".
- Then the stage line reads "Reading the abstracts · 1,180 of 2,410" rising; rows are unchanged (no per-row count yet).
- Then "Clustering into options · options may be folded together or added" with the dot; after 3 s the list changes once: "Transport subsidies for young job seekers" folds into "Youth hubs co-located with Jobcentre Plus" (the row slides under it as a grey line "Folded into Youth hubs"), and two new rows appear at the end with the origin word "found in the evidence": "Employer-led pre-apprenticeship traineeships" and "Benefit run-ons when a young person starts work". Every remaining row's right-hand line becomes a count: "38 documents", "12 documents" and so on.
- Then "Writing what each option would take" with the dot for 3 s; then, in one wave, every row gains a lever line in grey under its name (for example "Supply-side · Standard ambition"); the stage line moves to "Applying your constraints" for 2 s; then in one wave two rows move to a collapsed "Excluded · 2" group at the bottom with a one-line reason each ("Out of scope: not a youth measure"); then "Grouping into themes" for 2 s; then the rows regroup under three theme headings ("Getting into work", "Staying in work", "Advice and support") with a 300 ms rise; then "Shortlisting" for 2 s; then four rows gain a small navy "Shortlist" word, the stage line goes, and the status bar reads "The longlist is ready · Read it →" in green.
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

- Two routes to the agent, never three; the status bar is status only; no paused banner; no
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
- The mock (version 7) predates these rulings and still shows round counts, the status bar's
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
- The status bar's finish wording per walk: "Report ready", "The baseline is ready", "The longlist is
  ready", "The option's search is done", "The shortlist is proposed", each then "· Read it →", the
  whole line in green. A colleague who cannot answer a check-in sees "Paused · <row> · <elapsed>".
- Failed and skipped rows read "Stopped" and "Skipped".
- The breathing dot's lowest opacity is 0.5 (0.35 nearly vanished on white).
- The status bar shows the writer's whole section line while writing; shortening it to "Section n of M"
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
  (it does not rewrite the report); the status bar's writing state keeps "Section n of M" and drops
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
4. The sidebar's pane shows no running card: the status bar and the sidebar's run line already say
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

## Owner note after round 4 (2026-11-05): the thoroughness copy

The three thoroughness sentences the planner writes are cut to the plain voice (one source, the
planner prompt; hash re-pinned), corrected by the owner the same day (Rapid overview is not
abstracts only; say the total documents, the report's sections, and that deep extracts): "Up
to 150 documents. A short report of 3 sections."; "Up to 300 documents, about 15 read in full.
A report of up to 8 sections."; "Up to 600 documents, about 25 read in full with their
findings extracted. A report of up to 8 sections." Each then its band (~5-10, ~10-20, ~20-30
min). The mock says the same.

Owner, 2026-11-05: the three preset bands are Rapid overview ~5-10 min, Standard report ~10-20
min, Detailed report ~20-30 min (`task_plan.TIME_BANDS`, the one table the plan document and the
planner read). The off-diagonal cells (custom search × analysis pairs) keep their older values and
are flagged for the owner: some now read longer than the deep preset.

Owner, 2026-11-05 (after round 4): the settled part card sits between the pre-task card and
the one-line form, which was too subtle: a quiet block with a 2 px green left rule, the part's
name in navy, and under it one green bold tick line naming the outcome ("✓ Standard report ·
~10-20 min"; the scope's chips; the question's text; the recorded choice or the user's words
only where the plan names nothing), with Change beside it while the card is the newest
proposal. No title repeat, no card frame.

Owner, 2026-11-05: while the Task Agent is working (the "Drafting the plan" line under a
streaming reply), the Policy Atlas fold mark turns in place of the yellow dot; it holds still
after a dropped connection and under reduced motion. The run's dots (card rows, status bar, Result
tab) stay dots.

Owner, 2026-11-05: the scope card's chips are grouped by what they constrain, each group
under a small grey label: "Screening criteria" (the planner's "Screen: …" chips) and "Source
filters" ("Search: …"), the prefix dropped from each chip; chips with no prefix come first with
no label. The settled scope line reads the same way ("Screening criteria: a, b · Source
filters: c").

## Owner questions on a live run (2026-11-05, afternoon) and the rulings

1. Section token streaming: built as the streamed *forced* final turn, which only runs at
   the writer's turn cap (6); on a normal section the model emits through its own
   `emit_section` tool call on turn 2, which Bedrock delivers in one burst, so the page sees
   nothing until the section is done (Langfuse, the owner's run: no `synthesise:section_emit`
   generations). Owner go (2026-11-05, after the cost figures): the open turns offer a
   no-argument `write_section` tool instead of `emit_section`; that call (or a reply with no
   tool call) ends the gathering, and the streamed turn writes the section. The streamed
   request keeps the tools with none allowed and sends no structured-output schema, so the
   provider reuses the cached prefix (`research/exp-stream-cache-probe.md`); cost about a
   cached read per section. The section prompt's words changed; hash re-pinned.
2. The Result tab's footer "Checking claims and attaching citations" goes (owner: not useful).
   The claims check is per section and shows under the section's heading; after the last
   section the key-findings heading's dot is the one signal. Scene 6 and N8 are amended.
3. When a watched run finishes, the committed report takes the page by itself once the
   read models have it (owner: the swap is automatic). The "Report ready · Read the full
   report" footer and button go; N8's last clause is withdrawn. Citations during writing: a
   completed section's frame carries prose only, and the numbered markers are assigned when
   the whole report is read, so markers cannot show per section without carrying the section's
   claims on the frame and numbering provisionally (not in this slice).
4. The minimised card, the dock and the status bar say the same words in the same style (accepted;
   folded into item 5).
5. Where progress lives: the owner accepts the lead's recommendation of one in-chat trace in
   place of the running card, the minimised card, the dock and the status bar, consistent with
   task 054's `TocTrace`; the design is proposed to the owner before it is built.
6. The run block's event-log echoes ("Opened an evidence-search run", "Executed a search query
   × 55", "Recorded a steering decision", "Finished the run") leave the Task Agent thread. They
   are the task's audit events (task 025's decisions read, echoed into the chat by task 029);
   the sidebar showed them because polish round 2 took the card out of the sidebar and the
   thread fell back to the echo block. The History tab keeps the audit rows; making them
   readable there is a separate item for the owner.
7. The settled scope card gives each chip group its own line under a grey group label
   ("Screening criteria", "Source filters"), the values in green (owner: on one line the
   criteria and the filters read as one jumble, all in one colour).

## The run trace (owner, 2026-11-05): one progress surface, in the chat

Replaces the running card in the thread, its minimised state, the dock above the composer, the
run status bar under the lifecycle tabs and the sidebar's run line. Same shape as task 054's
`TocTrace`, so the two capabilities read alike when 054 merges; fed by this slice's event
stream, so the counts, the links and the paused state stay. Every label is the server's.

- **Place.** One block per run in the Task Agent thread, at the run's place, no card frame,
  the same right margin as the part cards. The sidebar renders the same block.
- **The status mark.** A 6 px square, no radius: Electric Blue while the run is live (it
  breathes while updates arrive and holds still 1.5 s after the last, and under reduced
  motion), Green when it ended well, Orange while paused, Red when it failed, Line 2 when
  idle. The owner chose the square and the blue over the yellow circle (2026-11-05); the same
  mark replaces the circle everywhere a run's state shows (the Result tab's section mark, the
  task list row, the sidebar). DESIGN.md records it.
- **Live, closed.** A header line that is a button (`aria-expanded`): the mark, then the
  current row's label and its activity line ("Writing · Section 3 of 7 · Costs and funding";
  "Searching and screening · 184 found so far"; "Still working on this step" after two quiet
  minutes), the run's elapsed time right after in tabular figures, then "· 6 steps". Meta
  size, semibold, navy; the counts and the time in the Figures style. Under it, in grey, the
  last finished row's one-liner rising in as it lands ("Searching and screening · 312 found ·
  118 relevant · 1 min 4 s · Sources →"). A long line truncates its words; the time stays.
- **Open.** "· hide steps" in the header; under it the step list: one row per plan step in
  order (today's spine rows: done rows with their counts, wall time and link; the row in
  progress with its activity and its own elapsed time; upcoming rows as names in grey), set
  under a hairline left rule, and "See plan" at the foot. The list stays open until closed.
- **Paused.** Orange mark; the header reads "Paused · a check-in is waiting on you" for the
  owner and "Paused · <row label> · <elapsed>" for a colleague; the check-in card sits under
  the block as today and glows once on arrival.
- **Ended.** The block folds to one line: Green mark, "Report ready · 14 min · Read it →" (the
  finish words per walk kind, the link to the result); a bad ending reads "Stopped · 14 min"
  or "Failed · 14 min" with no link. A chevron before the words opens the steps. The folded
  line is the run's one destination, so the separate run-finished notice goes.
- **A past run** (not in the stream) folds to its status word and its wall time, with no step
  list; the chevron is absent. *Round 11 (owner): it is the ended card, with its walk's link
  and, when the run read carries its steps, "Show steps"; see § Round 11, the workspace.*
- **Elsewhere.** Nothing else shows the run: the lifecycle tab dots, the browser title marker
  and the reconnecting banner stay. "See the plan" under the Result tab's title stays.
- **Motion.** The header's words re-mount with the 300 ms rise when the row changes; the last
  finished line rises in; the mark breathes; all still under reduced motion.
- **Phones.** The header wraps after the words; the elapsed time stays in view.

Rulings on the build (lead, 2026-11-05, from the agent's proposals): the sidebar shows the
Task Agent thread with the trace at the run's place and the check-in under it, and opens at the
thread's end (the earlier "after <row label>" sidebar line is gone with the sidebar's run
view); a past run reads the words its walk ended with ("Report ready", "The longlist is
ready", "Stopped", "Failed"); the live header ticks in seconds, ended and past lines use
minutes; before the first stage frame the header shows the mark, the time and the step count
only (the client invents no label); the chevron appears only on the ended line; the header's
words are Meta semibold navy with the time and the step count in grey, a good ending in the
deep green; step rows carry no marks (weight and colour carry state, plus a screen-reader
word); below 576 px the header's words may take two lines before the time wraps; the open
list's in-progress row repeats the header's activity (a polish item for the owner pass); the
degraded shortlist walk's ended line keeps its sentence ("Policy Atlas could not propose a
shortlist. Your places are unchanged.") with the red mark and no link; the lifecycle tab's
new-content mark is the same 6 px square, in navy.

## Owner round after the trace (2026-11-05, evening): notes and rulings

1. **A part card settles on the choice.** The moment the user picks an option or sends words,
   the card takes its settled form; it does not wait for the agent's reply (today it waited
   for the next turn to land).
2. **No tick.** The green tick on the settled card goes (lead, after the owner's question: the
   green rule and the green words already say the part is settled; the tick repeated them).
3. **The rule sits on the user's side.** The settled card's green rule moves to its right edge
   and the block keeps the user bubble's left indent (32 px), so a settled part reads as the
   user's decision, as the user's messages do. Text stays left-aligned.
4. **Smaller text in the sidebar.** In the sidebar's compact pane (the Task Agent and the chat
   conversations) Lead-size text renders at Body size (16 px, the floor); Body and Meta are
   unchanged.
5. **One way to change the scope.** The chips (pencil, ×, "+ add") are how the scope changes.
   The planner's "Add or change a constraint" option is not shown on the scope card; the
   card's one choice is a "Looks right" button, which records the planner's primary option
   and sends any staged chip edits with it.
6. **The live mark is the fold mark.** Wherever a run is live, the mark is the Policy Atlas fold
   mark turning (the animated one from the "Drafting the plan" line): the trace header, the
   sidebar's Task Agent mark, the task list row and the Result tab's section being written. It
   is 14 px in text lines and 17 px in the rail, and holds still under reduced motion. The
   static states keep the 6 px square (green ended well, orange paused, red failed, Line 2
   idle). The nav wordmark's mark no longer animates during a run: one animated logo per
   screen (owner).
7. **The writing section's mark moves into the action line.** On the Result tab the section
   being written shows its mark at the start of the action line under the heading ("◆ Looking
   for: …", "◆ Writing", "◆ Checking claims"), not after the heading's words.
8. **The Sources tab opens on the step that has landed.** While a run is live: All sources
   until classification completes, then Landscape, then Themes once mapping completes. After
   the run, Themes as today.
9. **The trace header reads at the chat's size.** The header's words are Lead (as the settled
   cards and the agent's prose); the step rows are Body; the time and the step count keep
   their grey.
10. **Streaming.** The server streams every section now (Langfuse, the owner's 13:24 run: a
    read turn, a 14-token ready turn, a 10 s streamed write per section). The page showed
    nothing because the deltas carried the writer's loop index while the skeleton numbers
    sections for display (Key findings first at 0, so each body section's display index is
    one higher): the first section's text landed on the Key findings slot. Fixed on the
    server: the deltas and the revising spans carry the display index (lead).

Rulings on the build (lead, 2026-11-05, from the agent's proposals): the scope card's
"Apply changes" goes, "Looks right" carries the staged chip edits (the staged list and
"Discard" stay); a failed send reopens the card beside its Retry; while a choice is on its way
the settled card shows the user's words or the chosen option's label (a primary confirm shows
the plan's outcome at once); a settled scope lists its chips with the staged edits applied;
the rail's Task Agent mark turns on every tab that mounts the sidebar; the Result tab's own
writing mark may turn beside it (owner, 2026-11-05, round 6); the rail's mark keeps its static
size; the settled card's green words are the deep green #0c6b5a everywhere (AA at 16 px); the trace header's step label is semibold and its activity regular;
a middot separator never starts a wrapped line; the scoping Result tab's live rows use the
fold mark too; the writing section's action line reads "◆ Writing" for the whole write.

- lead, 2026-11-05, round 6: while live, the trace's header is the turning fold mark and the
  run's elapsed time only ("6 min 12 s"); paused it keeps "Paused · a check-in is waiting on
  you · 6 min 12 s" (a colleague: "Paused · <row label> · <time>"). The step in progress takes
  the 6 px blue square, breathing while updates arrive, so one mark turns per block; the step's
  words and activity live only on its row; the screen-reader status keeps the header's words.
- lead, 2026-11-05, round 6: the live trace stays borderless, with the spine and the hairline
  rules (the agent's view: the rules already make the list one object, and a Card frame would
  make the trace the heaviest block in a thread that already holds the settled cards and the
  check-in card; the folded green ended line already makes a finished run easy to find).
  **Reversed by the owner on seeing it live (2026-11-05, round 7):** the live and paused
  trace takes the running card's frame again; see § Owner round 7.
- lead, 2026-11-05, round 6: no green pulse on the rail's mark when a step note arrives.
- lead, 2026-11-05, round 6: a step note for every step except Writing finishing (the title
  marker, the tab mark and the swap to the report already say it).
- lead, 2026-11-05, round 6: in a settled scope card the group labels are Caption size (same
  face, uppercase, grey); the part's name stays the Meta label.
- lead, 2026-11-05, round 6: the step note reads without the wall time ("Searching and
  screening · 312 found · 118 relevant · Sources →").

## Owner round 7 (2026-11-05, live-run notes): notes and rulings

1. **Citation marks while streaming look like the final marker, and stay.** A provisional
   citation is the final marker's chip in its muted look (Line border, Ground fill, grey
   Caption Semibold) with "·" for the number, "[·]", after the cited sentence; not a control,
   the source titles as hover text, named "Cited, being checked: <titles>". On completion the
   section's checked citations (`artefact.section_completed` `citations`) give the report's
   numbered marker in the report's look, not a control while live, named "Citation 3, Smith
   2023; details when the report is ready". The draft layer carries the muted chips as it
   fades off the checked prose, so nothing flashes. The final page has no muted chip for an
   unsupported claim (its tier shows only in the tooltip), so neither has the live page.
2. **The live page is the final page, and the swap is in place.** The live Result tab renders
   through the committed report's own page, section, prose and case-study components: the
   contents beside it, the kind row, the question as the title, "See the plan", the
   "Executive summary" and "Full report" part headings, the sections in `orderSections`
   order, case-study cards in the final card layout as each closes, and a references list at
   the foot that grows as sections are checked (numbered, titles only, no links, open). The
   committed report renders the same keyed tree, so React updates it in place: the scroll
   position stays, a section the reader was reading stays open (a section that becomes
   collapsible keeps showing), and what arrives fades in once over 300 ms on the strong
   ease-out (the download, the facts strip, "Ask about this analysis", the most relevant
   sources, the expand controls, the case-study chips, the references' authors and years,
   the method, and a marker whose number changed); under reduced motion it is a cut.
   "Written last, after the sections are checked." and the key-findings order stay.
3. **Streaming smoothness** (recipe: `research/streaming-text-smoothness.md`). The store's
   draft stays the arrival target; the page reveals it at max(0.15 chars/ms, backlog /
   800 ms), snapped to whole words, one state update per frame; a quiet draft shows its
   trailing word after 500 ms (tuning values, not sourced). Settled paragraphs are memoised;
   only the live paragraph re-renders. A revision cuts the revealed text back during render
   and holds the section's height until the text regrows. The page follows the text only for
   a reader within 40 px of the end and stops on the first upward scroll. Owner (2026-11-05):
   the words each frame reveals fade in over 150 ms, opacity only, one span per batch,
   dropped when the paragraph settles; no fade under reduced motion; no caret.
4. **The trace looks like the card we first designed.** Live or paused, the trace is a Card
   with the card's top line: the turning fold mark, "Running" in the label style, the elapsed
   time right-aligned in tabular figures; paused, the orange square and "Paused · a check-in
   is waiting on you" (the state word in the label style, the rest in grey) with the time at
   the right. No Minimise; the rows, spine and rules as round 6 built them, inside the frame.
   Ended, it folds to the frameless green line as before. The sidebar shows the same card.
5. owner, 2026-11-05, round 7: the step note withdrawn (it did not look right); the run status bar
   returns under the tabs on every non-Agent tab, status only, because it is now the only
   progress surface outside the Agent tab.

Rulings on the build (agent, for the lead to confirm): the live card spans the thread's
column like the check-in card (round 6's right margin stays on the ended line); the live
page's kind row reads "Baseline" when the skeleton has no key-findings slot; the slot before a
case-studies slot at index 1 is read as the key findings (the server's order), which the
mock's skeleton relies on.

## Owner round 8 (2026-11-05, evening, live-run notes): workspace and shell

Brief: `research/briefs/round-8-workspace.md` (lead decisions). Built as below.

1. **The ended state is the same card.** Ended, the trace keeps the card frame and the top
   line: the green square, the finish words in the label style ("REPORT READY"), the wall time
   and "Read it →"; stopped and failed in red the same way, with no link. The rows fold behind
   "Show steps" / "Hide steps". A past run not in the stream is the same folded card. The green
   one-liner is gone.
2. **Right-aligned counts, times and links.** The card reads as a table: the top line and every
   row share one template (words left; counts and time right-aligned in one grey column in
   tabular figures; the link right-aligned in blue in the last), one line box for every line so
   rows stand equal and the marks sit on the middle of the first line. Narrower than 32rem the
   right group follows the label on the line under it.
3. **The link while the step runs.** Searching and Screening → Sources, Classifying →
   Landscape, Mapping → Themes, Writing → Report, right-aligned like a done row's.
4. **The current row breathes.** The step in progress's activity line breathes with its square
   (1.6 s, opacity 1 to 0.6); the label holds still; still under reduced motion.
5. **Two rows for search and screen** ("Searching", "Screening"), each with its own counts and
   activity line, both linking to Sources (the backend's row split).
6. **"Change" on its own line** under the green words, left-aligned, a quiet control at Caption
   size.
7. **A fluid settle.** One container across the two states: the options and controls fade out
   over 150 ms while the card eases to its settled height and across to the user's indent over
   300 ms on the strong ease-out; the surface and the green rule ease in with it; the settled
   words rise in; the stepper line folds away. Reduced motion: a cut.
8. **The status bar** starts after the rail from `md` up (full width below), and the whole status bar is a
   button that opens the Task Agent in the sidebar (the Agent tab below `md`); step label
   semibold navy, activity grey, time grey and right-aligned, 10 px vertical padding, the mark
   on the first line. The owner reversed contract D8's "status only" for the status bar (2026-11-05,
   round 8).
9. **The rail** shows the static fold mark, named "Task Agent", with no hover status and no
   timer.
10. **Task list:** a running task's mark is the breathing 6 px blue square, one size with the
    other rows.
11. **Sources tab mark removed;** the Result tab's stays.
12. **Pulsing placeholders** keyed to the live stage, only where the value is absent: Relevant
    while screening; Evidence type and strength (relevant sources) while classifying; Status
    (relevant sources not yet read) while reading the full texts; three placeholder rows on
    Themes while mapping; placeholder bars in place of the evidence-types chart on Landscape
    while classifying. The Sources views refetch every 5 s while a stage that feeds them runs.

Rulings on the build (agent, for the lead to confirm):
- "Show steps" sits under the top line's words, at the folded card's foot, and stays there when
  the rows open below it (so the control that opened them closes them without moving); "See
  plan" stays at the foot of the open rows.
- The top line's time is Meta size, in the table's time column; the label style is unchanged.
- A past run's card is not a landmark region (the thread's one "Analysis run" region is the run
  the stream follows), so it no longer collides with the live card's name.
- A finish that is a sentence (the degraded shortlist walk's) keeps its case in navy; only a
  state word takes the label style.
- The placeholder bar is Line 2 (a step darker than the Result tab's Line placeholder lines): a
  short bar in a table cell needs the weight to read at the breathe's trough.
- A pulse needs the run to be running: a paused run (a check-in waiting) pulses nothing.

Lead rulings on the round-8 build (2026-11-05):
- lead, round 8: a done Classifying row links to the Landscape at once, superseding round 4's
  "link appears once Mapping is done" (the running row already links there).
- lead, round 8: the Writing row's link keeps "Report →" (to the Result tab), running and done.
- lead, round 8: "Show steps" under the top line's words, staying put as the rows open; "See
  plan" at the foot of the open rows.
- lead, round 8: the run status bar steps aside while the Task Agent is open in the sidebar (its
  trace shows the same words) and returns when the sidebar shuts or shows another chat; below
  `md`, where the sidebar does not show, it stays.
- lead, round 8: the agent's rulings above are accepted (the past run's card is not a landmark,
  a finish that is a sentence keeps its case, the top line's time at Meta size, the Line 2
  placeholder bar, no pulse while paused).

## Owner round 9 (2026-11-05, night, live-run notes): the page

Brief: `research/briefs/round-9-page.md` (lead decisions); the animation sweep
`research/animation-opportunities.md`, entries 1 to 10 with the lead's rulings (a) to (d).
Built as below.

1. **Search queries, live and at the top.** All sources opens with the queries block. While the
   search runs it is open under "Search queries": one table at Meta size, hairline rows, the
   backend once per group as a row-group label, each query as it goes out (a citation pass's or
   lookup's description in grey), a pulsing bar in Results until the count returns, then the
   count in tabular figures. The sources table and its count line wait for the first results and
   rise in together. Once the search ends the block folds to "12 search queries · 312 results ·
   Show"; the chevron opens the table; the committed coverage replaces the live rows in place.
   Queries wrap on words.
2. **The activity line during search** renders what the server sends ("searching · 184 found ·
   <query>", "following citations · 184 found"); the status bar truncates it on one line.
3. **The run status bar's link** (the strip is renamed the run status bar everywhere, code
   included; owner, round 9). A bar of two controls: the words (the Task Agent button,
   unchanged) and, after the time, the running step's view ("Sources →", "Landscape →",
   "Themes →", "Report →") while the reader is not on it and the run is not paused. Keyboard
   order words, then the link.
4. **The chips during the check** go from the muted chip to the checked marker's look at the
   peak (Blue Wash, the marker's blue border and text) and back, 1.2 s, 150 ms apart; the judged
   marker is unchanged.
5. **Themes while assigning.** From the found themes until the stage ends the Themes subtab lists
   them in the final layout, name and description, with a pulsing bar where each count will be;
   the counts fade in place, no reorder and no remount. The three anonymous rows remain only
   until the themes are found.
6. **Fluid appearance.** One arrival (`anim-rise`, now on the strong ease-out) for blocks that
   appear after a view's first paint; the history holds still. The Task Agent thread eases to its
   new height as it grows (growth only), the pin following, so it glides rather than jumps. Sweep
   entries applied: 1 the thread makes room; 2 history holds still; 3 the check-in rises, its ring
   blooms 150 ms after, it settles on the choice and its confirm step eases; 4 the trace eases
   its steps and folds over 200 ms, the plan card leaves as the trace arrives; 5 a decision card
   lays out its rows in turn; 6 the reply is paced; 7 values and rows landing on Sources and the
   found themes fade in (the Landscape chart's fade is the other builder's file); 8 the report's
   first words keep the placeholder height; 9 the status bar is a cut on a tab switch; 10 one
   curve, one breathing rhythm for skeletons (`animate-pulse` gone outside the Landscape file),
   the footer and jump-to-end on the strong ease-out, a sheet's exit along its edge.
7. **The top nav's hover.** The blue rule grows from the centre on hover and keyboard focus over
   200 ms and shrinks back; the active rule full and still; the lifecycle tabs the same; under
   reduced motion it appears without growing.

Lead rulings on the sweep (2026-11-05): (a) DESIGN.md's "a row that lands rises in once" is
dropped; a landing row keeps its place, its counts and time fade in and its square eases to
green. (b) A check-in settles the moment the user chooses, as part cards do, and comes back open
with its notice if the answer fails. (c) The plan document arrives with the sweep's values. (d)
`JumpToEnd` loses `rounded-full`.

Owner, round 9 (relayed by the lead): "Read in full" overclaims. The Sources status chip reads
"Full text" ("Abstract only" stays); the source's status line "Full text collected"; the CSV
column "Full text"; the Abstract-only hover "The full text hasn't been collected…"; the scoping
longlist's coverage line "no full texts collected".

Rulings on the build (agent, for the lead to confirm):
- The growing rule grows from the centre (the brief's first option): it says nothing about
  direction, and items differ in width.
- The status bar's link hides on the view it opens, judged by the path (the Themes subtab is the
  Sources index, so it does not hide "Sources →" there) and, for "Report →", by the Result tab.
- While the search runs with no sources in, the "No sources yet" card is not shown: the queries
  are the page until results land.
- The folded line's results total is the sum of the Results column, live or committed, so the
  line and the table agree.
- A check-in's "Stop the run" also settles the card at once, like an option.
- The eased height watches the DOM (a MutationObserver), not its size: a size observer started
  the animation inside its own delivery and the browser reported a "ResizeObserver loop" on every
  arrival.

## Consistency pass (build, 2026-11-05): the sweep, the lead's rulings and the owner's additions

From `research/consistency-sweep.md` (entries 1 to 8 and § 3) with the lead's rulings on § 4, the
carried items, and the owner's additions during the pass. DESIGN.md carries each rule.

- **Focus:** one rule in `index.css`, a 2px Electric Blue outline offset 2px on every control; the
  cut-corner primary, start and send buttons draw a 2px white ring inset 4px (their clip clipped the
  outside ring, so they showed none). `PagePrimary` is `buttonVariants` primary at the entry size.
- **Buttons:** an `outline` variant (Line 2 border on Paper, Navy Semibold Meta) for pagination,
  Download and the bordered card actions; the entry size is 52 px tall, at least 144 px wide, never
  wrapped; Start search is `variant="start" size="entry"`; Retry is always `Button` secondary small.
- **Inline actions:** three styles, Link, Quiet control, Prose link; "Ask about this analysis" at Meta.
- **Close and icons:** one `CloseButton`; one icon module, 16 px in 32 px boxes for chrome and 13 px in
  28 px boxes for row actions, one hover.
- **Type:** the report part heading is Heading, uppercase, Extrabold; section headings Lead below
  `md`; system-state headings Bold; labels on the label constants and token; no `font-medium`; the
  splash's two headlines are named tokens (`text-hero`, `text-hero-2`) and its prose is Lead.
- **Shape:** the plan card's round radio is the one radius exception (P4).
- **Layout:** every task tab pads `py-8`; task-tab gutters 16 px below `md`. List pages share one
  header: a 24 px context row, a 52 px title row with the actions right-aligned, a filters row always
  reserved at 40 px; actions above the title below `md`; 16 px gutters below `md`; 56 px rows, two
  fixed lines of 84 px on phones without owner and source count.
- **Header controls:** 40 px, Body Semibold, ghost (the primary's label size); "Find a project" on
  Projects, built as "Find a task". The Find popover: focused field, the recent five with nothing
  typed and no result line, results 150 ms after the last key, "No tasks match “…”" only once there
  are words, arrow keys and Enter, Escape closes, the popover tokens.
- **Navigation:** the growing rule grows from the left edge to the centre on hover and focus, runs
  full width when active, and a click continues it; the Sources subtabs take the same rule, their idle
  labels in the Grey token. The Mine/Organisation switcher uses the tab language: a 2px blue rule
  when active, no fill.
- **Account menu:** anchored under its button, rises in over 200 ms and leaves in 150 ms, the popover
  tokens, the identity then 40 px Meta rows, Sign out last; the button shows the open state; focus in
  on open and back on close; arrow keys; Escape and an outside press close it.
- **Containers:** a list loads inside its own frame with placeholder bars at the real row height; an
  empty list is the frame with a label and one sentence, left-aligned. The Landscape subtab's
  placeholder bars sit in the chart's own rows.
- **Landscape:** each ranked row with sources is a link to All sources (or Findings) filtered to its
  value, and each year to that year; folded rows, "Not reported", rows at zero, the funnel and the
  publisher countries are not links. One hover: the bar turns blue and the words go Navy, no row
  wash. The relevant count is one line at the top; headings count only what differs.
- **Sources table:** every filterable header keeps its label and filter on one line.
- **New page:** no "New task" eyebrow; the title starts where the lists' titles start.
- **Carried:** `LandscapeFallback` renders `LandscapeSkeleton`; the dead chart exports removed; the
  mock landscape uses the classifier's labels; "run status bar" in the mock comments.

## Round 10, the report page (owner, 2026-11-06)

Brief: `research/briefs/round-10-report.md`; the review `research/report-polish.md`, findings 1 to
11, with the lead's rulings on C1 to C7 and D1 to D5. Built as below; DESIGN.md § Report and
citations carries each rule.

1. **References** read as citations: "Sampleton A, Mockford C (2022). Title. Venue.
   doi.org/…", the number in a Grey tabular column, Body at every width, the title a link to its
   dossier (a real `?source=` address), the address a Grey link without its scheme on screen and
   in full in print; no authors, the entry starts at its title. Live: titles only (C5).
2. **Facts line**: "Sources 12 cited out of 118 included · Published 2019–2024 · Last updated 5
   November 2026" as one Meta line of label and value pairs; Study types dropped; the date
   always with its year (C4).
3. **Print**: the banner and the action line hidden, markers plain numbers, bullets as black
   squares, headings kept with what follows, entries not split.
4. **Markers**: the marker is the claim's one control and tab stop, with the preview on hover
   and focus, numbers ascending, named "Source 2: <title>" or "Sources 7 and 12" (C1); the
   words keep their hover and click but are not a button. The live inert marker's name is
   unchanged.
5. **Headings**: parts `h2`, sections in them `h3`, case-study titles `h4`; a baseline and the
   longlist keep `h2`; collapsible headings hold their button.
6. **Contents**: titles in full; the current section from a line a quarter down the pane; the
   method entry "How the evidence was gathered" (C2), only when it renders; below `md` a closed
   "Contents" disclosure under the title block that closes on a choice (D3).
7. **Case studies and most relevant sources** are ruled entries, not boxes; most relevant
   sources sit just before the references (D2).
8. **Key findings**: a Navy square bullet, 12 px between items.
9. **Title block**: the question is the `h1` on the live and the committed page (D1); "See the
   plan" and "Ask about this analysis" on one line, then the facts.
10. **Provenance sheet**: "Claim provenance" is the dialog's hidden description (C3); each
    citation reads "[2] Title", year and venue, the passage, then authors, institutions, chips
    (D5, chat included).
11. **Method**: theme counts at Body in the link style; evidence types in sentence case from one
    formatter (`evidenceTypeLabel`, exported from `artefactPresentation.ts`; C6).

One disclosure vocabulary across the report (C7): the chevron with "Show" / "Hide" in Grey
Semibold Meta, "Show all" / "Hide all" beside Full report. The appraisal chip is the soft tone
(D4). The scoping pages that share `ReportPage` and `SectionDisclosure` gain the phone contents,
the full titles and the spy line, the heading-holds-button pattern and the disclosure words; the
longlist's "Expand all" reads "Show all".

Rulings on the build (agent, for the lead to confirm):
- D4 is applied to the appraisal chip at every strength, not only "Very strong": the chip's tone
  never depended on its label.
- D1 is applied to the report; the baseline keeps its own title ("Do nothing: …"), which says
  what the profile is. Say if the baseline should take the question too.
- The facts line separates its pairs by space (24 px), not by "·" characters, so a wrapped line
  never starts or ends with a dot.
- A single publication year reads "2022", not "2022–2022".
- The Markdown download follows the page (lead, accepted): the question as its title (the
  generated title names the file), the most relevant sources before the references, and the
  references in the citation form with the full address, from the same `referenceParts`.

## Round 10, the list rows (owner and lead, 2026-11-06)

From `research/lists-rows-polish.md` (findings 1 to 8 and the "lower" list) with the lead's rulings
and one owner addition. DESIGN.md § Layout, "The list row", carries each rule.

- **Accessible name:** the row's content in order, joined by " · ": title, status word (with the
  live step on a running row), projects, owner (where the column shows), date. The project row
  reads name, owner, task count, date. The status square keeps its visible word.
- **Room for the name:** the capability column is 7.5rem, the status column 11.5rem ("Paused ·
  waiting on you" and most first names), the date column 5.5rem ("30 Sep 2025"); the prefix cap stays at 45%; the desktop
  row stays one line (P5 declined).
- **Phones:** line 1 the name alone; line 2 the status word and its live step, then " · " and the
  project in Grey, which gives way first, the date at the right; no capability below `md` (P3, and
  contract N15's short form).
- **Status words:** "Paused · waiting on you" on the reader's own task, "Paused · waiting on <first
  name>" on a colleague's (just "Paused" with no owner); " · " is the column's one separator
  ("Complete · with gaps"); "Archived" in the Archived view (P2); the words live in `runPresentation`, the one status
  vocabulary. A failed row shows "—" for its source count, not "0 sources".
- **Capability:** plain Meta Grey text on every row from `md` up, not a chip (P4).
- **Press:** Blue Tint at once (`active:bg-blue-tint active:duration-0`), easing back over 150 ms.
- **Dates:** "5 Nov" this year, "12 Oct 2025" before it, Meta, one formatter (P7).
- **Owner column:** off on Mine and Archived; on Organisation and a Project, the reader's own rows
  "You" (P6).
- **Show more:** the Tasks page (50 rows) and a Project (200 rows) stop at the server's page; an outline "Show more" at 40 px under the frame
  asks for the next page of the same filters (`useTasksPaged`, driven by the server's
  `pagination.has_more`), drops a task already listed, moves focus to the first new row, and offers Retry
  if the page fails.
- **Archived:** an "Archived" entry in the filters row, shown while the reader has archived tasks,
  lists their own archived tasks without the owner column. A reader with no organisation sees Mine
  and Archived.
- **The switcher** (owner addition): the nav's growing rule at 2 px, from the left edge to the
  centre on hover and focus over 200 ms on the strong ease-out, full under the active item, a click
  carrying it to the right edge; under reduced motion it appears without growing.
- **New page:** the question step has no capability line ("Evidence search" / "Options scoping");
  the heading names the work and starts at the 44 px top padding.

## Round 10, Share and History (owner and lead, 2026-11-06)

From `research/share-history-polish.md` with the lead's rulings. DESIGN.md § Components, "Share"
and "History", carries each rule. Screenshots: `research/screenshots/round10-share-history/`.

- **Share order and shape (S2, S6, S9, S10):** Public link, Organisation, Projects, each a settings
  row: the heading and the state left, the control right, a Line rule between rows; below `md` the
  control drops under the words and the card becomes the screen (no border or shadow, 16 px). The
  state is Navy Semibold Body, an explanation Grey. The page has a hidden `h1`, "Share".
- **No blue fill (S1, P1):** every Share control is the 40 px outline button ("Make public", "Stop
  sharing publicly", "Copy link", "Make private", "Share with organisation"); "Keep private" and
  "Remove" are the 40 px ghost; the "Add to a project" select is 40 px.
- **Making it public (S3):** "Make public" opens a second step inline: "Anyone with the link can
  read the report, the source list and the quoted excerpts, without signing in." with "Make public" and "Keep private"; focus moves to the sentence, Escape or
  "Keep private" closes it and returns focus. No modal, no motion. Public: "Public. Anyone with the
  link can read it.", the link in a read-only field (selected on focus) with "Copy link" beside
  it and "Copied" beside that for 2 s in a slot of its own; a failed copy selects the field and
  says "Couldn't copy. The link is selected." on the line under it. No toast for the public
  toggle (P4); the organisation change keeps its binding outcome toast (rubric 41).
- **In a project (S4, P3):** no "Make private" or "Share with organisation"; the line "Follows its
  project: <name>." (projects, plural, with each name a link).
- **A colleague (S5, S8):** the three states without controls: the public state line, the
  organisation state, the projects as links; no Remove, no select. A refused change shows the
  server's message under its section ("Only the task's owner can change its projects."), else the
  section's own "… couldn't be changed. Try again."
- **No projects (P5):** "Not in a project." and, for the owner with no project to add it to,
  "Create one in Projects." with Projects a link.
- **History by day (H4):** rows grouped by local day under a Meta Semibold Navy heading ("Today",
  "Yesterday", else "Tuesday 3 November 2026", en-GB), sticky at the top of the pane from `md` up;
  each row shows "09:02" (en-GB, local) in a 3.5 rem Meta Grey tabular column, the whole timestamp
  in `dateTime` and the hover title.
- **History rows (H1, H5, H9, H10):** below `md` the time sits over the sentence. No chips; only a
  failure keeps the 6 px Red square before its sentence, which says what failed. A row with
  details is a disclosure (`aria-expanded`, the 12 px chevron, the Blue Wash hover, the ring inset
  2 px); a row without is plain text. Details open under the sentence column over 200 ms, Paper,
  no rule, Label then Body Ink within 44em. The frame no longer clips.
- **Turns (H3, H6, P7):** a part card's press reads as the choice ("You chose “Standard depth”."),
  a scope edit as "You changed the scope:" with one line per change, the opening turn "You asked:
  “…”", later free text "You wrote: “…”", a failed turn adds "This didn't send."; the owner's
  name for a colleague, "Someone" when the server sends none. The decision log's sentences are the
  server's, which already name who acted for this reader (H2, H6).
- **Runs (H7, P10):** each run is one row at its start, "Ran the evidence search · 36 min" (else
  "The evidence search stopped · 12 min" or "… didn't complete · 5 min" with the Red square, "… is
  waiting at a check-in", "… is running"), with "Show steps" / "Hide steps" and the chevron under
  it, the trace's quiet control. The steps open over 200 ms on a Line 2 spine in the sentence
  column, 1.5 rem tighter than a row; the search row opens to every query. The check-in answer,
  the plan approval and the lifecycle changes stay rows of their own.
- **Loading and failure (H8):** nothing but the skeleton until both reads land (a day-heading bar
  over five 48 px rows of a time bar and a sentence bar); a failure is the list's frame with "The
  history couldn't be loaded." and a 40 px ghost "Try again"; empty is the frame with "Nothing
  yet." and "Your question and what follows will be listed here." (P11).
- **Account menu:** the "Administrator" line is Grey, not Electric Blue (blue is the one pen).

## Round 10, the Sources table and the Landscape years (owner and lead, 2026-11-06)

Brief: `research/briefs/round-10-sources.md`; the review `research/sources-table-polish.md`
(findings 1 to 16, built as proposed) with the lead's rulings; screenshots in
`research/screenshots/round10-sources/`. Built as below (DESIGN.md § The sources table and
§ Charts carry each rule).

1. **One filter row.** The screening toggles as their own group ("Screening"), Cited, then
   visible bordered selects for Key theme, Origin, Evidence type, Strength, Country and Year
   (the invisible native selects in the headers are gone); every control at least 24 px tall;
   "Clear filters" at the row's end once a filter besides the screening choice is set. The
   Year control's name carries the range ("Filter by year: 2015 to any"). Below `lg` a "Sort"
   select joins the row. The headers sort only.
2. **Columns.** Origin and Cited fold into the source's second line ("Venue · Origin", the green
   "Cited" chip at its end). **The provider labels stay "OpenAlex" and "Overton"** (owner ruling
   2026-11-06; the review's "Research" / "Policy document" is not taken). Six fixed columns;
   values plain Meta text that never wraps (an ellipsis when too long), the evidence type in
   sentence case from the report builder's formatter (`evidenceTypeLabel` in
   `artefactPresentation.ts`); "Cited" the one chip.
3. **The read-depth header stays "Status"** for now: the owner is choosing its name (the lead
   has proposed "Depth"); it is one constant, `STATUS_COLUMN_HEADER` in `sourcesPresentation.ts`.
4. **Headers on one line** at the Caption label size, each a 24 px sort button with a reserved
   12 px arrow, so labels and arrows share one baseline (owner, round 10: no two-line header).
5. **The Relevant figure** right-aligned in tabular figures after a 12 px tick or cross; its
   name carries the figure ("Relevant, 99% confidence: screening details").
6. **Hover reasons leave the tab order** (lead): the cells' reasons stay on hover; the title is
   the row's one tab stop, the dossier the keyboard's way to the same words. A row washes Paper 2
   under the pointer and while focus is in it.
7. **Download CSV** is the 40 px outline button on the count line's row. The view has no
   primary: the table has no single forward action (lead, round 10; this reverses the
   consistency sweep's count of Download CSV as this view's one primary).
8. **States in the table's frame**, copy as written in the review: loading (the real header and
   six placeholder rows at 88 px), "No sources yet" / "They appear here as the search finds
   them.", "No sources match" / "Clear the filters to see all 52." with "Clear filters", and
   "Sources couldn't be loaded." with a 40 px ghost "Try again". The count line reads
   "1–50 of 52 sources" on a paged list. Pagination is shared with Findings (`Pagination`): 40 px
   outline buttons, "Page 1 of 2" at Meta, and a page change starts at the new page's top.
9. **The frame**: hairlines above and below, no card, no shadow, no header band; the queries
   block keeps 32 px of air above the filter row.
10. **The stacked row** holds below `lg`, not only below `md` (agent, for the lead to confirm:
    from 768 to 1023 the six columns leave the title under 100 px). Title, "Venue · Year ·
    Origin" and the chip, then the values in column order, each carrying the dot to the next
    so a wrapped line never starts with one, placeholders in their slots.
11. **The automatic switch from All to Included** when screening completes stays as N16 rules;
    flagged for the review (it moves the table without the reader acting).
12. **The Landscape years** (owner): press and drag across the columns chooses a range, the
    covered columns Electric Blue as the pointer moves, a Meta label above them "2015 to 2020",
    release opens All sources for the range; one click opens one year; from the keyboard the
    chart is a listbox (arrows move, Shift extends, Enter opens, Escape drops); touch drags the
    same way with the label in a band above the columns; colour is the state, so reduced motion
    changes nothing. The chart is HTML now (Recharts left this file).
13. **Countries link** to All sources (`?country=`, the backend's round-10 filter); "Not
    reported" and the folded tail stay unlinked.
14. **The Sources tab remembers the subtab** the reader last chose on a task (owner, round 10):
    the stage-driven landing applies until they choose; from then their choice wins, live or
    done, until they choose another. Kept per task in `localStorage`; a storage failure falls
    back to the landing rule (`sourcesSubtab.ts`, `withSourcesLanding`).

## Round 10, Options scoping (owner and lead, 2026-11-06)

Brief: `research/briefs/round-10-scoping.md`; the review `research/options-scoping-polish.md`,
findings 1 to 15, with the lead's rulings. DESIGN.md § The longlist (Options scoping) carries
each rule. Screenshots: `research/screenshots/round10-scoping/`.

1. **Themes open by default** (D1) behind one switch, `THEMES_OPEN_BY_DEFAULT` in
   `LonglistView.tsx`, for the owner to decide (it reverses the 2026-09-23 ruling); the excluded
   options stay collapsed.
2. **One page, one row, one title.** `LonglistBuilding` and `LonglistView` are one component, so
   the walk's end gains controls without remounting the page; the title is "Longlist" with the
   question under it (D2); the row's anatomy holds from the first row (name, origin words, its
   search at the right, description, one meta line, the exclusion, the folds). Rows move into
   their themes in a 300 ms View Transition; the list never blanks; reduced motion cuts.
3. **Switches**: Group by and List / Grid are the outline switch; no grid below `md`. The Result
   tabs take the growing rule and stay on one line, the Report tab locked without its note.
4. **Shortlist page**: Assess is the one primary with its reason under it; Suggest more is an
   outline secondary with its reason as words; the risk appetite is a full-width field to 32rem.
5. **Marks** (D3): a searching row breathes the 6 px blue square; the longlist's stage line goes,
   the status bar says the words; one turning mark per screen.
6. **The shortlist toggle** in words ("Shortlisted", pressed / "Add to shortlist"); the meta line
   is fixed fields, wrapping whole; "No in-scope evidence" and "Excluded:" as words, red only on
   the failure word.
7. **The option card** says each thing once; the notices are a flat block; "Documents" uses the
   chevron with Show / Hide; the profile says "Middle on N of M" once; one Navy look for marked
   values with the direction word.
8. **The baseline gate** takes this week's check-in form (question title, facts line with
   "Baseline →", the key assumption as a sentence); its settled form is built
   (`SettledGateCard`) for `TaskAgentPane` to use in place of the user bubble and the recorded
   line.
9. **Links** (D4): `rowLink` covers the longlist walk ("Longlist →" on the step in progress, from
   Suggesting options on; round 11: its Searching, Screening and Classifying rows take the
   Evidence search's links) and the baseline walk (as an Evidence search, Writing → "Baseline →").
10. **The plan card** shows "Scoping plan · <time band>" as the annex has said since the build
    (the annex winning over the build).
11. **Copy accepted from the review**: C1 (one origin vocabulary), C4 (no kind labels, "Read
    from titles and abstracts", "Why:", "Not covered:"), C5's "No line stands out", C7, C9, C10
    ("The plan has changed. Suggest more to update the picks."), C11 ("Excluded" with its count).
    Not taken: C2 (the toggle's words rule), C5's "Typical" (the lead kept "Middle"), C6 (Assess
    stays as the primary).

Applied after the other builders finished (lead, 2026-11-06): the settled gate renders
`SettledGateCard` for a gate decision in the thread (no user bubble, no recorded line); the Result
tabs take the growing rule and the Report tab is locked with no note (C3); the status bar's
"Baseline →" hides while the Result tab shows the baseline; the "where" place loses its aqua tint
for the Navy square; the shortlist's title is "Shortlist" with the question under it. The New
page's eyebrow had already gone with the lists round. D1 stays open for the owner; the agent's
rulings below are confirmed by the lead.

Rulings on the build (agent, confirmed by the lead):
- The count is said once (R85): a row's right-hand line is its own search until the longlist read
  has the option, then the meta line's evidence signal says the documents; the annex's
  "Shortlist · 38 documents" becomes "Shortlisted" with the count on the meta line.
- The building rows show the option's description, as the finished rows do (one anatomy).
- Under a lever heading the row leaves the lever out, as a theme heading leaves the theme out.
- "Show all" / "Hide all" on the longlist is the page's own control (it starts as the D1 switch
  says), since the report's shared control always starts on "Show all".

## Round 11, lists (owner, 2026-11-06)

The owner's note: the third switcher entry, "Archived", listed only the reader's own archived
tasks whatever the scope, and the page never said so ("not clear"). Rule: Archived is not a scope.
This replaces round 10's "Archived" entry above. The owner then made three changes during the
round, relayed by the lead; the bullets give the final shape.

- **The switcher** keeps Mine and Organisation only.
- **The archived toggle** lists the archived tasks of the open scope: the reader's on Mine
  (`scope=mine&status=archived`), the organisation's on Organisation (`scope=all&status=archived`,
  asked for only once open), unscoped for a reader with no organisation. Off, the list is the
  active tasks as before. The scope holds across the toggle and the toggle across the scope.
- **Where and how it looks** (owner: the first build's outline button "doesn't need to be as
  prominent"; then the quiet control in the filters row "takes up a bit too much space for a
  button that people will hardly ever use"): at the list's foot, right-aligned in the row where
  "Show more" sits (alone when there is no more), under every state of the list. The quiet control
  of "See the plan" and "Show steps" (`QUIET_CONTROL_CLASS`) at Caption: "Show archived" off, "Hide
  archived" on; the changing label carries the state, with no `aria-pressed` (lead ruling: it
  would say the state twice). Its box is the foot row's 40 px and holds the wider label's width,
  so the words never move its edge.
- **On:** the list carries the heading "Archived" (an h2, Meta Semibold Navy, 8 px over the frame).
- **Source count:** a failed run shows the dash whether or not the task is archived (lead ruling;
  round 10 had kept the count on archived rows).
- **Owner column:** off on Mine, archived or not; on Organisation, archived or not, the reader's own
  rows "You".
- **Empty:** "No archived tasks" in the list's frame, no sentence under it; "Hide archived" stays
  under it as the way back.
- **Shown always** (build's reading; no note says otherwise): the toggle is there whether or not the
  open scope has archived tasks, so it never appears or leaves under the reader. Round 10 showed
  the entry only while the reader had archived tasks; the lead may restore a condition.
- **Find** (owner, the lead's recommendation accepted): "Find a task" / "Find a project" leave the
  header, which keeps only the primary. A magnifier (the icon module's new `SearchIcon`, 16 px in a
  40 px target, the quiet control's Grey and Navy hover, the house focus ring, `aria-label` and a
  tooltip below it naming it) ends the filters row on Tasks and Projects, after the admin's note;
  its glyph sits on the column's right edge (`-mr-3`). The same popover opens from it. On a
  project's page the magnifier sits before Make private in the filters row (build's reading of
  "the header keeps only the primary"). The filters row holds only the switcher and the magnifier.
- **Projects** (owner addition: projects can now be archived): the Projects page takes the same
  toggle, heading and foot row, listing the archived projects of the open scope through the
  projects list's `status` parameter (`scope=mine|all&status=archived`, or `status=archived` alone
  with no organisation), "No archived projects" when there are none. `ProjectsQuery.status` in
  `api/queries.ts` matches the generated types. The project row has no status word (name,
  owner, task count, date), so an archived project's row is left as it is. The menu that archives a
  project is the workspace builder's.

## Round 11, Options scoping (owner, 2026-11-06)

Brief: `research/briefs/round-11-scoping.md`. DESIGN.md § The longlist carries each rule.
Screenshots: `research/screenshots/round11-scoping/`.

1. **Names while clustering.** While "Clustering into options" runs, the option names the step
   publishes (the Themes frame with `stage: "longlist"`, the backend builder's this round) join
   the page as rows the moment they are named: a name no read has yet joins at the end, and
   every row not yet on the longlist reads "Assigning sources" after the
   breathing 6 px blue square. When the step commits, the longlist read brings each row's
   evidence line, which says the count; the row a published name drew keeps its place and key
   (its View Transition name is its name's), so it neither remounts nor rises again. During
   "Grouping into themes" (`stage: "theme"`) the theme names stand as headings under the rows,
   rising 60 ms apart, before any option is in them (no count beside a heading with no options);
   when the step commits the rows move under their themes in round 10's View Transition, and a
   heading the step named keeps its key, so it stays where it is. The page never blanks: the
   rows stay through both steps and the handover.
2. **The shortlist toggle** says what pressing it does: pressed, "Shortlisted" after a 12 px
   check (the Sources table's tick stroke, in Navy); on hover and keyboard focus its words become
   "Remove from shortlist"; unpressed, "Add to shortlist". All labels share one grid cell, so the
   button is always as wide as "Remove from shortlist" and neither the swap nor a press shifts
   the row; the words sit at the cell's end where the toggle closes a row (the longlist row from
   `sm` up, the option card, the Shortlist page) and at its start on a grid tile and a phone's
   row. The swap is a cut, never on touch, and not shown to the pointer that just pressed until
   it leaves and comes back, so the words that answer a press are the new state's. `aria-pressed`
   is kept and the accessible name stays the resting words ("Shortlisted", "Add to shortlist").
   The same component serves the longlist, the grid, the option card and the Shortlist page; the
   building list's "Shortlisted" words take the same check.
3. `THEMES_OPEN_BY_DEFAULT` is unchanged (the owner's decision is pending).
4. **The option card** (owner: "inconsistent text sizes, random bolding, not well organised
   information"). Before: `screenshots/longlist-ux-review/before-{rich,excluded}-{opened,expanded}-{1280,400}.png`;
   after: the same names with `after-`. Three blocks under the one rule: what it is (title,
   description, the origin line, How it works), What it would take, Where it stands (the notices,
   "Sources" with the evidence signal on one line and the standing, your outcomes, places,
   documents). Sizes and weights changed: the description and every section's prose from Lead
   (`REPORT_BODY_CLASS`, 19 px from `md`) to Body; the header's origin line from Body to Meta;
   the evidence signal from the header's Body Navy line into Where it stands at Body Ink; the
   profile's line names from Body Semibold Navy to Meta Grey regular, its sentences from Lead to
   Body; "Lever:" from Bold Navy inline to the field label (Meta Grey) over a regular value;
   "Your outcomes", "Where it has been evaluated", "Documents · N · …" and the document groups
   from Body Bold Navy to the field label; the place names from Bold Navy to regular Navy; the
   maturity line from Semibold Navy to regular Ink; document titles from Bold underlined to the
   prose link at Body; programme names from Bold to regular inside their Meta line; the
   outcome counts from Body to Meta Grey. The third section's title is "Where it stands" (the
   lead's word in the brief; it was "Evidence").
5. **The longlist** (owner: "very dense … overwhelming when a user first lands on it"; "general
   UX/UI principles"). The review is `research/longlist-ux-review.md` (24 findings, before
   screenshots `before-list-*`, `before-grid-1280`); after: `after-list-*`, `after-grid-1280`,
   `after-list-closed-*`. Fields moved: the origin words, relations, the evidence signal's later
   parts ("4 more describe it", "Evaluated in …", "Measures N of your M outcomes") and the folded
   suggestions ("Folded into …") left the row for the option card (its origin line, "also found
   as" and Where it stands); "Read from titles and abstracts" moved from the header to the
   list's foot; the theme heading's instrument nouns went (the lever is on every row and Group
   by Lever type answers it). The count line gains "N shortlisted". Theme, lever and Excluded
   headings are the Label style with the count beside them and one Body Grey description line;
   rows 16 px apart without rules, groups 32 px apart; the toggle is regular weight on the list;
   on a phone the controls close the row. Show all moves into the controls row.
6. **One switch** (lead): `ui/brand/OutlineSwitch.tsx`, 40 px on the longlist, 32 px for the
   Landscape's List · Map (its twin `ViewSwitch` removed).

Rulings on the build (agent, for the lead):
- The frame carries names and descriptions only, so a row's count arrives with the committed
  longlist (its evidence line), not batch by batch, and the options move under their themes when
  the theme step commits, not as each is assigned. Per-batch counts and per-theme membership
  would need the frame to carry them (see the report).
- Review findings not built, for the lead: 10 (the growing rule for the switches; DESIGN.md
  and round 10 say the outline switch, and the lead asked for it as a shared component), 18
  ("Show all N" stays a button), 24 (the row's profile summary: copy for the lead, see the
  report), and the ruling conflicts listed at the end of the review.
- "Assigning sources" goes on every row not yet on the longlist, the suggestions included, since
  the assignment runs over all of them; a row's own search line ("Searched · 312 found") gives
  way to it.

## Round 12, Options scoping (owner, 2026-11-06, evening)

Brief: `research/briefs/round-12-scoping.md`. DESIGN.md § The longlist carries each rule.
Screenshots: `research/screenshots/round12-scoping/` (`before-*` and `after-*`).

1. **D1 is closed: the groups are collapsed by default** (owner: "the groups should be
   collapsed by default"). `THEMES_OPEN_BY_DEFAULT` is gone. A finished list opens on the count
   line and every group heading shut with its count; "Show all" in the controls row opens them.
   While the walk builds the list its groups stay open (the rows moving into their themes are
   the news), and the walk's end leaves them as the reader has them; only an arrival on a
   finished list starts shut (`after-list-arrival-*`, `after-list-shown-*`).
2. **"Where it stands" is "Evidence" again.** Its "Sources" lines are one short sentence per
   fact at Body, nothing bold, in the owner's order: the documents that describe it (those that
   do not evaluate it, as the document groups below split them), the documents that evaluated
   it, where it was evaluated, how many of the user's outcomes it measures; the last two only
   once something evaluated it; the standing after them as its own line. Your outcomes, the
   places and the documents (prose links) stay under them. The collapsed section keeps the
   one-line signal as its summary (`before-card-*-evidence-*`, `after-card-*-evidence-*`).
3. **"Policy Atlas's estimate" is an info hover**: the heading loses the words; a 16 px "i"
   (`InfoIcon`, added to `ui/brand/icons.tsx`) in a 24 px target sits just after "What it would
   take", focusable, named "Policy Atlas's estimate", its tooltip "Policy Atlas's estimate from
   the sources." (owner correction: nothing about costing) The heading is a disclosure button and a button cannot hold
   another, so the glyph's button sits beside it, placed after the title's last word by
   measuring the title's text (kept there on reflow and font load); a press on it does not fold
   the section (`after-card-*-info-hover-*`, `after-card-*-info-focus-*`).
4. **The check-in card's words option**: `CheckInCard` renders no planner decision part (the
   scoping planner's `my_own_words` reaches only `PartCard`); a check-in option asks for words
   by the server's `requires_user_input`. No change.
5. **The count on the group's line** (owner: "the 'N options' next to the groups should be
   under it instead, or right aligned on the same line?"; lead: right-aligned on the heading's
   line). "6 options" sits at the line's right in Meta Grey, regular case, on one line at every
   width; the count lost its tabular figures, which opened a gap after a single digit.
6. **One dropdown** (owner: "When there are dropdowns in the app, make sure we use the custom
   styling and not the browser default"). `ui/brand/Select.tsx` is the Sources filter bar's
   popover listbox made shared: the field as the trigger (40 px Body or 32 px Meta, the 12 px
   chevron, Navy border while open), a select-only combobox; the list in the popover's tokens,
   as wide as the trigger; arrows, Home, End, first-letter type-ahead, Enter, Escape. On a phone
   the list opens as the popover does, never the platform's picker. `longlist/FieldSelect.tsx`
   is gone; the grid's Columns, the risk appetite (shortlist 40 px, plan document 32 px), the
   check-in's steering mode and Share's add to a project use it (`after-select-*`). DESIGN.md
   § Inputs carries the one-select rule.
7. **One right edge** (owner): a group heading's "Show" / "Hide" moves to the line's right,
   after the count, and "Show all" ends the controls row after List · Grid, so every count and
   control on the longlist sits on one right edge (`after-list-*`, `after-list-heading-hover-*`).
   This replaces item 5's "the chevron with the name".
8. **The controls row's rules come back** (owner): a Line hairline above and below Group by,
   List / Grid and Show all, 12 px inside each, as before round 11's density pass
   (`after-list-*`).
9. **No contents sidebar on the longlist** (owner): the list and the grid take the page's full
   content column (1180 px) rather than the report's reading measure; the Shortlist page has no
   nav and gets none; the baseline report keeps its contents. A link to a group still opens it
   (`useOpenWhenNavigated`).
10. **Group names in Navy** (owner: "not a massive fan of the grey text for the groups … hard
    to read in the collapsed view"): the heading's name is Navy at the Label style; the
    description stays Body Grey and the count Meta Grey, shut and open alike.
11. **The baseline gate shows no key assumption** (owner): the card loses the line; its settled
    form never had it. Everything else stays.
12. **Shortlisted first** (owner): within each group and each grid cell the shortlisted rows
    come first, the rest after them in their existing order (`shortlistedFirst`, one function
    for the list and the grid); a toggle moves the row in the regrouping's View Transition
    (`regroupTransition.ts`, now shared by the list and the grid), never a blank.
13. **The dossier opens over the option card** (owner bug: a document jumped to the Sources
    tab). A document's link (and its "+N more") is now the card's own path with `?source=` and
    `option=`; the card reads them and opens the Sources tab's dossier sheet over itself
    (`longlist/OptionDossier.tsx`: `SourceDossierBody` and `useDossierRecords` from `SourcesView`,
    read by the document's id), its slot reading "In this option". Close or Back returns to the card; the URL never leaves it
    (`after-card-*-dossier-*`).
14. **An option opens at its top** (owner bug: it opened at the foot, the app's scrolling pane
    keeping the longlist's offset). Once per option the card sets its scrolling ancestors to the
    top and focuses its title (`tabIndex=-1`, no ring); a link with a hash keeps its scroll, and a
    dossier or a notice never moves the reader.
15. **What a theme and a lever are** (owner, with the owner's corrections): an "i" beside Group
    by (`longlist/InfoHint.tsx`, the estimate's device, now shared), its tooltip two lines and
    nothing else: "Theme: a group of options that work in a similar way." / "Lever: the kind of
    action government takes." No intro sentence on the page.
16. **The count line counts levers** (owner): "24 options in 5 themes and 3 levers · 5
    shortlisted", the levers the distinct lever types of the included options (`leverCount`),
    singular "1 theme", "1 lever"; one formatter (`countsParts`).
17. **Read-only on the public link** (owner): under `usePublicView()` the longlist, the grid,
    the option card and the Shortlist page change nothing: a held place reads "Shortlisted"
    after its check as plain words (no toggle), no Exclude or Include again, no Add an option,
    no Suggest more or "Add more from the longlist", no Assess, the risk appetite as its words;
    the group controls, Columns and the dossier stay. With no picks the line drops its second
    sentence ("No picks beside your places."), since Suggest more is not there.
18. **"What it could take"** (owner): the heading's words, on the card and in DESIGN.md (the
    section's anchor id stays `what-it-would-take`; the backend's card export still says
    "What it would take", outside this brief).
19. **The profile's shut sentence** (owner): one Body sentence built from the marked lines
    (`profileSentence`, phrase table `PROFILE_SENTENCE_PHRASES` and `AMBITION_OPENINGS` in
    `longlistPresentation.ts`) replaces the marked cells and "Middle on N of M"; the ambition
    opens it, the harder lines follow "that will" joined with "and", then "but" and the easier
    ones; all in the middle, "A middle option on every count."; a line the profile lacks is left
    out; open, the table.
20. **Block order** (owner): what it is, then Evidence, then What it could take.
2. (changed by the owner) **Evidence** is no longer the Sources lines: the subsection, its
    standing line and Your outcomes went. Evidence is "Where it has been evaluated" (item 23:
    first), the notices, then the documents listed open (no disclosure) with each group's
    "Show all N", and one Meta Grey outcomes line at their foot ("Measures 2 of your 2
    outcomes."), the one fact that lived only in the Sources lines.
21. **Excluded rows** (owner): the row keeps every other row's sizes; the exclusion line is the
    meta line's Meta Grey, no red word, so the grey alone marks an excluded row; the grid's
    excluded tile says "Excluded" in Grey, not Red.
22. **The exclusion line** (owner: "Breaks your decision" was unclear): `exclusionLine`, one
    formatter for the row and the card's notice: "Set aside by you · <reason>" (reason left out
    when empty) for the reader's own, "Breaks "<constraint>" · <reason>" for a constraint's.
23. **Where it has been evaluated first** in Evidence (owner), the notices and the documents
    after it.

Lead's rulings on the report (2026-11-06): 1, 3, 4, 7 and 8 accepted as built. 2: the four
helpers left unused (`servesOutcome`, `noOutcomeMeasuredLine`, `outcomeCountLabel`,
`maturityLine`) and their tests are deleted. 5: the "i" works on touch: `InfoHint` opens its
words as a small popover (the popover's tokens) on a tap and as the tooltip on hover and focus,
one component. The phrase table is accepted with "need more coordination" / "it needs less
coordination". 6 (the mock's dossier for the card's document ids) goes to the backend builder.

24. **The sentence's takeaways** (owner): the ambition word and each line's phrase in Semibold
    Navy, the joining words regular (`profileSentenceParts`). Every line in the middle reads
    "**Average** on cost, time, workforce, coordination, delivery and impact." (owner: "A middle
    option on every count." was ambiguous).
25. **The documents are a disclosure**, closed: "Show 6 documents" / "Hide documents" after the
    12 px chevron, the quiet control's look; open, "Read from titles and abstracts only." then
    the two groups with their "Show all N".
26. **No "+N more"** (owner): the other records a document was folded from are words on its
    facts line ("also found as 2 other records"), not a link; only the title opens the dossier.
27. **A document is two lines** (owner): the reference in the References form (`referenceParts`:
    authors, year, the title as the link, the venue in Grey as the report's list; the backend
    builder added `authors` and `venue` to `OptionDocumentOut`; a part the read lacks is left out), then one Meta Grey line of facts joined by the middot (`documentFacts`: "evaluated in
    <place>" or the place, the design, "measures <outcome>", "also found as N other records");
    the programme, the folded kind and the tier went, and the standalone outcomes line went.
28. **The card at the report's scale** (owner: "a bit hard to read compared to the evidence
    search reports"). Changed: the description under the title, every section's sentences (the
    lever, the lead-in, the features, the places, the notices, the profile table's sentences)
    and the profile's shut sentence from Body to `REPORT_BODY_CLASS` (Lead 19 px from `md`,
    Body on a phone); the features list's gap from 4 px to 8 px (the report's list rhythm); a
    document's title link from the prose link (always underlined, blue on hover) to the
    References' title (Navy over a Line 2 underline, Navy on hover), its reference line breaking
    anywhere as the References do; its facts line 4 px under the reference (was 0); documents
    12 px apart (was a 12 px grid gap; the References' 8 px is for one-line entries, a document
    is two). Kept: the title and section headings (already the report's components), Meta for
    the field labels, the documents' note and group labels and the facts lines; nothing is
    smaller than Meta. Before and after: `r28-{before,after}-card-{rich,excluded}-whole-{1280,400}.png`.
29. **No eyebrow over the lever** (owner): How it works opens with one sentence, "Lever:
    regulation." (`leverLine` now uses the lever nouns: "Lever: enforcement, with regulation.").
30. **"Where it has been evaluated" is a subheading** (`h3`, the report's case-study title
    style: Lead Bold Navy, Body below `md`).
31. **The document groups are subheadings** (`h3`, Body Semibold Navy): "Evaluated it · 2".
32. **A document's facts** are Body Grey lines under its reference (`documentFactLines`): "Evaluated
    in the United Kingdom · Randomised or quasi-experimental study · also found as 2 other
    records" ("Described in …" for a document that only describes; the design through
    `evidenceTypeLabel`), then "Measures <outcome>" on its own line when there is one.
33. **The report's square bullets** (owner): the design features use `ui/brand/BulletList.tsx`,
    the report's 6 px Electric Blue square on the x-height, items 12 px apart. The report keeps its
    own class constants in `ArtefactView.tsx`; the report builder can swap them for
    `BULLET_ITEM_CLASS` / `BULLET_MARK_CLASS` from that module so there is one source. Shots:
    `r29-after-card-{rich,excluded}-whole-{1280,400}.png`.
34. **The estimate's words** (owner): "Policy Atlas's estimate from the abstracts. Not an
    assessment."
35. **The profile sentence always opens with the ambition and the potential impact** (owner),
    middle or not: "This is a[n] <ambitious | moderate-ambition | modest> option with <high |
    average | lower> potential impact" (owner: the middle says "ambition") (`AMBITION_WORDS`, `IMPACT_PHRASES`; the ambition word and the
    impact phrase strong), then " that will <harder lines>, but <easier lines>." as before; with
    only easier lines ", and <easier lines>."; with every other line in the middle ", and average
    on cost, time, workforce, coordination and delivery." (`OTHERS_MIDDLE_TAIL`). Potential
    impact left the phrase table; the old all-middle sentence went.
36. **The documents toggle carries the groups** (owner): "Show 6 documents · 2 evaluated it · 4
    describe it" (a group with none left out; "1 describes it"), "Hide documents" when open.
37. **No evaluation, said** (owner): with no document evaluating the option, "Where it has been
    evaluated" stays with one Body Grey line, "Not evaluated in any of these sources."
    (`NOT_EVALUATED_LINE`), then the documents disclosure.
38. **Only What it could take folds** (owner): How it works and Evidence are always open with no
    Show / Hide (`CardSection` is not collapsible unless asked); What it could take (shut, the
    sentence; open, the lines) and the documents list keep theirs.
39. **Discusses, not Measures, for a describing document** (owner): the outcome line reads
    "Measures <outcome>" on an evaluation and "Discusses <outcome>" on a document that only
    describes, recommends or mentions the option (`documentFactLines`).
40. **Your outcomes** (owner): a subheading in the Evidence block's subheading style after
    "Where it has been evaluated" and before the notices and the documents, then a ruled table in
    the report's method-table pattern (Line hairlines, Body, the label left, the value right in
    tabular figures): one row per plan outcome in the plan's order, "Measured in 2 · discussed in
    1" in Navy (a part with none left out), or "Not covered" in Grey (`outcomeCoverage`,
    `outcomeCoverageWords`: an evaluating document whose outcome tag names it measures it, any
    other discusses it). Absent when the plan has no outcomes.
41. **The plan's target first** (owner; corrected twice: the target is not always people, so no
    "population" anywhere, and the word is "targeted"): the table is "Your target and outcomes";
    its first row's label is the plan's target-unit words as the user wrote them, its value
    "Directly targeted in N" in Navy, or "Not directly targeted" in Grey (owner: no "of M
    documents"), and nothing else (`targetCoverage`, `targetCoverageWords`); the row is left out
    when no document's target is known. Whom the option acts on is not counted from the
    documents: it is the model's setting call, the profile's `acts_on`, said in How it works as
    "Acts on **food outlets**, **parents** and **councils**." after the setting (`actsOnParts`;
    " and k more" beyond six; omitted when empty). The table is absent when the plan has no
    target unit and no outcomes. Under each document the facts are three lines: the place and design (and "also
    found as N other records"), "Targeted <kind>" when known, then "Measures / Discusses
    <outcome>". The coverage cells take no tabular figures: under them the fallback face widens
    the spaces between words.
42. **The takeaway words in How it works** (owner): the lever nouns ("Lever: **regulation**.")
    and the delivery setting ("Delivered **in jobcentres and in community centres**. It
    typically involves:") in Semibold Navy, the rest regular (`leverLineParts`,
    `deliveredLeadInParts`, rendered by the card's `SentenceRuns` as the profile sentence is).

Round 12 follow-up (owner, items 43 to 49, on the committed round):

43. **A document's facts as a labelled list** in the dossier's facts pattern (`documentFacts`):
    the label at Meta Grey in a 6.5rem column, the value at the block's size in Ink; rows Where,
    Type, Targeted, Measures or Discusses, a row with no value left out; no middots.
44. **"Type"**, never "Design": the classifier's evidence type through `evidenceTypeLabel`, the
    Sources table's Type column.
45. **No "also found as N other records"** on the card; the dossier keeps the provenance.
46. **The plan's place has no mark** in "Where it has been evaluated"; leading the list is enough.
47 and 49. **What it could take, shut** (49 replaces 47's sentence): an intro line at the
    block's size, "Compared with the other options on the longlist, this option is:" (the marks are relative across
    the list), then the shared `BulletList`: the ambition first ("Ambitious" / "Moderate
    ambition" / "Modest"), the potential impact second ("High / Average / Lower potential
    impact"), then one point per other line not in the middle (`PROFILE_POINTS`: "Costs more" /
    "Costs less", "Longer to set up" / "Quicker to set up", "Slower to show results" / "Shows
    results sooner", "High workforce requirements" / "Low workforce requirements", "Needs more
    coordination" / "Needs less coordination", "More complex to deliver" / "Simpler to deliver"),
    or "Average on cost, time, workforce, coordination and delivery"; no bold, no full stops
    (`profilePoints`; the sentence builder and its phrase table are gone). Open, the lines.
48. **One reading size in Evidence** (owner): the "Your target and outcomes" table and the
    documents' fact values lose their own Body size and take the block's (`REPORT_BODY_CLASS`), as
    the places list; only the labels are Meta.
50. **The documents not dense** (owner, changing 43): one size for a whole entry, the block's
    reading size; the fact labels the same size in Grey in a fixed 7.5rem column (6.5rem on a
    phone), the values in Ink wrapping freely; the group headings and the "Read from titles and
    abstracts only." note at the same size; 20 px between documents with one hairline between
    them; nothing smaller.
51. **Under the list, "See these 12 documents in Sources"** ("See this document in Sources" for
    one; `seeInSourcesWords`), a prose link to `/tasks/{id}/sources/all?option={optionId}`.
52. **Every point relative to the longlist** (owner): the ambition "More ambitious" / "Average
    ambition" / "Less ambitious"; the impact "Higher / Average / Lower potential impact";
    workforce "Higher / Lower workforce requirements" (`AMBITION_POINTS`, `IMPACT_POINTS`,
    `PROFILE_POINTS`).

## Round 11, Sources (owner, 2026-11-06)

Brief: `research/briefs/round-11-sources.md`; screenshots in `research/screenshots/round11-sources/`
(`before/` and `after/`). Built as below (DESIGN.md § The search queries, § The sources table,
§ Charts and § Navigation carry each rule).

1. **Hover affordance.** The evidence type, the strength, the Relevant figure (and "retracted")
   and "Abstract only" carry their word under a dotted Grey underline 3 px below with the help
   cursor (`sources-hint-word`); the title stays the row's one tab stop.
2. **Strength's tone.** The 6 px square before the word: Green for Very strong and Strong, Navy
   for Moderate, Grey for Limited, Weak and Unrated (`strengthTone`). Limited sits with Weak (the
   brief names strong, moderate, weak and not assessed); a tier outside the vocabulary has no
   square.
3. **The filter bar.** One row of 32 px outline controls at Meta on one baseline, 8 px apart on
   every wrapped line: the screening choice as the outline switch, Cited, the facets idle as the
   outline button naming the facet, an applied filter a filled Navy chip ("Strength: Moderate ×";
   the words reopen the choices, the × clears it), Clear filters, and Download CSV at the right
   end. The labels left of the controls are gone (the control names its facet); the Year
   popover's "Clear" link is gone (the chip's × does it). It fits one row at 1280 with the
   fallback face; with a long applied value it wraps.
4. **Search queries, completed.** No card: one Meta Grey line above the filter bar, "Found with 5
   queries and 1 citation pass · Show", with the one disclosure. Open, ruled rows at Meta and the
   table's width: the query in Navy, the database in Grey, the count right-aligned; a citation
   pass its own Grey row in the past tense ("Followed citations from 50 sources"). The saved
   coverage now carries the passes (`CoverageBackendDetailOut.passes`, worded for a finished
   search, in the order run), so the line and the rows hold after a reload; the browser rewords
   only the stream's present tense until the saved coverage lands. The live list is unchanged and still folds over
   200 ms when the search ends. Reading taken: "the pass name in Grey" is the database each
   query went to, one Grey column, in place of the round-9 group labels.
5. **Inactive subtabs** `font-medium text-grey`, hover Navy; active `font-extrabold text-navy`.
6. **Funnel links.** Found → `?status=all` (the brief's "none for Found" would land on the
   Included default once screening is done, so the link names All), Relevant → `?status=Included`,
   Cited → `?cited=true`. Quality-checked, Full text and Shortlisted have no filter on the table
   and take no link.
7. **No population figure** at the top of the Landscape; "Classified so far" stays.
8. **The map.** A List / Map switch (outline switch, 32 px) at the heading's right, the list the
   default; the map (`LandscapeViewMap.tsx`, `React.lazy`) a choropleth on Natural Earth, five
   Navy steps on a log scale, none in Line 2, the legend "1 ▮▮▮▮▮ 30", hover "United Kingdom ·
   23" with the country Electric Blue, a press to the filtered table, "Not on the map: …" for
   names the atlas cannot place. No globe outline (the 1:110m frame without Antarctica clipped
   it). The list is the keyboard's path.

## Round 12, Sources (owner, 2026-11-06, evening)

Brief: `research/briefs/round-12-sources.md`, with the owner's changes sent during the build
(item 4: Limited is yellow; item 7 withdrawn and re-ruled; items 10 and 11 added); screenshots
in `research/screenshots/round12-sources/` (`before-*` and `after-*`, 1280 and 400, light and
dark). DESIGN.md § The search queries and § The sources table carry each rule.

Lead rulings on the report: "Title only" and its hovers, the link's name and the dossier's labels
accepted.

1. **Full text links to the document.** When the row carries `full_text_url` (the backend's
   round-12 field on `EvidenceItemOut`), "Full text" is a link to it, opening in a new tab
   (`target="_blank" rel="noopener noreferrer"`, the report's address rule): Navy over a Line 2
   underline turning Navy on hover, named "Full text (opens the document in a new tab)". It is
   the row's second tab stop after the title. Without the address the word stays plain.
2. **Status tones.** The 6 px square before the depth: Green "Full text", Yellow "Abstract
   only", Red "Title only". Red needs a word beside it (the Word Beside the Colour Rule), so the
   third state is "Title only": a relevant source with no full text and no abstract (a proposal
   for the lead, see the report). Its hover says why ("…only the title was read.").
3. **Cited in the Status column.** No chip: a 12 px Green tick (the Relevant column's glyph)
   and "Cited" in Ink on the line under the depth; on a stacked row it follows the depth on the
   same line. The table now carries no chips at all.
4. **Strength tones for every level.** Green Very strong and Strong, Yellow Moderate and
   Limited (owner change), Red Weak and Unrated. `strengthTone` keeps its three values
   (`strong`, `moderate`, `weak`); `strengthColour(tone)` names the palette colour and
   `toneSquareClass(colour)` draws the square in Tailwind classes for the report's badges.
   The legend is the strength header's tooltip (on hover and focus of its sort button): each
   square beside its tiers ("Very strong, Strong", "Moderate, Limited", "Weak, Unrated").
5. **The filter bar.** Filters only, 12 px between controls. Download CSV is the quiet control
   with the download glyph (`DownloadIcon` in the icon module; Grey Semibold over the Line 2
   underline). Built first at the bar's right end, it wrapped onto its own row at 1280; the lead
   ruled it onto the line under the table, at the right end after the page controls with 24 px
   before it. Phones keep the filters' four rows at 400 px. Each facet is the shared `Select`
   (`ui/brand/Select.tsx`) with the bar's own trigger through the `renderTrigger` seam added this
   round (default unchanged); the local listbox is gone.
6. **Filters wait with the table.** While the search runs and the table waits for its first
   results, the filter bar is hidden too; a filter or screening choice the reader set keeps it,
   so it can always be cleared.
7. **The finished search's line** (owner, re-ruled: no sheet; "Show" stays; the round-11 line
   "looks a bit like eyebrow text"). A Body sentence in Ink, "Found with 12 queries and 3
   citation passes · Show", "Show" the quiet control with the disclosure chevron; it stands
   alone above the table, under the filter bar (`QueriesSummary`). Open, the round-11 ruled
   rows. The live list while searching is unchanged and still folds over 200 ms.
8. **Widths with the sidebar open.** The view's `main` is a container (`@container/sources`)
   and the table's widths follow it, not the window: from 72 rem the evidence type is 17.25
   rem on one line; below, 12.5 rem then 9.75 rem (below 62 rem), wrapping to two lines with
   an ellipsis after the second; below 54 rem of column the row stacks (the phone row), with
   the Sort control in the filter bar. With the sidebar open at 1280 the column is about 47
   rem, so the rows stack there: no fixed-column layout leaves the source readable at that
   width (the four value columns' headers alone take 28 rem). The Status column widened to 8 rem
   for the square and "Abstract only".
9. **The dossier.** One type scale: the sheet's title, Body for the reference line and every
   sentence, Meta for labels and facts; no chips; no bold below the title. The reference line as
   the report's (`referenceParts`, the address a Grey link without its scheme); the facts as a
   ruled list (Evidence type, Why this type, Strength with its square, Status with its square
   and Cited, Year, Origin); then About (the AI-description chip became the label "About · AI
   description"), What happened to it, Details (the full authors with affiliation markers moved
   here), Tags, Cited in the report and Findings or Records, each under a Meta Grey label and
   ruled (the blue and grey left borders are gone); "Open original" as the small outline button
   at the foot.
10. **A query's results** (owner go). Each query and pass is a prose link to All sources with
    `?query=<query_id>` and `status=all`; applied, the bar shows the Navy chip "Query: <first 40
    characters…>" with its ×, and the count reads for the filtered set. The coverage read's rows
    carry `query_id` (a number); the stream's live rows do not yet, so a live row reads as plain
    words until it does. The server keeps no records for a search run before the ids were
    kept, so the page says "This search ran before queries were linked to their results." when a
    query that returned some comes back empty with no other filter and every screening choice.
11. **The count under the table** (owner). "52 sources" / "1–50 of 207 sources" at Meta Grey on
    the line under the table, the range at the left; at the right the page controls, then
    Download CSV (lead); the finished search's line stands alone above the table.

12. **The line under the table** (owner, replacing the lead's placement in item 5): Download CSV
    at the left; at the right the page size, the range, then the page controls.
13. **25 a page** (owner): the client asks for `page_size` 25 by default (the server's default
    stays); the shared `Select` at 32 px offers 25, 50 and 100 ("25 per page" …) at the right of
    the line under the table, before the range, once there are more than 25 sources. The choice
    is kept per task in `localStorage` (`policy-atlas:sources-page-size:<task>`, beside the
    subtab memory) and the URL carries `page_size` only when it is not 25; a choice drops `page`.
14. **The filter bar on two rows** (owner): the screening switch alone on the first row; the
    facet filters, Cited and Sort on the second with 12 px gaps, wrapping as they must; 8 px
    between the rows; no control is squeezed.
15. **The finished search, a section** (owner): the Landscape's section pattern
    (`LandscapeSection`), the heading "How the sources were found" over its hairline, then the
    Body sentence in Ink "Found with 12 queries and 3 citation passes · Show"; open, the ruled
    rows inside the section. It sits between the filter bar and the table, 24 px above and below,
    and is hidden while the live list shows (the live list keeps its place and look). This
    replaces item 7's placement.

16. **The section on one line, above the filter bar** (owner, replacing item 15's placement):
    the heading at the left and the sentence right-aligned on the same line (on phones the
    sentence wraps under it), the hairline under that line, the ruled rows under the hairline
    when open. It sits above the filter bar, 24 px clear of it, so the bar reads as the table's
    own head; the table has no heading. It reuses the Landscape section's heading row (its
    classes and `PANE_LABEL_CLASS`) rather than `LandscapeSection` itself, whose content padding
    would leave 16 px under the hairline when the section is shut. Hidden while the live list
    shows.
17. **The section's heading is "Search queries"** (owner: "How the sources were found" was not
    plain enough), the live list's own heading, one constant (`SEARCH_QUERIES_TITLE` in
    `SearchQueries.tsx`).

## Round 11, the workspace (owner, 2026-11-06)

Brief: `research/briefs/round-11-workspace.md`, with the owner's items 5 to 7 added during the
build (relayed by the lead). DESIGN.md carries each rule (§ Status mark, § The run trace, the
run status bar in § Layout, § The name and its menu, § Motion). Screenshots:
`research/screenshots/round11-workspace/`.

1. **The square's pulse.** `breathe` troughs at 0.25 (was 0.5); the 6 px mark alone adds scale 1
   to 0.8 (`anim-breathe-mark`, through `StatusMark`, so the trace rows, the task list rows and
   the longlist's searching rows all take it); the words beside it keep `breathe-soft`; the
   placeholder bars and skeletons keep `breathe` (now to 0.25) without the scale. Reduced motion
   unchanged. Six frames over one cycle: `r2-05-pulse-strip-1280-light.png`.
2. **Scoping row links.** On a longlist walk Searching and Screening link to Sources and
   Classifying to the Landscape, running and done (the Evidence search's rules); from Suggesting
   options on the step in progress links to the longlist; Reading the linked search links
   nothing; the baseline walk's Writing links to the baseline, as before.
3. **The baseline card after the longlist starts.** `PastRunLine` draws the ended card through
   the same component as `RunTrace` (no copy): the finish words, the wall time, "Read it →" to
   what the walk made (`resultHref`: the report, `?view=baseline`, `?view=longlist`), and the
   steps from the thread run's `stages` (`RunOut.stages`, the backend's shape:
   `{stage, label, status, started_at, ended_at, seconds, summary, counts}`) folded behind "Show
   steps", through `cardRows`. No steps in the read, no control. Not a landmark, no live region.
4. **The run status bar on a scoping walk** says the longlist walk's step: the store keeps a
   child search's stage frames off the tracked walk (confirmed with the mock's walk and a test
   that feeds a child's `stage.started`). Activity ticks carry no run id, so a child's tick on a
   stage key the walk shares (`acquire`) would still reach the walk's row (reported to the lead).
5. **The task header** (owner): the name at Title on one baseline with the capability in plain
   Grey (no chip), the 40 px chevron control, the menu in the popover's tokens with menu rows,
   Rename in place with "Save" and "Cancel", Archive as the two-step confirm in words, focus
   back on the chevron. Below `md` the name has its own line.
6. **Projects get the same menu** (owner): `ProjectName` on the project page's title, Rename and
   Archive (`useArchiveProject`); archiving goes to the Projects list; an archived project offers
   Rename only.
7. **The reconnecting line** (owner) takes the run status bar's frame on every tab but Agent:
   the bar's padding and type size, its words where the bar's words start, the Yellow Tint kept,
   after the rail, in place of the bar's words until the stream returns. On the Agent tab it sits
   at the top of the Task Agent's column (after the workspace rail); the sidebar's compact pane
   leaves it to the page's bar.

Rulings on the build (agent, for the lead to confirm):
- A past baseline card's link reads "Read it →" (the ended card's one destination), not
  "Baseline →": sharing the ended card's code gives its words. The steps' Writing row inside it
  still reads "Baseline →".
- A longlist walk's done Searching, Screening and Classifying rows link (the Evidence search's
  rules say done rows link); its other done rows still point nowhere, as round 10 had it.
- A run the thread lists that has not ended (a stale `running` row) keeps its status word and no
  link: there is no ended card to draw.
- The project's archive sentence follows the task's: "Archiving removes this project from your
  active projects."

Lead rulings on the build (2026-11-06): the past card keeps "Read it →" (one language); the
longlist walk's done Searching, Screening and Classifying rows link, confirmed; the archive
confirm reads "Archive" / "Keep it" for tasks and projects, and a project's sentence adds "Its
tasks stay as they are."; the breathing "Loading…" lines of words take `anim-breathe-soft`
(skeleton bars stay on `breathe`); the tick frames' run id and the mock's repeated
"Classifying" go to the backend builder.

## Round 12, the workspace (owner, 2026-11-06, evening)

Brief: `research/briefs/round-12-workspace.md`, with the owner's change to item 5 relayed by
the lead during the build. DESIGN.md carries each rule (§ The name and its menu, § The run
trace, § Plan card and check-ins, § Motion). Screenshots: `research/screenshots/round12-workspace/`.

1. **The task header.** The name at Heading (Lead below `md`), Bold Navy, truncating on one line;
   the 40 px chevron control on the name's baseline (the button's baseline is its glyph box's
   foot, the glyph dropped 3 px so the chevron's foot rests on the line; negative margins keep
   the box from growing the line); the capability on its own short line under the name in Meta
   Grey, at every width, kept under the field while renaming. The project page's title takes the
   chevron on its baseline, no line under it, and keeps the page title's size (see the lead's
   question below).
2. **"Drafting the plan" was jittery.** Measured frame by frame in the mock (the probe's numbers):
   when the reply's first line landed, the action line under it dropped 52 px under the thread's
   clip and slid back; once the turn was stored, each new reply line pushed the part card down
   28.5 px at once before the thread glided. Cause: the thread's eased box (round 9) heard every
   reply line first and eased with its bottom clipped, so whatever sat under the reply jumped and
   was hidden. Fix: the reply has its own eased box (`useEasedHeight`), mounted before its first
   words with the gap to the action line inside it, and `useEasedHeight` nests: it measures a
   microtask after the change, so the inner box eases first and the thread takes only what the
   inner box does not; a read-only ResizeObserver keeps the height it eases from current; an
   ease that ends short of content that grew under it carries on. After: the action line moves
   at most 1.9 px per frame (the user bubble's own rise), and a wrapping line moves the card at
   most 0.8 px per frame. The reveal pace (0.15 chars/ms, the 800 ms catch-up) is unchanged.
   Strip: `r2-05-streaming-strip-*`.
3. **The chat went empty after answering the baseline check-in in the sidebar.** Cause:
   "Confirm plan and build longlist" ends the baseline walk, and the server closes the Task
   Agent conversation in the same write (`api/continuation.py`, `close_task_agent_conversation`).
   The sidebar read only active conversations, so the id it was showing left the list, the
   panel took it for a chat and showed an empty one. The mock never closes the conversation, so
   it does not reproduce there. Fix: the sidebar and the run status bar also read the Task
   Agent's conversations of every status (`kind: "task_agent"`) when deciding whether the
   Task Agent is open. Test: `ChatSidePanel.test.tsx`, the gate answered, the conversation
   closed, the thread still shown.
4. **Done scoping rows link.** On a longlist walk a done Suggesting options, Clustering,
   Estimating, Applying your constraints or Grouping into themes row links "Longlist →", a done
   Shortlisting row "Shortlist →" (`?view=shortlist`), in the longlist walk and in the shortlist
   walk; the running rows keep round 11's rule; the baseline walk's Writing keeps "Baseline →".
5. **The stepper counts decisions** (owner change during the build): "Plan · decision n of M ·
   <part>", M the parts the planner asks, the question included, Who can act and Your options
   only once asked, both capabilities; the settled names before it stay. No case was found where
   the part after "·" reads "Question" once the user is past it: the name comes from the open
   card's own part id.

Lead rulings on the build (2026-11-06):
- The project page's title keeps its page title size (Display, Title below `md`).
- Chat's sheet keeps *abstract only* (task 046, AM10) on a quiet Meta Grey line of its own.
- An unjudged citation says it is unchecked: `citationJudgement` with no tier gives "Unchecked"
  over "Awaiting evidence check" (or "The evidence check could not run for this answer" when
  chat's check failed), in chat's sheet and the report's.
- The Agent tab (`WorkspaceView.tsx`) takes the sidebar's fix: a `?chat=` naming a closed Task
  Agent conversation still shows the Task Agent.
- Done, Searching for each option and Reading the abstracts link "Sources →" (the option
  searches' results are in the table).
- The longlist walk's own Searching, Screening and Classifying rows are the walk's (the mock now
  runs them beside the option searches, as the server does); no change.

## Round 13, Sources (owner, 2026-11-06, night)

Items 18 to 22 and 28 from the coordinator's round-13 notes; screenshots in
`research/screenshots/round13-sources/`. DESIGN.md § Charts, § The sources table and the Sources
tab's placeholder paragraph carry each rule.

18. **What the publisher countries count, on hover.** The sentence left the page for an `i`
    (`InfoHint`) beside the heading "Where sources were published", with one more line: "The
    country of the publishing venue, when the database reports it. Sources without one are
    counted as “Not reported”." / "This is not necessarily where the study took place." Its name
    is "About where sources were published". `LandscapeSection` takes the hint after its heading.
19. **Two more funnel links.** Appraised → `?appraised=true`, Full text accessed →
    `?depth=full_text` (the evidence read's filters, landed this round); in the table each is a
    Navy chip with its × ("Appraised ×", "Full text accessed ×"), and Clear filters takes them.
    Shortlisted still leads nowhere.
20. **The funnel's words.** "Quality-checked" reads "Appraised" (the count is the appraise
    stage's results, as the backend builder reports); "Full text" reads "Full text accessed". The
    table's Status words are unchanged.
21. **Relevant, not Included.** The screening switch reads All, Relevant, Screened out; the
    dossier's stage words read "Relevant", "Relevant — not shortlisted", "Relevant — abstract
    only". The API's value and the URL's `status=Included` stay.
22. **The scoping Themes subtab.** On an options-scoping task the subtab shows the longlist's
    option clusters from the longlist read: each theme a section (name, "N options", the
    description), its options as a ruled list linking to their cards, an excluded option in Grey.
    Themes with no known option are left out; options in no theme are not listed (the longlist
    shows them). The Evidence search's subtab is unchanged; the longlist is read only on a scoping
    task.
28. **The loading skeleton** (owner, clarified: the moment a finished search's table loads, not the
    live run). Each of the six skeleton rows draws the placeholder bar in every column, sized to
    it: the source's two lines, Year, Evidence type, Evidence strength, Relevant (at the right,
    as its figure sits) and Status; the stacked phone row carries the same bars inline; all
    breathe together. Before, Relevant and Status were blank. (Built first as a live-run change
    before the clarification: the status cell also pulses on a source marked "unavailable" while
    the full texts are fetched; that stays, as the owner's rule reads.)

## Round 14, Sources (owner, 2026-11-07)

Screenshots in `research/screenshots/round14-sources/`.

1. **"Collecting…" while the full texts are collected.** While the ingest stage is live a
   relevant source whose depth is not yet full text reads "Collecting…" in the Status column, in
   Grey on the soft breathe with a Line 2 square in the tone square's slot (in place of the
   placeholder bar), and settles to Full text, Abstract only or Title only as the fetch ends.
   It keys on the row's own pending state, `full_text_status` "queued" (the backend's, landed
   this round), with the ingest stage as the guard: a queued source outside the stage shows its
   depth. (Before the field landed it was inferred from the run; that, and round 13's pulse on
   sources marked "unavailable", are gone.)
2. **The whole Search queries line is the disclosure.** One button inside the section's heading
   spans the row: "Search queries" at the left, the sentence and Show / Hide at the right, the
   hairline under it, the house focus ring. Its accessible name carries its visible words,
   heading first ("Search queries: Found with 5 queries and 1 citation pass · Show"; lead, Label
   in Name), and the journeys find it without the `^` anchor; the region is named "Search
   queries".
3. **"Not reported" links.** The Landscape's "Not reported" country row opens All sources with
   `country=none` (`NO_COUNTRY` in `sourcesPresentation.ts`); the Country filter offers "Not
   reported" last when the landscape has such sources, and its chip reads "Country: Not
   reported". Until the backend's sentinel lands the link filters on the literal value.
4. **A scoping theme opens its sources** (owner). On a scoping task's Themes subtab each theme's
   name links to All sources with `?theme=<longlist theme id>`, in the Landscape rows' quiet
   link form (its own colour, underlined on hover); the options keep their links to the cards.
   On a scoping task the table's theme filter is named "Theme" and its choices are the
   longlist's themes (the longlist read, on scoping tasks only), so the applied chip reads
   "Theme: <name>".
6. **Document counts on the scoping themes** (owner). Each theme's heading carries its documents
   at Meta Grey to the right (the longlist's `GroupCount`), in place of the options count (the
   options are listed under it); each option row carries its own count right-aligned ("12
   documents", "1 document"). The theme's figure is the theme's own distinct count,
   `LonglistThemeOut.document_count` (landed this round); before it landed the options' counts
   were summed, which counted a shared document twice.
7. **Column headings on the open Search queries list** (owner). One header row above the ruled
   rows, "Query", "Database", "Results" (right-aligned over the counts), in the Sources table's
   header style (`TABLE_HEADER_TEXT_CLASS`, the Caption-size label the table and the live list
   use; the owner's note said Meta, the table's style is Caption); once, as the rows are one
   table.
5. **The applied chip is defined once** (lead): `APPLIED_CHIP_CLASS` and
   `APPLIED_CHIP_PART_CLASS` from `ui/brand/Chip.tsx`; the filter bar's local copies in
   `sourcesPresentation.ts` are deleted and `SourcesView` imports the shared ones.

## Round 14, the workspace (owner, 2026-11-07/08)

Relayed by the lead in items; no brief file. Screenshots: `research/screenshots/round14-workspace/`
(`r3-*` final; `r2-*` the confirming round before the last fixes).

1. **Tabs open at their top.** The shell's pane scrolls to its top when the lifecycle tab changes
   (`lib/openAtTop`'s rule; a Sources subtab or a `#hash` keeps its place); the report's expand
   state is untouched.
2. **The plan over a tab dims the page** with the sheets' scrim (`SHEET_SCRIM_CLASS`, now
   exported from `ui/radix/Sheet.tsx`); a press on it closes the plan. The Agent tab has none.
3. **The thread's jumps**, measured frame by frame (scratchpad `shots-ws14-probe.mjs`): the
   answered card's settle let the thread drop 90 to 184 px for a frame (scroll anchoring, then
   React's focus restore reading a shorter layout); the action line mounted under the thread's
   clip; the stored turn landed above the plan card, which jumped 392 px. Now: no scroll anchoring
   on the thread's pane; the card holds its open height through the settle's commit; each turn is
   one `GrowBox` keyed by its client id (in flight and stored), the plan card after both; the run
   block opens the same way; eased boxes measure deepest first and follow a nested ease instead of
   chasing it. Largest downward one-frame move 409 px before, 73 px of eased glide after.
   Strip: `r3-02-answer-strip-1280.png`.
4. **The run status bar** waits for the task's run read and never shows for a run the read says
   has ended (a newer run still shows).
5. **The chats**: answers paced through `usePacedText` / `PacedReply`; the shared `ActionLine`
   (turning mark and the stream's activity words, else the mark alone) under the answer, "Checking
   the evidence…" while it is checked; References as the report's (the blue number opening the
   source, the reference line, then the marks line: the verdict opening the citation's sheet, the
   type, the strength mark, the depth mark); the notices as yellow-square lines, not chips.
6. **The header names the project**: "Evidence search · in <project>" (and "and N more").
7. **The sidebar trace's links** sit on the row's right edge as the wide table's do.
8. **A backend rename is revealed as a generation** (`ChangingName` in `NameMenu.tsx`; the owner
   replaced the first cut's crossfade): the old name fades out over 150 ms, then the new one comes
   through `useRevealedText` in place, no width easing; the reader's own rename just commits.
   Strips: `r4-07-name-reveal-strip-1280.png`, `r4-07-name-reveal-strip-400.png`.
10. **The plan opens at its own top** every time, and again when its content first arrives.
9. **The Result tab stays current on the option cards** (`/options/*`), its rule full.

Rulings on the build (agent, for the lead):
- The action line can still be partly hidden for about 50 ms when a turn's first reply line lands
  while its block is still opening (300 ms); the mock answers in 200 ms, a live model later.
- The opening turn's block opens from nothing as the page lands, so its action line is revealed
  last (about 100 ms).
- The chat's line before the stream says anything is the turning mark alone (no words invented);
  the lead's "Checking claims" was not used: the existing "Checking the evidence…" stays.
- Chat's References rows no longer carry the quote (the report's rows do not); it is in the sheet.

## Polish log

| Round | Phase | Date | Notes applied | Sign-off |
|---|---|---|---|---|
| 1 | build, agent pass | 2026-11-05 | Plan side panel lies over the page instead of squeezing the report; task nav keeps a gutter before Plan; the card's step in progress keeps its clock on the label line on phones; the status bar's elapsed time never truncates; in-card inputs span the card on phones | lead |
| 2 | build, owner pass | 2026-11-05 | six notes applied (above); the transcript-read bug fixed; Classifying | owner (round 1 of 3) |
| 3 | build, owner pass (round 2 of 3) | 2026-11-05 | settled part cards name the plan's outcome at the conversation's text size; stage signposts under the card removed; Mapping links to Themes | owner |
| 4 | build, owner pass (round 3 of 3) | 2026-11-05 | option order as the planner gives it; no reason line; settled lines show the question and the chips; settled lines rise in | owner |
| 5 | build, owner questions on a live run | 2026-11-05 | no Result footer; automatic swap to the report; no event-log echoes in the thread; settled scope lines per group; the streaming fix; the run trace with the blue square mark in place of the card, dock and status bar | owner |
| 6 | build, owner round 6 (live-run notes) | 2026-11-05 | settled part cards take the user bubble's surface, the part's name a grey label; the live trace is the running card's body (rows in plan order on a spine, hairline rules, the fold mark on the step in progress, no step count or last-finished line); the shut rail shows the run's elapsed minutes under its mark and a step note slides out of it as each step finishes; the rail's mark turns on the Result tab too | owner |
| 7 | build, owner round 7 (live-run notes) | 2026-11-05 | citation marks while streaming are the final marker's muted chip, and checked markers stay; the live page is the final page and the swap updates it in place; streamed prose paced with word snapping, frozen paragraphs and a 150 ms fade per batch; the trace is the running card again; the step note withdrawn and the run status bar returns | owner |
| 8 | build, owner round 8 (live-run notes) | 2026-11-05 | the ended trace is the same card (finish on the top line, rows behind "Show steps"); the card reads as a table with right-aligned counts, times and links; the running step links to its page and its activity line breathes; Searching and Screening as two rows; "Change" on its own line; one container for the decision card's settle; the status bar starts after the rail and opens the Task Agent; the rail's mark static with no status or timer; one mark size in the task list; no Sources tab mark; pulsing placeholders on the Sources tab keyed to the live stage, with a 5 s refetch | owner |
| 9 | build, owner round 9 (live-run notes) | 2026-11-05 | the search queries at the top of All sources, live as they go out and folded once the search ends, the sources table waiting for the first results; the activity line names the query that is out; the run status bar (renamed from the run strip) links to the running step's view; the checking chips run a blue wave; the found themes show while their documents are assigned; the nav and lifecycle tabs grow their blue rule on hover; arrivals: only what arrives after a view's first paint rises, the thread makes room for it, a decision card lays itself out, the reply comes at a steady pace, values land with a fade, the check-in settles on the choice, the trace eases its steps and its fold, the plan card leaves as the trace arrives, sheets leave the way they came, the plan document arrives from its edge; "Read in full" becomes "Full text" | owner |
| 9b | build, consistency pass | 2026-11-05 | the sweep's entries 1 to 8 and § 3, the lead's rulings on § 4 and the owner's additions (above): one focus rule and the inset ring on the cut corner; the outline variant, the entry size, Retry as a button; three inline-action styles; one close button and one icon module; the report part heading at Heading; the radio as the one radius exception; splash tokens; `py-8` on every tab; the nav and subtab rule from the left edge; Find a project and the Find popover; header controls at Body; the account menu; no New page eyebrow; Landscape rows as links with one hover and one count line; one header rule on the Sources table | lead |
| 9c | build, round 10 (five read-only reviews, then six builders) | 2026-11-06 | the report page (the question as title, the facts line, references with addresses, markers as the one control, a heading outline, ruled lists, print); the Sources table (visible filters with Country and a year range, fixed columns, a stacked phone row) and the years drag range; the list rows (the accessible name with status, the name cell widened, dates, Show more, Archived); Share and History (reordered Share with a two-step public confirm; History by day with sentences naming the step and the actor); the longlist as one component with rows moving into themes, one primary on the shortlist page, the gate card in the settled language; the backend's sentences, paging, country filter and refusal message | lead |
| 9d | build, round 11 (owner live-run notes) | 2026-11-06 | the square's pulse deeper with a scale, the citation wave as a visible sequence; scoping rows linking to Sources and Landscape, the baseline card keeping its link and its steps once the longlist starts, ticks and the option-search stage naming their walk; option and theme names appearing while clustering runs, the shortlist toggle saying Remove on hover, the option card in three blocks, the longlist row cut to its name, description and one grey line after a UX audit; most relevant sources and case studies back in cards above the Full report, the date on its own line, the sources count linking to References, the method as a ruled table, blue x-height bullets; the hover affordance and strength tone in the Sources table, the filter bar, the finished queries as one line with saved citation passes, greyed inactive subtabs, clickable funnel rows, the population line removed, a List / Map switch with a choropleth; Archived as a quiet foot link in the open scope, Find as a magnifier in the filters row; the name-and-menu header for tasks and projects with rename inline and a two-step archive, projects archivable, the reconnecting line in the run status bar's frame; the shortlist count fixed | lead |
| 9e | build, round 12 (owner live-run notes, evening) | 2026-11-06 | the scoping planner's Something else option and its question decision (lead prompt change, v7); the header name at Heading with the capability under it; the planner's reply in its own eased box; the sidebar and Agent tab reading a closed Task Agent conversation; done scoping rows linking; the stepper counting decisions; groups closed by default with Navy names, the count right-aligned, Show/Hide on the right edge, rules around the controls row, no contents nav, shortlisted first, the theme-and-lever hover, levers counted; the option card as what it is, Evidence (places first) and What it could take with a code-built sentence, the estimate behind an i, the dossier over the card, the card opening at its top, Set aside by you; the shared Select for every dropdown; the gate card without the key assumption; the public link reaching the longlist and shortlist read-only; the report's expand state (watched, fresh, kept across tabs), badges reordered with the table's strength tone and a working classification hover, the citation sheet on one scale; Sources tones (green, yellow, red), Full text linking to the document, Cited under the status, the two-row filter bar, Download CSV and the page size on the foot line, 25 a page, How the sources were found as a section, queries filtering the table; the list gap fixed by a subgrid, the Projects list paged and ordered by the server, row menus for rename and archive; the backend's option-search count from dispatch, combined and Estimating, places split into Several countries / Place not stated / Other, full_text_url, query_id and record ids, projects by last activity, the card export | lead |
| 9f | build, round 13 (owner live-run notes, 2026-11-06, late) and consolidation batch A | 2026-11-06 | the shared disclosure word, reference line, info hover and remembered choices (batch A); the longlist row's plain document count, the group heading shared by the list and grid with its shortlisted count, View as, the columns choice on the controls row, a wider Add an option, uncovered levers as a Body line, Other for the lever that fits none, the shortlist control as a circled check, Exclude only on the card and one-click with Add a reason after, excluding a theme or lever at its heading, the option card's documents without authors and in the References style with a link to the filtered table, the profile table at one size in a logical order, Your target and outcomes first with its values on two lines, no abstracts note; the New page's Project field (always shown, with New project…) and the scoping search field with one-line explanations; Share's two explanation lines; Landscape's published-country note in an i, the funnel rows Appraised and Full text accessed clickable, Relevant in the screening filter, the scoping task's Themes subtab from the longlist, the loading skeleton's bars in every column; the backend's depth and appraised filters, distinct appraised counts, a reason added after an exclusion updating in place; the page's scrollbar gutter kept | lead |
| 9g | build, round 14 (owner live-run notes, 2026-11-07 to 09) | 2026-11-09 | a task named from the refined question at the step 1 decision and a chat titled from its first message (lead prompts task_title_v1, chat_title_v1), the header revealing the new name like streamed text; the shortlist's not-covered note with one writer (shortlist_note_v1; the shortlist prompt v2 writes no note) refreshed once on opening and after a pause, 'Written before your latest changes'; the References numbers blue and opening the source, the method as one designed section at the prose width, the report titled with the plan's question, the boxes on the shared marks line; tabs opening at their top, the plan's scrim on non-Agent tabs and the plan opening at its top, the Task Agent's three measured jumps fixed with one growing block per turn, the action line never under the composer, the status bar gated on loaded data, chats on the paced reveal with the mark and activity line and References in the report's form, the header naming the project, the sidebar trace's links right-aligned, the Result tab active on option cards; Collecting… from the row's queued status, the whole queries line as the trigger, Not reported linking (country=none), scoping theme headings filtering the table with distinct counts; the task list's timer kept, the New page's searchable multi-select of the user's finished searches, the foot reorganised, the archive sentence naming the solo tasks; one ProjectPicker; projects archiving their solo tasks, own searches linkable anywhere and never flagged, depth and theme filters, the mock's ingest stage | lead |
| 9h | build, round 15 (owner live-run notes, 2026-11-09) | 2026-11-09 | the option card's exclusion block at the top as labelled facts with plain words (no 'Breaks'), the rows' one short exclusion phrase, the breadcrumb naming the origin, the note step on the standard tier, run-less History events kept out of the thread | lead |
| 9i | build, consolidation batch B (seven rules the owner accepted 2026-11-06) | 2026-11-09 | one home each for dates (`lib/dates.ts`, three named forms), counts (`lib/format.ts`), a task's status words and mark (`ui/brand/taskStatus.ts`; "Paused · waiting on you" / "waiting on <first name>", "Running" before the first step, "Stopped" for an aborted or interrupted run), the filter chip (`FilterChip` in `ui/brand/Chip.tsx`), the list furniture (`ui/brand/list/`: frames, skeleton, empty and error states, foot row, Show more, Pagination), the rotating chevron (`DisclosureChevron`) and the address link (`ReferenceUrl`); the view-level copies deleted (`views/Pagination.tsx`, `landingPresentation`'s status words, `formatListDate`, `reportDateLabel`, History's three date formatters, the two count formatters, eight hand-drawn chevrons, two hand-built anchors). Where copies differed the shared rule won: the re-run notice carries the year, History's hover loses its seconds, the chat divider is "5 Nov" for every locale, five chevrons now turn Navy on hover, both addresses use the stricter href check. Left alone on purpose: Findings' toggle chips (a choice, not a filter), the fixed select chevrons, the chat list's date buckets. For the owner: the paused words supersede the trace's earlier "a check-in is waiting on you"; aborted (grey) and interrupted (red) both read "Stopped" with their marks kept. § Consolidation, batch B above has the full list. | lead |
| 10 | review, agent pass | | | lead |
| 11 | review, owner pass | | | owner |

## Deferred polish

Notes the owner gave that this slice does not take, with where they go (`docs/deferred.md`).
None yet; the owner will add them on the live app.

## Round 11, the report page (owner, 2026-11-06)

Brief: `research/briefs/round-11-report.md`. Built as below; DESIGN.md § Report and citations
carries each rule. Screenshots: `research/screenshots/round11-report/`.

1. **Most relevant sources** are back where they stood before round 10: the executive summary's
   last part, after the case studies and above the Full report (an `h3`, its contents entry
   between "Case studies" and "Full report"), live and committed; the download follows. This
   reverses round 10's D2.
2. **Case studies and most relevant sources are ruled cards again**, the case studies' card from
   before round 10: a Line hairline box, 16 px inside, 12 px apart, no shadow. A card's chip row
   takes no room while it is empty, so the foot is the padding.
3. **The date has its own line** under the title: "Last updated 5 November 2026" at Meta Grey,
   committed only. The facts line keeps "Sources 12 cited out of 118 included · Published
   2019–2024"; the sources count links to `#references` and opens the References as the
   contents do (it no longer leads to the Sources tab's cited filter).
4. **"How the evidence was gathered"**: shut, its one line at the References' size; open, the
   counts first as a ruled table, one stage a row in the Landscape funnel's names (Found,
   Relevant, Full text, Shortlisted, Cited), the figures right-aligned in one column of tabular
   figures; then the plain sentence, kept; then the distributions and key themes as tables of the
   same width under Body Semibold captions, not headings, so the section is one heading in the
   outline. Body at every width, as the References. It stays folded (see the report's answer).
5. **Key findings**: the Electric Blue square comes back (reversing round 10's Navy) and sits on
   the middle of the x-height: the item aligns the square to the first line's baseline and raises
   it by half an `ex` less half its height. Measured at 1280 (19 px) and 400 (16 px): on the
   x-height to the pixel (`round11-report/r2-*-bullets-crop.png`).
6. **The citation-checking wave** reads as a sequence: a 2 s cycle; each chip muted until 25 %,
   in to the checked look with a 1 px blue halo by 40 %, held to 50 %, out by 65 %; 350 ms
   between chips, counted across the section (`run.markAt` already carried the paragraph's offset:
   `draftBlocks` numbers the marks over every block of the section, and a test pins marks in two
   paragraphs at 0 and 1). Reduced motion unchanged. Eight frames over one cycle:
   `round11-report/r2-checking-strip.png`.

Rulings on the build (agent, for the lead to confirm):
- The counts use the Landscape funnel's stage names rather than new words, so the product has
  one vocabulary for the funnel; "Relevant" there sits beside "included" in the shut line and the
  facts line. Say if the method should read "Included" instead.
- The plain sentence now stands alone after the counts table, so it takes a capital and a full
  stop: "This section covers only the cited sources — the Landscape tab shows the whole search."
- The date line arrives with the committed report, so the action line moves down one line at the
  swap (it fades in with the facts; the reading place is kept).

## Round 12, lists (owner, 2026-11-06, evening)

The owner's note: "In the organisation view of the tasks list, why is the gap between the task
status (completed / not started / …) and the owner name so big? It's making the task names
cramped."

- **Cause:** the row's grid gave the status column a fixed 11.5rem, sized for its widest form
  ("Paused · waiting on <first name>"), and the owner a fixed 8rem with the name right-aligned in
  it. On a "Complete" row by "You" that left about 230 px of white between the two words (about
  110 px of unused status column, the 16 px gap, about 100 px in front of the right-aligned
  "You"), while the name cell kept only what the fixed columns left (410 px at 1280).
- **Rule:** the task list is one grid and every row a subgrid of it (`taskListGridClass` on the
  list, `taskListItemClass` on the item, the row's `md:grid-cols-subgrid`), so the capability,
  status and owner columns are `auto`: as wide as the widest value this list holds. The status
  column is at most 11.5rem and keeps 8 px of its own on the 16 px gap, so the widest status word
  stands 24 px from the owner (or the count on Mine). The owner is capped at 8rem, ellipsed beyond
  it, the full name as hover text, and left-aligned so every owner starts 24 px after the widest
  status word. Only the name track is flexible: every remaining pixel goes to the name. The count
  and date tail stays fixed (5.5rem each; the date track is 6.5rem because the row's 16 px right
  padding sits in a subgrid's edge track), so a project row's count and date still end under a
  task row's. Phones are unchanged (the list is not a grid below `md`).
- **Measured** (1280, Organisation, the same eight long-named rows): with no colleague's paused
  task and short owners, the name cell grows from 410 to 488 px (239 to 317 at 1024) and the gap
  from "Complete · with gaps" to "Grace Hopper" is 24 px. With the worst case (a colleague's
  "Paused · waiting on Bartholomew" and two owners past 8rem) both caps hold and the name gains
  only the capability's slack (410 to 417 px); the remaining white then sits after a short owner.
- **The Projects page** (lead ruling): its project rows keep their fixed 8rem owner column, but the
  owner cell takes the same `rowOwnerCellClass` (left-aligned, ellipsed at 8rem), so the two lists'
  owners read alike. The owner column shows the full display name (lead ruling: not first names).
- **The Projects list pages** (lead): it reads `useProjectsPaged` (the server's page, `has_more`)
  and ends in the Tasks list's foot row: the shared "Show more" (`ShowMore`, now exported from
  `TaskListPanel`) at the left while the server holds more, the archived toggle at the right, the
  toggle still passing `status`. A project listed twice across two pages is dropped; focus moves to
  the first project that arrived (found by id); a later page
  that fails keeps the rows and offers Retry under them. The project pickers stay on `useProjects`.
  The server orders projects by their last activity and sends it on every row
  (`ProjectOut.last_activity_at`), so the page keeps the server's order (a page that arrives with
  "Show more" lands below the rows shown) and dates each row by it; the client's own re-sort over a
  200-task scan (`newestTaskUpdateByProject`, `projectLastUpdated`, `sortProjectsByLastUpdated`)
  is deleted.
- **The row's menu** (owner: "There should be a way to delete or archive and rename tasks and
  projects on the tasks/project lists"; the lead's rule): every task and project row its owner
  owns ends in the headers' quiet chevron control (40 px, Grey), a sibling of the row's link in the
  row's right padding (48 px on every row, so the columns line up whether or not a row has it; the
  task list's date track is 8.5rem to hold that padding). From `md` up it shows on hover, focus and
  while open; on phones always. `NameMenu.tsx` is split into `NameActionsMenu` (the menu with the
  Archive confirm) and `NameRenameField` (the field with Save and Cancel); the headers'
  `NameMenu` composes the two, and the rows (`ListRowMenu.tsx`) open the same menu. Rename puts
  the field in the row's place on the Blue Wash; Archive, once confirmed, folds the row by its
  height and opacity over 200 ms where it stood and then leaves it out, even if the list's refetch
  is slower (`useDepartingRows`). An archived task or project offers Rename only. The control's
  accessible name is "Task settings: <name>" / "Project settings: <name>" so each row's is its
  own; its tooltip is the headers' "Task settings" / "Project settings".
- **The dots and Add to project** (owner, round 12): the rows' control is the three dots
  (`MoreIcon`, new in the icon module: three round dots across the 16-unit grid's middle); the
  headers keep the chevron. A task's menu, on its row and on the task header alike, has "Add to
  project" between Rename and Archive (`useAddToProjectStep` in `NameMenu.tsx`, one build for
  both; `NameActionsMenu` takes further steps as `steps`). The step is the Share page's control:
  "Add to a project" over the app's `Select` ("Select a project") listing the projects the Share
  page offers less those the task is in, then "Add" (outline, off until a project is chosen) and
  "Cancel"; it runs `useUpdateTask` with the task's `project_ids` plus the chosen one, and the
  list's refetch updates the row's project. A refusal reads the Share page's "The projects
  couldn't be changed. Try again." in the step. With no project left the item is disabled, its
  grey reason line "Already in every project" (lead ruling: the list is the Share page's, every
  project it offers, so the reason does not say "your"). Project rows and the project page's menu have no such
  item.

## Round 12, the report page (owner, 2026-11-06, evening)

Brief: `research/briefs/round-12-report.md`. Built as below; DESIGN.md § Report and citations and
§ Overlays carry each rule. Screenshots: `research/screenshots/round12-report/` (`before-*` and
`after-*`, 1280 and 400; the app has no dark theme, so `-dark` matches `-light`).

1. **The expand state** is one piece of state per task, in memory (a module store in
   `ArtefactOutline.tsx`, not localStorage): `all` (what Show all / Hide all last said) and each
   collapsible part's own open state by its id. The live page seeds it open
   (`seedReportExpanded`, in the render that first shows the live page, before its sections
   render), so a reader who watched the writing finds every section open, the References and the
   method included, and "Hide all". A reader who opens a finished report fresh finds the sections
   shut and "Show all". Moving between the task's tabs keeps each section and the control's word
   (the Result route mounts again and reads the store). Leaving the task forgets it:
   `useForgetReportExpandOnLeave(taskId)` is for the task shell to call (see the shapes below);
   a page load starts empty. Tests: the watched path in `ArtefactView.live.test.tsx`, the tab and
   fresh paths and the forget in `ArtefactView.expand.test.tsx`, the watched path and a tab
   switch in e2e scene 6.
2. **The chips on case studies and most relevant sources** read classification, then strength,
   then "Since 2019" / "Cited by 3 claims". The strength chip carries the Sources table's 6 px tone
   square before its word (`strengthTone`, `strengthColour`, `toneSquareClass`, imported: Green,
   Yellow, Red, the table's round 12 colours; the sheet's strength the same). Both hovers are Meta,
   set once on the Tooltip (`className="text-meta"`), not inside each hover's content. Both show the help
   cursor (on the shared `ChipWithTooltip`, so chat's verdict chip takes it too). The
   classification's hover did not exist: the artefact carries no reasoning for a type
   (`CitationOut` and `CaseStudyCardOut` have no `classification_reason`). The chip now reads it
   from the cited source's dossier (`useSourceDossier`, `SourceDossierOut.classification_reason`)
   when the hover first opens, cached for the task; a case-study card's source is its first
   citation of the card's type (`cardEvidenceSourceId`). A breathing line stands while it
   arrives.
3. **The claim provenance sheet**: one type scale (the title, Body, Meta; no Caption, no chips, no
   bold but the source's name); its blocks in a fixed order with one Line hairline between them
   and no boxes, coloured left borders or tinted callouts: the claim's words; any explainer (gap,
   pattern, theme, weak grounding) at Body with its details at Meta Grey; then each citation: the
   quote first, highlighted in its passage; the source line as the References read it ("[1]
   Sampleton A, Mockford C (2022). **Universal breakfast clubs and diet quality**. BMJ Open."), the
   name the way into the dossier; the evidence type and strength at Meta Grey (the strength's tone
   square and dotted word, its reason on hover); the judge's verdict as a Meta Grey label ("Tier 2
   · grounded") over its words at Body Navy. The Sheet's close button and focus rules are
   unchanged.

4. **A shared options scoping task** (owner addition): the public view renders the Result's view
   switch (Baseline, Longlist, Shortlist) whenever the task has a longlist, never a longlist being
   built; a task with no longlist keeps the baseline alone. Routing only, in `ArtefactView`; the
   scoping builder makes the longlist, grid, option card and shortlist read-only under
   `usePublicView()`. Test: `ArtefactView.publicView.test.tsx`.

5. **"How the evidence was gathered" links** (owner, item 7): each row's label is a link in the
   Link style where the sources table can filter to it, with the Landscape's filters: Found
   `?status=all`, Relevant `?status=Included`, Cited `?cited=true` (Full text and Shortlisted
   plain); an evidence type `?cited=true&type=…`, a year `?cited=true&year_from=Y&year_to=Y`, a
   country `?cited=true&country=…` ("Not reported" plain), a theme `?cited=true&theme=…`. The
   counts stay plain, right-aligned (a theme's count lost its "→" link). The method has no
   strength distribution, so no strength row. Screenshot: `after-method-open-1280-light*.png`.
6. **Fixes**: the Markdown download writes a case study's facts type, then strength; the dotted
   underline of a value with a reason is one utility, `reason-word` (`index.css`), used by the
   Sources table and the sheet (`.sources-hint-word` is gone); the hover chips sit on an
   `inline-flex` wrapper, so the strength chip (whose first item is the empty tone square, which
   set its baseline) no longer sits 1 px low; the key findings use the shared
   `BULLET_ITEM_CLASS` / `BULLET_MARK_CLASS` (`ui/brand/BulletList.tsx`), the gap's square still
   Yellow.

Rulings on the build (agent, for the lead to confirm):
- "Hide all" after a watched run opens "How the evidence was gathered" too, which round 11 keeps
  folded on a fresh report: the control would otherwise say "Hide all" over a shut section.
- The sheet's judge label is the tier's own label ("Tier 2 · grounded"), and the words are the
  judge's rationale, or the tier's meaning ("Grounded in a specific passage") when there is none;
  no new words.
- The institutions line left the sheet: the References' form names authors only, and the
  institutions stay in the dossier one click away.
- A failed passage lookup shows the quote alone in quotation marks at Body Navy (it was italic
  Grey), the honest fallback chat also uses.
- The sheet's number "[1]" is Regular Grey, not the References' Semibold, to keep the name the
  one bold.
- The sheet's source name is a `role="button"` span (Enter and Space open the dossier, the house
  focus ring), not a `<button>`: a button breaks as a block, which left ". BMJ Open." alone on a
  phone's line. It stays a button to chat's and the journey's tests, and is not a link because
  chat's dossier is not on a `?source=` address.

Proposals for the lead (copy):
- The classification hover when the dossier has no reasoning: "No reasoning was recorded for
  this type." (built; the table's pattern is "No screening reasoning was recorded.").
- The classification hover when the dossier read fails: "The reasoning could not be loaded."
  (built).

Shapes other builders must wire:
- The task shell (`AppShell.tsx`, the workspace builder; and `PublicTaskShell.tsx` for the public
  view) calls `useForgetReportExpandOnLeave(taskId)` from `./ArtefactOutline` with the route's
  `taskId` (`string | undefined`), once, in the component that stays mounted across a task's tabs.
  Without it a reader who leaves a task and comes back in the same page session finds the state
  they left (a page load is still fresh).
- Chat's provenance sheet (`ChatMessages.tsx`, `ChatCitationBlock`) still passes its verdict and
  appraisal as `chips`; the shared block now takes `judgement={citationJudgement(tier,
  rationale)}` (exported), `evidenceType` and `strength` instead, and `chips` should go once chat
  moves.

## Round 12, consolidation (owner, 2026-11-06, evening)

Owner: "We should have a central place for things like strength tones and stuff like that instead
of re-implementing it everywhere it's used, or it will lead to drift." DESIGN.md § Components
carries the rule (the Defined-Once Rule): shared vocabulary is defined once under
`frontend/src/ui/brand/` and imported; a view-level copy of a shared rule is a defect.

**The move.** `ui/brand/evidence.ts` holds the evidence vocabulary and nothing else: the strength
tiers in the sort's order (`STRENGTH_TIERS`, `strengthRank`), their tones and colours
(`strengthTone`, `strengthColour`, `strengthTierColour`, `toneSquareClass`), the legend
(`STRENGTH_LEGEND`, read from the tones) and the hover (`strengthHint`, `STRENGTH_FALLBACK_HINT`);
the read depth's words (`FULL_TEXT`, `ABSTRACT_ONLY`, `TITLE_ONLY`), tones and hovers
(`readDepthLabel`, `readDepthColour`, `readDepthHint`, `humanReason`); the evidence-type formatter
(`evidenceTypeLabel`); the judge's labels (`TIER_LABEL`, `TIER_TEXT`, `citationJudgement`,
`UNCHECKED`, `uncheckedLabel`, `uncheckedWords`). `ui/brand/EvidenceMarks.tsx` holds the marks:
`ToneSquare` (the 6 px square, `data-tone` its colour), `StrengthMark` (square then word) and
`DepthMark` (square then word). The originals were deleted from `sourcesPresentation.ts`,
`artefactPresentation.ts`, `ArtefactView.tsx` and `ChatMessages.tsx`, and the colour rules from
`sources.css` (its `.sources-tone` keeps only the table's 7 px gap and seat on the line). The
Sources table, its legend and dossier, the report's chips and citation sheet, chat's sheet and
verdict chip, the Landscape charts, the report's method table and the longlist's document line
import them. Tests: `ui/brand/evidence.test.tsx`; the views' tests keep what is theirs.

**Where two copies differed** (the table's rule kept, except where noted):
1. The report's square named its tone in `data-tone` ("strong"); the table's named its colour
   ("green"). Colour everywhere now. The colours themselves already agreed (Green, Yellow, Red).
2. The strength hover without a type: the report said "The cited source's appraised evidence
   strength — …", the table "The source's appraised evidence strength — …". The table's words
   everywhere.
3. The strength hover with a type: the table wrote the classifier's Title Case type into the
   sentence ("appraised from the document type: Systematic Review"), the report the formatter's
   sentence case. Kept the formatter (not the table) because DESIGN.md's rule is "evidence types
   read in sentence case everywhere, from one formatter", which the table's own type cell follows.
4. Chat's text-basis line read "abstract only" in lowercase Grey with no mark; it now reads the
   table's "Abstract only" after its Yellow square (`DepthMark`). A copy change on task 046's
   contract item 7, made because the brief asks every "Abstract only" to come from the module;
   the lead may revert it to the old words by passing them, but then it is a second copy.
5. The longlist's document line printed the evidence type as the server sent it; it now goes
   through `evidenceTypeLabel` like every other surface.
6. The tone square's spacing stays the surface's: the table's 7 px inline margin and 2 px seat, the
   report's and chat's 6 px flex gap, the legend's 8 px. Not merged: spacing is layout, not
   vocabulary.

**Left alone, on purpose**: the run status mark (`ui/brand/Card.tsx` `StatusMark`, already shared,
a different vocabulary: blue, green, orange, red, navy, breathing), the Navy 6 px squares of the
longlist's levels and the new-content mark and the Blue key-finding bullet (not evidence tones);
the mock server's strength sort rank (`mock/api.ts`, it mirrors the backend); the API layer's
strength filter type (`api/queries.ts`, which should not import from `ui/`); the CSV export's
"Full text" column (the `read_in_full` true/false field, an export column name); the dossier's
"Read basis: Title only" (what screening read, a different fact); the pipeline status words
("Full text collected", "Included — abstract only").

## Consolidation, batch A (owner, 2026-11-06, evening)

Owner: shared pieces live once under `frontend/src/ui/brand/` and are imported; views never
re-implement them. Four pure moves; nothing a reader sees changed.

1. **The disclosure word.** `DisclosureWord` (the chevron, then "Show" or "Hide") and
   `useExpandForPrint` (a disclosure opens when the browser is about to print) moved from
   `views/ArtefactOutline.tsx` to `ui/brand/Disclosure.tsx`. Importers: the report outline
   (`ArtefactOutline.tsx`), the report (`ArtefactView.tsx`), the longlist (`LonglistView.tsx`).
   `useOpenWhenNavigated` stays in the outline: it answers the report's contents list and hash
   links and scrolls the report pane, so it is the report's, not the disclosure's. Test:
   `ui/brand/Disclosure.test.tsx`.
2. **The reference line.** `referenceParts`, `referenceCitation`, `referenceAuthorName`,
   `referenceAuthorsShort`, `displayUrl`, `withFullStop` and the types `ReferenceLike`,
   `AuthorshipLike` moved from `views/artefactPresentation.ts` to `ui/brand/reference.ts`.
   Importers: the report's References and citation sheet (`ArtefactView.tsx`), the dossier
   (`SourcesView.tsx`), the option card (`OptionCard.tsx`), the Markdown download
   (`artefactPresentation.ts`). No `ReferenceLine` component: the four surfaces render the parts
   differently (the References' arriving fade and print address, the sheet's bold title button,
   the dossier's line without its title, the card's link to the dossier). Tests moved to
   `ui/brand/reference.test.ts`.
3. **The info hover.** `InfoHint` and its test moved from `views/longlist/` to
   `ui/brand/InfoHint.tsx`; the longlist and the option card import it.
4. **Remembered choices.** One helper, `lib/remembered.ts` (`rememberedChoice`, `rememberedKey`):
   `lib/` because it is a non-visual helper, as `lib/freshness.ts` and `lib/safeHref.ts` are. Key
   scheme `policy-atlas:<name>:<taskId>`; read and write wrapped in try/catch; a stored string that
   is no longer a value reads as nothing. The Sources subtab (`sourcesSubtabChoice`, in
   `views/lifecycle.ts` beside the landing rule that reads it) and the page size
   (`sourcesPageSizeChoice`, in `views/sourcesPresentation.ts` beside the page sizes) use it. The
   keys are unchanged, so a reader's choices survive: `policy-atlas:sources-subtab:<taskId>`
   ("themes", "/landscape", "/all", "/findings") and `policy-atlas:sources-page-size:<taskId>`
   ("25", "50", "100"). `views/sourcesSubtab.ts` was deleted; its test is
   `views/sourcesLanding.test.ts`, the helper's own `lib/remembered.test.ts`.

**Left alone, on purpose** (each would change what a reader sees, so not a pure move; for the
lead): the hand-rolled rotating chevron in the search queries' "Show" (`SearchQueries.tsx`, Body
size, baseline-aligned), the option card's documents toggle (`OptionCard.tsx`, its own words),
History's row chevron and "Show steps" (`HistoryView.tsx`), the trace's "Show steps"
(`RunTrace.tsx`) and the findings table's row chevron (`FindingsView.tsx`); the plan panel's own
`InfoHint` on the navy surface (`workspace/PlanDocument.tsx`, a hand-drawn glyph in on-navy
tokens); the chats sidebar's open-or-shut memory (`policy-atlas:chats-sidebar`, not per task).

## Consolidation, batch B (owner, 2026-11-06; built 2026-11-09)

Seven rules the owner accepted (2026-11-06), each defined once and used everywhere; the copies
were deleted. Where two copies differed a rule had to be chosen; each choice is named below, so the
lead can reverse it by changing the one home.

1. **Dates** (`lib/dates.ts`): `formatDate(value, form, { now, weekday })` with three named forms,
   `short` ("5 Nov" this year, "12 Oct 2025" before it), `long` ("6 November 2026") and `time`
   ("09:02"). Fixed month and day names, so no locale writes "Sept"; the reader's local time on
   the 24-hour clock; "" for a value it cannot read. Importers: the task row and the project row
   (`short`), the chat's date divider (`short`), the report's "Last updated" line and its re-run
   notice (`long`), History's rows (`time`), their hover text (`long` then "at" then `time`) and
   day headings (`long` with the weekday). Deleted: `formatListDate` and its month table
   (`listPageChrome.ts`), `reportDateLabel` (`ArtefactView.tsx`), `rowTime`, `fullTime` and the
   three `Intl.DateTimeFormat`s (`historyPresentation.ts`), the chat divider's locale call.
   **Chosen:** the long form always carries its year, so the re-run notice now reads "This report
   is from 3 November 2026" (it dropped the year within the current year); the History row's hover
   loses its seconds ("3 November 2026 at 09:02"); the chat's divider moves from the browser's
   locale ("Nov 5" to a US reader) to the lists' "5 Nov".
2. **Counts** (`lib/format.ts`): `formatCount(n)`, en-GB ("1,234"). `countOf` (`lib/vocabulary.ts`)
   now groups its count through it, and so do the trace's counts (`COUNT_FORMAT`, deleted), the
   longlist's search line (`FOUND_FORMAT`, deleted), the Sources range, totals and empty sentence,
   the search queries' totals and results, the themes' document counts, the task row's source
   count, the page numbers, the report's "Cited by", the snapshot and funnel lines, the Landscape's
   classified line, the Markdown download's counts, the shortlist's document lines, the check-in's
   query and finding counts, the step count and the longlist's excluded, middle-word and measures
   lines. Visible only past 999 (a row's "1200 sources" now reads "1,200 sources").
3. **A task's status words** (`ui/brand/taskStatus.ts`): `taskStatusWord(status, { isOwner,
   ownerName, archived, stale })`, `taskStatusTone` (the row's mark), `isStale`, `RUNNING_WORD`,
   and a finished walk's words (`READY_WORDS`, with the `WalkKind` type, moved from
   `runProgress.ts`). The list row, the run trace's top line (running, paused, stopped, failed),
   the run status bar (through `traceWords` and `useRunWords`) and the browser title's unseen
   finish read them; the caller adds the live step and timer. The trace and the status bar now
   carry the owner's name (`TaskLiveProvider` and `RunTrace` take `ownerName`, from
   `TaskOut.owner_display`). Deleted: `runPresentation`, `taskStatus` and `isStale` from
   `landingPresentation.ts` (its tests moved to `ui/brand/taskStatus.test.ts`); the trace's own
   paused and ended strings. **Chosen** (each a visible change):
   - Paused, the trace and the status bar now read the list's words: "Paused · waiting on you" to
     the owner (was "Paused · a check-in is waiting on you"), "Paused · waiting on Grace" to a
     colleague (was "Paused · <step label>"), "Paused" with no owner. The brief lists these words;
     the annex's trace rulings (§ The run trace, "Paused") said the older ones. DESIGN.md's trace
     paragraph now says the new words.
   - Running with no step yet, the list row reads "Running" (was "Analysing the evidence…", wrong
     for an Options scoping walk); the trace already said "Running".
   - An interrupted run reads "Stopped" on the list row (was "Interrupted"), as the trace did.
   - Kept as they were, not in the brief's list: the trace's finish words per walk ("Report
     ready", the longlist's) where the list says "Complete"; "Complete · with gaps"; "Stale"; the
     marks (a stopped trace is Red; on the list an interrupted row's mark is Red and an aborted
     row's is Line 2, under the same word "Stopped").
4. **The filter chip** (`FilterChip` in `ui/brand/Chip.tsx`): one control in two looks, the
   outline box idle and the filled Navy chip with its × applied, its words a button (the ref's:
   it is the select's popover trigger) or, `whole`, the whole chip one button that clears, or
   `staticWords`; the × its own button named by `clearLabel`. `FILTER_CONTROL_BASE` (the 32 px box)
   moved beside it; the screening switch imports it. Importers: the Sources filter bar (Cited, the
   select filters and the Year filter, the query chip, the funnel's set chips), the multi-select's
   chosen items, the plan card's scope chips. Deleted: `FILTER_CONTROL_IDLE` and the exported
   `APPLIED_CHIP_CLASS` / `APPLIED_CHIP_PART_CLASS` (now private to the chip), the four hand-built
   chips in `SourcesView.tsx`, the multi-select's, and the plan card's blue-tint chip with its ✎
   and text ×. **Chosen:** the plan card's chips take the Sources look (Meta, 32 px, Navy), their
   words open the editor in place of the ✎ (the button keeps its name, "Edit <chip>"), the × is
   the 12 px glyph; read-only, the words alone; 8 px between chips (was 6 px).
5. **List furniture** (`ui/brand/list/`): `ListStates.tsx` holds `LIST_FRAME_CLASS`,
   `LIST_CONTROL_CLASS` (the 40 px ghost), `ListSkeleton`, `ListEmpty` (now with an `action` at the
   right) and `ListError`, each taking the surface's frame (`frameClassName`); `ListFoot.tsx` holds
   `ListFootRow` (its right end a row of items), `ShowMore` (takes `loading`) and `Pagination`.
   Importers: the Tasks and Projects lists (`TaskListPanel.tsx`, `ProjectsView.tsx`,
   `TasksListView.tsx`), History, All sources and Findings. The Sources table keeps its own frame
   (rules above and below, `sources-frame`) and its table-shaped loading rows; its empty, failed and
   no-match states are `ListEmpty` / `ListError` in that frame, and its foot is `ListFootRow`:
   Download CSV at the left, the page size, the range and the page controls on the same line at the
   right. Deleted: `views/Pagination.tsx`, `listFrameClass` (`listPageChrome.ts`), the furniture in
   `TaskListPanel.tsx`, `SourcesEmpty` and `FRAME_CONTROL_CLASS` (`SourcesView.tsx`). **Chosen:**
   the lists' spacing: the Sources foot is 16 px under the table and 16 px between its ends (was 20
   and 24); Findings' page controls sit 16 px under the table (was 20); the Sources empty state's
   padding is the lists' 24 px (was 20). Pagination no longer carries its own top margin.
6. **One rotating chevron** (`DisclosureChevron` in `ui/brand/Disclosure.tsx`): the 12 px glyph,
   right when shut, down when open over 200 ms on the strong ease-out, a cut under reduced motion,
   Grey turning Navy with its control's hover (the control carries `group`); `className` seats it.
   Users: `DisclosureWord`, the search queries' "Show", the option card's documents toggle,
   History's rows and "Show steps", the trace's "Show steps", the Findings rows, the report's
   phone contents, the longlist's "Show all" and the chats' Archived (`group-open:` turns it).
   Deleted: History's `RowChevron` and eight hand-drawn copies. **Chosen:** the search queries'
   rule (Grey, Navy with the control's hover): before, five copies stayed Grey on hover; the chats'
   Archived chevron turned over 150 ms on the plain ease-out and now takes the 200 ms. None honoured
   reduced motion before.
7. **The address link** (`ReferenceUrl` in `ui/brand/ReferenceUrl.tsx`): the address without its
   scheme, Grey over the Line 2 underline turning Navy, a new tab, nothing for an address that is
   not http or https (`safeHref`); `printFull` prints the full address. The References pass it, the
   dossier does not. Deleted: the two hand-built anchors (`ArtefactView.tsx`, `SourcesView.tsx`).
   **Chosen:** the dossier's stricter check (`safeHref`) for both.

**Left alone, on purpose** (for the lead): the Findings table's toggle chips (`filterChipClass`,
blue tint, no ×: a choice, not an applied filter); the chat's report-context chip and its text ×
(`ContextBar.tsx`) and the check-in's section rows with their ✎ and × (`CheckInBundle.tsx`): not
filter chips, but each a text glyph DESIGN.md asks for a `CloseIcon`; the conversation list's
"Today / This week / Earlier" buckets (groups, not a date form); the trace's step row "Stopped" (a
step's state); the fixed-down chevrons of the selects and the header menu (they do not turn).

## Round 13, Options scoping (owner, 2026-11-06)

Screenshots: `research/screenshots/round13-scoping/`.

1. **The row's grey line says the document count alone** ("12 documents"); the evaluated /
   describe split is the card's (owner: avoid information overload).
2. **A card document's reference has no authors**: the title first, the year in brackets after
   it, the venue after in Grey; the title takes the report's References style
   (`SOURCE_TITLE_LINK_CLASS`, now exported from `ui/brand/reference.ts`; the report's own copy
   in `ArtefactView.tsx` can import it).
3. **What it could take, open**: the line's name (Grey) and its mark take the block's reading
   size, as the sentence cells.
4. **The open table's order**: ambition, potential impact, the lines that compare (cost, time to
   set up, time to effect, workforce, coordination, delivery complexity), then those that do not
   (who decides, dependencies). The shut points keep their order.
5. **"Your target and outcomes" leads Evidence**, above "Where it has been evaluated".
7. **Group by reads "Theme · Lever"** (was "Lever type"); the grid's first head reads "Lever" too
   (lead: every user-facing "Lever type" becomes "Lever").
8. **One group heading for both views** (`longlist/GroupHeading.tsx`): the list's group headings
   and the grid's column and row heads, the name in the Label style in Navy and the count in Meta
   Grey after it on the same line; counts only in the heads, never in a cell.
9. **The shortlist toggle is a circled check** (`CheckCircleIcon`): an outline circle in Grey
   when the option holds no place, filled Electric Blue with a white check when it does, a 40 px
   target, `aria-pressed`, its name and tooltip "Add to shortlist" / "Remove from shortlist", the
   fill easing over 150 ms (none under reduced motion); the public link and the building list show
   the filled glyph with no button. The words toggle and its hover swap are gone.
10. **Exclude leaves the rows and the tiles**: on the option card only, a quiet text control
    "Exclude" / "Include again" (one action is not a menu).
11. **No "Read from titles and abstracts" note** at the longlist's foot or in the card's
    documents.
12. **Excluding whole groups**: each theme and lever heading carries "Exclude" at its right,
    which sets aside every included option in the group through the per-option route with the
    reason "with the theme <name>" / "with the lever <name>" (`groupExclusionReason`); a group
    whose options are all set aside keeps its heading with "Include again", reversing it for those
    options. None on the public link.
13. **"View as" before the List / Grid switch** (Meta Grey).
14. **The controls row keeps the view switch still** (owner, corrected): Group by with Show all
    (list) or "Columns" and its choice with Show excluded (grid) on the left; "View as" and the
    List / Grid switch on the right edge in both views.
15. **The Add an option field takes the row** up to the prose measure, Add after it.
16. **The levers with no option, said plainly** in both views: "No options for: **Enforce existing
    powers**, **Devolve** and **Change who runs the system**" in Body Ink, the names Semibold Navy
    (`uncoveredLevers`), under the controls row in the grid and at the foot of the lever groups in
    the list; never "Other".
17. **Coverage on two lines**: "Measured in 6" over "Discussed in 7" (`outcomeCoverageLines`).
24. **A group's count says what is shortlisted**: "12 options · 3 shortlisted" (`groupCountWords`),
    in both views.
25. **The grid's tiles**: the check in the tile's top-right corner at a 24 px glyph in its 40 px
    target, the name wrapping clear of it; heads on one line, the count after the name.
26. **"Other", not "No lever fits"**, in the list and the grid; the card's "Lever: **other**.".
Corrections (owner, same round): the count line and "Show all" sit inside the controls' hairlines,
under the controls row, Show all at the count line's right edge in the headings' Show / Hide look,
"Hide all" once every group is open (by Show all or one by one), none in the grid; the group control
is not on the heading nor at the foot but the open group's first line, "Exclude this theme" /
"Exclude this lever" (or "Include again"), under the heading and description, before the rows, at
their left edge; a shut group offers nothing.

Later the same round (owner):
- **The grid's heads carry no counts**, the name alone in the shared heading; the list's group
  headings keep theirs.
- **The levers with no option** are listed directly under the grid in the row heads' column only:
  "No options for", then each lever on its own line, all in the row-head style (the Label style)
  in Grey, 8 px apart, no hairlines, no cells; in the list's lever view, the last group heading
  "No options for" in Grey with the names as one Grey line in the same style under it. Never
  "Other".
- **Exclude's words**: "Exclude" on the card, "Exclude theme" / "Exclude lever" on a group, each
  after the module's `ExcludeIcon` (a circle with a diagonal bar) at 12 px; "Include again"
  after `UndoIcon`; the tooltip carries the meaning: the group's "Excludes these options from the
  shortlist. They stay on the longlist under Excluded and can be included again.", the card's
  "Excludes this option from the shortlist. It stays on the longlist under Excluded and can be
  included again." The Excluded group reads "Excluded from shortlisting by a constraint or by
  you." (owner: the reason is on each row).
- **Excluded, grouped** (item 28): a theme or lever excluded whole shows under Excluded as its
  own group, identified by the reason its Exclude recorded ("with the theme <name>"): its heading
  in the shared heading style in Grey with its count, its one-line description as when included,
  then "Include again", then its rows; the options excluded one by one follow, after the groups.
  The group's old heading on the list goes.
- **One word, "Excluded"** (owner): the reader's own exclusion line reads "Excluded by you" (·
  with the theme <name> · <reason>), a constraint's keeps "Breaks <constraint>"; the Excluded
  section's description reads "Excluded from shortlisting by a constraint or by you." History's
  sentence is the backend's and stays.
- **One row for both states** (item 29): an excluded row has the included row's lines (name,
  description, the one meta line with the document count), then the exclusion line with "Add a
  reason" (while it invites one) and "Include again"; the grey alone marks it.
- **A Result-tab switch opens at the top**: the Longlist and the Shortlist (and the option card)
  open with the pane at its top and focus on the title (`longlist/openAtTop.ts`). The Baseline is
  the report builder's page (`ArtefactView.tsx`) and needs the same hook there.

27. **Exclude acts at once** (the card's and a group's): the exclusion line reads "Set aside by
    you" (or "· with the theme <name>") followed by "Add a reason", a quiet control that opens the
    field with Save and Cancel; saved, the reason joins the line (after the group's words). It
    posts the exclusion route again with the reason, which records it (and logs a second exclusion
    in History).

Later again the same round (owner, lead rulings):
- **Excluded is a section, not a group**: its heading "Excluded" at the page's section size
  (`REPORT_SECTION_HEADING_CLASS`, Navy, sentence case), "Excluded from shortlisting by a
  constraint or by you." under it, below a Line hairline across the list 32 px either side; inside
  it only groups, each in the shared group heading (level 3, name in Grey) with Show / Hide, shut
  by default, its description showing while shut: each theme or lever excluded whole, then the
  options excluded one by one under one group headed "Options" with its count. No loose rows. Show
  all opens the themes, not these.
- **Rows inside an excluded group** read "Excluded by you" alone (plus a reason of their own); the
  group's heading names the theme or lever.
- **One action column**: a group's control sits on its description's line, right-aligned, only
  while the group is open; the words, then the glyph at the row toggle's size
  (`TOGGLE_GLYPH_SIZE`) centred in the toggle's 40 px width, so the glyphs line up with the
  toggles'; its hit area is its own line, clear of the heading's Show / Hide (asserted by boxes in
  the scoping e2e). An excluded row's "Include again" takes the same form on the same column
  (`EdgeAction`, one control for both). The group's words: "Exclude theme" / "Exclude lever",
  and on an excluded group "Include theme again" / "Include lever again"; an option's stays
  "Include again".
- **"Add a reason" is the option card's only**: the rows and groups lose it; a reason given on the
  card shows on the row's exclusion line as text.
- **The card's two controls take one form**: glyph then words in the quiet style, side by side —
  the circled check (filled, `aria-pressed`) with "Add to shortlist" / "Shortlisted", and
  "Exclude" / "Include again" with their glyphs, both at `TOGGLE_GLYPH_SIZE`. Rows and tiles keep
  the icon-only toggle. The tooltips say "from being shortlisted": "Excludes these options from
  being shortlisted. …" (group) and "Excludes this option from being shortlisted. …" (card).
- **"No options found for"** (the search found none; it does not rule them out): a Body Grey
  sentence-case line, the lever names under it in the row-head style 8 px apart. In the grid, a
  Line hairline across the grid's width under its last row, then the foot 24 px below it in the
  row heads' column; in the list's lever view the same words and names as the last block.
- **Only a regroup moves the rows**: the View Transition runs for the build's theme wave, a new
  grouping or Columns line, and a whole theme or lever excluded or included again; a shortlist
  toggle, Show excluded and one option's exclude or include again update in place. The app's
  chrome (the header and its hairline, the task bar, the stage bar, the run status bar) carries
  its own transition names (`shell-chrome`), held still above the moving rows.
- **A shortlist press changes only its own control**: the pressed toggle shows its new state at
  once and holds it until the read agrees (or the request fails); no other toggle dims or redraws
  while it is sent.
- **Exclude's tooltips end at "under Excluded"**: the group's "Excludes these options from being
  shortlisted. They stay on the longlist under Excluded.", the card's "Excludes this option from
  being shortlisted. It stays on the longlist under Excluded." (no "and can be included again").
- **Round 14 (owner): an excluded lever is not "No options found for"**: the foot lists only the
  lever types no option carries at all, included or excluded; a lever excluded whole sits under
  Excluded and never joins the foot. One predicate (`uncoveredLevers`) for the grid and the list.
- **One foot for both views** (owner): the list's lever view ends with the grid's foot, the same
  component (`NoOptionsFoot`): "No options found for", then each lever on its own line in the row
  heads' style, 8 px apart. Round 14 (owner): the foot carries its own Line hairline across the
  full width with 24 px below it, so the list's lever view separates its last group from the foot
  as the grid does.
- **An excluded tile in the grid** has no word: its name in the list's excluded Grey, and in the
  corner where other tiles hold the toggle the `ExcludeIcon` at the toggle's 24 px in Grey, not a
  control, its tooltip (and accessible name) the exclusion line ("Excluded by you · with the theme
  <name>" or "Breaks "<constraint>" · …").

## Round 13, the New page's optional fields (owner, 2026-11-06)

The owner's note (item 6): user testing found the New task page's "Starts from" part unclear for
an options scoping task. Rule (relayed by the lead): two plain optional fields under the question
step, each a label and one explanation in Body Grey, nothing else; no eyebrow, no "Starts from".

- **Project** (both capabilities): "Add this task to a project. You can do this later too." over
  the shared `Select`, the projects the task menu's "Add to project" uses (`useProjects()`),
  "None" first and chosen (a project preset from `?project=` stays chosen). Shown while the reader
  has a project to offer, as before.
- **Evidence search to start from** (options scoping only, 24 px under Project): "Optional. An
  evidence search you have already run gives the scoping its sources and report; without one it
  searches for each option." over the shared `Select`, "None" first and chosen. It replaces the
  checklist: one search, not several.
- **What it offers** (build's reading of the server's link rules, `_write_links`: a source must
  be a finished Evidence search sharing a project with the new task): the reader's active Evidence
  searches whose latest walk succeeded or finished with gaps and that are in a project; with a
  project chosen, only that project's. With no project chosen, each search carries its project
  on a grey line, and choosing one files the task in the search's first project, shown at once in
  the Project field. Changing the project to one the chosen search is not in sets the search back
  to None. The field stays on a scoping task even with nothing to offer (None alone), so it never
  comes and goes as the project changes.
- **Create:** one request carries both (`useCreateTask` already sends `project_ids` and
  `from_task_ids` together, so nothing needs chaining).
- **Always there, and New project…** (owner: the field was not visible to them, because it showed
  only while the reader had a project to offer): the Project field shows on both capabilities'
  New pages whatever the reader has. Its list is "None", the reader's projects, then "New
  project…". That choice opens a name field under the dropdown (Body, a 40 px field, labelled
  "New project name" for a screen reader), focused and selected as it opens; Escape leaves it,
  back to None with focus on the dropdown (the rename field's rules). On Create the project is made
  first (`useCreateProject`), then the task with its id; a blank name reads as None. If the project
  cannot be made, no task is made and the page says "The task couldn't be started. Try again."
  With "New project…" chosen no search can be offered (the new project has none), so the search
  field reads None.

## Round 13, Share's section lines (owner, 2026-11-06)

The owner's note (item 23): each sharing section gets one plain explanatory line in Body Grey
under its heading, nothing else. `SettingsRow` takes `explain`, drawn straight under the `h2`
and above the state. The owner then had the lines say the effect of the choice, since the first
words read as if the task were already shared: Public link "Making this task public creates a
link that anyone can open to read the report, without a Policy Atlas account." (on the owner's
control and a colleague's read-only row alike); Organisation "Sharing with your organisation
lets everyone in it open this task from their Tasks list."; Projects keeps its current line
("Not in a project." or its list). The words live in `SHARE_COPY` (`publicExplain`,
`orgExplain`).

## Round 13, the rename field's word (owner, 2026-11-06)

The rename field's button reads "Save", not "Save name", on the task and project headers and on
the list rows (one constant in `NameMenu.tsx`). Its accessible name stays "Save name", which
holds the visible word (WCAG 2.5.3, label in name), so the end-to-end journey and the tests that
find it by that name are unchanged.

## Round 13, the New page's Project and search fields, second pass (owner, 2026-11-06)

- **Create a project in place** (owner: typing a name did nothing until the task was made):
  "New project…" swaps the dropdown for the name field on the same row and width, with an outline
  "Create" and a quiet "Cancel" (ghost) beside it. Create, or Enter in the field, makes the
  project at once (`useCreateProject`), and the dropdown comes back with it chosen (listed
  locally until the projects' refetch carries it); Cancel or Escape brings the dropdown back at
  None with focus on it. A failure keeps the name and says "The project couldn't be created. Try
  again." under the field. A name typed but not created when the task is started is still made
  first, then the task in it; a blank one reads as None.
- **Several searches again** (`from_task_ids` is a list): the single dropdown becomes a checklist
  under the label, one row per linkable search (finished, in a project), none checked: a 16 px
  square box in the plan radio's language (Navy at 40 % empty, Navy with a white tick checked,
  Line 2 disabled), the name at Body Navy and the search's project on a grey line. Checking one
  with no project chosen files the task in its first project; a search outside the chosen project
  is unchecked and disabled, its grey line "In another project"; choosing another project unchecks
  the searches it does not hold. While a new project is being named, every search reads "In
  another project" (a new project holds none).

## Round 13, one way to make a project and to add a task to one (owner, 2026-11-06)

The owner's audit: every place that creates a project or adds a task to one is one implementation.

- **`ProjectPicker`** (`views/ProjectPicker.tsx`): the app's `Select` of projects ending in "New
  project…", which swaps the dropdown for `ProjectNameField` on the same row and width; Create
  makes the project and brings the dropdown back with it chosen (listed until the refetch carries
  it), Cancel brings it back with nothing chosen. An optional first choice stands for no project
  (the New page's "None").
- **`ProjectNameField`** (same file): the Body name field with an outline "Create" and a quiet
  "Cancel", Enter creating and Escape cancelling, focused with its text selected, the one error
  line "The project couldn't be created. Try again." under it with the name kept.
- **`useMakeProject`** and **`useAddTaskToProject`** (`views/projectActions.ts`): the one way to
  create a project (calling back with its id) and the one way to add a task to a project (the
  task's `project_ids` plus the new one, `useUpdateTask`).
- **Changed with it:** the task menu's "Add to project" is never disabled (a task in every project
  offers "New project…"), so "Already in every project" goes; the Share page's add control shows
  for the owner whatever projects exist, so its "Create one in Projects." line and link go; the
  Projects page's New project form is the name field with the outline Create (its Create was the
  page's one blue fill), under its visible "Project name" label.

## Round 13, the citation sheet (owner, 2026-11-06, night)

The owner on round 12's sheet: "the citation sidebar now reads badly; the claim, the source, the
quote and the judge's appraisal cannot be told apart". Two passes were replaced on the owner's
word: labelled rows in the dossier's facts pattern, and a revert to the round-11 sheet (withdrawn:
"do not revert the whole sheet"). As built, round 12's polish is kept (the one type scale, the
quote's highlight, the shared marks, the Meta tooltips) and the old layout's separation comes back:

- **Title:** "Evidence for this claim" (`PROVENANCE_SHEET_TITLE`; it read "Where this comes
  from"). Chat's sheet uses the same title.
- **Claim:** a Meta Grey "Claim" label over the words at Body Navy behind the 2 px Electric Blue
  left rule. It is the only coloured rule ("keep it on the Claim block only").
- **Judge, once, directly under the Claim.** The verdict is the claim's: the backend moved
  `grounding_tier` and `grounding_rationale` from `CitationOut` to `ClaimOut`, with no compat
  fields. Live, the verdict comes from `LiveSection.checkedClaims`, matched by claim id or span.
  - The label: "Judge", led by the blue fold-mark diamond (`FoldMarkIcon`, 10 px, "to show it is
    an AI judgement").
  - The callout: tinted Blue Wash 2 for a checked tier, Red Tint for unsupported, Ground for
    unchecked; inside, the tier's label in Navy Semibold, then the words at Body Grey.
  - Chat still passes a per-citation `judgement`, set first in its box. Chat's turn shape is
    unchanged.
- **Sources:** "Source" or "Sources · N", counting sources and never quotes, over one box per
  source. A claim's citations are grouped by `source_id`, else by the title.
  - Each box has a Line hairline all round and 16 px inside, and no coloured rule.
  - The source comes first, unlabelled, with 12 px of room above and below it:
    - "[n] Title" at Body Semibold Navy, the title the link to the dossier;
    - then "Sampleton A, Mockford C · 2022 · BMJ Open" in Grey;
    - then the evidence type, dotted, with its reasoning read from the dossier on hover;
    - then the strength. The References keep their author-year form.
  - Then each quote under its own label: "Quote", or "Quote 1", "Quote 2" when one source gives
    several.
- **Back from a source.** A source opened from the sheet shows "Back" in the dossier's header,
  before the close button. It is the icons module's left arrow (`ArrowLeftIcon`), in the quiet style, named
  and tooltipped "Back to the claim".
  - It returns to the same claim's sheet, and so does the browser's Back: the entry the reader
    leaves is rewritten with `?claim=`, and the source opens on a new entry that keeps it.
  - × or an outside press closes everything.
  - A source opened from anywhere else gets no Back.
- **Loading line:** the source sheet's loading line is one constant, `DOSSIER_LOADING_LINE` ("Loading
  source details…"), in `SourcesView.tsx`. The report, the Sources table and the option card use
  it.

Screenshots: `research/screenshots/round12-report/before13-sheet-{1280,400}-light*.png` (round
12's sheet), `after13-sheet-{1280,400}-light*.png` and `after13-dossier-back-1280-light.png`.
Tests: `ArtefactView.test.tsx`, `ArtefactView.expand.test.tsx` (the order, the one coloured rule,
the claim's Judge, grouping by source with numbered quotes, Back and its absence) and
`ArtefactView.report.test.tsx` (one Judge over two sources).

## Round 13, the method's row links (owner, 2026-11-07)

"How the evidence was gathered": the Full text row now links to the sources read in full
(`?depth=full_text`, the evidence read's depth filter, which landed this round); Shortlisted stays
plain (no filter). Every row label that links (the counts, the distributions, the themes) takes
the References' quiet title link (`SOURCE_TITLE_LINK_CLASS`: Navy, the Line 2 underline turning
Navy on hover), not the Electric Blue prose link, so the table is calm; the sentence's "the
Landscape tab" stays a prose link. Screenshot: `research/screenshots/round12-report/after-method-open-1280-light.png`.
Test: `ArtefactView.report.test.tsx` (the hrefs, Full text included, and the quiet style).


## Round 14, lists and the New page (owner, 2026-11-07)

- **A running row's timer:** the live step and its timer are two cells in the status column; the
  step is `min-w-0 truncate`, the timer (" · 28 min") never shrinks. The pair's hover text is the
  whole line.
- **"Evidence search to start from" is a searchable multi-select** (`ui/brand/MultiSelect.tsx`):
  the Select's trigger and popover, a filter field at the top of the list ("Find a search", focused
  as it opens; "No finished evidence searches" when nothing matches), a row per search through the
  shared `Checkbox` with its project on a grey line, the chosen ones as removable Navy chips under
  the trigger (the applied-chip classes now in `ui/brand/Chip.tsx`), the trigger reading "None",
  the one name or "2 selected". It lists every finished Evidence search the reader owns, in any
  project or none; there is no "In another project" rule and choosing a search never files the
  task in a project (the server's shared-project rule is relaxed this round).
- **The page's foot:** the question's box holds the text alone; the primary moved out of it to a
  row of its own at the right, after the fields, with nothing below it (a failure's sentence sits
  above it). Removed: the primary from inside the question box; "You can do this later too." from
  the Project help line; the checklist and its "In another project" lines; the second error card
  (one card says whichever failed).
- **The project archive confirm** says what happens to the tasks: "Archiving removes this project
  from your active projects and archives its N tasks that are in no other project." ("its 1 task
  that is"; the clause left out at none or while the count is unknown), N from the project row's
  `solo_task_count`, typed locally until the generated type carries it.

## Round 14, the report page (owner, 2026-11-07/08)

1. **References' numbers.** "[1]" is Electric Blue again and a button. It opens the source's
   sheet by its reference title, as the title link does, and is named "Source 1: <title>". While
   the report is written the number is Grey and plain, since there is no dossier yet. The markers
   in the body keep their rule.
2. **"How the evidence was gathered", polished as one section.**
   - Every table spans the report's prose measure (the 32rem cap is gone), with a fixed layout and
     Line hairline rules.
   - Every table has one 80 px figure column at the right: the numbers alone, Navy, tabular
     figures, right-aligned, so they line up down the whole section. " documents" is dropped from
     the distribution and theme rows; the captions and the sentence say what is counted.
   - There is 32 px between every part, and each caption sits 8 px above its table.
   - The sentence ("The rest of this section covers only the cited sources; the Landscape tab
     shows the whole search.") appears once, between the search's counts and the cited sources'
     tables it introduces.
   - The "Where published" note sits under its table at Meta Grey, as a footnote rather than a
     second sentence of body.
3. **Title.** The report's `h1`, live and committed, is the plan's refined research question
   (`plan.question` from `usePlan`). The fallback is the task's question, then the stream's, then
   the task's name. The plan read is not on the public surface, so a public link reads the task's
   question (`usePlan` gets an empty id there, which disables it). The download's title follows
   the same question.
4. **Case studies and most relevant sources.** The chips are gone. Each box takes the citation
   sheet's marks line (`EvidenceMarksLine`) under its title, and after the authors on a source:
   the type (dotted, its reasoning on hover), the strength with its tone square, then "Since
   2019" or "Cited by 3 claims", at Meta Grey joined by middots. It arrives with the committed
   report. The now-unused `ClassificationChip` and `AppraisalChip` are deleted.

Screenshots: `research/screenshots/round12-report/before14-*` and `after14-*`: title, references,
method open (two scrolls), the boxes, at 1280 and 400. Tests: `ArtefactView.test.tsx` (the number
opens the source and is plain while live), `ArtefactView.report.test.tsx` (the plan's title and
its fallback, the marks line in both boxes, the method's one column), `ArtefactView.live.test.tsx`
(the live title).

## Round 14, the shortlist's note kept current (owner, 2026-11-08)

- On opening the Shortlist page, if the read says `note_stale`, the page asks
  `POST /tasks/{id}/shortlist/note` once. After a shortlist change on the page, one timer waits
  3 s after the last change and asks once if the note is still stale; each change resets it,
  leaving the page cancels it. The longlist never asks; the public link never asks.
- While stale and not yet rewritten, a Meta Grey line under the note: "Written before your latest
  changes." While it is rewritten, the Task Agent's working line stands in the note's place
  (`ActionLine`: the turning fold mark and "Reviewing the shortlist for gaps"; owner, the words
  do not breathe); the new note replaces it with the arrivals' fade (`anim-swap-in`). The note the
  page opened with does not fade.
- Built in `longlist/shortlistNote.ts` (`useRefreshShortlistNote`, `useNoteRefresh`,
  `NOTE_REFRESH_PAUSE_MS`); the route is typed locally until the generated client carries it.


- **The start-from help line** (owner, round 14): "Optionally start from a completed evidence
  search to draw from its sources and report." (the owner's words without "in the same project",
  which the field no longer requires), replacing "Optional. An evidence search you have already
  run gives the scoping its sources and report; without one it searches for each option."
  (`START_FROM_HELP` in `NewTaskView.tsx`).

- **Correction, the searches offered** (owner, round 14, correcting the lead's reading of the
  earlier note): the multi-select lists only the reader's own finished Evidence searches in the
  chosen project; with no project chosen, only those in no project. Picking a search never
  changes the Project field; changing the project clears the picks it does not hold, and naming a
  new project clears them all (it holds none). The rows drop the grey project line (every row
  listed is in the one place). The help line reads exactly "Optional. Start from a completed
  evidence search in the same project to draw from its sources and report." (owner, 2026-11-09:
  "Optional." as its own sentence). This supersedes the
  "any project or none" bullet and the help line above.

- **No project, no searches** (owner, round 14, replacing the no-project case above): with no
  project chosen, or "New project…" not yet created, "Evidence search to start from" is disabled
  (`MultiSelect`'s `disabled`: Ground fill, Grey words, it does not open, no chips) and its trigger
  reads "Choose a project first", with no extra line. Choosing a project enables it and lists that
  project's completed searches; changing the project clears the picks it does not hold, and going
  back to None clears them all.

## Round 15, the option card's exclusion at the top (owner, 2026-11-09)

- An excluded option's card (by a constraint, by Policy Atlas or by the reader) shows its
  exclusion at the top, under the title, description and header line and above How it works,
  not among the Evidence section's notices: the same words and controls ("Excluded:" in Red, the
  exclusion line, "Add a reason" while it invites one), in the notices' flat form with a Line-2
  rule at its left. Include again stays in the card's action row by the breadcrumb.
- Screenshot: `research/screenshots/round15-scoping-card-excluded-1280.png`.
- **Rows say who, in one phrase** (owner): an excluded row and an excluded tile's tooltip read
  "Excluded by a constraint", "Excluded by you", or "Excluded with the theme <name>" / "Excluded
  with the lever <name>" (`exclusionPhrase`); no constraint's words, no reason.
- **The card's exclusion as labelled facts** (owner; lead correction: `by` is "constrain" or
  "user" only): the Red heading line "Does not meet a constraint" or "Excluded by you" (· with the
  theme <name>), then "Constraint" (when there is one) and "Why" (Policy Atlas's or the reader's
  reason, "Add a reason" after it while it invites one); labels in Meta Grey at a fixed width; no
  By row; "Breaks" is gone (`exclusionFacts`).
- **The card's breadcrumb follows its origin** (owner): opened from the Shortlist page it reads
  "Shortlist / <option>" and links back there (the option links carry `{ from: "shortlist" }` in
  their state); from the longlist, or on a direct load, "Longlist / <option>". Browser Back
  returns to the same page.
- Screenshots: `research/screenshots/round15-scoping-card-excluded-1280.png`,
  `research/screenshots/round15-scoping-excluded-open-1280.png` (and `-shut-`).
- **Lead rulings, same round**: rows inside an excluded group carry no exclusion phrase (the
  group's heading names the theme or lever); rows in the "Options" group keep "Excluded by a
  constraint" / "Excluded by you". The Evidence section's constraint notices say "Does not meet:"
  instead of "Breaks:"; the word "Breaks" is gone from the product.

