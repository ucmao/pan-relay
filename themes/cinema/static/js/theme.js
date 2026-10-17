(() => {
  const filters = [...document.querySelectorAll('.filter-chip[data-category]')];
  const cards = [...document.querySelectorAll('.poster-card')];
  const empty = document.getElementById('no-results');

  filters.forEach((filter) => {
    filter.addEventListener('click', () => {
      filters.forEach((item) => {
        const selected = item === filter;
        item.classList.toggle('selected', selected);
        item.setAttribute('aria-selected', String(selected));
      });

      const category = filter.dataset.category;
      let visible = 0;
      cards.forEach((card) => {
        const show = card.dataset.category === category;
        card.hidden = !show;
        if (show) visible += 1;
      });
      empty.hidden = visible !== 0;
    });
  });
})();
