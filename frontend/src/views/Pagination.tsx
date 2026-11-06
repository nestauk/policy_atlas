import { Figures } from "../lib/figures";
import { Button } from "../ui/brand/Button";

/**
 * Previous and Next under a paged table (All sources, Findings): outline
 * buttons at the 40 px control height and "Page 1 of 2" between them at Meta
 * size in tabular figures (task 058, round 10). The caller moves the reader
 * to the top of the new page.
 *
 * Args:
 *   page: The page shown, from 1.
 *   totalPages: How many pages there are.
 *   onPage: Called with the page to show.
 */
export function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  return (
    <nav aria-label="Pages" className="mt-5 flex items-center gap-3">
      <Button variant="outline" className="h-10 py-0" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span className="text-meta text-grey">
        <Figures text={`Page ${page} of ${totalPages}`} />
      </span>
      <Button variant="outline" className="h-10 py-0" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </nav>
  );
}
