import { createContext, useContext, type ReactNode } from "react";

/**
 * Whether the surrounding task view is the public (link-shared) view —
 * task 037. Default `false`: the full signed-in app never sets it, so
 * every existing surface keeps today's behaviour.
 *
 * The public view renders the same Results and Sources components but must
 * issue only public-surface requests: consumers use this bit to disable the
 * chat queries and hide chat affordances. The SSE stream is handled at the
 * shell instead (`RunStreamProvider connect={false}`).
 */
const PublicViewContext = createContext(false);

export function PublicViewProvider({
  value,
  children,
}: {
  value: boolean;
  children: ReactNode;
}) {
  return <PublicViewContext.Provider value={value}>{children}</PublicViewContext.Provider>;
}

/** Read whether this render sits inside the public task view. */
export function usePublicView(): boolean {
  return useContext(PublicViewContext);
}
