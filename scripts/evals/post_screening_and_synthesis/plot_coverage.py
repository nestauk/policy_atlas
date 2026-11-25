"""Plot ingested-denominator coverage for one synthesis eval run.

Reads ``scores`` from each briefing's ``eval_results.json`` under
``results/runs/<run>/`` and draws interactive nested horizontal bars.

Usage (from the repo root)::

    uv run --project backend python \
        scripts/evals/post_screening_and_synthesis/plot_coverage.py \
        --run 2026-11-05-deep-necessary-facts

Writes ``results/runs/<run>/coverage_ingested.html`` and ``.png`` (the PNG
needs ``kaleido``, declared in the backend ``dev`` dependency group).
"""

from __future__ import annotations

import argparse
import json
import logging

import pandas as pd
import plotly.graph_objects as go

import _bootstrap  # noqa: F401
from utils import RESULTS_DIR

STRICT = "coverage_ingested"
LENIENT = "coverage_ingested_lenient"

# Nesta brand: blue for the strict bar, the same hue one step lighter for the
# lenient bar it sits inside (nested bars share a hue; validated pair).
STRICT_COLOUR = "#0000FF"
LENIENT_COLOUR = "#9999FF"
INK = "#000000"
MUTED_INK = "#52514e"
GRID = "#E6E6E6"
FONT = "Century Gothic, sans-serif"
OUT_STEM = "coverage_ingested"
PNG_SCALE = 2
FIG_WIDTH = 1200  # px; without this the PNG export defaults to 700 and looks portrait

HOVER = (
    "<b>%{y}</b><br>"
    "Strict coverage: %{customdata[0]:.0%}<br>"
    "Lenient coverage: %{customdata[1]:.0%}<br>"
    "Ingested facts: %{customdata[2]}<extra></extra>"
)


def load_scores(run: str) -> pd.DataFrame:
    """Strict and lenient ingested coverage per briefing in a run folder."""
    rows = {
        path.parent.name: json.loads(path.read_text())["scores"]
        for path in sorted((RESULTS_DIR / run).glob("*/eval_results.json"))
    }
    return pd.DataFrame.from_dict(rows, orient="index")[[STRICT, LENIENT, "n_ingested"]]


def draw_nested_bars(scores: pd.DataFrame) -> go.Figure:
    """Interactive horizontal strict-inside-lenient bars, Nesta styled."""
    scores = scores.sort_values(STRICT)
    customdata = scores[[STRICT, LENIENT, "n_ingested"]].to_numpy()

    fig = go.Figure()

    # Background: lenient coverage, value labelled past the end of the bar.
    fig.add_trace(
        go.Bar(
            y=scores.index,
            x=scores[LENIENT],
            orientation="h",
            name="Lenient: fully + partially represented",
            marker=dict(color=LENIENT_COLOUR, cornerradius=4),
            text=scores[LENIENT],
            texttemplate="%{text:.0%}",
            textposition="outside",
            textfont=dict(color=MUTED_INK),
            customdata=customdata,
            hovertemplate=HOVER,
        )
    )

    # Foreground: strict coverage, value labelled inside its end in white.
    fig.add_trace(
        go.Bar(
            y=scores.index,
            x=scores[STRICT],
            orientation="h",
            name="Strict: fully represented",
            marker=dict(color=STRICT_COLOUR, cornerradius=4),
            text=scores[STRICT],
            texttemplate="%{text:.0%}",
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="white"),
            customdata=customdata,
            hovertemplate=HOVER,
        )
    )

    fig.update_layout(
        title=dict(
            text=(
                "<b>Coverage of key facts by ingested sources</b>"
                "<br><span style='font-size:13px;color:#52514e'>"
                "One bar per briefing, ordered by strict coverage</span>"
            ),
            x=0,
            xanchor="left",
        ),
        font=dict(family=FONT, color=INK, size=16),
        barmode="overlay",
        bargap=0.35,
        paper_bgcolor="white",
        plot_bgcolor="white",
        width=FIG_WIDTH,
        height=max(450, len(scores) * 38 + 180),
        margin=dict(l=20, r=40, t=120, b=60),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            xanchor="left",
            x=0,
            title=None,
        ),
        uniformtext=dict(minsize=12, mode="hide"),
    )

    fig.update_xaxes(
        title="Share of key facts with an ingested source",
        range=[0, 1.12],
        tickformat=".0%",
        tickvals=[0, 0.25, 0.5, 0.75, 1.0],
        showgrid=True,
        gridcolor=GRID,
        zeroline=False,
        showline=False,
    )
    fig.update_yaxes(
        title=None,
        categoryorder="array",
        categoryarray=scores.index.tolist(),
        showgrid=False,
        ticks="",
        automargin=True,
    )

    return fig


def plot(run: str) -> None:
    """Draw and save the per-briefing coverage figure for one run."""
    scores = load_scores(run)
    mean = scores[[STRICT, LENIENT]].mean()

    fig = draw_nested_bars(scores)

    out = RESULTS_DIR / run / OUT_STEM
    fig.write_html(out.with_suffix(".html"))
    fig.write_image(out.with_suffix(".png"), scale=PNG_SCALE)

    logging.info(
        "mean strict %.3f, lenient %.3f -> %s.{html,png}",
        *mean,
        out,
    )


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", required=True, help="run folder under results/runs")
    plot(parser.parse_args().run)


if __name__ == "__main__":
    main()
