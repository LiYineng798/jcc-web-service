const detailElements = {
  themeToggle: document.querySelector('#themeToggle'),
  themeIcon: document.querySelector('#themeIcon'),
  themeText: document.querySelector('#themeText'),
};

function setDetailTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, detailElements.themeToggle, detailElements.themeIcon, detailElements.themeText);
}

setDetailTheme(localStorage.getItem('theme') || 'light');
detailElements.themeToggle?.addEventListener('click', () => {
  setDetailTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

async function initializeChampionDetail() {
  try {
    const responses = await Promise.all([
      fetch('/static/s18-preview/champions.json'),
      fetch('/static/s18-preview/traits.json'),
    ]);
    if (responses.some((response) => !response.ok)) return;
    const [champions, traits] = await Promise.all(responses.map((response) => response.json()));
    window.JccS18ChampionUi?.configure(champions, traits);
    window.JccS18ChampionUi?.bindChampionLinks(document);
  } catch (error) {
    console.error('S18 champion previews failed to initialize', error);
  }
}

initializeChampionDetail();
