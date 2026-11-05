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
  list; the chevron is absent.
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
| 10 | review, agent pass | | | lead |
| 11 | review, owner pass | | | owner |

## Deferred polish

Notes the owner gave that this slice does not take, with where they go (`docs/deferred.md`).
None yet; the owner will add them on the live app.
