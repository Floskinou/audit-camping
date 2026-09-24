// Audit Camping — interactions
(function () {
  'use strict';

  const filterInput = document.getElementById('filter-camping');
  const filterRegion = document.getElementById('filter-region');
  const filterScore = document.getElementById('filter-score');
  const cards = Array.from(document.querySelectorAll('.camping-card'));
  const counter = document.getElementById('results-count');
  const emptyState = document.getElementById('empty-state');
  const catalog = document.getElementById('campings');

  function normalizeQuery(value) {
    return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  function matchesScore(card, selected) {
    if (selected === 'all') return true;
    if (selected === 'critical') return card.dataset.critical === 'true';
    const score = card.dataset.score;
    if (selected === 'na') return score === 'na';
    if (score === 'na') return false;
    const value = Number(score);
    if (selected === 'low') return value <= 1;
    if (selected === 'mid') return value >= 2 && value <= 3;
    if (selected === 'high') return value >= 4;
    return true;
  }

  function filterCards() {
    const query = normalizeQuery(filterInput ? filterInput.value.trim() : '');
    const region = filterRegion ? filterRegion.value : 'all';
    const selectedScore = filterScore ? filterScore.value : 'all';
    let visible = 0;

    cards.forEach((card) => {
      const haystack = (card.dataset.name || '').toLowerCase();
      const cardRegion = card.dataset.region || '';
      const matchesQuery = !query || haystack.includes(query);
      const matchesRegion = region === 'all' || cardRegion === region;
      const show = matchesQuery && matchesRegion && matchesScore(card, selectedScore);
      card.hidden = !show;
      if (show) visible += 1;
    });

    if (counter) counter.textContent = `${visible} camping${visible > 1 ? 's' : ''}`;
    if (emptyState) emptyState.hidden = visible !== 0;
  }

  if (filterInput) filterInput.addEventListener('input', filterCards);
  if (filterRegion) filterRegion.addEventListener('change', filterCards);
  if (filterScore) filterScore.addEventListener('change', filterCards);
  filterCards();

  if (location.hash === '#campings' && catalog) catalog.open = true;

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener('click', (event) => {
      const target = document.querySelector(link.getAttribute('href'));
      if (target) {
        event.preventDefault();
        if (target === catalog) {
          catalog.open = true;
          if (link.hasAttribute('data-filter-alerts') && filterScore) {
            filterScore.value = 'critical';
            filterCards();
          }
        }
        history.pushState(null, '', link.getAttribute('href'));
        const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
        target.scrollIntoView({ behavior, block: 'start' });
        if (target === catalog && filterInput) filterInput.focus({ preventScroll: true });
      }
    });
  });
})();
