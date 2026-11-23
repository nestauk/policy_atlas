# PostHog in Policy Atlas

PostHog is the product analytics service we use. This guide tells you what it does in Policy
Atlas, how to turn it on, and how to do the three common jobs: read usage data, control a
feature with a flag, and run an A/B test.

## What PostHog does here

1. **Records use.** It records each page view and each click, and it records some named
   events (for example, a download).
2. **Controls features.** A *feature flag* is a switch in PostHog. The app asks PostHog for the
   value and shows or hides a feature. You change the switch in PostHog; you do not deploy.
3. **Runs A/B tests.** PostHog shows different versions of a feature to different people and
   compares the results. PostHog calls this an *experiment*.

There are two senders. The browser sends page views, clicks and download events. The API sends
events for actions that change data (for example, sharing a task). The two senders identify a
person with the same value (the `sub` claim of the sign-in token), so PostHog shows one person
with one timeline.

## Turn it on

### On your computer

1. The API: set `POSTHOG_PROJECT_TOKEN` and `POSTHOG_HOST` in `backend/.env`.
2. The browser: create the file `frontend/.env.local` with the same two values:

   ```
   VITE_POSTHOG_PROJECT_TOKEN=phc_...
   VITE_POSTHOG_HOST=https://eu.i.posthog.com
   ```

3. Start the app again with `make dev`. Vite reads `.env.local` only when it starts.

Git ignores `frontend/.env.local`. The project token is public by design: it can only send
events and read flag values. It cannot read your data.

If one of the two values is missing, PostHog does not start in the browser. The app works as
usual, sends nothing, and each feature flag uses its fallback (see "Feature flags").

PostHog also does not start in mock mode (`VITE_MOCK=1`) or in the unit tests.

### On staging and production

**This is not done.** Read "Before you turn it on for real people" at the end of this guide.

## What is recorded

### Automatic

The browser SDK (the PostHog library, `posthog-js`) records these with no code from us:

- `$pageview`: each page a person opens, with its address.
- `$autocapture`: each click on a button, link or form control, with the text of the element.
- `$pageleave`: when a person leaves a page.

Use these to answer "which pages" and "which buttons". In PostHog, open **Activity** to see
the events arrive.

### Named events

A named event is more reliable than a click, because it does not change when we change the
text of a button. Use named events for the numbers you care about.

| Event | Sent by | When | Properties |
| --- | --- | --- | --- |
| `file_downloaded` | Browser | A person selects an item in a Download menu, or selects "Download CSV" on the sources page. | `format`: the menu label, for example `PDF`, `Markdown`, `Sources (CSV)`. |
| `task_shared` | API | A task becomes shared. | `audience`: `organisation` or `public`. |
| `task_unshared` | API | A task stops being shared. | `audience`: `organisation` or `public`. |
| `project_shared` | API | A project becomes shared with the organisation. | `audience`: `organisation`. |
| `project_unshared` | API | A project becomes private. | `audience`: `organisation`. |

The API sends the share events only when the value changes. A request that is refused, or
that repeats the current value, sends nothing.

The API sent some events before this change (for example `run_started` and `task_archived`).
To find them all, search the backend for `capture_event(`.

### Add a named event

In the browser, call `track` from `frontend/src/lib/analytics.ts`:

```ts
import { track } from "../lib/analytics";

track("report_printed", { pages: 12 });
```

In the API, call `capture_event` from `backend/src/policy_atlas/api/analytics.py`:

```python
capture_event(request, "report_printed", properties={"pages": 12})
```

Rules for names:

- Use `object_verb` in the past tense, in lower case with underscores: `file_downloaded`.
- Send the event from the API if the action changes data. An ad blocker can stop a browser
  event, but it cannot stop an API event.
- Do not put text that a person typed (a question, a task name) in a property.

## Feature flags

### The two flags we have

| Flag key in PostHog | What it controls |
| --- | --- |
| `options_scoping` | "Options scoping" on the New task page. |
| `theory_of_change` | "Theory of change" on the New task page. |

The flag key is the same as the capability key in `frontend/src/lib/capabilities.ts`.

### How the app decides

`useCapabilities()` in `capabilities.ts` asks PostHog for each flag.

- PostHog answers **on** or **off**: the app uses that answer.
- PostHog gives **no answer**: the app uses the fallback, which is the old environment
  variable (`VITE_OPTIONS_SCOPING=1`, `VITE_THEORY_OF_CHANGE=1`).

PostHog gives no answer in three cases: PostHog is not turned on, the flags have not arrived
yet (a moment after the first page load), or the flag does not exist in PostHog.

So `make dev` still shows the two capabilities with no PostHog token, because the Makefile
sets the two variables. When you add the token and create the flags, PostHog decides.

### Create the flags in PostHog

Do this one time for each flag.

1. In PostHog, open **Feature flags** and select **New feature flag**.
2. Type the key exactly: `options_scoping` (then do the same for `theory_of_change`).
3. Under **Release conditions**, select who gets it. For example: 100% of users, or only
   people whose ID is in a list.
4. Save. To hide the capability from all people, turn the flag off.

A person's ID in PostHog is the `sub` value of the sign-in token. With `make dev`, the ID is
`dev-user`.

### Theory of change has a second switch

The API has its own switch, `POLICY_ATLAS_THEORY_OF_CHANGE` (set by `theory_of_change` in
`infra/pa_config.json`). While it is off, the API refuses to make a theory of change, whatever
the flag says. This is a safety control, and the flag does not replace it.

To release theory of change in an environment: turn the API switch on first, then use the
PostHog flag to select who sees it.

### Put a new feature behind a flag

```tsx
import { useFeatureFlagEnabled } from "posthog-js/react";

function Toolbar() {
  const showExport = useFeatureFlagEnabled("new_export_button");
  return showExport ? <NewExportButton /> : null;
}
```

`useFeatureFlagEnabled` gives `undefined` when PostHog gives no answer. In the example,
`undefined` hides the feature. This is the safe choice for a feature that is not ready.

A flag in the browser only hides a control. It is not security. If people must not be able to
use a feature, the API must refuse the request too.

When a feature is released to all people, delete the flag from the code and from PostHog.

## A/B tests

An A/B test in PostHog is a feature flag with more than one value (PostHog calls the values
*variants*) and a goal. PostHog puts each person in one variant and keeps them there.

1. In PostHog, open **Experiments** and select **New experiment**. Give it a flag key, for
   example `share_button_wording`. PostHog makes the variants `control` and `test`.
2. Select the goal. This is one of our events, for example `task_shared`.
3. In the code, show a different version for each variant:

   ```tsx
   import { useFeatureFlagVariantKey } from "posthog-js/react";

   const variant = useFeatureFlagVariantKey("share_button_wording");
   const label = variant === "test" ? "Share with my team" : "Share with organisation";
   ```

4. Deploy, then start the experiment in PostHog. PostHog shows the result for each variant.
5. When the test ends, keep the better version and delete the flag from the code.

The app has no experiment today. This section tells you how to make the first one.

## Where the code is

| File | What it does |
| --- | --- |
| `frontend/src/lib/analytics.ts` | Starts PostHog in the browser. Has `track` and `identifyUser`. |
| `frontend/src/main.tsx` | Calls `initAnalytics()` before the app shows. |
| `frontend/src/App.tsx` | Tells PostHog who is signed in, and resets at sign-out. |
| `frontend/src/lib/capabilities.ts` | Reads the two capability flags. |
| `frontend/src/views/DownloadMenu.tsx`, `SourcesView.tsx` | Send `file_downloaded`. |
| `backend/src/policy_atlas/api/app.py` | Starts PostHog in the API. |
| `backend/src/policy_atlas/api/auth.py` | Tells PostHog which person made each API request. |
| `backend/src/policy_atlas/api/analytics.py` | Has `capture_event`. |
| `backend/src/policy_atlas/api/routers/tasks.py`, `projects.py` | Send the share events. |

Session replay (a video-like record of a session) is off. We did not ask for it, and the
site's security policy stops the script that it needs.

## Before you turn it on for real people

These four items are open. Do them before you put a PostHog token in a staging or production
build.

1. **The privacy notice.** The notice in `frontend/src/views/legal/PrivacyView.tsx` says that
   we do not collect IP addresses or device information. The PostHog browser SDK collects
   both by default. It also keeps an identifier in a cookie and in the browser's local
   storage, and autocapture records the text of the element a person clicks, which can be the
   name of a task. A person with authority over data protection must decide: change the
   notice, or limit what PostHog collects, or both. Settings that limit collection are
   "Discard client IP data" (in the PostHog project settings) and, in `analytics.ts`,
   `mask_all_text: true` (no click text) and `persistence: "memory"` (no cookie and no local
   storage; flags then load again on each page load).
2. **The security policy of the site.** The deployed site only lets the browser talk to the
   addresses in `connect-src` (`infra/infra/components/security_headers.py`). The PostHog
   address is not in the list, so the browser will block PostHog. Add the address there.
3. **The build.** `scripts/deploy.sh` must give `VITE_POSTHOG_PROJECT_TOKEN` and
   `VITE_POSTHOG_HOST` to the frontend build. The API needs `POSTHOG_PROJECT_TOKEN` and
   `POSTHOG_HOST` in its environment (`infra/infra/policy_atlas_stack.py`). Neither is set
   today.
4. **Ad blockers.** Many ad blockers stop requests to PostHog. For a person with an ad
   blocker, the browser sends no events, and each flag uses its fallback. On production the
   fallback is "off". If this is a problem, PostHog can be reached through our own address
   (a *reverse proxy*).

The ops pages (`frontend/src/ops/`) do not use PostHog.
