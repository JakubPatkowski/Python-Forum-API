// Flat ESLint config (ESLint 9) for the React 18 + Vite SPA.
//
// Rationale:
//   * The app uses the automatic JSX runtime (Vite's @vitejs/plugin-react),
//     so `React` does not need to be in scope — `react-in-jsx-scope` is off.
//   * `react-hooks` enforces the Rules of Hooks (real bug class).
//   * `react-refresh` keeps components Fast-Refresh friendly during dev.
//   * Unused vars are an error, but an underscore prefix opts out (common for
//     intentionally-ignored args / catch bindings).
import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  // Never lint build output or dependencies.
  { ignores: ['dist/**', 'node_modules/**', 'public/**'] },

  js.configs.recommended,

  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,

      // Automatic JSX runtime — no need to import React in every file.
      'react/react-in-jsx-scope': 'off',
      'react/jsx-uses-react': 'off',
      // PropTypes are not used in this project (no TypeScript yet either).
      'react/prop-types': 'off',

      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

      'no-unused-vars': ['error', { args: 'none', varsIgnorePattern: '^_', ignoreRestSiblings: true }],
    },
  },

  // Node-context config files.
  {
    files: ['*.config.js', 'vite.config.js'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
];
