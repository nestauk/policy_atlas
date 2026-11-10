import { useState } from "react";

import type { components } from "../../api/gen/types";
import { useOptionVerb, useShortlistVerb } from "../../api/mutations";
import { actionFailedNotice } from "../../lib/errors";
import { ACTION_CONTROL_CLASS, ActionGlyph, WithTooltip } from "../../ui/brand/actionControls";
import { CheckCircleIcon, ICON_CHROME } from "../../ui/brand/icons";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { Tooltip, TooltipProvider } from "../../ui/radix/Tooltip";
import { usePublicView } from "../publicView";
import {
  ADD_TO_SHORTLIST_WORDS,
  EXCLUDE_FROM_SHORTLISTING,
  EXCLUDE_OPTION_TOOLTIP,
  REMOVE_FROM_SHORTLIST_WORDS,
  SHORTLISTED_WORD,
} from "./longlistPresentation";

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
  const [notice, setNotice] = useState<ActionNotice | null>(null);

  // Blank sends no reason.
  const exclude = (optionId: string, reason: string) => {
    const trimmed = reason.trim();
    if (excludeOption.isPending || walkActive) return;
    setNotice(null);
    excludeOption.mutate(trimmed === "" ? { optionId } : { optionId, reason: trimmed }, {
      onError: (error) =>
        setNotice({ optionId, text: actionFailedNotice(error, "The option couldn't be excluded. Try again.") }),
    });
  };

  // A whole group at once (round 13, owner): every given option through the
  // same per-option action, each its own request.
  const excludeGroup = (optionIds: readonly string[], reason: string) => {
    if (walkActive || optionIds.length === 0) return;
    setNotice(null);
    for (const optionId of optionIds) {
      excludeOption.mutate(
        { optionId, reason },
        { onError: (error) => setNotice({ optionId: null, text: actionFailedNotice(error, "The options couldn't be excluded. Try again.") }) },
      );
    }
  };
  const includeGroup = (optionIds: readonly string[]) => {
    if (walkActive || optionIds.length === 0) return;
    setNotice(null);
    for (const optionId of optionIds) {
      includeOption.mutate(
        { optionId },
        { onError: (error) => setNotice({ optionId: null, text: actionFailedNotice(error, "The options couldn't be included again. Try again.") }) },
      );
    }
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

  // `onFail` lets the pressed control drop the state it showed at once.
  const shortlist = (optionId: string, onFail?: () => void) => {
    if (shortlistOption.isPending || walkActive) return;
    setNotice(null);
    shortlistOption.mutate(
      { optionId },
      {
        onError: (error) => {
          onFail?.();
          setNotice({ optionId, text: actionFailedNotice(error, "The option couldn't be added to the shortlist. Try again.") });
        },
      },
    );
  };

  const unshortlist = (optionId: string, onFail?: () => void) => {
    if (unshortlistOption.isPending || walkActive) return;
    setNotice(null);
    unshortlistOption.mutate(
      { optionId },
      {
        onError: (error) => {
          onFail?.();
          setNotice({
            optionId,
            text: actionFailedNotice(error, "The option couldn't be removed from the shortlist. Try again."),
          });
        },
      },
    );
  };

  return {
    walkActive,
    notice,
    setNotice,
    exclude,
    include,
    excludeGroup,
    includeGroup,
    shortlist,
    unshortlist,
    excludePending: excludeOption.isPending,
    includePending: includeOption.isPending,
  };
}

type OptionActions = ReturnType<typeof useOptionActions>;

type ShortlistState = NonNullable<components["schemas"]["OptionSummaryOut"]["shortlist"]>["state"];

/** Whether an option holds a shortlist place (a pick or one added by you). */
function holdsPlace(state: ShortlistState | null | undefined): boolean {
  return state === "proposed" || state === "added_by_you";
}

/**
 * "Shortlisted" with no control, for a row that holds a place while the
 * longlist is still being built and on the public link: the filled circled
 * check in Electric Blue, its word for a screen reader (round 13, owner).
 */
export function ShortlistedWord({ className, glyphSize }: { className?: string; glyphSize?: number }) {
  return (
    <span className={cn("inline-flex h-10 w-10 items-center justify-center text-blue", className)}>
      <CheckCircleIcon filled size={glyphSize} />
      <span className="sr-only">{SHORTLISTED_WORD}</span>
    </span>
  );
}

/**
 * The shortlist state as an icon toggle (round 13, owner): a circled check
 * in a 40 px target, an outline circle in Grey when the option holds no place, filled
 * Electric Blue when it does; `aria-pressed`, and its name and tooltip say
 * what pressing does ("Add to shortlist" / "Remove from shortlist"). The
 * press eases the fill over 150 ms (none under reduced motion). On the
 * public link the filled glyph shows with no button; nothing for an option
 * without a place there, or for an excluded option without one. Disabled
 * while a walk runs or the change is on its way.
 */
export function ShortlistToggle({
  actions,
  optionId,
  shortlistState,
  excluded,
  glyphSize,
  worded = false,
  className,
}: {
  actions: OptionActions;
  optionId: string;
  shortlistState: ShortlistState | null | undefined;
  excluded: boolean;
  /** The option card's form (round 13, owner): the glyph, then "Add to
   *  shortlist" / "Shortlisted" in the quiet style, beside Exclude. */
  worded?: boolean;
  /** The glyph's size; the target stays 40 px (the grid's tiles: 24). */
  glyphSize?: number;
  className?: string;
}) {
  const publicView = usePublicView();
  const glyph = glyphSize ?? TOGGLE_GLYPH_SIZE;
  const recorded = holdsPlace(shortlistState);
  // The pressed control shows its new state at once and keeps it until the
  // read agrees (or the request fails); no other control dims or changes
  // while it is sent (round 13, owner: no marker flashes).
  const [wanted, setWanted] = useState<boolean | null>(null);
  if (wanted !== null && wanted === recorded) setWanted(null);
  const holds = wanted ?? recorded;
  if (!holds && excluded) return null;
  if (publicView) return holds ? <ShortlistedWord className={className} glyphSize={glyphSize} /> : null;
  const label = holds ? REMOVE_FROM_SHORTLIST_WORDS : ADD_TO_SHORTLIST_WORDS;
  const press = () => {
    if (wanted !== null) return;
    setWanted(!recorded);
    const undo = () => setWanted(null);
    if (recorded) actions.unshortlist(optionId, undo);
    else actions.shortlist(optionId, undo);
  };
  if (worded) {
    return (
      <WithTooltip note={label}>
        <button
          type="button"
          aria-pressed={holds}
          disabled={actions.walkActive}
          onClick={press}
          className={cn(ACTION_CONTROL_CLASS, holds && "text-blue", className)}
        >
          <CheckCircleIcon filled={holds} size={TOGGLE_GLYPH_SIZE} className="shrink-0" />
          {holds ? "Shortlisted" : ADD_TO_SHORTLIST_WORDS}
        </button>
      </WithTooltip>
    );
  }
  return (
    <TooltipProvider delayDuration={250}>
      <Tooltip content={<p>{label}</p>}>
        <button
          type="button"
          aria-pressed={holds}
          aria-label={label}
          disabled={actions.walkActive}
          onClick={press}
          className={cn(
            "pressable inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center transition-colors duration-150",
            "hover:bg-blue-tint-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent",
            holds ? "text-blue" : "text-grey hover:text-navy",
            className,
          )}
        >
          <CheckCircleIcon filled={holds} size={glyph} />
        </button>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * Exclude, or Include again on an excluded option, as a quiet text control
 * (round 13, owner: on the option card only; one action is not a menu).
 * Exclude acts at once (round 13, owner: no reason asked first; "Add a
 * reason" follows the exclusion line). Nothing on the public link.
 */
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
  const publicView = usePublicView();
  if (publicView) return null;
  const disabled = excluded ? actions.includePending || actions.walkActive : actions.excludePending || actions.walkActive;
  const control = (
    <button
      type="button"
      disabled={disabled}
      onClick={() => (excluded ? actions.include(optionId) : actions.exclude(optionId, ""))}
      className={cn(ACTION_CONTROL_CLASS, className)}
    >
      {/* At the card's shortlist toggle's size (round 13, owner). */}
      <ActionGlyph include={excluded} size={TOGGLE_GLYPH_SIZE} />
      {excluded ? "Include again" : EXCLUDE_FROM_SHORTLISTING}
    </button>
  );
  // What it does, on hover and focus (round 13, owner).
  return excluded ? control : <WithTooltip note={EXCLUDE_OPTION_TOOLTIP}>{control}</WithTooltip>;
}

/** The list row's shortlist toggle glyph; a group's control draws its
 *  glyph at the same size, so the two make one column (round 13, owner). */
export const TOGGLE_GLYPH_SIZE = ICON_CHROME;

/**
 * Exclude or Include again on the page's action column (round 13, owner):
 * the words, then the glyph at the row toggle's size centred in the
 * toggle's 40 px width, so its glyph sits in the toggles' column; the hit
 * area is the line's height. One control for both states, on a group's
 * description line and on an excluded row.
 */
export function EdgeAction({
  label,
  include,
  disabled,
  onClick,
  tooltip,
  className,
}: {
  label: string;
  include: boolean;
  disabled: boolean;
  onClick: () => void;
  tooltip?: string;
  className?: string;
}) {
  return (
    <WithTooltip note={tooltip}>
      <button
        type="button"
        data-testid="edge-action"
        disabled={disabled}
        onClick={onClick}
        className={cn(ACTION_CONTROL_CLASS, "shrink-0 gap-0", className)}
      >
        {label}
        <span data-testid="edge-action-glyph" className="inline-flex w-10 justify-center">
          <ActionGlyph include={include} size={TOGGLE_GLYPH_SIZE} />
        </span>
      </button>
    </WithTooltip>
  );
}

/** Whether an exclusion still invites the reader's reason: their own, with
 *  no words yet, or only the group it went with (round 13, owner). */
export function invitesReason(exclusion: { by: string; reason?: string | null } | null | undefined): boolean {
  if (exclusion == null || exclusion.by !== "user") return false;
  const reason = (exclusion.reason ?? "").trim();
  return reason === "" || /^with the (theme|lever) [^:]+$/.test(reason);
}

/**
 * "Add a reason" after an exclusion line (round 13, owner): a quiet text
 * control that opens the inline field with Save and Cancel; saved, the
 * reason joins the line (after the group's words when it went with one).
 * The exclusion route records the new reason. Nothing on the public link.
 */
export function AddReason({
  actions,
  optionId,
  current,
  className,
}: {
  actions: OptionActions;
  optionId: string;
  /** The reason the exclusion holds now ("" or "with the theme <name>"). */
  current: string;
  className?: string;
}) {
  const publicView = usePublicView();
  const [editing, setEditing] = useState(false);
  const [words, setWords] = useState("");
  if (publicView) return null;
  if (!editing) {
    return (
      <button
        type="button"
        disabled={actions.walkActive}
        onClick={() => setEditing(true)}
        className={cn(QUIET_CONTROL_CLASS, "text-meta disabled:cursor-not-allowed disabled:opacity-40", className)}
      >
        Add a reason
      </button>
    );
  }
  const base = current.trim();
  return (
    <form
      className={cn("mt-2 flex flex-wrap items-center gap-2", className)}
      onSubmit={(event) => {
        event.preventDefault();
        const typed = words.trim();
        if (typed === "") return;
        actions.exclude(optionId, base === "" ? typed : `${base}: ${typed}`);
        setEditing(false);
      }}
    >
      <input
        autoFocus
        aria-label="Why exclude this option?"
        value={words}
        onChange={(event) => setWords(event.target.value)}
        placeholder="Why exclude this option?"
        className={REASON_INPUT_CLASS}
      />
      <Button type="submit" variant="secondary" size="sm" disabled={words.trim() === "" || actions.excludePending}>
        Save
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
        Cancel
      </Button>
    </form>
  );
}

