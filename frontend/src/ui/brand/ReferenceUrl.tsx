import { safeHref } from "../../lib/safeHref";
import { displayUrl } from "./reference";

/** The address's look: Grey over a Line 2 underline, both turning Navy on hover. */
const REFERENCE_URL_CLASS =
  "text-grey underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:text-navy hover:decoration-navy";

/**
 * A reference's web address (task 058, consolidation batch B): the last part
 * of the reference line, shown without its scheme ("doi.org/10.1000/x") and
 * opening in a new tab. The report's References and the source dossier use
 * it. Nothing renders for an address that is not http or https.
 *
 * Args:
 *   url: The source's address, untrusted.
 *   printFull: Print the full address, scheme and all (the References: a
 *     printed reference list must be followable); otherwise print shows what
 *     the screen does (the dossier).
 */
export function ReferenceUrl({ url, printFull = false }: { url: string; printFull?: boolean }) {
  const href = safeHref(url.trim());
  if (href === undefined) return null;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={REFERENCE_URL_CLASS}>
      {printFull ? (
        <>
          <span className="print:hidden">{displayUrl(href)}</span>
          <span className="hidden print:inline">{href}</span>
        </>
      ) : (
        displayUrl(href)
      )}
    </a>
  );
}
