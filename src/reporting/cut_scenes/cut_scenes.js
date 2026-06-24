(function() {
  var bookFilter = document.getElementById('book-filter');
  var sigFilter = document.getElementById('sig-filter');
  var searchInput = document.getElementById('search-input');
  var container = document.getElementById('scenes-container');
  var resultCount = document.getElementById('result-count');

  // Populate book dropdown
  Object.keys(BOOK_NAMES).forEach(function(key) {
    var opt = document.createElement('option');
    opt.value = key;
    opt.textContent = BOOK_NAMES[key];
    bookFilter.appendChild(opt);
  });

  function render() {
    var book = bookFilter.value;
    var sig = sigFilter.value;
    var query = searchInput.value.toLowerCase().trim();
    var html = '';
    var count = 0;

    var books = book === 'all' ? Object.keys(CUT_SCENES) : [book];
    books.forEach(function(bookKey) {
      var chapters = CUT_SCENES[bookKey];
      if (!chapters) return;
      var bookHtml = '';
      var bookHasScenes = false;

      chapters.forEach(function(ch) {
        var scenes = ch.cut_scenes.filter(function(s) {
          if (sig === 'high' && s.significance !== 'high') return false;
          if (sig === 'medium' && s.significance === 'low') return false;
          if (query) {
            var text = (s.title + ' ' + s.description + ' ' + (s.characters || []).join(' ')).toLowerCase();
            if (text.indexOf(query) === -1) return false;
          }
          return true;
        });
        if (scenes.length === 0) return;
        bookHasScenes = true;
        count += scenes.length;

        var scenesHtml = scenes.map(function(s) {
          return '<div class="scene-card ' + s.significance + '">' +
            '<div class="scene-title">' + esc(s.title) + '</div>' +
            '<div class="scene-desc">' + esc(s.description) + '</div>' +
            '<div class="scene-meta">' +
              '<span class="sig ' + s.significance + '">' + s.significance + '</span>' +
              '<span class="scene-chars">' + (s.characters || []).join(', ') + '</span>' +
            '</div></div>';
        }).join('');

        bookHtml += '<div class="chapter-group">' +
          '<div class="chapter-title" onclick="this.classList.toggle(\'expanded\');this.nextElementSibling.classList.toggle(\'visible\')">' +
          'Ch ' + ch.chapter_number + ': ' + esc(ch.chapter_title) + ' (' + scenes.length + ')</div>' +
          '<div class="scenes-list">' + scenesHtml + '</div></div>';
      });

      if (bookHasScenes) {
        html += '<div class="book-section"><h2>' + BOOK_NAMES[bookKey] + '</h2>' + bookHtml + '</div>';
      }
    });

    container.innerHTML = html || '<p style="text-align:center;color:#666">No scenes match your filters.</p>';
    resultCount.textContent = '(' + count + ' scenes)';
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  bookFilter.addEventListener('change', render);
  sigFilter.addEventListener('change', render);
  searchInput.addEventListener('input', render);

  // Check URL hash for book filter
  if (window.location.hash) {
    var h = window.location.hash.slice(1);
    if (CUT_SCENES[h]) bookFilter.value = h;
  }

  render();

  // Auto-expand if single book selected
  bookFilter.addEventListener('change', function() {
    if (bookFilter.value !== 'all') {
      var titles = container.querySelectorAll('.chapter-title');
      titles.forEach(function(t) { t.classList.add('expanded'); t.nextElementSibling.classList.add('visible'); });
    }
  });
})();
