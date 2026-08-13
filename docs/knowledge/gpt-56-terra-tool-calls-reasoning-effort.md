---
type: Integration quirk
title: gpt-5.6-terra rejects function tools unless reasoning_effort="none"
description: On /v1/chat/completions, gpt-5.6-terra (and likely its fast-conversational class) returns a provider 400 for any tool-bearing call without reasoning_effort="none". Stub-tested adapters ship this bug silently — only a live call reveals it.
tags: [openai, gpt-5.6-terra, chat, tool-calls, provider-quirk, reasoning-effort]
timestamp: 2026-08-11
---

# Rule

Every tool-bearing call to `gpt-5.6-terra` on the chat-completions surface pins
`reasoning_effort="none"` — all three chat provider calls in
`runtime/chat_backend_openai.py` carry it, and
`tests/runtime/test_chat_backend_openai.py` asserts the pin on each (the faked
client records kwargs), so losing it fails deterministically instead of only in
production.

# Why

Found at the 029 H3 live check: the stub-tested adapter was green, the first
live tool call 400'd. The pin matches the owner's fast-conversational model
selection intent (same provider, same approved route — no model change), so it
was resolved as an in-vocabulary deviation, not a contract change.

# Watch out

Any NEW tool-bearing moment on this model class needs the same pin — and its
first live call is the only trustworthy proof. Budget one live smoke for any
adapter whose stub can't carry provider-side validation.
