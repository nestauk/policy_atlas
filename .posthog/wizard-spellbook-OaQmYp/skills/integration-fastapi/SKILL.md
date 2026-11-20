---
name: integration-fastapi
description: PostHog integration for FastAPI applications
metadata:
  author: PostHog
  version: 1.66.0
---

# PostHog integration for FastAPI

This skill helps you add PostHog analytics to FastAPI applications.

## Workflow

Follow these steps in order to complete the integration:

1. `references/1-begin.md` - PostHog Setup - Begin ← **Start here**
2. `references/2-edit.md` - PostHog Setup - Edit
3. `references/3-revise.md` - PostHog Setup - Revise
4. `references/4-conclude.md` - PostHog Setup - Conclusion

## Reference files

- `references/EXAMPLE.md` - FastAPI example project code
- `references/1-begin.md` - Start the event tracking setup process by analyzing the project and creating an event tracking plan
- `references/2-edit.md` - Implement PostHog event tracking in the identified files, following best practices and the example project
- `references/3-revise.md` - Review and fix any errors in the PostHog integration implementation
- `references/4-conclude.md` - Review and fix any errors in the PostHog integration implementation
- `references/python.md` - Python
- `references/identify-users.md` - Identify users
- `references/COMMANDMENTS.md` - Framework-specific rules the integration must follow

The example project shows the target implementation pattern. Consult the documentation for API details.

## Key principles

- **Environment variables**: Always use environment variables for PostHog keys. Never hardcode them.
- **Minimal changes**: Add PostHog code alongside existing integrations. Don't replace or restructure existing code.
- **Match the example**: Your implementation should follow the example project's patterns as closely as possible.

## Framework guidelines

- A missing PostHog configuration must never break the app — read keys optionally (never a required setting, and never with a format check such as a URL rule in an env schema, which a blank value fails at boot), guard init and capture behind their presence, and keep build and boot working with no PostHog environment set — but never silently: in development or debug builds fail loudly, using the language's idiomatic error, with the message "<VAR> variable required by PostHog is missing or un-configured, this causes events to be silently missed. This error stops appearing once <VAR> is configured" (substituting the actual variable name); production stays a no-op. Only client code, in a browser or on a device, raises it as an error. Server-side code (a server, a worker, a module they load) logs that message as a warning outside production and keeps running, because an error there stops the process from booting for anyone without PostHog keys. A process another program launches, such as an MCP server on STDIO, has nobody watching it boot and no development build — it always writes the warning to stderr (never stdout, which can carry the protocol)
- Sending analytics must never fail or stall the app's own work. Where the app waits on a flush, handle any error it raises and keep the wait short. A long-running server or worker whose SDK sends in the background needs no flush after each capture
- Add PosthogASGIMiddleware, as the ASGI section of the Python docs shows. Create the client where you build the app, not in the lifespan - middleware cannot be added once the app starts
- Call posthog.flush() in the lifespan shutdown to ensure all events are sent before the app exits
- Do NOT call capture_exception() in an @app.exception_handler(Exception) catch-all - the middleware already captures those exceptions
- Use Pydantic Settings with @lru_cache decorator on get_settings() for caching and easy test overrides
- Use FastAPI dependency injection (Depends) for accessing current_user and settings in route handlers
- Use the same context API pattern as Flask/Django (with new_context(), identify_context(user_id), then capture())
- Remember that source code is available in the venv/site-packages directory
- posthog is the Python SDK package name
- Install dependencies with `pip install posthog` or `pip install -r requirements.txt`, at the version the Python SDK docs pin, and do NOT use unquoted version specifiers like `>=` directly in shell commands. To keep the docs' range, write it into `requirements.txt` and run `pip install -r requirements.txt`
- In CLIs and scripts: MUST call posthog.shutdown() before exit or all events are lost
- Always use the Posthog() class constructor (instance-based API) instead of module-level posthog.api_key config
- Always include enable_exception_autocapture=True in the Posthog() constructor to automatically track exceptions
- PosthogFlaskIntegration (posthog.integrations.flask), PosthogASGIMiddleware (posthog.integrations.asgi), and the Django REST Framework exception handler (posthog.integrations.drf) need posthog 7.69.0 or later - when you add one, require at least that version
- NEVER send PII in capture() event properties — no emails, full names, phone numbers, physical addresses, IP addresses, or user-generated content
- PII belongs in identify() person properties, NOT in capture() event properties. Safe event properties are metadata like message_length, form_type, boolean flags.
- Register posthog_client.shutdown with atexit.register() to ensure all events are flushed on exit
- The Python SDK has NO identify() method — use posthog_client.set(distinct_id=user_id, properties={...}) to set person properties, or use identify_context(user_id) within a context

## Identifying users

Identify users during login and signup events. Refer to the example code and documentation for the correct identify pattern for this framework. If both frontend and backend code exist, pass the client-side session and distinct ID using `X-POSTHOG-DISTINCT-ID` and `X-POSTHOG-SESSION-ID` headers to maintain correlation.

## Error tracking

Add PostHog error tracking to relevant files, particularly around critical user flows and API boundaries.
