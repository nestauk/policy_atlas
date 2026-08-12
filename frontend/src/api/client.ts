import createClient from "openapi-fetch";

import type { AuthApi } from "../auth/types";
import { createAuthMiddleware } from "./authMiddleware";
import type { paths } from "./gen/types";

/** Default API base: same-origin. The generated `paths` already carry the
 * full `/api/v1/...` prefix, so the base is "" — the Vite dev proxy matches
 * `/api` and forwards to the backend. `VITE_API_BASE_URL` overrides for a
 * cross-origin API host. */
const DEFAULT_BASE_URL = "";

/**
 * Return the base URL shared by generated API calls and raw stream requests.
 *
 * Returns:
 *   The configured API origin, or the same-origin empty base.
 */
export function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL;
}

/**
 * Build a typed `openapi-fetch` client bound to the generated `paths`.
 *
 * @param baseUrl - API base URL. Defaults to `VITE_API_BASE_URL`, falling
 *   back to same-origin ("") in its absence.
 * @returns An `openapi-fetch` client whose request/response shapes are
 *   inferred from the generated OpenAPI types — one schema drives both ends.
 */
export function createApiClient(baseUrl: string = apiBaseUrl()) {
  return createClient<paths>({ baseUrl });
}

/**
 * Build a typed `openapi-fetch` client with the auth middleware wired in —
 * every request carries `Authorization: Bearer <token>` from `auth`, and a
 * 401 triggers exactly one silent-refresh-then-retry before surfacing.
 *
 * @param auth - The active `AuthApi` (from `useAuth()`).
 * @param baseUrl - API base URL. Defaults to `VITE_API_BASE_URL`, falling
 *   back to same-origin ("") in its absence.
 */
export function createAuthedApiClient(
  auth: AuthApi,
  baseUrl: string = apiBaseUrl(),
) {
  const client = createClient<paths>({ baseUrl });
  client.use(createAuthMiddleware(auth));
  return client;
}
