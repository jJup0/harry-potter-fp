#!/usr/bin/env python3
"""
Generate an interactive HTML dashboard with Plotly visualizations.
Opens as a single self-contained HTML file — no server needed.
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCORES_FILE = os.path.join(PROJECT_ROOT, "output", "scores", "scores_comparative.json")
SCREEN_TIME_FILE = os.path.join(PROJECT_ROOT, "data", "metrics", "screen_time.json")
BOOK_MENTIONS_FILE = os.path.join(PROJECT_ROOT, "data", "metrics", "book_mentions.json")
PARSED_SCREENPLAYS = os.path.join(PROJECT_ROOT, "data", "parsed", "screenplays")
PARSED_BOOKS = os.path.join(PROJECT_ROOT, "data", "parsed", "books")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "output", "dashboard.html")

DIMENSIONS = ["personality", "narrative_role", "motivations", "character_arc"]
DIM_LABELS = {
    "personality": "Personality",
    "narrative_role": "Narrative Role",
    "motivations": "Motivations",
    "character_arc": "Character Arc",
}

HOUSE_COLORS = {
    "Gryffindor": "#740001",
    "Slytherin": "#1a472a",
    "Ravenclaw": "#0e1a40",
    "Hufflepuff": "#ecb939",
    "Other": "#666666",
}

# Rough house assignments for major characters
HOUSES = {
    "Harry Potter": "Gryffindor",
    "Ron Weasley": "Gryffindor",
    "Hermione Granger": "Gryffindor",
    "Neville Longbottom": "Gryffindor",
    "Ginny Weasley": "Gryffindor",
    "Fred Weasley": "Gryffindor",
    "George Weasley": "Gryffindor",
    "Albus Dumbledore": "Gryffindor",
    "Rubeus Hagrid": "Gryffindor",
    "Sirius Black": "Gryffindor",
    "Remus Lupin": "Gryffindor",
    "Minerva McGonagall": "Gryffindor",
    "Arthur Weasley": "Gryffindor",
    "Molly Weasley": "Gryffindor",
    "Peter Pettigrew": "Gryffindor",
    "Seamus Finnigan": "Gryffindor",
    "Dean Thomas": "Gryffindor",
    "Lavender Brown": "Gryffindor",
    "Parvati Patil": "Gryffindor",
    "Colin Creevey": "Gryffindor",
    "Draco Malfoy": "Slytherin",
    "Severus Snape": "Slytherin",
    "Lord Voldemort": "Slytherin",
    "Lucius Malfoy": "Slytherin",
    "Bellatrix Lestrange": "Slytherin",
    "Narcissa Malfoy": "Slytherin",
    "Vincent Crabbe": "Slytherin",
    "Gregory Goyle": "Slytherin",
    "Horace Slughorn": "Slytherin",
    "Pansy Parkinson": "Slytherin",
    "Blaise Zabini": "Slytherin",
    "Luna Lovegood": "Ravenclaw",
    "Cho Chang": "Ravenclaw",
    "Padma Patil": "Ravenclaw",
    "Gilderoy Lockhart": "Ravenclaw",
    "Sybill Trelawney": "Ravenclaw",
    "Cedric Diggory": "Hufflepuff",
    "Nymphadora Tonks": "Hufflepuff",
    "Pomona Sprout": "Hufflepuff",
    "Dolores Umbridge": "Slytherin",
}

FILM_ORDER = [
    "1_philosophers_stone",
    "2_chamber_of_secrets",
    "3_prisoner_of_azkaban",
    "4_goblet_of_fire",
    "5_order_of_the_phoenix",
    "6_half_blood_prince",
    "7_deathly_hallows_p1",
    "8_deathly_hallows_p2",
]
FILM_LABELS = {
    "1_philosophers_stone": "PS",
    "2_chamber_of_secrets": "CoS",
    "3_prisoner_of_azkaban": "PoA",
    "4_goblet_of_fire": "GoF",
    "5_order_of_the_phoenix": "OotP",
    "6_half_blood_prince": "HBP",
    "7_deathly_hallows_p1": "DH1",
    "8_deathly_hallows_p2": "DH2",
}
BOOK_ORDER = [
    "1_philosophers_stone",
    "2_chamber_of_secrets",
    "3_prisoner_of_azkaban",
    "4_goblet_of_fire",
    "5_order_of_the_phoenix",
    "6_half_blood_prince",
    "7_deathly_hallows",
]
BOOK_LABELS = {
    "1_philosophers_stone": "PS",
    "2_chamber_of_secrets": "CoS",
    "3_prisoner_of_azkaban": "PoA",
    "4_goblet_of_fire": "GoF",
    "5_order_of_the_phoenix": "OotP",
    "6_half_blood_prince": "HBP",
    "7_deathly_hallows": "DH",
}


def load_data():
    with open(SCORES_FILE) as f:
        scores = json.load(f)
    with open(SCREEN_TIME_FILE) as f:
        screen_time = json.load(f)
    with open(BOOK_MENTIONS_FILE) as f:
        book_mentions = json.load(f)
    return scores, screen_time, book_mentions


def build_co_occurrence():
    """Build character co-occurrence matrix from screenplay scenes."""
    from collections import Counter

    cooccur = Counter()
    for fname in sorted(os.listdir(PARSED_SCREENPLAYS)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PARSED_SCREENPLAYS, fname)) as f:
            data = json.load(f)
        for scene in data["scenes"]:
            chars = scene.get("characters", [])
            for i, a in enumerate(chars):
                for b in chars[i + 1 :]:
                    pair = tuple(sorted([a, b]))
                    cooccur[pair] += 1
    return cooccur


# --- Chart builders ---


def fig_ranking_bar(scores, top_n=30):
    """Stacked bar chart of top characters by FP dimension."""
    top = scores[:top_n]
    names = [s["character"] for s in top]
    fig = go.Figure()
    colors = {
        "personality": "#e74c3c",
        "narrative_role": "#3498db",
        "motivations": "#2ecc71",
        "character_arc": "#f39c12",
    }
    for dim in DIMENSIONS:
        fig.add_trace(
            go.Bar(
                name=DIM_LABELS[dim],
                x=names,
                y=[s["overall"][dim] for s in top],
                marker_color=colors[dim],
                hovertemplate="%{x}<br>"
                + DIM_LABELS[dim]
                + ": %{y:.1f}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        title=f"Top {top_n} Characters by Faithfulness Score",
        xaxis_title="Character",
        yaxis_title="FP Score (out of 100)",
        yaxis=dict(range=[0, 105]),
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def fig_radar_comparison(scores, char_names):
    """Radar chart comparing multiple characters."""
    fig = go.Figure()
    colors = px.colors.qualitative.Set2
    for i, name in enumerate(char_names):
        s = next((s for s in scores if s["character"] == name), None)
        if not s:
            continue
        vals = [s["overall"][d] for d in DIMENSIONS] + [s["overall"][DIMENSIONS[0]]]
        labels = [DIM_LABELS[d] for d in DIMENSIONS] + [DIM_LABELS[DIMENSIONS[0]]]
        fig.add_trace(
            go.Scatterpolar(
                r=vals,
                theta=labels,
                fill="toself",
                name=name,
                line_color=colors[i % len(colors)],
                opacity=0.7,
            )
        )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 25])),
        title="Character Comparison — FP Dimensions",
        height=500,
    )
    return fig


def fig_scatter_presence(scores):
    """Scatter: book mentions vs screenplay words, sized by FP score."""
    data = []
    for s in scores:
        m = s.get("meta", {})
        sw = m.get("screenplay_words", 0)
        bm = m.get("book_mentions", 0)
        if sw == 0 and bm == 0:
            continue
        house = HOUSES.get(s["character"], "Other")
        data.append(
            {
                "character": s["character"],
                "screenplay_words": sw,
                "book_mentions": bm,
                "total_fp": s["overall"]["total"],
                "house": house,
            }
        )
    df = pd.DataFrame(data)
    fig = px.scatter(
        df,
        x="book_mentions",
        y="screenplay_words",
        size="total_fp",
        color="house",
        hover_name="character",
        color_discrete_map=HOUSE_COLORS,
        title="Character Presence: Books vs Films (sized by FP score)",
        labels={
            "book_mentions": "Book Mentions",
            "screenplay_words": "Screenplay Words",
        },
        size_max=40,
        height=600,
    )
    fig.update_layout(xaxis_type="log", yaxis_type="log")
    return fig


def fig_heatmap_screen_time(screen_time, top_n=25):
    """Heatmap of screen time (words) per character per film."""
    # Get top characters by total
    sorted_chars = sorted(
        screen_time.items(), key=lambda x: x[1].get("_total", 0), reverse=True
    )[:top_n]
    chars = [c[0] for c in sorted_chars]

    z = []
    for char in chars:
        row = []
        for film in FILM_ORDER:
            row.append(screen_time.get(char, {}).get(film, 0))
        z.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[FILM_LABELS.get(f, f) for f in FILM_ORDER],
            y=chars,
            colorscale="YlOrRd",
            hovertemplate="%{y}<br>%{x}: %{z} words<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Screen Time Heatmap — Top {top_n} Characters (words spoken)",
        height=max(400, top_n * 22),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def fig_heatmap_book_mentions(book_mentions, top_n=25):
    """Heatmap of book mentions per character per book."""
    sorted_chars = sorted(
        book_mentions.items(), key=lambda x: x[1].get("_total", 0), reverse=True
    )[:top_n]
    chars = [c[0] for c in sorted_chars]

    z = []
    for char in chars:
        row = []
        for book in BOOK_ORDER:
            row.append(book_mentions.get(char, {}).get(book, 0))
        z.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[BOOK_LABELS.get(b, b) for b in BOOK_ORDER],
            y=chars,
            colorscale="YlGnBu",
            hovertemplate="%{y}<br>%{x}: %{z} mentions<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Book Mentions Heatmap — Top {top_n} Characters",
        height=max(400, top_n * 22),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def fig_arc_timeline(scores, char_names):
    """Line chart showing per-source FP total across films/books for selected characters."""
    fig = go.Figure()
    colors = px.colors.qualitative.Set2

    for i, name in enumerate(char_names):
        s = next((s for s in scores if s["character"] == name), None)
        if not s:
            continue

        # Films
        film_x, film_y = [], []
        for film in FILM_ORDER:
            if film in s.get("per_source", {}):
                ps = s["per_source"][film]
                total = sum(ps.get(d, 0) for d in DIMENSIONS)
                film_x.append(FILM_LABELS.get(film, film))
                film_y.append(total)

        # Books
        book_x, book_y = [], []
        for book in BOOK_ORDER:
            if book in s.get("per_source", {}):
                ps = s["per_source"][book]
                total = sum(ps.get(d, 0) for d in DIMENSIONS)
                book_x.append(BOOK_LABELS.get(book, book))
                book_y.append(total)

        color = colors[i % len(colors)]
        if film_x:
            fig.add_trace(
                go.Scatter(
                    x=film_x,
                    y=film_y,
                    mode="lines+markers",
                    name=f"{name} (film)",
                    line=dict(color=color),
                    marker=dict(symbol="circle"),
                )
            )
        if book_x:
            fig.add_trace(
                go.Scatter(
                    x=book_x,
                    y=book_y,
                    mode="lines+markers",
                    name=f"{name} (book)",
                    line=dict(color=color, dash="dash"),
                    marker=dict(symbol="diamond"),
                )
            )

    fig.update_layout(
        title="Character FP Score Across Installments",
        xaxis_title="Installment",
        yaxis_title="FP Score (per source)",
        yaxis=dict(range=[0, 105]),
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def build_dashboard(scores, screen_time, book_mentions):
    """Assemble all charts into a single HTML dashboard."""
    top_chars = [s["character"] for s in scores[:6]]

    figs = [
        ("ranking", fig_ranking_bar(scores, 30)),
        ("radar", fig_radar_comparison(scores, top_chars)),
        ("scatter", fig_scatter_presence(scores)),
        ("heatmap_films", fig_heatmap_screen_time(screen_time, 25)),
        ("heatmap_books", fig_heatmap_book_mentions(book_mentions, 25)),
        ("timeline", fig_arc_timeline(scores, top_chars[:4])),
    ]

    # Build HTML
    html_parts = [
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Harry Potter Character Faithfulness Dashboard</title>
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }
  h1 { text-align: center; color: #f0c75e; font-size: 2em; margin-bottom: 5px; }
  .subtitle { text-align: center; color: #aaa; margin-bottom: 30px; }
  .chart-container { background: #16213e; border-radius: 12px; padding: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
  .stats { display: flex; justify-content: center; gap: 40px; margin-bottom: 30px; flex-wrap: wrap; }
  .stat { text-align: center; }
  .stat-value { font-size: 2.5em; font-weight: bold; color: #f0c75e; }
  .stat-label { color: #aaa; font-size: 0.9em; }
  .note { text-align: center; color: #888; font-size: 0.85em; margin-top: 30px; }
</style>
</head>
<body>
<h1>⚡ Harry Potter Character Faithfulness Dashboard</h1>
<p class="subtitle">FP = Personality + Narrative Role + Motivations + Character Arc (each /25, total /100)</p>

<div class="stats">
  <div class="stat"><div class="stat-value">"""
        + str(len(scores))
        + """</div><div class="stat-label">Characters Scored</div></div>
  <div class="stat"><div class="stat-value">7</div><div class="stat-label">Books Analyzed</div></div>
  <div class="stat"><div class="stat-value">8</div><div class="stat-label">Films Analyzed</div></div>
  <div class="stat"><div class="stat-value">"""
        + f"{scores[0]['overall']['total']:.1f}"
        + """</div><div class="stat-label">Highest FP Score</div></div>
</div>
"""
    ]

    for name, fig in figs:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(22,33,62,0.8)",
            font_color="#eee",
        )
        chart_html = fig.to_html(full_html=False, include_plotlyjs=(name == "ranking"))
        html_parts.append(f'<div class="chart-container">{chart_html}</div>')

    html_parts.append("""
<p class="note">
  ⚠️ Scores are currently placeholder heuristics based on corpus size. Real scoring awaits Aitor's rules document.<br>
  Generated by the HP Character Faithfulness Project.
</p>
</body></html>""")

    return "\n".join(html_parts)


def main():
    scores, screen_time, book_mentions = load_data()
    print(f"Building dashboard with {len(scores)} characters...")

    html = build_dashboard(scores, screen_time, book_mentions)

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"Dashboard saved to {OUTPUT_FILE} ({size_mb:.1f} MB)")
    print(f"Open in browser: file://{os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
