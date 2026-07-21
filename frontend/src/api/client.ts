import createClient from "openapi-fetch";

import type { paths } from "./gen/types";

/** Default API base URL when `VITE_API_BASE_URL` is unset (local dev proxy). */
const DEFAULT_BASE_URL = "/api";

/**
 * Build a typed `openapi-fetch` client bound to the generated `paths`.
 *
 * @param baseUrl - API base URL. Defaults to `VITE_API_BASE_URL`, falling
 *   back to `/api` in its absence.
 * @returns An `openapi-fetch` client whose request/response shapes are
 *   inferred from the generated OpenAPI types — one schema drives both ends.
 */
export function createApiClient(baseUrl: string = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL) {
  return createClient<paths>({ baseUrl });
}
