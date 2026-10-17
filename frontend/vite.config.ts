import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import { readFileSync, readdirSync } from 'node:fs';

export default defineConfig(({ mode }) => ({
  resolve: { alias: { '@': resolve(import.meta.dirname, '.') } },
  plugins: [{ name: 'dependency-notices', generateBundle() {
    const packages = JSON.parse(readFileSync(resolve(import.meta.dirname, 'package-lock.json'), 'utf8')).packages;
    const notices: string[] = [];
    const bundledModules = Array.from(this.getModuleIds()).map(id => id.replaceAll('\\', '/'));
    for (const [path, meta] of Object.entries(packages) as [string, { dev?: boolean }][]) {
      if (!path.startsWith('node_modules/') || meta.dev) continue;
      if (mode === 'avatar' && !bundledModules.some(id => id.includes(`/${path}/`))) continue;
      if (mode !== 'avatar' && ['@bible-strong/avatar-core', '@bible-strong/avatar-web', 'ajv', 'fast-deep-equal', 'fast-uri', 'json-schema-traverse', 'require-from-string'].some(name => path === `node_modules/${name}`)) continue;
      const directory = resolve(import.meta.dirname, path);
      const pkg = JSON.parse(readFileSync(resolve(directory, 'package.json'), 'utf8'));
      const license = readdirSync(directory).find(name => /^(license|licence|copying)(\.|$)/i.test(name));
      notices.push(`${pkg.name} ${pkg.version}\n${license ? readFileSync(resolve(directory, license), 'utf8') : pkg.license || ''}`);
    }
    if (mode === 'avatar') notices.unshift(readFileSync(resolve(import.meta.dirname, 'avatar-presets.NOTICE.txt'), 'utf8'));
    if (mode === 'home') notices.push(readFileSync(resolve(import.meta.dirname, 'components/ui/animated-icon.LICENSE.txt'), 'utf8'));
    this.emitFile({ type: 'asset', fileName: 'THIRD_PARTY_NOTICES.txt', source: notices.join('\n\n----\n\n') });
  } }],
  build: {
    outDir: resolve(import.meta.dirname, mode === 'avatar' ? '../static/avatar-lab' : mode === 'home' ? '../static/home-card-icons' : mode === 'account' ? '../static/account-profile' : mode === 'audit' ? '../static/admin/audit-logs' : '../static/admin/season-packages'),
    emptyOutDir: true,
    rollupOptions: { onwarn(warning, warn) { if (warning.code !== 'MODULE_LEVEL_DIRECTIVE') warn(warning); } },
    lib: { entry: resolve(import.meta.dirname, mode === 'avatar' ? 'avatar.ts' : mode === 'home' ? 'home-card-icons.tsx' : mode === 'account' ? 'account-profile.tsx' : mode === 'audit' ? 'audit-logs.tsx' : 'season-packages.tsx'), name: mode === 'avatar' ? 'JccAvatarLab' : mode === 'home' ? 'JccHomeCardIcons' : mode === 'account' ? 'JccAccountProfile' : mode === 'audit' ? 'JccAuditLogs' : 'JccSeasonPackages', formats: ['iife'], fileName: () => 'app.js', cssFileName: 'app' },
  },
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
}));
