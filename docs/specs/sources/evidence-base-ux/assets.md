# Evidence Base UX assets

The Evidence Base wireframe is paired with:
- `evidence-base-wireframes.html`
- `nesta-brand-tokens.md`
- `hifi.css`

These files are source context for spec/rubric/task-contract agents. They are not production frontend code and do not define backend contracts.

## Fonts

A separate `fonts/` folder was supplied with the wireframes.

**Status (2026-06-22): the font binaries are currently tracked in git** (`fonts/Averta-*.otf`,
`fonts/Zosia-Display.woff{,2}`), which contradicts the policy below. Recommend **removing them
from version control** (`git rm` the `fonts/` binaries) and keeping only this note, **unless** the
project owner has already confirmed the licensing/visibility/deployment points below. Left in
place pending that decision — flagged, not silently deleted.

Do not commit, vendor, redistribute or package font files unless the project owner has confirmed:
- the font licences;
- repository visibility;
- whether the fonts may be used in development, staging and production;
- the intended deployment path.

Until that is confirmed, implementation specs should use approved fallback font stacks and keep the UI functional without local font files.

Agents must not download replacement fonts, recreate logos or invent brand assets. Use official master artwork where required.