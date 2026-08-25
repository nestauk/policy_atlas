import { useParams } from "react-router";

import { useUpdateProject } from "../api/mutations";
import { usePortfolios, useProject } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { COPY, LIFECYCLE_LABELS } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";

/**
 * Share: assignment lives here from task creation. Real sharing/export is
 * still named as coming, not pretended to exist.
 */
export function ShareView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const portfolios = usePortfolios();
  const update = useUpdateProject(projectId);
  useDocumentTitle(project.data?.name, LIFECYCLE_LABELS.share);

  const memberIds = project.data?.portfolio_ids ?? [];
  const portfolioName = new Map(
    (portfolios.data?.data ?? []).map((portfolio) => [portfolio.portfolio_id, portfolio.name]),
  );
  const available = (portfolios.data?.data ?? []).filter(
    (portfolio) => !memberIds.includes(portfolio.portfolio_id),
  );

  const setMembership = (portfolioIds: string[]) => {
    update.mutate({ portfolio_ids: portfolioIds });
  };

  return (
    <main className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
      <section aria-labelledby="membership-heading">
        <h2 id="membership-heading" className="text-lead font-semibold text-navy">
          Projects this task belongs to
        </h2>
        {memberIds.length === 0 ? (
          <p className="mt-3 text-body text-grey">Not in a project yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {memberIds.map((portfolioId) => (
              <li key={portfolioId} className="flex items-center justify-between gap-3">
                <span className="text-body text-navy">
                  {portfolioName.get(portfolioId) ?? portfolioId}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setMembership(memberIds.filter((candidate) => candidate !== portfolioId))
                  }
                  disabled={update.isPending}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
        {available.length > 0 && (
          <label className="mt-4 block max-w-md">
            <span className="mb-1 block text-caption font-semibold text-grey">Add to a project</span>
            <select
              className="w-full border border-line bg-paper px-3 py-2 text-body text-navy"
              defaultValue=""
              disabled={update.isPending}
              onChange={(event) => {
                const value = event.target.value;
                if (value === "") return;
                setMembership([...memberIds, value]);
                event.target.value = "";
              }}
            >
              <option value="">Select a project</option>
              {available.map((portfolio) => (
                <option key={portfolio.portfolio_id} value={portfolio.portfolio_id}>
                  {portfolio.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>
      <p className="mt-10 text-lead text-grey">{COPY.shareComingSoon}</p>
    </main>
  );
}
