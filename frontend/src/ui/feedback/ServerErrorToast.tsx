import { useCallback } from "react";

import { useToast } from "../radix/Toast";

/** Send recoverable server failures to the shared toast surface. */
export function useServerErrorToast() {
  const { toast } = useToast();
  return useCallback((retry: () => void | Promise<void>) => {
    toast({
      title: "Something went wrong",
      description: "Your work is still here. Try the request again.",
      tone: "error",
      action: { label: "Retry", onClick: () => void retry() },
    });
  }, [toast]);
}
