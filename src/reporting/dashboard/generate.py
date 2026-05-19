#!/usr/bin/env python3
"""
Generate an interactive HTML dashboard with Plotly visualizations.
Opens as a single self-contained HTML file - no server needed.
"""

import json
import os
import re

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
SCORES_DIR = os.path.join(PROJECT_ROOT, "output", "scores", "comparative")
SCORES_FILE = os.path.join(PROJECT_ROOT, "output", "scores", "scores_comparative.json")
SCREEN_TIME_FILE = os.path.join(PROJECT_ROOT, "data", "source", "metrics", "screen_time_v2.json")
BOOK_MENTIONS_FILE = os.path.join(PROJECT_ROOT, "data", "source", "metrics", "book_mentions_v2.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "output", "dashboard.html")

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]
DIM_LABELS = {
    "personality": "Personality",
    "narrative_role": "Narrative Role",
    "motivations": "Motivations",
    "character_arc": "Character Arc",
}
DIM_COLORS = {
    "personality": "#e74c3c",
    "narrative_role": "#3498db",
    "motivations": "#2ecc71",
    "character_arc": "#f39c12",
}


def load_data():
    with open(SCORES_FILE) as f:
        scores = json.load(f)
    with open(SCREEN_TIME_FILE) as f:
        screen_time = json.load(f)
    with open(BOOK_MENTIONS_FILE) as f:
        book_mentions = json.load(f)
    return scores, screen_time, book_mentions


def load_justifications():
    justifications = {}
    for fname in sorted(os.listdir(SCORES_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(SCORES_DIR, fname)) as f:
            data = json.load(f)
        comp = data.get("per_source", {}).get("comparative", {})
        justifications[data["character"]] = {
            "justification": comp.get("justification", {}),
            "key_observations": comp.get("key_observations", ""),
        }
    return justifications


def load_template():
    with open(os.path.join(DASHBOARD_DIR, "template.html")) as f:
        return f.read()


def load_css():
    with open(os.path.join(DASHBOARD_DIR, "style.css")) as f:
        return f.read()


def load_js():
    with open(os.path.join(DASHBOARD_DIR, "dashboard.js")) as f:
        return f.read()


# --- Chart builders ---


def fig_ranking_bar(scores, title="Top", ascending=False):
    if ascending:
        subset = sorted(scores, key=lambda s: s["overall"]["total"])
    else:
        subset = scores[:]

    names = [s["character"] for s in subset]
    totals = [s["overall"]["total"] for s in subset]
    fig = go.Figure()
    for dim in DIMENSIONS:
        fig.add_trace(
            go.Bar(
                name=DIM_LABELS[dim],
                x=names,
                y=[s["overall"][dim] for s in subset],
                marker_color=DIM_COLORS[dim],
                customdata=totals,
                hovertemplate="%{x}<br>" + DIM_LABELS[dim] + ": %{y:.1f}<br>Total: %{customdata}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        title=f"{title} Characters by Faithfulness Score",
        xaxis_title="Character",
        yaxis_title="FP Score (out of 100)",
        yaxis=dict(range=[0, 105]),
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def fig_scatter_presence(scores):
    data = []
    for s in scores:
        m = s.get("meta", {})
        sw = m.get("screenplay_words", 0)
        bm = m.get("book_mentions", 0)
        if sw == 0 and bm == 0:
            continue
        data.append({
            "character": s["character"],
            "screenplay_words": sw,
            "book_mentions": bm,
            "total_fp": s["overall"]["total"],
        })
    df = pd.DataFrame(data)
    fig = px.scatter(
        df,
        x="book_mentions",
        y="screenplay_words",
        color="total_fp",
        hover_name="character",
        color_continuous_scale="RdYlGn",
        title="Character Presence: Books vs Films (colour = FP score)",
        labels={
            "book_mentions": "Book Mentions",
            "screenplay_words": "Screenplay Words",
            "total_fp": "FP Score",
        },
        height=600,
    )
    fig.update_layout(xaxis_type="log", yaxis_type="log")
    fig.update_traces(marker=dict(size=10))
    return fig


def fig_score_distribution(scores):
    totals = [s["overall"]["total"] for s in scores]
    fig = go.Figure(go.Histogram(
        x=totals,
        nbinsx=20,
        marker_color="#f0c75e",
        hovertemplate="Score %{x}: %{y} characters<extra></extra>",
    ))
    fig.update_layout(
        title="FP Score Distribution",
        xaxis_title="FP Score",
        yaxis_title="Number of Characters",
        height=350,
    )
    return fig


# --- HTML builders ---


def build_charts_html(scores):
    fig_top = fig_ranking_bar(scores, title="Top")
    fig_bottom = fig_ranking_bar(scores, title="Lowest", ascending=True)
    fig_presence = fig_scatter_presence(scores)
    fig_dist = fig_score_distribution(scores)

    figs = [
        ("top", fig_top),
        ("bottom", fig_bottom),
        ("scatter", fig_presence),
        ("dist", fig_dist),
    ]

    parts = []
    for name, fig in figs:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(22,33,62,0.8)",
            font_color="#eee",
        )
        chart_html = fig.to_html(full_html=False, include_plotlyjs=(name == "top"))
        if name in ("top", "bottom"):
            dropdown = (
                f'<select class="count-select" onchange="updateChart(\'{name}\', this.value)">'
                '<option value="5">5</option>'
                '<option value="10">10</option>'
                '<option value="20" selected>20</option>'
                '<option value="50">50</option>'
                '<option value="100">100</option>'
                '<option value="all">All</option>'
                '</select>'
            )
            parts.append(f'<div class="chart-container" id="container-{name}">{dropdown}{chart_html}</div>')
        else:
            parts.append(f'<div class="chart-container" id="container-{name}">{chart_html}</div>')

    return "\n".join(parts)


def build_character_cards_html(scores, justifications):
    parts = []
    for s in scores:
        name = s["character"]
        total = s["overall"]["total"]
        j = justifications.get(name, {})
        just = j.get("justification", {})
        obs = j.get("key_observations", "")

        dim_html = ""
        for dim in DIMENSIONS:
            score = s["overall"][dim]
            text = just.get(dim, "No justification available.")
            dim_html += (
                f'<div class="dim-row">'
                f'<span class="dim-name">{DIM_LABELS[dim]}</span>'
                f'<span class="dim-score">{score:.0f}/25</span>'
                f'<p class="dim-text">{text}</p>'
                f'</div>'
            )

        obs_html = f'<div class="obs"><strong>Key observations:</strong> {obs}</div>' if obs else ""

        parts.append(
            f'<div class="char-card" onclick="this.classList.toggle(\'expanded\')">'
            f'<div class="char-header">'
            f'<span class="char-name">{name}</span>'
            f'<span class="char-score">{total:.0f}</span>'
            f'<span class="expand-hint">click to expand</span>'
            f'</div>'
            f'<div class="char-details">{dim_html}{obs_html}</div>'
            f'</div>'
        )

    return "\n".join(parts)


def build_dashboard(scores):
    justifications = load_justifications()
    template = load_template()

    # Build character data for JS filtering
    char_data = []
    for s in scores:
        m = s.get("meta", {})
        char_data.append({
            "name": s["character"],
            "personality": s["overall"]["personality"],
            "narrative_role": s["overall"]["narrative_role"],
            "motivations": s["overall"]["motivations"],
            "character_arc": s["overall"]["character_arc"],
            "total": s["overall"]["total"],
            "book_mentions": m.get("book_mentions", 0),
            "screenplay_words": m.get("screenplay_words", 0),
            "presence": m.get("book_mentions", 0) + m.get("screenplay_words", 0),
        })

    html = template.replace("{{CSS}}", load_css())
    html = html.replace("{{JS}}", load_js())
    html = html.replace("{{CHARACTER_DATA_JSON}}", json.dumps(char_data))
    html = html.replace("{{JUSTIFICATIONS_JSON}}", json.dumps(justifications))
    html = html.replace("{{NUM_SCORED}}", str(len(scores)))
    html = html.replace("{{HIGHEST_FP}}", f"{scores[0]['overall']['total']:.0f}")
    html = html.replace("{{LOWEST_FP}}", f"{scores[-1]['overall']['total']:.0f}")
    html = html.replace("{{AVERAGE_FP}}", f"{sum(s['overall']['total'] for s in scores) / len(scores):.0f}")
    html = html.replace("{{CHARTS}}", build_charts_html(scores))
    html = html.replace("{{CHARACTER_CARDS}}", build_character_cards_html(scores, justifications))

    return html


def main():
    scores, screen_time, book_mentions = load_data()
    print(f"Building dashboard with {len(scores)} characters...")

    html = build_dashboard(scores)

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"Dashboard saved to {OUTPUT_FILE} ({size_mb:.1f} MB)")
    print(f"Open in browser: file://{os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
