/**
 * Where Radix portals mount: inside the full-screen element while one is
 * open (only it shows then), otherwise the default, the page body.
 */
export function portalContainer(): HTMLElement | undefined {
  if (typeof document === "undefined") return undefined;
  return (document.fullscreenElement as HTMLElement | null) ?? undefined;
}
