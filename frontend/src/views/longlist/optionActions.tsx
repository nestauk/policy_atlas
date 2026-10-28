import { useState, type ReactNode } from "react";

import type { components } from "../../api/gen/types";
import { useOptionVerb, useShortlistVerb } from "../../api/mutations";
import { actionFailedNotice } from "../../lib/errors";
import { BanIcon, MinusIcon, PlusIcon, UndoIcon } from "../../ui/brand/ActionIcons";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { Tooltip, TooltipProvider } from "../../ui/radix/Tooltip";

/** The reason and add-option inputs share one look. */
export const REASON_INPUT_CLASS =
  "min-w-0 flex-1 border border-line-2 bg-paper px-3 py-1.5 text-body text-ink placeholder:text-grey/80 " +
  "focus-visible:outline-2 focus-visible:outline-blue";

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
 *  (owner, 2026-10-27: icons, not words; hover tooltips). The provider sits
 *  on each button so the rows need no wrapper. */
const ICON_BUTTON_CLASS = "h-8 w-8 justify-center px-0 py-0 text-grey hover:text-navy";

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
        <Button
          variant="secondary"
          size="sm"
          aria-label={label}
          className={cn(ICON_BUTTON_CLASS, className)}
          disabled={disabled}
          onClick={onClick}
        >
          {children}
        </Button>
      </Tooltip>
    </TooltipProvider>
  );
}
type ShortlistState = NonNullable<components["schemas"]["OptionSummaryOut"]["shortlist"]>["state"];

/** "Add to shortlist" on an included option holding no place (or only a
 *  Policy Atlas pick), "Remove from shortlist" on one holding any place
 *  (task 055). Nothing for an excluded or merged option. */
export function ShortlistActionButton({
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
  const holds = shortlistState === "proposed" || shortlistState === "added_by_you";
  if (holds) {
    return (
      <IconAction
        label="Remove from shortlist"
        className={className}
        disabled={actions.unshortlistPending || actions.walkActive}
        onClick={() => actions.unshortlist(optionId)}
      >
        <MinusIcon />
      </IconAction>
    );
  }
  if (excluded) return null;
  return (
    <IconAction
      label="Add to shortlist"
      className={className}
      disabled={actions.shortlistPending || actions.walkActive}
      onClick={() => actions.shortlist(optionId)}
    >
      <PlusIcon />
    </IconAction>
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
