# 029 web-research pass — 2025–26 practice survey (rev 2.1 input)

Three-lane survey run 2026-08-10 (owner-directed) to check the rev-2 contract against
current practice. Condensed; per-lane sources below. Verdicts as adjudicated into the
contract rev 2.1 status block.

## Lane 1 — multi-conversation project containers

- Container = files + instructions + chats everywhere; project knowledge is ambient in
  every chat, **raw transcripts are never shared between chats by default**. Cross-chat
  recall, where it exists (ChatGPT project memory; Claude project-scoped memory), is
  opt-in and memory-mediated, fenced per project.
  - Claude Projects: https://support.claude.com/en/articles/9517075-what-are-projects ·
    https://claude.com/blog/memory
  - ChatGPT Projects: https://help.openai.com/en/articles/10169521-projects-in-chatgpt ·
    https://help.openai.com/en/articles/8590148-memory-faq
  - Perplexity Spaces: https://airespo.com/resources/perplexity-spaces-explained-in-depth/
  - Gemini Gems (persona container, not project): https://support.google.com/gemini/answer/15235603
- **Durable state lives in artifacts, not threads** — NotebookLM "Save to note", Copilot
  Pages, Claude project knowledge; "promote from chat to artifact" is the persistence
  gesture (matches our promotion-to-block deferred seam).
  - NotebookLM chat: https://support.google.com/notebooklm/answer/16179559 ·
    https://9to5google.com/2025/10/29/notebooklm-chat-upgrade/
  - Copilot Notebooks: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-microsoft-365-copilot-notebooks ·
    https://techcommunity.microsoft.com/blog/microsoft365copilotblog/what%E2%80%99s-new-in-notebooks--june-2026/4525625
- Many-short-chats beats one-long-thread (context rot):
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents ·
  https://www.producttalk.org/context-rot/
- Auto-titling: cheap model from early messages, async, always renameable (Claude Code
  uses Haiku): https://code.claude.com/docs/en/sessions
- Chats are per-user even in shared containers (Claude/Perplexity/NotebookLM).
- Counter-signal noted: the two most evidence-centric products (NotebookLM, Copilot
  Notebooks) use a **single persistent chat pane** per container; multiplicity comes
  from promoted artifacts. Our model carries both: many chats *and* the artefact layer.

## Lane 2 — transcript persistence & context assembly

- Layered context is the 2026 consensus: sliding window base + rolling summarization +
  optional recall; window-only is a legitimate v1 with a named upgrade path.
  https://neuraltrust.ai/blog/context-window-optimization ·
  https://explainx.ai/blog/conversation-history-management-ai-agents-2026 ·
  https://docs.langchain.com/oss/python/langchain/short-term-memory
- ChatGPT memory is notably *not* RAG: pinned facts + summaries + full current thread.
  https://www.shloked.com/writing/chatgpt-memory-bitter-lesson
- Provider-side state (OpenAI `store=true`/`previous_response_id`, Conversations API)
  is prototype convenience: still billed full input each turn; ZDR forces it off;
  compliance writing (EU AI Act Arts. 12/19, FOI) points to an app-owned, durable,
  access-logged store. **Owning Postgres is the recommended pattern, not a compromise.**
  https://developers.openai.com/api/docs/guides/conversation-state ·
  https://www.confident-ai.com/knowledge-base/guides/enterprise-ai-governance-audit-trails
- Idempotency: Stripe-style client keys, stable across retries, server replay of the
  stored assistant message; dedupe-before-generate (LLM calls are expensive).
  https://zuplo.com/learning-center/implementing-idempotency-keys-in-rest-apis-a-complete-guide
- Cost bounding: K-turns + token ceiling, truncate oldest first; summary refresh on
  threshold, not per turn.
- Streaming: "when a human is watching, streaming is almost always worth turning on";
  non-streaming reserved for background jobs / whole-payload validation. Interactive
  RAG expectation ≈ 1–3 s to first useful output; blocking grounded answers land
  5–15 s. https://www.firsttoken.dev/p/streaming-llm-responses-without-breaking-your-backend ·
  https://redis.io/blog/streaming-llm-responses/ ·
  https://milvus.io/ai-quick-reference/what-is-an-acceptable-latency-for-a-rag-system-in-an-interactive-setting-eg-a-chatbot-and-how-do-we-ensure-both-retrieval-and-generation-phases-meet-this-target

## Lane 3 — grounded/cited chat UX & security

- Citation rendering norm: **inline numbered markers + hover-card + click-to-source**
  (NotebookLM per-passage + hover-to-quote; Harvey per-sentence links; OpenAI
  file_search annotations). Footer-only lags.
  https://support.google.com/notebooklm/answer/16179559 ·
  https://developers.openai.com/api/docs/guides/tools-file-search ·
  https://research.contrary.com/company/harvey
- Fabrication prevention: web products largely trust the model (11–57% citation
  hallucination in deep-research agents; misattribution > fake sources); corpus
  products constrain structurally (Anthropic Citations API cites provided chunks only;
  Harvey verifies against legal DBs). Post-hoc: CiteFix (streaming-compatible),
  resolvability checks (cited id ∈ retrieval log) — **our deterministic floor matches
  best practice**; id-membership does not catch misattribution (→ eval slice).
  https://arxiv.org/html/2605.06635v1 ·
  https://platform.claude.com/docs/en/build-with-claude/citations ·
  https://arxiv.org/pdf/2504.15629 ·
  https://futureagi.com/blog/evaluating-llm-citation-attribution-2026/
- User-facing groundedness tiers are **rare** (NotebookLM abstains rather than labels;
  Contextual AI highlights ungrounded claims; Consensus/Elicit show evidence meters) —
  our per-answer tier chip leads consumer practice.
  https://docs.contextual.ai/reference/enable-groundedness-score
- Formatting: markdown-rich is the default; plain prose is a deliberate trade — and a
  security control: EchoLeak (CVE-2025-32711) exfiltrated via rendered markdown links
  from "read-only" chat. No-markdown rendering closes that channel.
  https://airia.com/ai-security-in-2026-prompt-injection-the-lethal-trifecta-and-how-to-defend/
- Streaming + citations are decoupled in the state of the art: stream prose, attach
  verified citations at completion (Cohere fast/accurate modes; CiteFix).
  https://docs.cohere.com/docs/rag-citations ·
  https://vercel.com/kb/guide/building-ai-chat-app-with-rag-and-citations-on-vercel
- Security posture: read-only tool allowlisting + segregating retrieved content matches
  OWASP LLM Top 10 2025 (LLM01) and the lethal-trifecta cut (remove the
  external-communication leg).
  https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf ·
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/

## Scorecard (as folded into rev 2.1)

- **Leads practice:** trust tiers + abstention · deterministic citation floor ·
  read-only + no-markdown (closes EchoLeak-class exfil).
- **Matches:** owned transcript store · idempotency · many-chats container ·
  no cross-chat recall · tool allowlisting · "corpus doesn't hold this" messaging.
- **Lagged, fixed in rev 2.1:** footer-only citations → inline `[n]` + quote-in-context.
- **Lags, owner decision:** blocking answers vs stream-then-verify (❓ at the 🛑).
- **Named residual:** misattribution not caught by id-membership → eval slice.
