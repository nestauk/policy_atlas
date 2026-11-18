/**
 * In-app feedback: the API hooks.
 *
 * In a file of its own, not in `queries.ts` and `mutations.ts`, so that each
 * feedback element stays one small unit behind its feature flag.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "./gen/types";
import { useApiClient } from "./queries";

export type UserProfile = components["schemas"]["UserProfileOut"];
export type UserProfileAnswers = components["schemas"]["UserProfileIn"];

const PROFILE_KEY = ["me", "profile"] as const;

/**
 * Throw an API error body as an `Error`, so a caller can show one message.
 *
 * Args:
 *   error: The error envelope from the API client.
 */
function raise(error: unknown): never {
  const body = error as { error?: { message?: string } } | undefined;
  throw new Error(body?.error?.message ?? "Something went wrong");
}

/**
 * `GET /api/v1/me/profile`: the caller's onboarding profile.
 *
 * Args:
 *   enabled: False when the onboarding element is off, so no request is made.
 *
 * Returns:
 *   The query. Its data has `completed_at: null` until the form is completed.
 */
export function useProfile(enabled = true) {
  const client = useApiClient();
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/me/profile");
      if (error) raise(error);
      return data;
    },
    enabled,
    // Changes only when this user saves or skips, and both write the cache.
    staleTime: Infinity,
  });
}

/** `PUT /api/v1/me/profile`: complete the profile, or edit a completed one. */
export function useSaveProfile() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (answers: UserProfileAnswers) => {
      const { data, error } = await client.PUT("/api/v1/me/profile", { body: answers });
      if (error) raise(error);
      return data;
    },
    onSuccess: (profile) => queryClient.setQueryData(PROFILE_KEY, profile),
  });
}

/** `POST /api/v1/me/profile/skip`: record the one "Skip for now". */
export function useSkipProfile() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await client.POST("/api/v1/me/profile/skip");
      if (error) raise(error);
      return data;
    },
    onSuccess: (profile) => queryClient.setQueryData(PROFILE_KEY, profile),
  });
}
