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
  const configNode = document.querySelector('#seasonDetailConfig');
  if (!configNode) return;
  try {
    const response = await fetch(configNode.dataset.dataUrl);
    if (!response.ok) return;
    const data = await response.json();
    window.JccSeasonChampionUi?.configure({
      seasonId: configNode.dataset.seasonId,
      assetRoot: configNode.dataset.assetRoot,
      champions: data.champions || [],
      traits: data.traits || [],
    });
    window.JccSeasonChampionUi?.bindChampionLinks(document);
  } catch (error) {
    console.error('champion previews failed to initialize', error);
  }
}

initializeChampionDetail();
