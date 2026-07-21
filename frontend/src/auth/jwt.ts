/**
 * Best-effort, unverified read of a JWT's `sub` claim for local display
 * only (e.g. showing "signed in as ..." in the dev-token panel).
 *
 * This is NOT verification — the API is the only party that verifies a
 * token (RS256 against the issuer JWKS, per the web-api.md auth boundary).
 * Returns `null` for anything that doesn't parse as a three-segment JWT
 * with a string `sub`.
 */
export function readUnverifiedJwtSub(token: string): string | null {
  const segments = token.split(".");
  if (segments.length !== 3) return null;
  try {
    const payloadJson = base64UrlDecode(segments[1]);
    const payload: unknown = JSON.parse(payloadJson);
    if (
      typeof payload === "object" &&
      payload !== null &&
      "sub" in payload &&
      typeof (payload as { sub?: unknown }).sub === "string"
    ) {
      return (payload as { sub: string }).sub;
    }
    return null;
  } catch {
    return null;
  }
}

function base64UrlDecode(segment: string): string {
  const padded = segment.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(segment.length / 4) * 4, "=");
  return atob(padded);
}
