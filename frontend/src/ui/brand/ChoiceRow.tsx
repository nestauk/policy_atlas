import { scrub } from "../../lib/scrub";
import { cn } from "./cn";

/**
 * One choice in a radio list (one shape for a choice): the
 * label, then its plain sentences in grey. Nothing is pre-selected; the dot
 * fills only once the user has chosen.
 */
export function ChoiceRow({
  label,
  sentences,
  selected,
  disabled = false,
  onChoose,
  ...data
}: {
  label: string;
  /** The option's sentence, then its reason, when it has them. */
  sentences: Array<string | null | undefined>;
  selected: boolean;
  disabled?: boolean;
  onChoose: () => void;
  [dataAttribute: `data-${string}`]: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      className="-mx-2 flex w-[calc(100%+1rem)] cursor-pointer items-start gap-3 px-2 py-2 text-left transition-colors duration-150 hover:bg-paper-2 disabled:cursor-default disabled:hover:bg-transparent"
      onClick={onChoose}
      {...data}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-1 flex size-4 shrink-0 items-center justify-center rounded-full border-2",
          selected ? "border-navy" : "border-navy/40",
        )}
      >
        {selected ? <span className="size-2 rounded-full bg-navy" /> : null}
      </span>
      <span className="min-w-0">
        <span className="block text-body font-semibold text-navy">{scrub(label)}</span>
        {sentences
          .filter((sentence): sentence is string => sentence != null && sentence !== "")
          .map((sentence) => (
            <span key={sentence} className="block text-body text-grey">
              {scrub(sentence)}
            </span>
          ))}
      </span>
    </button>
  );
}
