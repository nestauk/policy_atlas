"""The option card as text, for the shortlist proposal (task 055, P7; A12, A13).

One builder renders an :class:`~policy_atlas.api.contract.read_models.OptionOut`
the way the option card (``frontend/src/views/longlist/OptionCard.tsx``) shows
it, in the card's order, as plain Markdown: the header, the callouts, *How it
works*, *What it would take*, *Evidence* (with the maturity rung), then one
line per document. What Policy Atlas reads is what the user can see (S13).

Left out, as the contract's card-text matrix says: the exclusion block
(excluded options are never candidates), the action buttons, every link and
URL, and whether the documents disclosure is open.

The document lines are kept apart from the rest (:class:`CardText`) because
they are the one block the character ceiling may cut: :func:`fit_cards` trims
them one per option per round, oldest year first, and counts the cut.

The words copy the card's own helpers in ``longlistPresentation.ts``; the
maturity words follow the contract's § Terms. Every field is scrubbed of
control characters and folded onto one line, so a model-written field can
never start a line of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from policy_atlas.api.contract.read_models import (
    AuthorityOut,
    EvaluatedCountryOut,
    GuessOut,
    JudgementOut,
    MaturityOut,
    OptionDocumentOut,
    OptionOut,
    ProfileLineOut,
    RelationOut,
)
from policy_atlas.core.prompt_fields import sanitize_prompt_field
from policy_atlas.options_scoping.longlist.maturity import MATURITY_RECENT_YEARS

#: A generous per-field cap; the ceiling on the whole request is the real bound.
_FIELD_MAX = 4_000

#: Design features the card shows (``FEATURES_SHOWN`` in ``OptionCard.tsx``).
FEATURES_SHOWN = 6

#: The line names (``PROFILE_LINE_LABELS`` in ``planVocabulary.ts``), in the card's order.
LINE_NAMES: dict[str, str] = {
    "cost": "Cost",
    "time_to_set_up": "Time to set up",
    "time_to_effect": "Time to effect",
    "workforce": "Workforce requirements",
    "who_decides": "Who decides",
    "dependencies": "Dependencies",
    "coordination": "Coordination requirements",
    "delivery_complexity": "Delivery complexity",
    "potential_impact": "Potential impact",
}

#: The level word each mark takes (``LEVEL_WORDS``); lines absent here carry no mark.
LEVEL_WORDS: dict[str, dict[str, str]] = {
    "cost": {"less": "Cheaper", "more": "Costlier"},
    "time_to_set_up": {"less": "Quicker", "more": "Slower"},
    "time_to_effect": {"less": "Quicker", "more": "Slower"},
    "workforce": {"less": "Lower", "more": "Higher"},
    "coordination": {"less": "Lower", "more": "Higher"},
    "delivery_complexity": {"less": "Simpler", "more": "More complex"},
    "ambition": {"less": "Smaller", "more": "Bigger"},
}

#: The authority words (``AUTHORITY_LABELS``).
AUTHORITY_LABELS: dict[str, str] = {
    "within_your_power": "Within your power",
    "needs_action_by": "Needs action by another body",
    "unclear": "Unclear who can act",
}

#: The maturity rung's words (contract § Terms).
RUNG_WORDS: dict[str, str] = {
    "proposal_only": "Proposed, not yet implemented",
    "described": "Implemented, not yet evaluated",
    "evaluated": "Evaluated",
    "reviewed": "Evaluated, including a review",
}

#: The ids of the three built-in checks; the callout never shows them.
_BUILT_IN_CHECK_IDS = frozenset({"relevant", "distinct", "in_scope"})

#: Settings said as a place phrase (``SETTING_PHRASES``); other kinds read "in {plural}".
_SETTING_PHRASES: dict[str, str] = {
    "home": "at home",
    "online": "online",
    "workplace": "at work",
    "community": "in the community",
    "primary care": "in primary care",
    "secondary care": "in secondary care",
    "hospital": "in hospitals",
    "school": "in schools",
    "shop": "in shops",
}

_COUNTRIES_WITH_THE = frozenset(
    {
        "netherlands",
        "philippines",
        "czech republic",
        "gambia",
        "bahamas",
        "maldives",
        "dominican republic",
        "democratic republic of the congo",
        "republic of the congo",
    }
)


@dataclass(frozen=True)
class CardText:
    """One option card as text, its document lines kept apart.

    Attributes:
        fixed: Everything but the document lines, ending with the documents
            summary line when the option has documents.
        document_lines: One ``(year, line)`` per document, in the card's
            order; the year (``None`` when unknown) decides the cut order.
    """

    fixed: str
    document_lines: list[tuple[int | None, str]]

    def render(self, lines: Sequence[tuple[int | None, str]] | None = None) -> str:
        """Join the fixed text and the document lines that are kept.

        Args:
            lines: The document lines to show; all of them when ``None``.

        Returns:
            The card's text.
        """
        kept = self.document_lines if lines is None else lines
        return "\n".join([self.fixed, *(line for _, line in kept)])


def _t(value: object) -> str:
    """One field as display text: scrubbed, on one line, trimmed."""
    text = sanitize_prompt_field(str(value), max_chars=_FIELD_MAX)
    return " ".join(text.split())


def _count_of(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _capitalise(value: str) -> str:
    return value[:1].upper() + value[1:]


def _join_and(parts: Sequence[str]) -> str:
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _constraint_label(text: str) -> str:
    return text.strip().rstrip(".。")


def _origin_label(option: OptionOut) -> str:
    if option.origin == "clustered":
        return f"clustered from {_count_of(option.document_count, 'document', 'documents')}"
    if option.origin == "suggested":
        return "suggested by Policy Atlas"
    if option.origin == "from_evidence_search":
        section = (option.from_section or "").strip()
        return f"from your evidence search · {section}" if section else "from your evidence search"
    return "added by you"


def _relation_label(relation: RelationOut) -> str:
    prefix = "part of" if relation.kind == "part_of" else "includes"
    return f"{prefix} {relation.other_name}"


def _lever_label(option: OptionOut) -> str:
    return (
        "No lever fits"
        if option.primary_lever_type is None
        else _capitalise(option.primary_lever_type)
    )


def _country_with_article(name: str) -> str:
    key = name.strip().lower()
    return f"the {name}" if key.startswith("united") or key in _COUNTRIES_WITH_THE else name


def _evaluated_in(countries: Sequence[EvaluatedCountryOut]) -> str:
    if not countries:
        return "No evaluation gives a place"
    first = _country_with_article(countries[0].country)
    if len(countries) == 1:
        return f"Evaluated in {first}"
    if len(countries) == 2:
        return f"Evaluated in {first} and {_country_with_article(countries[1].country)}"
    others = _count_of(len(countries) - 1, "other country", "other countries")
    return f"Evaluated in {first} and {others}"


def _evidence_signal(option: OptionOut) -> str:
    """The evidence signal under the header (``evidenceSignal``)."""
    documents = option.document_count
    if documents == 0:
        return "No documents yet"
    evaluated = option.evaluated_count
    describing = documents - evaluated
    if evaluated == 0:
        describe = _count_of(describing, "document describes", "documents describe")
        return f"No evaluations, {describe} it"
    parts = [f"{_count_of(evaluated, 'document', 'documents')} evaluated it"]
    if describing > 0:
        parts.append(f"{describing} more describe it")
    parts.append(_evaluated_in(option.evaluated_countries))
    measured, total = option.outcomes_evaluated, option.outcomes_total
    parts.append(
        "Measures none of your outcomes"
        if measured == 0
        else f"Measures {measured} of your {_count_of(total, 'outcome', 'outcomes')}"
    )
    return " · ".join(parts)


def _evidence_opener(evaluated: int, documents: int) -> str:
    """The Evidence section's first line (``evidenceOpener``)."""
    if documents == 0:
        return "No document names this option yet."
    if evaluated == 0:
        verb = "recommends" if documents == 1 else "recommend"
        describe = _count_of(documents, "document describes", "documents describe")
        return f"No evaluations. {describe} or {verb} it."
    describing = documents - evaluated
    more = ""
    if describing > 0:
        s = "s" if describing == 1 else ""
        more = f" {describing} more describe{s} or recommend{s} it."
    return f"Evaluated in {_count_of(evaluated, 'document', 'documents')}.{more}"


def _no_outcome_measured(outcomes: int) -> str:
    if outcomes == 1:
        return "No evaluation measured any of your outcome."
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
    count = words[outcomes] if 2 <= outcomes <= 10 else str(outcomes)
    return f"No evaluation measured any of your {count} outcomes."


def _plural(word: str) -> str:
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        return f"{word[:-1]}ies"
    if word.endswith(("s", "x", "ch", "sh")):
        return f"{word}es"
    return f"{word}s"


def _delivered_lead_in(settings: Sequence[str]) -> str:
    """The lead-in to the design features, naming the setting (``deliveredLeadIn``)."""
    phrases = [
        _SETTING_PHRASES.get(kind.strip().lower(), f"in {_plural(kind.strip().lower())}")
        for kind in settings
        if kind.strip()
    ]
    if not phrases:
        return "It typically involves:"
    return f"Delivered {_join_and(phrases)}. It typically involves:"


def _lever_line(option: OptionOut) -> str:
    if option.primary_lever_type is None:
        return "Lever: none fits."
    also = [_capitalise(kind) for kind in option.secondary_lever_types]
    primary = _capitalise(option.primary_lever_type)
    return f"Lever: {primary}, with {' and '.join(also)}." if also else f"Lever: {primary}."


def _authority_words(authority: AuthorityOut) -> str:
    body = (authority.body or "").strip()
    if authority.label == "needs_action_by" and body:
        return f"Needs action by {body}"
    return AUTHORITY_LABELS[authority.label]


def _notices(judgements: Sequence[JudgementOut], guesses: Sequence[GuessOut]) -> list[str]:
    """The constraint callout's lines, in words (``constraintNotices``)."""
    lines: list[str] = []
    for judgement in judgements:
        if judgement.constraint_id in _BUILT_IN_CHECK_IDS:
            continue
        label = _constraint_label(_t(judgement.constraint_text))
        if judgement.verdict == "breaks":
            lines.append(f'Breaks "{label}". {_t(judgement.reason)}')
        elif judgement.verdict == "cannot_check":
            lines.append(f'Cannot check "{label}". {_t(judgement.reason)}')
    for guess in guesses:
        label = _constraint_label(_t(guess.constraint_text))
        if guess.leaning == "likely_falls_short":
            lines.append(f'May fall short: "{label}". {_t(guess.guess)}')
        elif guess.leaning == "cannot_say":
            lines.append(f'Cannot check "{label}". {_t(guess.guess)}')
    return lines


def _maturity_line(maturity: MaturityOut, today_year: int | None) -> str:
    """The rung with its design mix and its two modifiers, in words."""
    parts = [f"Maturity: {RUNG_WORDS[maturity.rung]}"]
    if maturity.design_mix:
        parts.append(_t(maturity.design_mix))
    if maturity.none_in_your_setting:
        parts.append("none in your setting")
    if maturity.stale:
        year = (
            today_year - MATURITY_RECENT_YEARS
            if today_year is not None
            else maturity.latest_evaluation_year
        )
        if year is not None:
            parts.append(
                f"most recent evaluation before {year}"
                if today_year is not None
                else f"most recent evaluation in {year}"
            )
    return " · ".join(parts)


def _place_with_detail(document: OptionDocumentOut) -> str | None:
    place = (document.place or "").strip()
    if not place:
        return None
    if place.lower() == "not stated":
        label = "place not stated"
    elif place.lower() == "other":
        label = "other place"
    else:
        label = _t(place)
    detail = (document.place_detail or "").strip()
    if detail and detail.lower() != place.lower():
        return f"{label} ({_t(detail)})"
    return label


def _document_line(document: OptionDocumentOut) -> str:
    """One document as the disclosure lists it, without its link (``DocumentLine``)."""
    parts = [_t(document.title)]
    if document.task_source_snapshot_id is not None:
        if document.programme_name:
            parts.append(_t(document.programme_name))
        place = _place_with_detail(document)
        if place is not None:
            parts.append(place)
        if document.tried_on_kind:
            parts.append(_t(document.tried_on_kind))
        if document.measured:
            parts.append(_t(document.measured))
    for part in (document.tier, document.evidence_type, document.year):
        if part is not None and part != "":
            parts.append(_t(part))
    group = "evaluated it" if document.role == "evaluated" else "describes or recommends it"
    return f"- {' · '.join(parts)} ({group})"


def option_card_text(option: OptionOut, *, today_year: int | None = None) -> CardText:
    """Render one option card as text, in the card's order.

    Args:
        option: The card's read model.
        today_year: The current year, for the "most recent evaluation before
            YEAR" modifier (the year five years back); ``None`` names the
            newest evaluation's own year instead.

    Returns:
        The fixed text and the document lines, apart.
    """
    out: list[str] = [f"## {_t(option.name)}", _t(option.description)]
    header = [_lever_label(option), _origin_label(option)]
    header += [_t(_relation_label(relation)) for relation in option.relations]
    if option.also_found_as:
        header.append(f"also found as: {', '.join(_t(name) for name in option.also_found_as)}")
    out.append(" · ".join(header))
    out.append(_evidence_signal(option))

    if option.no_in_scope_evidence and option.in_scope is not None:
        out.append(
            f"No in-scope evidence: none of its {option.in_scope.documents} documents pass "
            f"{_t(option.in_scope.restriction)}. It stays on the longlist until the scope changes."
        )
    if option.search_pending:
        out.append("Its own evidence search is still running.")
    out.extend(_notices(option.judgements, option.guesses))

    out.append("### How it works")
    out.append(_lever_line(option))
    lever_reason = (
        option.lever_none_fits_reason or option.lever_reason
        if option.primary_lever_type is None
        else option.lever_reason
    )
    if lever_reason and lever_reason.strip():
        out.append(_t(lever_reason))
    profile = option.profile
    out.append(_delivered_lead_in(profile.settings if profile is not None else []))
    out.extend(
        f"- {_capitalise(_t(feature))}"
        for feature in option.design.design_features[:FEATURES_SHOWN]
    )

    if profile is not None:
        out.append("### What it would take")
        ambition_word = LEVEL_WORDS["ambition"][option.ambition] if option.ambition else None
        ambition = f"Ambition: {_t(option.ambition_reason or '')}".rstrip()
        out.append(f"{ambition} ({ambition_word})" if ambition_word else ambition)
        by_key: dict[str, ProfileLineOut] = {line.key: line for line in profile.lines}
        for key, name in LINE_NAMES.items():
            line = by_key.get(key)
            if line is None:
                continue
            row = f"{name}: {_t(line.sentence)}"
            if key == "who_decides" and option.authority is not None:
                row = f"{row} ({_authority_words(option.authority)})"
            elif line.mark is not None and key in LEVEL_WORDS:
                row = f"{row} ({LEVEL_WORDS[key][line.mark]})"
            out.append(row)

    out.append("### Evidence")
    out.append(_evidence_opener(option.evaluated_count, option.document_count))
    document_lines: list[tuple[int | None, str]] = []
    if option.document_count > 0:
        by_outcome = option.evidence.outcome_counts.by_outcome
        if by_outcome:
            out.append("Your outcomes:")
            if all(entry.evaluated == 0 for entry in by_outcome):
                out.append(_no_outcome_measured(len(by_outcome)))
            else:
                served = {name.strip().lower() for name in option.outcomes_served}
                for entry in by_outcome:
                    count = (
                        "none"
                        if entry.evaluated == 0
                        else _count_of(entry.evaluated, "evaluation", "evaluations")
                    )
                    target = (
                        ""
                        if entry.outcome.strip().lower() in served
                        else " · not a target of this option"
                    )
                    out.append(f"- {_t(entry.outcome)}: {count}{target}")
        if option.place_sentences:
            out.append("Where it has been evaluated:")
            out.extend(
                f"- {_t(entry.place)}: {_t(entry.sentence)}" for entry in option.place_sentences
            )
    if option.maturity is not None:
        out.append(_maturity_line(option.maturity, today_year))
    if option.document_count > 0:
        documents = option.documents
        summary = f"Documents · {len(documents)}"
        out.append(f"{summary} · read from titles and abstracts only" if documents else summary)
        document_lines = [(document.year, _document_line(document)) for document in documents]
    return CardText(fixed="\n".join(out), document_lines=document_lines)


def fit_cards(cards: Sequence[CardText], budget: int) -> tuple[list[str], int]:
    """Fit the cards under a character budget by cutting document lines.

    While the cards, joined by a blank line, are longer than ``budget``, each
    card in turn loses its oldest document line (a line with no year counts
    as oldest), one line per card per round. Nothing else is ever cut; when
    every document line is gone the texts are returned as they are and the
    caller decides (the shortlist fails rather than truncate).

    Args:
        cards: The cards, in their order.
        budget: The most characters the joined texts may take.

    Returns:
        ``(texts, cut)``: the rendered cards and the number of lines cut.
    """
    kept = [list(card.document_lines) for card in cards]
    texts = [card.render(lines) for card, lines in zip(cards, kept, strict=True)]

    def total() -> int:
        return sum(len(text) for text in texts) + 2 * max(len(texts) - 1, 0)

    cut = 0
    while total() > budget and any(kept):
        for index, lines in enumerate(kept):
            if total() <= budget:
                break
            if not lines:
                continue
            oldest = min(
                range(len(lines)),
                key=lambda i: (lines[i][0] is not None, lines[i][0] or 0, i),
            )
            del lines[oldest]
            texts[index] = cards[index].render(lines)
            cut += 1
    return texts, cut
