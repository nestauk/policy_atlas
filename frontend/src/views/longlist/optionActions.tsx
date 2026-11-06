import { useState, type ReactNode } from "react";

import type { components } from "../../api/gen/types";
import { useOptionVerb, useShortlistVerb } from "../../api/mutations";
import { actionFailedNotice } from "../../lib/errors";
import { BanIcon, UndoIcon, iconButtonClass } from "../../ui/brand/icons";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { Tooltip, TooltipProvider } from "../../ui/radix/Tooltip";
import { ADD_TO_SHORTLIST_WORDS, SHORTLISTED_WORD } from "./longlistPresentation";

/** The reason and add-option inputs share one look. */
export const REASON_INPUT_CLASS =
  "min-w-0 flex-1 border border-line-2 bg-paper px-3 py-1.5 text-body text-ink placeholder:text-grey/80";

/** A refused action's notice, next to the control it came from (task 045,
 *  F15); `optionId` null is the list's add row. */
export type ActionNotice = { optionId: string | null; text: string };

/** Exclude (with an optional reason — owner, 2026-09-24) and include again,
 *  shared by the list view and the option card. */
export function useOptionActions(taskId: string, walkActive: boolean) {
  const excludeOption = useOptionVerb(taskId, "exclude");
  const includeOption = useOptionVerb(taskId, "include");
  const shortlistOption = useShortlistVerb(taskId, "shortlist");
  const unshortlistOption = useShortlistVerb(taskId, "unshortlist");
  const [excludingId, setExcludingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<ActionNotice | null>(null);

  // Blank sends no reason.
  const exclude = (optionId: string, reason: string) => {
    const trimmed = reason.trim();
    if (excludeOption.isPending || walkActive) return;
    setNotice(null);
    excludeOption.mutate(trimmed === "" ? { optionId } : { optionId, reason: trimmed }, {
      onSuccess: () => setExcludingId(null),
      onError: (error) =>
        setNotice({ optionId, text: actionFailedNotice(error, "The option couldn't be excluded. Try again.") }),
    });
  };

  const include = (optionId: string) => {
    if (includeOption.isPending || walkActive) return;
    setNotice(null);
    includeOption.mutate(
      { optionId },
      {
        onError: (error) =>
          setNotice({ optionId, text: actionFailedNotice(error, "The option couldn't be included again. Try again.") }),
      },
    );
  };

  const shortlist = (optionId: string) => {
    if (shortlistOption.isPending || walkActive) return;
    setNotice(null);
    shortlistOption.mutate(
      { optionId },
      {
        onError: (error) =>
          setNotice({ optionId, text: actionFailedNotice(error, "The option couldn't be added to the shortlist. Try again.") }),
      },
    );
  };

  const unshortlist = (optionId: string) => {
    if (unshortlistOption.isPending || walkActive) return;
    setNotice(null);
    unshortlistOption.mutate(
      { optionId },
      {
        onError: (error) =>
          setNotice({
            optionId,
            text: actionFailedNotice(error, "The option couldn't be removed from the shortlist. Try again."),
          }),
      },
    );
  };

  return {
    walkActive,
    excludingId,
    setExcludingId,
    notice,
    setNotice,
    exclude,
    include,
    shortlist,
    unshortlist,
    shortlistPending: shortlistOption.isPending,
    unshortlistPending: unshortlistOption.isPending,
    excludePending: excludeOption.isPending,
    includePending: includeOption.isPending,
  };
}

type OptionActions = ReturnType<typeof useOptionActions>;

/** An icon-only row action: a square ghost-grey hit area, the action's name
 *  as the accessible label and as a hover tooltip in the system's own skin
 *  (owner, 2026-10-27: icons, not words; hover tooltips). Exclude and Include
 *  again; the shortlist is a toggle in words since round 10. The provider
 *  sits on each button so the rows need no wrapper. */

function IconAction({
  label,
  disabled,
  onClick,
  className,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <TooltipProvider delayDuration={250}>
      <Tooltip content={<p>{label}</p>}>
        <button
          type="button"
          aria-label={label}
          className={cn(iconButtonClass("chrome"), className)}
          disabled={disabled}
          onClick={onClick}
        >
          {children}
        </button>
      </Tooltip>
    </TooltipProvider>
  );
}
type ShortlistState = NonNullable<components["schemas"]["OptionSummaryOut"]["shortlist"]>["state"];

/** Whether an option holds a shortlist place (a pick or one added by you). */
function holdsPlace(state: ShortlistState | null | undefined): boolean {
  return state === "proposed" || state === "added_by_you";
}

/** The toggle's words at Meta, the quiet control's underline turning Navy on
 *  hover; held, the words go Navy after a 6 px Navy square, the mark the
 *  building list shows before the toggle exists. 32 px tall, the icon
 *  actions' height. */
const SHORTLIST_TOGGLE_CLASS =
  "inline-flex min-h-8 cursor-pointer items-center gap-1.5 whitespace-nowrap text-meta font-semibold " +
  "underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 " +
  "hover:text-navy hover:decoration-navy disabled:cursor-not-allowed disabled:no-underline disabled:opacity-60";

/** The held state's mark: a 6 px Navy square (DESIGN.md: the status mark's
 *  size), not a word in a chip. */
function HeldMark() {
  return <span aria-hidden="true" className="inline-block size-1.5 flex-none bg-navy" />;
}

/** "Shortlisted" as plain words, for a row that holds a place while the
 *  longlist is still being built (no controls yet): the toggle's held look
 *  without the control, so the walk's end only adds the underline. */
export function ShortlistedWord({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex min-h-8 items-center gap-1.5 whitespace-nowrap text-meta font-semibold text-navy", className)}>
      <HeldMark />
      {SHORTLISTED_WORD}
    </span>
  );
}

/**
 * The shortlist state as a toggle in words (round 10, lead ruling on
 * finding 6): "Shortlisted" with `aria-pressed` true on an option that holds
 * a place (pressing it gives the place up), "Add to shortlist" on an
 * included option that holds none. Nothing for an excluded option without a
 * place. Disabled while a walk runs or the change is on its way.
 */
export function ShortlistToggle({
  actions,
  optionId,
  shortlistState,
  excluded,
  className,
}: {
  actions: OptionActions;
  optionId: string;
  shortlistState: ShortlistState | null | undefined;
  excluded: boolean;
  className?: string;
}) {
  const holds = holdsPlace(shortlistState);
  if (!holds && excluded) return null;
  return (
    <button
      type="button"
      aria-pressed={holds}
      disabled={(holds ? actions.unshortlistPending : actions.shortlistPending) || actions.walkActive}
      onClick={() => (holds ? actions.unshortlist(optionId) : actions.shortlist(optionId))}
      className={cn(SHORTLIST_TOGGLE_CLASS, holds ? "text-navy" : "text-grey", className)}
    >
      {holds && <HeldMark />}
      {holds ? SHORTLISTED_WORD : ADD_TO_SHORTLIST_WORDS}
    </button>
  );
}

/** "Include again" on an excluded option, else "Exclude" (hidden while its
 *  reason form is open). */
export function OptionActionButton({
  actions,
  optionId,
  excluded,
  className,
}: {
  actions: OptionActions;
  optionId: string;
  excluded: boolean;
  className?: string;
}) {
  if (excluded) {
    return (
      <IconAction
        label="Include again"
        className={className}
        disabled={actions.includePending || actions.walkActive}
        onClick={() => actions.include(optionId)}
      >
        <UndoIcon />
      </IconAction>
    );
  }
  if (actions.excludingId === optionId) return null;
  return (
    <IconAction
      label="Exclude"
      className={className}
      disabled={actions.walkActive}
      onClick={() => actions.setExcludingId(optionId)}
    >
      <BanIcon />
    </IconAction>
  );
}

type ReasonFormProps = { actions: OptionActions; optionId: string; className: string };

/** The reason form an Exclude opens: the input, Exclude, Cancel. It mounts
 *  fresh on each open, so the reason starts blank. */
export function ExcludeReasonForm(props: ReasonFormProps) {
  return props.actions.excludingId === props.optionId ? <ReasonForm {...props} /> : null;
}

function ReasonForm({ actions, optionId, className }: ReasonFormProps) {
  const [reason, setReason] = useState("");
  return (
    <form
      className={className}
      onSubmit={(event) => {
        event.preventDefault();
        actions.exclude(optionId, reason);
      }}
    >
      <input
        autoFocus
        aria-label="Why exclude this option?"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder="Why exclude this option?"
        className={REASON_INPUT_CLASS}
      />
      <Button type="submit" variant="secondary" size="sm" disabled={actions.excludePending || actions.walkActive}>
        Exclude
      </Button>
      <Button variant="ghost" size="sm" onClick={() => actions.setExcludingId(null)}>
        Cancel
      </Button>
    </form>
  );
}
