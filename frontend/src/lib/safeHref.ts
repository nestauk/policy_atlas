/**
 * Validate a source-derived URL before binding it to an `href`.
 *
 * Args:
 *   url: Untrusted, source-derived URL string.
 *
 * Returns:
 *   `url` unchanged when it parses to the `http:` or `https:` scheme,
 *   otherwise `undefined` — callers render the text without a link rather
 *   than trust an arbitrary scheme (`javascript:`, `data:`, etc.).
 */
export function safeHref(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? url : undefined;
  } catch {
    return undefined;
  }
}
