/**
 * In-app feedback: the API hooks.
 *
 * In a file of its own, not in `queries.ts` and `mutations.ts`, so that each
 * feedback element stays one small unit behind its feature flag.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import type { components, paths } from "./gen/types";
import { useApiClient } from "./queries";

export type FeedbackRecord = components["schemas"]["FeedbackOut"];
export type FeedbackKind = FeedbackRecord["kind"];
/** The body of a submit: one of the per-kind models, selected by `kind`. */
export type FeedbackBody =
  paths["/api/v1/feedback"]["post"]["requestBody"]["content"]["application/json"];

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

const feedbackKey = (taskId: string, kind: FeedbackKind) => ["feedback", taskId, kind] as const;

/**
 * `GET /api/v1/feedback`: the caller's active records of one kind on a task.
 * A flag shows again after a reload because of this read.
 *
 * Args:
 *   taskId: The task.
 *   kind: The feedback kind.
 *   enabled: False when the kind's element is off, so no request is made.
 *
 * Returns:
 *   The query. Its data is the list of records that are not retracted.
 */
export function useFeedback(taskId: string, kind: FeedbackKind, enabled = true) {
  const client = useApiClient();
  return useQuery({
    queryKey: feedbackKey(taskId, kind),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/feedback", {
        params: { query: { task_id: taskId, kind } },
      });
      if (error) raise(error);
      return data.data;
    },
    enabled: enabled && taskId !== "",
  });
}

/** How often a pending missing-paper resolution is read again, in milliseconds. */
const RESOLUTION_POLL_MS = 2000;

/**
 * `GET /api/v1/feedback/{id}`: one record, read again while the resolution of
 * a missing paper is pending.
 *
 * Args:
 *   feedbackEventId: The record.
 *   initial: The record as the submit returned it. No request is made when
 *     its resolution is already known.
 *
 * Returns:
 *   The query. Its data is the newest read of the record.
 */
export function useFeedbackRecord(feedbackEventId: string, initial: FeedbackRecord) {
  const client = useApiClient();
  const pending = (record: FeedbackRecord | undefined) =>
    record?.resolution != null && record.resolution.failure_stage == null;
  return useQuery({
    queryKey: ["feedback", "record", feedbackEventId] as const,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/feedback/{feedback_event_id}", {
        params: { path: { feedback_event_id: feedbackEventId } },
      });
      if (error) raise(error);
      return data;
    },
    initialData: initial,
    enabled: pending(initial),
    refetchInterval: (query) => (pending(query.state.data) ? RESOLUTION_POLL_MS : false),
  });
}

/**
 * `POST /api/v1/feedback`: store one feedback record.
 *
 * Args:
 *   taskId: The task whose list of records to refresh, when there is one.
 */
export function useSubmitFeedback(taskId?: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: FeedbackBody) => {
      const { data, error } = await client.POST("/api/v1/feedback", { body });
      if (error) raise(error);
      return data;
    },
    onSuccess: (record) =>
      taskId === undefined
        ? undefined
        : queryClient.invalidateQueries({ queryKey: feedbackKey(taskId, record.kind) }),
  });
}

/**
 * `DELETE /api/v1/feedback/{id}`: retract one record. The row is kept.
 *
 * Args:
 *   taskId: The task whose list of records to refresh.
 *   kind: The kind of the record.
 */
export function useRetractFeedback(taskId: string, kind: FeedbackKind) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (feedbackEventId: string) => {
      const { error } = await client.DELETE("/api/v1/feedback/{feedback_event_id}", {
        params: { path: { feedback_event_id: feedbackEventId } },
      });
      if (error) raise(error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: feedbackKey(taskId, kind) }),
  });
}

/** A page event that the frontend sends to the analytics relay. */
export type AnalyticsEvent =
  paths["/api/v1/analytics/events"]["post"]["requestBody"]["content"]["application/json"]["event"];

/**
 * `POST /api/v1/analytics/events`: send one page event to the relay.
 *
 * The browser has no PostHog script. The API adds the user and forwards the
 * event; it takes an event name and a task id, and no free text. A failure is
 * ignored: analytics must not disturb the page.
 *
 * Returns:
 *   A function that sends one event. Call it only where the `analytics`
 *   element is on.
 */
export function useTrackEvent() {
  const client = useApiClient();
  return useCallback(
    (event: AnalyticsEvent, taskId?: string) => {
      void client
        .POST("/api/v1/analytics/events", { body: { event, task_id: taskId ?? null } })
        .catch(() => undefined);
    },
    [client],
  );
}
