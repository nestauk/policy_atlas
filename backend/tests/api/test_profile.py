"""Onboarding profile routes: ``/api/v1/me/profile`` behind the ``onboarding`` flag."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine

from tests.api.resource_support import api_client

ONBOARDING = frozenset({"onboarding"})
URL = "/api/v1/me/profile"
ANSWERS = {
    "department": "dfe",
    "team_type": "analysis_evidence",
    "primary_job": "j3",
}


def test_with_the_flag_off_every_profile_route_is_a_404(tmp_path: Path, engine: Engine) -> None:
    """The API surface with the flag off is the same as before the element."""
    del engine
    with api_client(tmp_path) as (client, owner, _other):
        assert client.get(URL, headers=owner).status_code == 404
        assert client.put(URL, headers=owner, json=ANSWERS).status_code == 404
        assert client.post(f"{URL}/skip", headers=owner).status_code == 404


def test_the_profile_routes_need_a_signed_in_user(tmp_path: Path, engine: Engine) -> None:
    """No token, no profile."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, _owner, _other):
        assert client.get(URL).status_code == 401


def test_a_new_user_has_an_empty_profile(tmp_path: Path, engine: Engine) -> None:
    """Before the first answer every field is null: the form is due."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, owner, _other):
        response = client.get(URL, headers=owner)

        assert response.status_code == 200, response.text
        assert set(response.json().values()) == {None}


def test_completing_the_profile_stores_the_answers(tmp_path: Path, engine: Engine) -> None:
    """The first PUT completes the profile, with no earlier ``GET /me`` call."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, owner, other):
        body = {
            **ANSWERS,
            "department": "other",
            "department_other": "Office for Examples",
            "secondary_job": "j7",
            "panel_opt_in": True,
        }

        saved = client.put(URL, headers=owner, json=body)

        assert saved.status_code == 200, saved.text
        profile = client.get(URL, headers=owner).json()
        assert {key: profile[key] for key in body} == body
        assert profile["completed_at"] is not None
        assert profile["skipped_once_at"] is None
        assert profile["source"] is None
        # One user's profile is not another user's.
        assert client.get(URL, headers=other).json()["completed_at"] is None


def test_the_first_two_questions_are_required(tmp_path: Path, engine: Engine) -> None:
    """Department, team type and the main use are required; codes are closed lists."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, owner, _other):
        for missing in ANSWERS:
            body = {key: value for key, value in ANSWERS.items() if key != missing}
            assert client.put(URL, headers=owner, json=body).status_code == 422, missing
        for field, value in (
            ("primary_job", "j9"),
            ("team_type", "marketing"),
            ("department", "Department for Education"),
        ):
            response = client.put(URL, headers=owner, json={**ANSWERS, field: value})
            assert response.status_code == 422, field
        assert client.get(URL, headers=owner).json()["completed_at"] is None


def test_only_the_first_skip_is_recorded(tmp_path: Path, engine: Engine) -> None:
    """Exactly one "Skip for now": a second skip does not move the time."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, owner, _other):
        first = client.post(f"{URL}/skip", headers=owner)
        second = client.post(f"{URL}/skip", headers=owner)

        assert first.status_code == 200, first.text
        assert first.json()["skipped_once_at"] is not None
        assert first.json()["completed_at"] is None
        assert second.json()["skipped_once_at"] == first.json()["skipped_once_at"]


def test_a_skip_then_a_completion_keeps_both_times(tmp_path: Path, engine: Engine) -> None:
    """A user who skipped once and then completed the form has both times."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, owner, _other):
        skipped = client.post(f"{URL}/skip", headers=owner).json()

        completed = client.put(URL, headers=owner, json=ANSWERS).json()

        assert completed["skipped_once_at"] == skipped["skipped_once_at"]
        assert completed["completed_at"] is not None
        assert completed["primary_job"] == "j3"


def test_an_edit_replaces_the_answers_and_keeps_the_completion_time(
    tmp_path: Path, engine: Engine
) -> None:
    """The profile is editable afterwards; ``completed_at`` is the first completion."""
    del engine
    with api_client(tmp_path, feedback_elements=ONBOARDING) as (client, owner, _other):
        first = client.put(URL, headers=owner, json={**ANSWERS, "secondary_job": "j1"}).json()

        edited = client.put(URL, headers=owner, json={**ANSWERS, "primary_job": "j5"}).json()

        assert edited["primary_job"] == "j5"
        assert edited["secondary_job"] is None
        assert edited["completed_at"] == first["completed_at"]
