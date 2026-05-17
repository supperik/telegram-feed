// ESLint 9 flat config (migrated from .eslintrc.cjs because ESLint 9 dropped
// legacy config support). Preserves the same lint surface the plan specified.
import js from '@eslint/js';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default [
  { ignores: ['dist/**', 'src/routeTree.gen.ts', 'node_modules/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node, ...globals.es2022 },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // `no-unused-vars` is superseded by the TS-aware rule above.
      'no-unused-vars': 'off',
      // TypeScript already validates identifiers (including type-only globals
      // like `RequestInit`) at compile time. The eslint `no-undef` rule does
      // not know about TS type globals and produces false positives.
      'no-undef': 'off',
    },
  },
];
