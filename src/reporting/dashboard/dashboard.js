var DIM_LABELS = {
  personality_voice: 'Personality & Voice',
  narrative_role_agency: 'Narrative Role & Agency',
  motivations_internal_conflict: 'Motivations',
  character_arc: 'Character Arc',
  key_relationships: 'Key Relationships',
  complexity_nuance_lost_material: 'Complexity & Nuance'
};
var DIM_MAXES = {
  personality_voice: 25,
  narrative_role_agency: 20,
  motivations_internal_conflict: 15,
  character_arc: 15,
  key_relationships: 10,
  complexity_nuance_lost_material: 15
};

function updateChart(chartId, count) {
  var container = document.getElementById('container-' + chartId);
  var plotDiv = container.querySelector('.js-plotly-plot');
  var totalBars = plotDiv.data[0].x.length;
  var n = (count === 'all') ? totalBars : parseInt(count);
  Plotly.relayout(plotDiv, {'xaxis.range': [-0.5, n - 0.5]});
}

function getFilteredNames(minBook, minFilm) {
  return CHARACTER_DATA
    .filter(function(c) { return c.book_mentions >= minBook && c.screenplay_words >= minFilm; })
    .map(function(c) { return c.name; });
}

function applyFilterFromInput() {
  var minBook = parseInt(document.getElementById('book-value').value) || 0;
  var minFilm = parseInt(document.getElementById('film-value').value) || 0;
  doFilter(minBook, minFilm);
}

function applyFilter() {
  var bookSliderVal = parseInt(document.getElementById('book-slider').value);
  var filmSliderVal = parseInt(document.getElementById('film-slider').value);
  var maxBook = Math.max.apply(null, CHARACTER_DATA.map(function(c) { return c.book_mentions; }));
  var maxFilm = Math.max.apply(null, CHARACTER_DATA.map(function(c) { return c.screenplay_words; }));
  var minBook = bookSliderVal === 0 ? 0 : Math.max(25, Math.floor(Math.pow(10, bookSliderVal / 100 * Math.log10(maxBook)) / 25) * 25);
  var minFilm = filmSliderVal === 0 ? 0 : Math.max(25, Math.floor(Math.pow(10, filmSliderVal / 100 * Math.log10(maxFilm)) / 25) * 25);
  document.getElementById('book-value').value = minBook;
  document.getElementById('film-value').value = minFilm;
  doFilter(minBook, minFilm);
}

function doFilter(minBook, minFilm) {
  var validNames = new Set(getFilteredNames(minBook, minFilm));

  // Update bar charts
  ['top', 'bottom'].forEach(function(id) {
    var container = document.getElementById('container-' + id);
    if (!container) return;
    var plotDiv = container.querySelector('.js-plotly-plot');
    var isBottom = (id === 'bottom');

    var filtered = CHARACTER_DATA.filter(function(c) { return c.book_mentions >= minBook && c.screenplay_words >= minFilm; });
    if (isBottom) {
      filtered.sort(function(a, b) { return a.total - b.total; });
    } else {
      filtered.sort(function(a, b) { return b.total - a.total; });
    }

    var names = filtered.map(function(c) { return c.name; });
    var dims = ['personality_voice', 'narrative_role_agency', 'motivations_internal_conflict', 'character_arc', 'key_relationships', 'complexity_nuance_lost_material'];
    for (var i = 0; i < dims.length; i++) {
      var vals = filtered.map(function(c) { return c[dims[i]]; });
      Plotly.restyle(plotDiv, {y: [vals], x: [names]}, [i]);
    }

    var select = container.querySelector('.count-select');
    var count = select.value;
    var n = (count === 'all') ? names.length : Math.min(parseInt(count), names.length);
    Plotly.relayout(plotDiv, {'xaxis.range': [-0.5, n - 0.5]});
  });

  // Update scatter
  var scatterContainer = document.querySelector('#container-scatter');
  if (scatterContainer) {
    var plotDiv = scatterContainer.querySelector('.js-plotly-plot');
    var filtered = CHARACTER_DATA.filter(function(c) { return c.book_mentions >= minBook && c.screenplay_words >= minFilm && (c.book_mentions > 0 || c.screenplay_words > 0); });
    Plotly.restyle(plotDiv, {
      x: [filtered.map(function(c) { return c.book_mentions; })],
      y: [filtered.map(function(c) { return c.screenplay_words; })],
      'marker.color': [filtered.map(function(c) { return c.total; })],
      text: [filtered.map(function(c) { return c.name; })],
      hovertext: [filtered.map(function(c) { return c.name; })],
    }, [0]);
  }

  // Update character cards (only if no search active)
  var searchVal = document.getElementById('char-search').value.trim().toLowerCase();
  if (!searchVal) {
    document.querySelectorAll('.char-card').forEach(function(card) {
      var name = card.querySelector('.char-name').textContent;
      card.style.display = validNames.has(name) ? '' : 'none';
    });
  }

  document.getElementById('presence-count').textContent = '(' + validNames.size + ' characters)';
}

// --- Search ---
function applySearch() {
  var query = document.getElementById('char-search').value.trim().toLowerCase();
  document.querySelectorAll('.char-card').forEach(function(card) {
    var name = card.querySelector('.char-name').textContent.toLowerCase();
    if (query) {
      card.style.display = name.includes(query) ? '' : 'none';
    } else {
      applyFilter();
    }
  });
}

// --- Detail panel ---
function showCharacterPanel(charName) {
  var char = CHARACTER_DATA.find(function(c) { return c.name === charName; });
  if (!char) return;
  var just = JUSTIFICATIONS[charName] || {};
  var justDims = just.justification || {};
  var obs = just.key_observations || '';

  var html = '<h2 class="panel-title">' + charName + '</h2>';
  html += '<div class="panel-score">' + char.total + ' / 100</div>';

  var dims = ['personality_voice', 'narrative_role_agency', 'motivations_internal_conflict', 'character_arc', 'key_relationships', 'complexity_nuance_lost_material'];
  for (var i = 0; i < dims.length; i++) {
    var dim = dims[i];
    var dimJust = justDims[dim];
    var justText = '';
    if (typeof dimJust === 'object' && dimJust !== null) {
      justText = dimJust.penalty_logic || dimJust.difference || 'No justification available.';
    } else {
      justText = dimJust || 'No justification available.';
    }
    html += '<div class="panel-dim">';
    html += '<div class="panel-dim-header"><span class="panel-dim-name">' + DIM_LABELS[dim] + '</span><span class="panel-dim-score">' + (char[dim] || 0) + '/' + DIM_MAXES[dim] + '</span></div>';
    html += '<p class="panel-dim-text">' + justText + '</p>';
    html += '</div>';
  }
  if (obs) {
    html += '<div class="panel-obs"><strong>Key observations:</strong> ' + obs + '</div>';
  }

  document.getElementById('panel-content').innerHTML = html;
  document.getElementById('detail-panel').classList.add('active');
  // Update URL hash
  history.replaceState(null, '', '#character=' + encodeURIComponent(charName));
  // Briefly ignore outside clicks so the opening click doesn't immediately close
  panelJustOpened = true;
  setTimeout(function() { panelJustOpened = false; }, 100);
}

var panelJustOpened = false;

function closePanel() {
  document.getElementById('detail-panel').classList.remove('active');
  history.replaceState(null, '', window.location.pathname);
}

// --- Init ---
window.addEventListener('load', function() {
  var bookSlider = document.getElementById('book-slider');
  var filmSlider = document.getElementById('film-slider');
  var bookValue = document.getElementById('book-value');
  var filmValue = document.getElementById('film-value');

  bookSlider.addEventListener('input', function() {
    applyFilter();
  });
  filmSlider.addEventListener('input', function() {
    applyFilter();
  });

  // Manual number input
  document.getElementById('book-value').addEventListener('change', function() {
    applyFilterFromInput();
  });
  document.getElementById('film-value').addEventListener('change', function() {
    applyFilterFromInput();
  });

  // Apply initial filter (default min 10 screenplay words)
  applyFilter();

  // Search
  document.getElementById('char-search').addEventListener('input', applySearch);

  // Set initial chart range
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

  applyFilter();

  // Close panel on click outside
  document.addEventListener('click', function(e) {
    var panel = document.getElementById('detail-panel');
    if (panelJustOpened) return;
    if (panel.classList.contains('active') && !panel.contains(e.target)) {
      closePanel();
    }
  });
  document.getElementById('detail-panel').addEventListener('click', function(e) {
    e.stopPropagation();
  });

  // Click handlers on bar charts
  ['top', 'bottom'].forEach(function(id) {
    var container = document.getElementById('container-' + id);
    if (!container) return;
    var plotDiv = container.querySelector('.js-plotly-plot');
    plotDiv.on('plotly_click', function(data) {
      if (data.points && data.points.length > 0) {
        showCharacterPanel(data.points[0].x);
      }
    });
  });

  // Click handler on scatter
  var scatterContainer = document.getElementById('container-scatter');
  if (scatterContainer) {
    var plotDiv = scatterContainer.querySelector('.js-plotly-plot');
    plotDiv.on('plotly_click', function(data) {
      if (data.points && data.points.length > 0) {
        var name = data.points[0].hovertext || data.points[0].text;
        showCharacterPanel(name);
      }
    });
  }

  // Escape key closes panel
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closePanel();
  });

  // Open character from URL hash
  var hash = window.location.hash;
  if (hash.startsWith('#character=')) {
    var name = decodeURIComponent(hash.substring('#character='.length));
    showCharacterPanel(name);
  }
});
