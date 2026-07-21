/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL. Defaults to `/api` (the local dev proxy) when unset. */
  readonly VITE_API_BASE_URL?: string;
}
