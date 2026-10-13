"""Offline checks for the screening eval. No network and no model calls.

Run: uv run --project backend python scripts/evals/screening/tests/test_screening.py
"""

import json
import tempfile
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401
import pandas as pd
from adapter import (
    dataset_manifest,
    load_and_adapt_dataset,
    load_csmed,
    load_synergy,
    load_three_ie,
    sample_data,
)
from metrics import calculate_metrics, cost_usd
from policy_atlas.evidence_search.assess.screen_prompt import ScreenRepWire
from policy_atlas.evidence_search.assess.screening_backend import StubScreeningBackend
from build_targets import clean_title, fit_criteria
from analyse_runs import f_score, keep_share, mcnemar_exact_p, wilson_interval
from rank_baselines import auc, average_precision, bm25_scores, tokens
from run_screen import screen_frame, use_settings
from targets import select_targets
from vote import combine_reps


def _rep(decision: str, confidence: float = 0.8) -> ScreenRepWire:
    return ScreenRepWire(decision=decision, confidence=confidence, reason="because")


def test_select_targets_all_and_unknown() -> None:
    assert len(select_targets(None)) == 30
    assert [item["name"] for item in select_targets(["Psych_CBT_Anxiety"])] == [
        "Psych_CBT_Anxiety"
    ]
    try:
        select_targets(["not-a-target"])
    except ValueError as exc:
        assert "not-a-target" in str(exc)
    else:
        raise AssertionError("unknown target should fail")


def test_csmed_maps_included_and_filters_review() -> None:
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / "CESMeD"
    folder.mkdir()
    pd.DataFrame(
        [
            {
                "review_id": "CD1",
                "document_id": 7,
                "title": "Kept",
                "abstract": "yes",
                "decision": "Included",
            },
            {
                "review_id": "CD1",
                "document_id": 8,
                "title": "Dropped",
                "abstract": None,
                "decision": "excluded",
            },
            {
                "review_id": "CD2",
                "document_id": 9,
                "title": "Other review",
                "abstract": "no",
                "decision": "included",
            },
        ]
    ).to_csv(folder / "CSMeD-FT-dev.csv", index=False)

    frame = load_csmed("CD1", tmp)
    assert list(frame["doc_id"]) == ["CSMeD_7", "CSMeD_8"]
    assert list(frame["ground_truth_relevant"]) == [1, 0]
    assert frame.loc[frame["doc_id"] == "CSMeD_8", "abstract_or_summary"].isna().all()


def test_synergy_uses_label_included() -> None:
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / "SYNERGY"
    folder.mkdir()
    pd.DataFrame(
        [
            {"title": "A", "abstract": "a", "label_included": 1},
            {"title": "B", "abstract": "b", "label_included": 0},
        ]
    ).to_csv(folder / "van_Dis_2020.csv", index=False)
    frame = load_synergy("van_Dis_2020", tmp)
    assert list(frame["doc_id"]) == ["SYNERGY_van_Dis_2020_0", "SYNERGY_van_Dis_2020_1"]
    assert list(frame["ground_truth_relevant"]) == [1, 0]


def test_three_ie_treats_other_maps_as_negatives() -> None:
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / "Three_IE"
    folder.mkdir()
    pd.DataFrame([{"Title": "On topic", "Abstract": "yes"}]).to_csv(
        folder / "3ie_EGM_Climate_2024.csv", index=False
    )
    pd.DataFrame([{"title": "Other map", "summary": "no"}]).to_csv(
        folder / "3ie_EGM_WASH_2023.csv", index=False
    )
    frame = load_three_ie("3ie_EGM_Climate_2024", tmp)
    labels = dict(zip(frame["doc_id"], frame["ground_truth_relevant"], strict=True))
    assert labels["3IE_3ie_EGM_Climate_2024_0"] == 1
    assert labels["3IE_3ie_EGM_WASH_2023_0"] == 0

    only = tmp / "only_one" / "Three_IE"
    only.mkdir(parents=True)
    pd.DataFrame([{"title": "Alone", "abstract": "no other map"}]).to_csv(
        only / "solo.csv", index=False
    )
    try:
        load_three_ie("solo", only.parent)
    except ValueError as exc:
        assert "negative" in str(exc).lower()
    else:
        raise AssertionError("a single 3ie file should fail")


def _labelled(n_pos: int, n_neg: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "doc_id": [f"d{i}" for i in range(n_pos + n_neg)],
            "title": ["t"] * (n_pos + n_neg),
            "abstract_or_summary": ["a"] * (n_pos + n_neg),
            "ground_truth_relevant": [1] * n_pos + [0] * n_neg,
        }
    )


def test_three_ie_pool_is_even_and_skips_target_map_studies() -> None:
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / "Three_IE"
    folder.mkdir()
    pd.DataFrame(
        {"title": ["Shared study", "Only here"], "abstract": ["x", "y"]}
    ).to_csv(folder / "target.csv", index=False)
    big = [f"Big {i}" for i in range(500)] + ["shared  STUDY!"]
    pd.DataFrame({"title": big, "abstract": "a"}).to_csv(
        folder / "big.csv", index=False
    )
    small = [f"Small {i}" for i in range(500)]
    pd.DataFrame({"title": small, "abstract": "a"}).to_csv(
        folder / "small.csv", index=False
    )
    frame = load_three_ie("target", tmp)
    negatives = frame[frame["ground_truth_relevant"] == 0]
    assert "shared  STUDY!" not in set(negatives["title"])
    sources = negatives["doc_id"].str.split("_").str[1].value_counts()
    assert sources.to_dict() == {"big": 100, "small": 100}

    manifest = dataset_manifest(tmp)
    assert sorted(manifest) == [
        "Three_IE/big.csv",
        "Three_IE/small.csv",
        "Three_IE/target.csv",
    ]
    assert all(len(value) == 64 for value in manifest.values())


def test_sample_caps_and_mini_is_inside_full() -> None:
    # 2 positives, 4 negatives: 2 * 3 = 6 wanted, only 4 available.
    sampled = sample_data(_labelled(2, 4))
    assert int(sampled["ground_truth_relevant"].sum()) == 2
    assert len(sampled) == 6
    assert list(sampled["doc_id"]) == list(sample_data(_labelled(2, 4))["doc_id"])

    # 1 positive: three negatives per positive.
    assert len(sample_data(_labelled(1, 9))) == 4

    # Large pool: full keeps 50 + 100, mini keeps 5 + 5, inside full.
    pool = _labelled(400, 900)
    full = sample_data(pool, "full")
    mini = sample_data(pool, "mini")
    assert int(full["ground_truth_relevant"].sum()) == 50 and len(full) == 150
    assert int(mini["ground_truth_relevant"].sum()) == 5 and len(mini) == 10
    assert set(mini["doc_id"]) <= set(full["doc_id"])


def test_adapt_fills_missing_text() -> None:
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / "SYNERGY"
    folder.mkdir()
    pd.DataFrame([{"title": None, "abstract": None, "label_included": 1}]).to_csv(
        folder / "Hall_2012.csv", index=False
    )
    frame = load_and_adapt_dataset(
        {"id": "Hall_2012", "dataset_source": "SYNERGY", "name": "x", "query": "q"},
        tmp,
    )
    assert frame.iloc[0]["title"] == "No title"
    assert frame.iloc[0]["abstract_or_summary"] == "No abstract available"


def test_keep_rule() -> None:
    unsure = combine_reps([_rep("unsure", 0.9)], reps_requested=1, title_only=False)
    assert unsure.status == "relevant"
    assert unsure.confidence == 0.5

    dropped = combine_reps(
        [_rep("not_relevant", 0.7)], reps_requested=1, title_only=False
    )
    assert dropped.status == "not_relevant"
    assert dropped.confidence == 0.7

    majority_drop = combine_reps(
        [_rep("relevant"), _rep("not_relevant"), _rep("not_relevant")],
        reps_requested=3,
        title_only=False,
    )
    assert majority_drop.status == "not_relevant"
    assert majority_drop.flags == ()

    tie = combine_reps(
        [_rep("relevant", 0.6), _rep("not_relevant", 0.6)],
        reps_requested=2,
        title_only=False,
    )
    assert tie.status == "relevant"
    assert "tie_broken" in tie.flags

    veto = combine_reps(
        [_rep("relevant"), _rep("not_relevant"), _rep("not_relevant")],
        reps_requested=3,
        title_only=True,
    )
    assert veto.status == "relevant"
    assert "title_only_unanimity_applied" in veto.flags

    unsure_does_not_veto = combine_reps(
        [_rep("unsure"), _rep("not_relevant"), _rep("not_relevant")],
        reps_requested=3,
        title_only=True,
    )
    assert unsure_does_not_veto.status == "not_relevant"

    short = combine_reps([_rep("relevant")], reps_requested=3, title_only=False)
    assert short.status == "failed"
    assert short.confidence is None


def test_metrics_and_cost() -> None:
    frame = pd.DataFrame(
        {
            "ground_truth_relevant": [1, 1, 0, 0],
            "predicted_relevant": [1, 0, 1, 0],
            "confidence": [0.9, 0.2, 0.4, None],
        }
    )
    metrics = calculate_metrics(frame)
    assert metrics["tp"] == 1 and metrics["fn"] == 1
    assert metrics["fp"] == 1 and metrics["tn"] == 1
    assert metrics["recall"] == 0.5
    assert metrics["precision"] == 0.5
    # F2 = 5 * p * r / (4p + r) = 5 * 0.25 / 2.5 = 0.5
    assert metrics["f_beta_2"] == 0.5
    assert metrics["avg_conf_tp"] == 0.9
    assert metrics["avg_conf_tn"] is None

    # 1M uncached input at $0.75, 1M cached at $0.075, 1M output at $4.50.
    assert (
        cost_usd(
            "gpt-5.4-mini",
            prompt_tokens=2_000_000,
            cached_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        == 0.75 + 0.075 + 4.50
    )
    assert (
        cost_usd(
            "gpt-5.6-luna",
            prompt_tokens=1_000_000,
            cached_tokens=0,
            completion_tokens=0,
        )
        == 0.20
    )
    assert (
        cost_usd("gpt-unknown", prompt_tokens=10, cached_tokens=0, completion_tokens=10)
        is None
    )


def test_screen_frame_runs_the_production_loop() -> None:
    class CountingStub(StubScreeningBackend):
        def __init__(self) -> None:
            self.payloads = []

        def screen_envelope(self, payload, *, rep_index=0):
            self.payloads.append(payload)
            return super().screen_envelope(payload, rep_index=rep_index)

    frame = pd.DataFrame(
        {
            "doc_id": ["a", "b"],
            "title": ["With abstract", "Title only"],
            "abstract_or_summary": ["Some abstract.", None],
            "ground_truth_relevant": [1, 0],
        }
    )
    use_settings(model="gpt-5.4-mini", reps=3, effort=None)
    stub = CountingStub()
    screened, _usage, retries = screen_frame(frame, backend=stub, intent="q", reps=3)
    assert len(stub.payloads) == 6 and retries == 0
    sources = {payload.tss_id: payload.abstract_source for payload in stub.payloads}
    assert sources == {"a": "publisher_abstract", "b": "none"}
    assert list(screened["doc_id"]) == ["a", "b"]
    assert list(screened["n_relevant"]) == [3, 3]
    assert list(screened["predicted_relevant"]) == [1, 1]
    first = json.loads(screened.iloc[0]["rep_answers"])
    assert first == [{"decision": "relevant", "confidence": 0.9}] * 3


def test_system_prompt_override_reaches_the_messages() -> None:
    import policy_atlas.evidence_search.assess.screen_prompt as product_prompt
    from policy_atlas.evidence_search.assess.screen_prompt import (
        ScreenEnvelopePayload,
        build_screen_messages,
    )

    original = product_prompt.SCREEN_SYSTEM_PROMPT
    prompt_file = Path(tempfile.mkdtemp()) / "short.txt"
    prompt_file.write_text("Short prompt.", encoding="utf-8")
    try:
        label = use_settings(
            model="gpt-5.4-mini", reps=3, effort=None, system_prompt=prompt_file
        )
        payload = ScreenEnvelopePayload(
            tss_id="x", title="t", abstract=None, abstract_source=None, intent="q"
        )
        assert build_screen_messages(payload)[0]["content"] == "Short prompt."
        assert label.startswith("short@") and len(label) == len("short@") + 12
        assert use_settings(model="gpt-5.4-mini", reps=3, effort=None) == "screen_v2"
        # A later run without a prompt file gets the production prompt back.
        assert build_screen_messages(payload)[0]["content"] == original
        use_settings(model="gpt-5.4-mini", reps=3, effort="low")
        use_settings(model="gpt-5.4-mini", reps=3, effort=None)
        import policy_atlas.evidence_search.assess.screening_backend as backend_module

        assert not hasattr(backend_module.parse_structured, "keywords")
    finally:
        product_prompt.SCREEN_SYSTEM_PROMPT = original


def test_analysis_statistics() -> None:
    low, high = wilson_interval(95, 100)
    assert round(low, 3) == 0.888 and round(high, 3) == 0.978
    assert mcnemar_exact_p(0, 0) == 1.0
    assert f_score(0.5, 1.0) == 2 / 3
    assert round(f_score(0.5, 1.0, beta=2), 4) == 0.8333
    assert f_score(0.0, 0.0) == 0.0
    assert round(mcnemar_exact_p(2, 6), 3) == 0.289
    assert round(mcnemar_exact_p(0, 6), 4) == 0.0312
    answers = [
        {"decision": "relevant", "confidence": 0.9},
        {"decision": "unsure", "confidence": 0.5},
        {"decision": "not_relevant", "confidence": 0.9},
        {"failed": "RuntimeError"},
    ]
    assert keep_share(answers) == 2 / 3
    assert keep_share([{"failed": "x"}]) != keep_share([{"failed": "x"}])  # nan


def test_build_rules() -> None:
    assert (
        clean_title("Rosuvastatin for lowering lipids")
        == "Rosuvastatin for lowering lipids"
    )
    assert (
        clean_title("Long-term Outcomes of CBT. A Systematic Review and Meta-analysis")
        == "Long-term Outcomes of CBT"
    )
    assert (
        clean_title("Food systems in LMICs: a living evidence gap map")
        == "Food systems in LMICs"
    )
    assert clean_title("Water: An outcome-to-outcome systematic map") == "Water"
    assert clean_title("Sexual and Reproductive Health Evidence Gap Map") == (
        "Sexual and Reproductive Health"
    )
    assert clean_title("Drivers of migration: an evidence gap map update") == (
        "Drivers of migration"
    )

    kept, dropped = fit_criteria("q", ["a" * 900, "b" * 900, "c" * 900])
    assert dropped == 1 and len(kept) == 2
    long_paragraph = "First sentence is here. " * 50
    kept, dropped = fit_criteria("q", [long_paragraph.strip()])
    assert all(len(item) <= 1000 for item in kept) and len(kept) > 1


def test_rank_baselines() -> None:
    assert tokens("The Effects of CBT, in 2020!") == ["effects", "cbt", "2020"]
    docs = ["anxiety therapy trial", "anxiety", "heart failure care"]
    frequency = Counter(word for text in docs for word in set(tokens(text)))
    scores = bm25_scores("anxiety therapy", docs, frequency, len(docs), 7 / 3)
    assert scores[0] > scores[1] > scores[2] == 0.0

    labels = pd.Series([1, 0, 1, 0])
    assert auc(pd.Series([0.9, 0.1, 0.8, 0.2]), labels) == 1.0
    assert auc(pd.Series([0.5, 0.5, 0.5, 0.5]), labels) == 0.5
    assert average_precision(pd.Series([1, 2, 3, 4]), labels) == (1 / 1 + 2 / 3) / 2


def _main() -> None:
    test_select_targets_all_and_unknown()
    test_sample_caps_and_mini_is_inside_full()
    test_three_ie_pool_is_even_and_skips_target_map_studies()
    test_keep_rule()
    test_metrics_and_cost()
    test_csmed_maps_included_and_filters_review()
    test_synergy_uses_label_included()
    test_three_ie_treats_other_maps_as_negatives()
    test_adapt_fills_missing_text()
    test_screen_frame_runs_the_production_loop()
    test_analysis_statistics()
    test_build_rules()
    test_rank_baselines()
    test_system_prompt_override_reaches_the_messages()
    print("ok")


if __name__ == "__main__":
    _main()
