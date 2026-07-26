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

// Hover previews need the season index, but most visitors never hover —
// defer the download until the first pointer/focus touches a champion link.
let detailDataPromise = null;

async function loadChampionPreviewData(configNode) {
  const response = await fetch(configNode.dataset.dataUrl);
  if (!response.ok) throw new Error('season index request failed');
  const data = await response.json();
  window.JccSeasonChampionUi?.configure({
    seasonId: configNode.dataset.seasonId,
    assetRoot: configNode.dataset.assetRoot,
    assetVersion: configNode.dataset.version || '',
    champions: data.champions || [],
    traits: data.traits || [],
  });
  window.JccSeasonChampionUi?.bindChampionLinks(document);
}

function initializeChampionDetail() {
  const configNode = document.querySelector('#seasonDetailConfig');
  if (!configNode) return;
  const prime = () => {
    if (!detailDataPromise) {
      detailDataPromise = loadChampionPreviewData(configNode).catch((error) => {
        console.error('champion previews failed to initialize', error);
      });
    }
  };
  document.querySelectorAll('[data-champion-id]').forEach((link) => {
    link.addEventListener('pointerenter', prime, {once: true});
    link.addEventListener('focus', prime, {once: true});
  });
}

initializeChampionDetail();
