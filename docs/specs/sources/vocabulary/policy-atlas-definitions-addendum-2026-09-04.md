---
type: Frozen design source
title: Policy Atlas definitions — addendum (owner + colleague, 2026-09-04)
description: Amendments to the definitions document agreed the same day — the Agent tab, chats stay chats, and the pinned "Task Agent" primary chat — plus recorded future direction.
tags: [source, vocabulary, frozen]
timestamp: 2026-09-04
---

# Definitions addendum (2026-09-04)

> Frozen source (ADR 0002). Relayed by the owner after a conversation with a
> colleague, amending [policy-atlas-definitions.md](policy-atlas-definitions.md).
> Where the two differ, this addendum wins. The living glossary is
> `docs/specs/system/vocabulary.md`.

## Amendments

- The **Plan** tab becomes the **Agent** tab. It is where the user initially has the
  planning chat.
- The Agent tab shows **all chats within a Task** in a sidebar. Chats are still called
  **chats**.
- The user can have different kinds of chats with the Agent, and sees them all in the
  Agent tab.
- The **primary chat** for a Task (what is currently called the plan chat) is called the
  **Task Agent**. It is the pinned first chat in the Agent tab and has a visual
  distinction to show it is a different type of chat. The other chats are just named
  chats.

The "Planning mode / Agent mode / Questions mode" labels in the original document are
withdrawn by these amendments: the modes are not surfaced as words.

## Future direction (information only, not in scope of task 038)

- A user may want to re-run some aspect of a Task, or the whole Task, from a new chat
  rather than only from the Task Agent. Iterative re-running of Tasks is not bottomed
  out and can be its own feature.
- Active (not archived) chats become reachable anywhere in the app, including outside a
  Task, from the round chat/Agent icon. Users should eventually ask questions with any
  Tasks or Projects as context — possibly adjusted when the meta-analysis capability
  arrives.
- Making chat more functional is a separate task, alongside iteration, meta-analysis
  and artefact editing.
