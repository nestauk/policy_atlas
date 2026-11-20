import { useMe } from "../api/queries";

/** Yellow-tint band under the sensitive-information banner once the caller
 *  has used their yearly task quota. Not dismissible: the
 *  state lasts until a task ages out or an administrator acts. `task_quota`
 *  is null for admins, who are exempt. */
export function QuotaBanner() {
  const quota = useMe().data?.task_quota;
  if (quota == null || quota.used < quota.limit) return null;

  return (
    <div
      role="status"
      // A screen notice, not part of a printed report.
      className="print-hide shrink-0 border-b border-yellow bg-yellow-tint px-5 py-1.5 text-body text-navy"
    >
      <p>
        You have reached your usage quota of {quota.limit} tasks. Contact your Policy Atlas administrator to
        request more.
      </p>
    </div>
  );
}
