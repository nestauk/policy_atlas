# Sign-in page branding

The look of the Cognito sign-in page ("managed login") when an environment sets
`sign_in.page` to `"managed"` in `infra/pa_config.json`. `infra/infra/cognito_auth.py` reads
these files at synth and puts them into one `CfnManagedLoginBranding` resource for the web
app's client. ADR 0049.

| File | What it is |
|---|---|
| `settings.json` | The style document: colours, borders, logo positions, light and dark mode. It started as the AWS default (read back with `DescribeManagedLoginBrandingByClient`) with the AWS blues swapped for the `DESIGN.md` colours. `categories.global.pageHeader.enabled` is true (the header carries the logo) and `colorSchemeMode` is `DYNAMIC` (follows the browser's light or dark mode). AWS publishes no schema for it. |
| `assets.json` | Which image goes where: category, colour mode, file type and file. |
| `wordmark-light.svg`, `wordmark-dark.svg` | The header logo: the diamond and "Policy Atlas". "Policy" is navy (white in dark mode) and "Atlas" electric blue (lighter in dark mode). |
| `mark.svg` | The diamond, used as the favicon. |

## Rules AWS enforces

- A logo's width-to-height ratio must be between 1:1 and 4:1, or the deploy fails.
- There is no font setting, and the page's wording cannot be changed.

## The wordmark

The letters are drawn shapes, not text, because the sign-in page cannot load our fonts. They
were made from Zosia Display at weight 800 (as in the app's `NavLogo`) with fontTools: each
letter's outline is written as an SVG path at 26 px, with tracking of -0.02 em. The diamond
is as tall as the letters above the baseline, with a 6-unit gap before "Policy". The font
file itself is licensed and is never committed; only these letter shapes are (owner approval,
2026-11-19).

## Changing a colour

Edit the hex value in `settings.json` (eight digits: colour plus `ff` for full opacity),
deploy staging, and look at the page in light and dark mode.
