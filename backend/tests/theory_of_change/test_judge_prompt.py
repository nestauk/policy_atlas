"""toc_judge_v4 message assembly: the test block and the tidied step text."""

from policy_atlas.theory_of_change.evidence.judge_prompt import build_judge_messages

ITEM = (
    "Lower excess energy leads to less obesity.\n"
    "From: Children consume less excess dietary energy\n"
    "To: Fewer children in England live with obesity\n"
    "If IF children eat less, for FOR children, then THEN fewer are obese, "
    "because BECAUSE energy balance..\n"
)


def _user(item_text: str) -> str:
    messages = build_judge_messages(
        item_text=item_text,
        population="Children in England",
        place="England",
        document_id="d1",
        title="A trial",
        year=2004,
        text="Abstract.",
        modelling=False,
    )
    return str(messages[1]["content"])


def test_the_test_names_the_steps_source_and_target() -> None:
    user = _user(ITEM)
    assert "Source (what changes first): Children consume less excess dietary energy" in user
    assert "Target (what should follow): Fewer children in England live with obesity" in user
    assert user.index("<the_test>") < user.index("<step>")


def test_doubled_if_then_keywords_are_tidied() -> None:
    user = _user(ITEM)
    tidy = "If children eat less, for children, then fewer are obese, because energy balance."
    assert tidy in user
    assert "IF" not in user and ".." not in user


def test_missing_from_and_to_lines_say_not_stated() -> None:
    assert "Source (what changes first): not stated" in _user("A step with no lines.")
