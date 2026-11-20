# Framework rules

Follow these when integrating PostHog into this framework.

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
