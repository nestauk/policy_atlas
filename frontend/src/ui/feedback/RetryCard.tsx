import { Button } from "../brand/Button";
import { Card } from "../brand/Card";
import { cn } from "../brand/cn";

/**
 * A view that could not load (task 058 consistency pass): one sentence on
 * what failed and a Retry button under it, the same `Button` secondary small
 * the Agent tab's failed turn uses, so Retry looks one way everywhere.
 */
export function RetryCard({
  copy,
  onRetry,
  className,
}: {
  copy: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <Card role="alert" className={cn("flex flex-col items-center gap-3 p-8 text-center", className)}>
      <p className="text-body text-navy">{copy}</p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        Retry
      </Button>
    </Card>
  );
}
