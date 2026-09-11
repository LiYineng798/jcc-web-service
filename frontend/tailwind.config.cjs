module.exports = {
  content: ['./*.tsx', './components/**/*.tsx'],
  important: '#seasonPackageRoot',
  corePlugins: { preflight: false },
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: { extend: { colors: {
    background: 'var(--admin-surface)', foreground: 'var(--text)', border: 'var(--admin-border)',
    muted: { DEFAULT: 'var(--admin-surface-muted)', foreground: 'var(--muted)' },
    ring: 'var(--text)', destructive: 'var(--admin-danger)',
  } } },
};
