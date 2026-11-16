import { scrub } from "../../lib/scrub";
import { cn } from "../../ui/brand/cn";
import { LABEL_CLASS } from "../../ui/brand/label";

/**
 * A group's name and count, the one heading style for the longlist (round
 * 13, owner): the list's group headings and the grid's column and row
 * heads. The name in the Label style in Navy (uppercase, tracked, bold);
 * the count after it in Meta Grey, regular case.
 *
 * Args:
 *   title: The group's name (a theme, a lever type, a level word).
 *   count: The count's words ("6 options"); "" for none.
 *   stacked: The count on its own line under the name (a narrow grid head).
 *   className: Layout for the whole heading.
 */
export function GroupHeading({
  title,
  count,
  stacked = false,
  className,
}: {
  title: string;
  count: string;
  stacked?: boolean;
  className?: string;
}) {
  return (
    <span className={cn(LABEL_CLASS, "text-navy", className)}>
      <GroupName title={title} />
      {count !== "" && (stacked ? <br /> : " ")}
      {count !== "" && <GroupCount count={count} />}
    </span>
  );
}

/** The group's name in the heading style: uppercase Label, Navy. */
export function GroupName({ title, className }: { title: string; className?: string }) {
  return <span className={cn("uppercase text-navy", className)}>{scrub(title)}</span>;
}

/** The group's count beside its name: Meta Grey, regular case. */
export function GroupCount({ count, className }: { count: string; className?: string }) {
  return <span className={cn("whitespace-nowrap text-meta font-normal tracking-normal normal-case text-grey", className)}>{count}</span>;
}
