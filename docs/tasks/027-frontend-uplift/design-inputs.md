# Design inputs: PR #35 adjudication (2026-07-28)

PR #35 (`demo-live-run-test-1`, Karlis Kanders — "Refined Project UI mock up")
proposes a capabilities→artifacts product model on the demo branch: top-level
tabs collapse to Workspace + Sources + Chats; an artifact gallery with a
"+ New job" capability picker (evidence base real; value-for-money,
stakeholder mapping, theory of change, meta-analysis as canned mocks);
per-artifact detail with Output/Activity-log tabs; an IDE-style resizable
multi-thread chat rail with per-thread artifact context; a Chats library
(archive/reopen/delete); Sources project-wide with per-artifact "Cited in"
chips (mocked).

**Adjudication (owner-directed, 2026-07-28):**

| PR #35 element | Ruling |
|---|---|
| Transcript durability (chats must not disappear) | **027 strand 12** |
| Collapsible/resizable chat rail (single thread) | **027 strand 3** |
| Multi-thread chat + Chats library + per-thread artifact context | co-pilot Q&A slice (needs the lead-authored Q&A prompt surface; 027's transcript schema is shaped for it) |
| Artifact gallery / capability picker / multi-artifact IA / "Cited in" | workspace-cluster slice (needs run/artifact-scoped read models; chain mechanics already verified) |
| Four non-EB capabilities (VfM, stakeholders, ToC, meta-analysis) | roadmap — unspecced product capabilities, each its own chain + prompts. Note: "meta-analysis" plausibly an EB depth option, not a sibling capability |
| Output/Activity-log tab grammar for artifact detail | design reference for workspace-cluster; 027's components (journey cards, evidence page) are IA-agnostic and will move into it unchanged if adopted |

**Why not the new IA now:** the backing backend is two slices of work; the
current surfaces are the demo-validated ones (RETRO §2, CEO-proxy walked);
and ~90% of 027 is IA-agnostic components, so adopting the artifact IA later
is a thin-shell change, not a rebuild — PR #35's own `ArtifactDetail`
demonstrates this by re-mounting the existing views as its tabs.

**⚠️ Branch hygiene before PR #35 is used further as a demo:**
`backend/.dev-issuer/dev-key.pem` + `jwks.json` (private key, force-added past
`backend/.gitignore`, public repo — keypair is burned, rebase out and
regenerate locally) and `demo/server/projects.json` (runtime sidecar) must
come out of the branch history.
