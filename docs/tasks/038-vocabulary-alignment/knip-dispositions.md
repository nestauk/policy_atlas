# knip dispositions (D8 / Phase 8 item 2)

Tool: `knip@5.88.1` via `pnpm dlx` (no new dependency). Fresh run taken on
`task/038-vocabulary-alignment` after Phases 4, 5a, 5b, 7 (the plan's D8
worklist was taken on `dev` `8626594f`, before those phases; this table
supersedes it as the run-time authority — file/line numbers below match the
current tree, not the worklist).

Rule: an unused export referenced inside its own file loses `export`; one
referenced nowhere is deleted; tests, e2e specs and the dynamic imports in
`routes.tsx`/`main.tsx` count as references. `src/api/gen/**` and
`playwright.fe-api-smoke.config.ts` are always kept.

Raw output: `knip-before.txt` (52 unused exports, 47 unused exported types, 1
unused file, 1 duplicate export) and `knip-after.txt` (2 unused exported
types — both `src/api/gen/types.ts`, generated — and 1 unused file — the
smoke-test config, kept by rule).

| File | Symbol | Disposition | Reason |
|---|---|---|---|
| `src/App.tsx` | `App` (named, beside default) | un-export | `main.tsx` and `App.test.tsx` only ever import the default; dropped the named `export` on the function, kept `export default App` |
| `src/api/client.ts` | `createApiClient` | delete | referenced nowhere (only its own declaration and a `README.md` mention, which was corrected) |
| `src/lib/composerSeed.ts` | `seedComposer` | delete | referenced nowhere; the `policy-atlas:seed-composer` DOM event has no dispatcher left |
| `src/mock/fixtures.ts` | `MOCK_ORGANISATION_ID` | un-export | only used inside `fixtures.ts` itself (`mockTask` fixture) |
| `src/mock/fixtures.ts` | `MOCK_PLANNING_TURN_IDS` | un-export | only used inside `fixtures.ts` itself |
| `src/mock/index.ts` | `MOCK_CHECK_IN_ID` (re-export) | delete | barrel re-export unused — `api.ts` imports it directly from `./fixtures`, not via the barrel; the underlying export in `fixtures.ts` stays (still a direct-import reference) |
| `src/mock/index.ts` | `MOCK_RUN_ID` (re-export) | delete | same — `api.ts` imports directly from `./fixtures` |
| `src/store/conversations.ts` | `ChatStreamInterruptedError` | un-export | thrown and referenced only within `conversations.ts` |
| `src/store/conversations.ts` | `OptimisticChatTranscriptState` (type) | un-export | only used inside `conversations.ts` |
| `src/store/conversations.ts` | `OptimisticChatTranscriptAction` (type) | un-export | only used inside `conversations.ts` |
| `src/store/conversations.ts` | `ChatStreamEvent` (type) | un-export | only used inside `conversations.ts` |
| `src/store/index.ts` | `reduceRunStreamFrame`, `initialOptimisticTranscriptState`, `reduceOptimisticTranscript`, `retryInputForOptimisticTurn`, `transcriptRows`, `chatTranscriptRows`, `consumeChatStream`, `initialOptimisticChatTranscriptState`, `reduceOptimisticChatTranscript`, `retryInputForOptimisticChatTurn`, `RUN_STREAM_INVALIDATE_DEBOUNCE_MS`, `GLOBAL_LIVENESS_KEY` (12 barrel re-exports) | delete | none of these is ever imported from `"../store"` / `"../../store"`; each origin module (`reducer.ts`, `transcript.ts`, `conversations.ts`, `useRunStream.tsx`, `types.ts`) keeps its own direct export because its own test file (or a sibling module) imports it straight from the source file, not the barrel |
| `src/store/index.ts` | `CheckInOut`, `PlanState`, `TaskSummary`, `RunRef`, `StageLiveness`, `StageName`, `OptimisticTranscriptAction`, `OptimisticTranscriptState`, `PlanningTranscriptTurn`, `ChatStreamEvent`, `OptimisticChatTranscriptAction`, `OptimisticChatTranscriptState` (12 barrel re-exported types) | delete | same — no consumer imports these type names from the barrel; `CheckInOut`/`PlanningTranscriptTurn` keep their origin export (real direct-import consumers exist); the rest are handled at their origin file below |
| `src/store/thread.ts` | `SessionAnsweredCheckIn` | un-export | only used inside `thread.ts`; consumers only ever import the functions (`recordSessionAnsweredCheckIn`, `sessionAnsweredCheckIn`) |
| `src/store/transcript.ts` | `OptimisticTranscriptState` | un-export | only used inside `transcript.ts` (flagged at both barrel and origin — zero outside consumers) |
| `src/store/transcript.ts` | `OptimisticTranscriptAction` | un-export | same |
| `src/store/types.ts` | `PlanState`, `TaskSummary`, `RunRef`, `StageLiveness`, `StageName` | un-export | each used only as a field type inside `RunStreamState` in `types.ts` itself; no direct importer anywhere (confirmed once the barrel re-export above was removed) |
| `src/ui/brand/Nav.tsx` | `NAV_BAR_HEIGHT_PX` | delete | referenced nowhere, not even inside `Nav.tsx` itself |
| `src/ui/brand/foldMark.ts` | `H`, `MID`, `CORNERS`, `OUTER`, `ALL`, `SAND`, `TEAL`, `SALMON`, `PINK`, `Corner`, `Point`, `FoldFrame`, `SplashPathsResult` | un-export | all used internally to build `FRAMES`/`splashFoldFrames`/`splashPathsAt`; `FoldPath`, `framePaths`, `pathsAt`, `splashFoldFrames`, `splashPathsAt`, `BRAND_MARK_SIZE`, `BRAND_MARK_VIEWBOX`, `BLUE`, `FRAMES`, `STATIC_LOGO_FRAME`, `PASTEL_SHEET_COLOURS`, `SPLASH_LAYOUT` stay exported — consumed by `foldMark.test.ts`, `FoldMarkAnimated.tsx`, `FoldMarkIcon.tsx`, `SplashField.tsx` |
| `src/ui/brand/Button.tsx` | `ButtonProps` | un-export | only used inside `Button.tsx` as the `Button` component's own prop type |
| `src/ui/brand/LifecycleBar.tsx` | `LifecycleBarItem` | un-export | only used inside `LifecycleBar.tsx` |
| `src/ui/radix/Popover.tsx` | `PopoverAnchor` | delete | referenced nowhere; `Popover`/`PopoverTrigger`/`PopoverContent` stay (used elsewhere) |
| `src/ui/radix/Sheet.tsx` | `SheetClose` | delete | referenced nowhere |
| `src/ui/feedback/index.ts` | `errorCode`, `fieldErrorsFromEnvelope`, `conflictSentences`, `isConflictCode`, `ErrorBoundary` (re-exports), `ConflictCode`, `FieldErrorMap` (re-exported types) | delete | barrel re-exports unused — every consumer (`SourcesView.tsx`, `ProjectsView.tsx`, `PlanningPane.tsx`, `AppShell.tsx`, `FieldErrors.tsx`, etc.) imports these directly from `../../lib/errors` or `./ErrorBoundary`, not from the barrel; `FieldErrors`, `InterruptedRunCard`, `NotFoundView`, `ReauthRedirect`, `ReconnectingBanner` stay in the barrel (real barrel consumers, e.g. `ReauthRedirect` via `"../ui/feedback"`) |
| `src/lib/capabilities.ts` | `CapabilityKey` | delete | referenced nowhere, not even inside `capabilities.ts` |
| `src/lib/errors.ts` | `ConflictCode` | un-export | flagged at both the (now-removed) barrel and the origin — zero outside consumers; still used inside `errors.ts` to type `conflictSentences` and narrow in `isConflictCode` |
| `src/api/queries.ts` | `TasksQuery`, `ProjectsQuery`, `FindingsQuery`, `ConversationQuery` | un-export | each only used inside `queries.ts` (its own query-key builder and hook) |
| `src/api/sse.ts` | `ConnectEventStreamOptions`, `EventStreamConnection` | un-export | only used inside `sse.ts`, by `connectEventStream` |
| `src/auth/index.ts` | `AuthUser` (re-export) | delete | barrel re-export unused; `AuthApi`, `AuthStatus` stay (real barrel consumers) |
| `src/auth/types.ts` | `AuthUser` | un-export | only used inside `types.ts` as `AuthApi.user`'s type; no direct importer anywhere |
| `src/views/FindingsView.tsx` | `statRows` | un-export | only used inside `FindingsView.tsx` |
| `src/views/decisionsPresentation.ts` | `DECISION_DETAIL_LABELS`, `FriendlyDetail`, `PresentedDecision` | un-export | each only used inside `decisionsPresentation.ts` |
| `src/views/landingPresentation.ts` | `STALE_AFTER_MONTHS`, `RunPresentation` | un-export | each only used inside `landingPresentation.ts` |
| `src/views/listPageChrome.ts` | `PAGE_COLUMN_MAX_W` | un-export | only used inside `listPageChrome.ts` to build `WIDE_PAGE_CLASS` |
| `src/views/sourcesPresentation.ts` | `humanReason` | un-export | only used inside `sourcesPresentation.ts` |
| `src/views/splash/SplashFeatureSteps.tsx` | `SPLASH_FEATURES` | un-export | only used inside `SplashFeatureSteps.tsx` |
| `src/views/workspace/checkInPresentation.ts` | `BACKEND_LABELS`, `CHECK_IN_COUNT_LABELS`, `TRIGGER_COPY`, `PresentedCheckInRender` | un-export | each only used inside `checkInPresentation.ts` |
| `src/views/workspace/planOverlay.ts` | `yearFromIso`, `geographyFromConstraints` | un-export | each only used inside `planOverlay.ts` |
| `src/views/workspace/planVocabulary.ts` | `RESEARCH_APPROACH_PRESETS`, `TIME_BANDS` | un-export | each only used inside `planVocabulary.ts` |
| `src/views/workspace/runProgress.ts` | `currentStepLabel`, `RunningCardTone`, `StageSignpost` | un-export | each only used inside `runProgress.ts` |
| `src/views/ArtefactView.tsx` | `SpanSegment` (type) | un-export | only used inside `ArtefactView.tsx` (incl. `BulletSegment`) |
| `src/views/TaskListPanel.tsx` | `TaskListItem` (type) | un-export | only used inside `TaskListPanel.tsx` |
| `src/views/historyPresentation.ts` | `HistoryRow` (type) | un-export | only used inside `historyPresentation.ts` |
| `src/views/workspace/rail.tsx` | `RailState` (type) | un-export | only used inside `rail.tsx` (`useRail`'s return type) |
| `src/views/workspace/journey/presentation.ts` | `FUNNEL_STAGES`, `funnelBarWidth`, `completionCopy` | delete (dead-with-justification) | became test-only when `JourneyPane` was deleted (Phase 1); no non-test consumer remains. Their tests in `presentation.test.ts` were deleted too; `timelineSummary` (used by `runProgress.ts`) and its test were kept |
| `playwright.fe-api-smoke.config.ts` | (whole file) | keep | `scripts/fe_api_smoke.sh` runs it |
| `src/api/gen/types.ts` | `webhooks`, `$defs` | keep | generated file — never hand-edited |

## Counts

- Before: 1 unused file, 52 unused exports, 47 unused exported types, 1
  duplicate export (101 findings total).
- After: 1 unused file (kept — smoke config), 2 unused exported types (kept —
  generated). Nothing else remains.
- Dispositions applied: 2 whole-symbol deletions with no export at all
  (`NAV_BAR_HEIGHT_PX`, `CapabilityKey`) referenced nowhere even internally;
  5 further deletions of dead functions/re-exports referenced nowhere
  (`createApiClient`, `seedComposer`, `PopoverAnchor`, `SheetClose`, plus the
  3-symbol `journey/presentation.ts` dead-with-justification group and its
  now-pointless tests); 2 barrel-only re-export groups pruned entirely
  (`ui/feedback/index.ts`, `auth/index.ts`'s `AuthUser` line, `mock/index.ts`'s
  two lines) whose underlying origin exports mostly survive on direct-import
  grounds; one large barrel (`store/index.ts`) trimmed of 24 dead re-exports
  (12 values + 12 types); roughly 40 symbols across ~25 files lost their
  `export` keyword while staying in place, each because it is used only
  inside its own file.
