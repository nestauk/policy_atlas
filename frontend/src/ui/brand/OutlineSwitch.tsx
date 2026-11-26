import { cn } from "./cn";

/**
 * A switch between two or three views: the outline button's look, joined into one bar,
 * `aria-pressed` on each; the chosen one takes a Navy border and Navy words,
 * the others stay Grey and turn Navy on hover. Never a fill: the fill belongs
 * to the page's one primary. 40 px tall beside the page's other controls (the
 * longlist's Group by and List / Grid); 32 px in a filter bar (the
 * Landscape's List / Map).
 *
 * Args:
 *   label: The group's accessible name.
 *   choices: The views, in order.
 *   value: The chosen view.
 *   onChange: Called with the view pressed.
 *   height: 40 (default) or 32 px.
 *   disabled: Every button inert; the chosen one keeps its look, the others
 *     take the disabled outline's Line 2 words and no hover.
 */
export function OutlineSwitch<K extends string>({
  label,
  choices,
  value,
  onChange,
  height = 40,
  disabled = false,
}: {
  label: string;
  choices: ReadonlyArray<{ key: K; label: string }>;
  value: K;
  onChange: (key: K) => void;
  height?: 40 | 32;
  disabled?: boolean;
}) {
  return (
    <div role="group" aria-label={label} className="flex">
      {choices.map((choice, index) => {
        const pressed = choice.key === value;
        return (
          <button
            key={choice.key}
            type="button"
            aria-pressed={pressed}
            disabled={disabled}
            onClick={() => onChange(choice.key)}
            className={cn(
              "pressable relative cursor-pointer border bg-paper text-meta font-semibold transition-colors duration-150",
              height === 40 ? "h-10 px-3.5" : "h-8 px-3",
              index > 0 && "-ml-px",
              "disabled:cursor-default",
              pressed
                ? "z-10 border-navy text-navy"
                : disabled
                  ? "border-line-2 text-line-2"
                  : "border-line-2 text-grey hover:bg-hover-fill hover:text-navy",
            )}
          >
            {choice.label}
          </button>
        );
      })}
    </div>
  );
}
