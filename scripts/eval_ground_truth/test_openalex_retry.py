"""Self-check for ``openalex_get``'s retry-on-504 behaviour.

Run it with:  uv run --project backend python scripts/eval_ground_truth/test_openalex_retry.py

It never touches the network: it swaps ``httpx.get`` and ``time.sleep`` for
fakes, so it only tests the retry decisions.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import httpx  # noqa: E402

import ground_truth  # noqa: E402


def _fake_responses(*status_codes):
    """Return a stand-in for ``httpx.get`` that yields these codes in order."""
    codes = list(status_codes)

    def fake_get(url, **_kwargs):
        return httpx.Response(codes.pop(0), request=httpx.Request("GET", url))

    return fake_get


def demo():
    with patch("time.sleep"):  # no real waiting in the test
        # A 504 then a 200: the retry wins, the caller sees only the 200.
        with patch("httpx.get", _fake_responses(504, 200)):
            assert ground_truth.openalex_get("/works/W1").status_code == 200

        # A genuine 404 is not transient: return it at once, do not retry.
        with patch("httpx.get", _fake_responses(404, 200)):
            assert ground_truth.openalex_get("/works/W1").status_code == 404

        # Always 504: give up after 5 tries and hand back the last response.
        with patch("httpx.get", _fake_responses(504, 504, 504, 504, 504)):
            assert ground_truth.openalex_get("/works/W1").status_code == 504

        # A connection error that later clears is also retried.
        calls = {"n": 0}

        def flaky_get(url, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectTimeout("boom")
            return httpx.Response(200, request=httpx.Request("GET", url))

        with patch("httpx.get", flaky_get):
            assert ground_truth.openalex_get("/works/W1").status_code == 200

    print("openalex_get retry self-check passed")


if __name__ == "__main__":
    demo()
