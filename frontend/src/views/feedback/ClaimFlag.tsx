/**
 * The claim flag (in-app feedback, element D), inside the claim's evidence sheet.
 *
 * Three parts share one state, which `ClaimFlagProvider` holds:
 * - `FlaggableSource` wraps each cited-source block. It adds the checkbox
 *   "Doesn't support the claim" and notes when the block came into view.
 * - `ClaimFlagBlock` is the form at the foot of the sheet.
 * - `FlagClaimButton` is the small control on a claim in the report body. It
 *   opens the same sheet at the form: one entry point, one record.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  useFeedback,
  useRetractFeedback,
  useSubmitFeedback,
  type FeedbackBody,
  type FeedbackRecord,
} from "../../api/feedback";
import { Button } from "../../ui/brand/Button";
import { Checkbox } from "../../ui/brand/Checkbox";
import { cn } from "../../ui/brand/cn";

type ClaimFlagBody = Extract<FeedbackBody, { kind: "claim_flag" }>;
type Reason = ClaimFlagBody["reason"];

/** "What's wrong with it?": each reason's label and its plain meaning. */
const REASONS: ReadonlyArray<{ value: Reason; label: string; meaning: string }> = [
  { value: "wrong", label: "Wrong", meaning: "Factually incorrect." },
  {
    value: "overstated",
    label: "Overstated",
    meaning: "Stronger than the evidence supports, for example certain where the source is mixed.",
  },
  {
    value: "unsupported",
    label: "Citation doesn't support it",
    meaning: "Tick which source above.",
  },
];
const REASON_LABELS = Object.fromEntries(
  REASONS.map(({ value, label }) => [value, label]),
) as Record<Reason, string>;

interface ClaimFlagState {
  taskId: string;
  artefactId: string;
  claimId: string;
  /** Whether the sheet opened from the flag control: scroll to the form. */
  openAtFlag: boolean;
  /** The citations ticked as "Doesn't support the claim". */
  failing: ReadonlySet<string>;
  setFailing: (citationIds: string[], failing: boolean) => void;
  /** The citations whose source block came into view. */
  viewed: ReadonlySet<string>;
  markViewed: (citationIds: string[]) => void;
}

const ClaimFlagContext = createContext<ClaimFlagState | null>(null);

/** The claim flag's shared state. The parts below are used only inside the provider. */
function useClaimFlag(): ClaimFlagState {
  const state = useContext(ClaimFlagContext);
  if (state === null) throw new Error("the claim flag parts need a ClaimFlagProvider");
  return state;
}

/**
 * Add or remove ids in a set, as a new set.
 *
 * Args:
 *   current: The set.
 *   ids: The ids to change.
 *   present: True to add them, false to remove them.
 *
 * Returns:
 *   The new set. `current` is not changed.
 */
function withIds(current: ReadonlySet<string>, ids: string[], present: boolean): Set<string> {
  const next = new Set(current);
  for (const id of ids) {
    if (present) next.add(id);
    else next.delete(id);
  }
  return next;
}

/**
 * Hold the state of one claim's flag for the parts in the sheet.
 *
 * Args:
 *   taskId: The task.
 *   artefactId: The report that holds the claim.
 *   claimId: The claim.
 *   openAtFlag: Whether the sheet opened from the flag control.
 *   children: The sheet.
 */
export function ClaimFlagProvider({
  taskId,
  artefactId,
  claimId,
  openAtFlag = false,
  children,
}: {
  taskId: string;
  artefactId: string;
  claimId: string;
  openAtFlag?: boolean;
  children: ReactNode;
}) {
  const [failing, setFailingState] = useState<ReadonlySet<string>>(new Set());
  const [viewed, setViewed] = useState<ReadonlySet<string>>(new Set());
  // Stable functions, so that an effect that uses one does not run again on
  // each render.
  const setFailing = useCallback(
    (citationIds: string[], isFailing: boolean) =>
      setFailingState((current) => withIds(current, citationIds, isFailing)),
    [],
  );
  const markViewed = useCallback(
    (citationIds: string[]) =>
      setViewed((current) =>
        citationIds.every((id) => current.has(id)) ? current : withIds(current, citationIds, true),
      ),
    [],
  );
  const state: ClaimFlagState = {
    taskId,
    artefactId,
    claimId,
    openAtFlag,
    failing,
    setFailing,
    viewed,
    markViewed,
  };
  return <ClaimFlagContext.Provider value={state}>{children}</ClaimFlagContext.Provider>;
}

/**
 * One cited-source block with its "Doesn't support the claim" checkbox.
 *
 * The block's citations count as viewed when the block is in view. A browser
 * with no `IntersectionObserver` records nothing as viewed.
 *
 * Args:
 *   citationIds: The claim's citations of this source.
 *   children: The source block.
 */
export function FlaggableSource({
  citationIds,
  children,
}: {
  citationIds: string[];
  children: ReactNode;
}) {
  const { failing, setFailing, markViewed } = useClaimFlag();
  const box = useRef<HTMLDivElement>(null);
  const key = citationIds.join(",");
  useEffect(() => {
    if (box.current === null || typeof IntersectionObserver === "undefined") return undefined;
    const ids = key.split(",");
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) markViewed(ids);
    });
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [key, markViewed]);
  return (
    <div ref={box}>
      {children}
      <Checkbox
        checked={citationIds.every((id) => failing.has(id))}
        onChange={(checked) => setFailing(citationIds, checked)}
        label={<span className="text-meta text-navy">Doesn't support the claim</span>}
      />
    </div>
  );
}

/** The form at the foot of the sheet: flag the claim, or change or remove the flag. */
export function ClaimFlagBlock() {
  const uid = useId();
  const { taskId, artefactId, claimId, openAtFlag, failing, setFailing, viewed } = useClaimFlag();
  const flags = useFeedback(taskId, "claim_flag");
  const submit = useSubmitFeedback(taskId);
  const retract = useRetractFeedback(taskId, "claim_flag");
  const flag: FeedbackRecord | undefined = flags.data?.find(
    (record) => record.target_id === claimId,
  );
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [attempted, setAttempted] = useState(false);
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    if (openAtFlag) box.current?.scrollIntoView({ block: "start" });
  }, [openAtFlag]);

  const noReason = reason === null;
  const noSource = reason === "unsupported" && failing.size === 0;
  const busy = submit.isPending || retract.isPending;
  const reset = () => {
    setEditing(false);
    setReason(null);
    setNote("");
    setAttempted(false);
    setFailing([...failing], false);
  };
  const onSubmit = () => {
    setAttempted(true);
    if (noReason || noSource) return;
    submit.mutate(
      {
        kind: "claim_flag",
        surface: "report_claim_sidebar",
        task_id: taskId,
        artefact_id: artefactId,
        claim_id: claimId,
        reason,
        failing_citation_ids: [...failing],
        provenance_viewed: [...viewed],
        note: note.trim() || null,
      },
      { onSuccess: reset },
    );
  };

  const heading = <h3 className="text-body font-bold text-navy">Flag this claim</h3>;
  if (flag !== undefined && !editing) {
    const stored = flag.payload as { reason: Reason; note?: string };
    return (
      <section ref={box} aria-label="Flag this claim" className="border-t border-line pt-4">
        {heading}
        <p role="status" className="mt-2 text-body text-navy">
          You flagged this claim: {REASON_LABELS[stored.reason]}.
        </p>
        <div className="mt-3 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="min-h-11"
            disabled={busy}
            onClick={() => {
              setReason(stored.reason);
              setNote(stored.note ?? "");
              setEditing(true);
            }}
          >
            Change
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="min-h-11"
            disabled={busy}
            onClick={() => retract.mutate(flag.feedback_event_id)}
          >
            Remove flag
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section ref={box} aria-label="Flag this claim" className="border-t border-line pt-4">
      {heading}
      <fieldset className="mt-2">
        <legend className="text-meta font-semibold text-navy">What's wrong with it?</legend>
        <div className="mt-1 flex flex-col">
          {REASONS.map(({ value, label, meaning }) => (
            <label
              key={value}
              className="flex min-h-11 cursor-pointer items-start gap-3 py-2 text-body text-navy"
            >
              <input
                type="radio"
                name={`${uid}-reason`}
                required
                checked={reason === value}
                onChange={() => setReason(value)}
                className="mt-1 size-4 shrink-0 accent-navy"
              />
              <span>
                {label}
                <span className="block text-meta text-grey">{meaning}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {attempted && (noReason || noSource) && (
        <p role="alert" className="mt-1 text-meta text-red">
          {noReason ? "Choose what is wrong with the claim." : "Tick at least one source above."}
        </p>
      )}
      <label htmlFor={`${uid}-note`} className="mt-3 block text-meta font-semibold text-navy">
        Note <span className="font-normal text-grey">(optional)</span>
      </label>
      <textarea
        id={`${uid}-note`}
        rows={2}
        value={note}
        maxLength={2000}
        onChange={(event) => setNote(event.target.value)}
        className="mt-1.5 w-full border border-line-2 bg-paper px-3 py-2.5 text-body text-navy outline-none focus:border-blue"
      />
      {(submit.isError || retract.isError) && (
        <p role="alert" className="mt-1 text-meta text-red">
          We could not save the flag. Try again.
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <Button variant="outline" className="min-h-11" disabled={busy} onClick={onSubmit}>
          Submit flag
        </Button>
        <Button variant="ghost" className="min-h-11" disabled={busy} onClick={reset}>
          Cancel
        </Button>
      </div>
    </section>
  );
}

/**
 * The flag control on a claim in the report body. It shows when the pointer
 * is on the claim (the parent has the `group` class) or the control has focus.
 *
 * Args:
 *   onFlag: Opens the claim's evidence sheet at the flag form.
 *   className: Placement.
 */
export function FlagClaimButton({ onFlag, className }: { onFlag: () => void; className?: string }) {
  return (
    <button
      type="button"
      aria-label="Flag this claim"
      title="Flag this claim"
      onClick={onFlag}
      className={cn(
        "ml-0.5 inline-flex cursor-pointer items-center align-[-2px] text-grey opacity-0 transition-opacity hover:text-navy focus-visible:opacity-100 group-hover:opacity-100 print:hidden",
        className,
      )}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="size-3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 22V4" />
        <path d="M4 4h13l-2 4 2 4H4" />
      </svg>
    </button>
  );
}
