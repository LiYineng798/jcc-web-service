(() => {
  'use strict';
  const menus = [...document.querySelectorAll('.toolbox-menu')];
  document.addEventListener('click', (event) => {
    menus.forEach((menu) => { if (!menu.contains(event.target)) menu.open = false; });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    menus.filter((menu) => menu.open).forEach((menu) => {
      menu.open = false;
      menu.querySelector('summary').focus();
      event.preventDefault();
    });
  });
})();
