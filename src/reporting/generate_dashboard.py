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

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
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
    """Load per-character justifications from individual score files."""
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


def fig_ranking_bar(scores, title="Top", ascending=False):
    """Stacked bar chart of characters by FP dimension. Shows all, JS controls visibility."""
    if ascending:
        subset = sorted(scores, key=lambda s: s["overall"]["total"])
    else:
        subset = scores[:]

    names = [s["character"] for s in subset]
    fig = go.Figure()
    for dim in DIMENSIONS:
        fig.add_trace(
            go.Bar(
                name=DIM_LABELS[dim],
                x=names,
                y=[s["overall"][dim] for s in subset],
                marker_color=DIM_COLORS[dim],
                hovertemplate="%{x}<br>" + DIM_LABELS[dim] + ": %{y:.1f}<extra></extra>",
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
    """Scatter: book mentions vs screenplay words, coloured by FP score."""
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


def build_character_details_html(scores, justifications):
    """Build expandable character detail sections."""
    parts = []
    for s in scores:
        name = s["character"]
        total = s["overall"]["total"]
        j = justifications.get(name, {})
        just = j.get("justification", {})
        obs = j.get("key_observations", "")

        safe_id = re.sub(r"[^a-z0-9]", "_", name.lower())

        dim_html = ""
        for dim in DIMENSIONS:
            score = s["overall"][dim]
            text = just.get(dim, "No justification available.")
            dim_html += f"""
            <div class="dim-row">
              <span class="dim-name">{DIM_LABELS[dim]}</span>
              <span class="dim-score">{score:.0f}/25</span>
              <p class="dim-text">{text}</p>
            </div>"""

        obs_html = f'<div class="obs"><strong>Key observations:</strong> {obs}</div>' if obs else ""

        parts.append(f"""
        <div class="char-card" onclick="this.classList.toggle('expanded')">
          <div class="char-header">
            <span class="char-name">{name}</span>
            <span class="char-score">{total:.0f}</span>
            <span class="expand-hint">click to expand</span>
          </div>
          <div class="char-details">
            {dim_html}
            {obs_html}
          </div>
        </div>""")

    return "\n".join(parts)


def build_dashboard(scores, screen_time, book_mentions):
    """Assemble all charts into a single HTML dashboard."""
    justifications = load_justifications()

    fig_top = fig_ranking_bar(scores, title="Top")
    fig_bottom = fig_ranking_bar(scores, title="Lowest", ascending=True)
    fig_presence = fig_scatter_presence(scores)

    figs = [
        ("top", fig_top),
        ("bottom", fig_bottom),
        ("scatter", fig_presence),
    ]

    char_details = build_character_details_html(scores, justifications)

    html_parts = [
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Harry Potter Character Faithfulness Dashboard</title>
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }
  h1 { text-align: center; color: #f0c75e; font-size: 2em; margin-bottom: 5px; }
  h2 { color: #f0c75e; margin-top: 40px; }
  .subtitle { text-align: center; color: #aaa; margin-bottom: 30px; }
  .chart-container { background: #16213e; border-radius: 12px; padding: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); position: relative; }
  .stats { display: flex; justify-content: center; gap: 40px; margin-bottom: 30px; flex-wrap: wrap; }
  .stat { text-align: center; }
  .stat-value { font-size: 2.5em; font-weight: bold; color: #f0c75e; }
  .stat-label { color: #aaa; font-size: 0.9em; }
  .count-select { position: absolute; top: 15px; right: 15px; z-index: 10; background: #1a2a4e; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 4px 8px; font-size: 0.85em; }

  /* Character cards */
  .char-card { background: #16213e; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; cursor: pointer; transition: background 0.2s; }
  .char-card:hover { background: #1a2a4e; }
  .char-header { display: flex; align-items: center; gap: 12px; }
  .char-name { font-weight: bold; flex: 1; }
  .char-score { font-size: 1.3em; font-weight: bold; color: #f0c75e; }
  .expand-hint { color: #666; font-size: 0.8em; }
  .char-details { display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #333; }
  .char-card.expanded .char-details { display: block; }
  .char-card.expanded .expand-hint { display: none; }
  .dim-row { margin-bottom: 10px; }
  .dim-name { font-weight: bold; color: #aaa; }
  .dim-score { color: #f0c75e; margin-left: 8px; }
  .dim-text { margin: 4px 0 0 0; color: #ccc; font-size: 0.9em; line-height: 1.4; }
  .obs { margin-top: 12px; padding: 10px; background: #0f1a30; border-radius: 6px; font-size: 0.9em; color: #bbb; }

  .note { text-align: center; color: #888; font-size: 0.85em; margin-top: 30px; }
</style>
</head>
<body>
<h1>Harry Potter Character Faithfulness Dashboard</h1>
<p class="subtitle">FP = Personality + Narrative Role + Motivations + Character Arc (each /25, total /100)</p>

<div class="stats">
  <div class="stat"><div class="stat-value">"""
        + str(len(scores))
        + """</div><div class="stat-label">Characters Scored</div></div>
  <div class="stat"><div class="stat-value">"""
        + f"{scores[0]['overall']['total']:.0f}"
        + """</div><div class="stat-label">Highest FP</div></div>
  <div class="stat"><div class="stat-value">"""
        + f"{scores[-1]['overall']['total']:.0f}"
        + """</div><div class="stat-label">Lowest FP</div></div>
  <div class="stat"><div class="stat-value">"""
        + f"{sum(s['overall']['total'] for s in scores) / len(scores):.0f}"
        + """</div><div class="stat-label">Average FP</div></div>
</div>
"""
    ]

    for name, fig in figs:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(22,33,62,0.8)",
            font_color="#eee",
        )
        chart_html = fig.to_html(full_html=False, include_plotlyjs=(name == "top"))
        if name in ("top", "bottom"):
            dropdown = f'''<select class="count-select" onchange="updateChart('{name}', this.value)">
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="20" selected>20</option>
              <option value="50">50</option>
              <option value="all">All</option>
            </select>'''
            html_parts.append(f'<div class="chart-container" id="container-{name}">{dropdown}{chart_html}</div>')
        else:
            html_parts.append(f'<div class="chart-container">{chart_html}</div>')

    # JS to control bar chart x-axis range
    html_parts.append("""
<script>
function updateChart(chartId, count) {
  var container = document.getElementById('container-' + chartId);
  var plotDiv = container.querySelector('.js-plotly-plot');
  var totalBars = plotDiv.data[0].x.length;
  var n = (count === 'all') ? totalBars : parseInt(count);
  Plotly.relayout(plotDiv, {'xaxis.range': [-0.5, n - 0.5]});
}
// Set initial range after plots render
window.addEventListener('load', function() {
  var isMobile = window.innerWidth < 768;
  var defaultN = isMobile ? 5 : 20;
  ['top', 'bottom'].forEach(function(id) {
    var container = document.getElementById('container-' + id);
    if (!container) return;
    var plotDiv = container.querySelector('.js-plotly-plot');
    var select = container.querySelector('.count-select');
    select.value = String(defaultN);
    Plotly.relayout(plotDiv, {'xaxis.range': [-0.5, defaultN - 0.5]});
  });
});
</script>
""")

    html_parts.append(f"""
<h2>All Characters - Click for Scoring Details</h2>
{char_details}

<p class="note">
  Scores generated via comparative LLM analysis (book corpus vs film corpus).<br>
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
