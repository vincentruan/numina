import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import prettierConfig from 'eslint-config-prettier'
import globals from 'globals'

export default tseslint.config(
  // Ignore generated/build output
  {
    ignores: ['**/node_modules/**', '**/dist/**', '**/coverage/**', '**/*.d.ts'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  prettierConfig,
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        extraFileExtensions: ['.vue'],
      },
      globals: globals.browser,
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // Prevent cross-app imports from adult frontend
      'no-restricted-imports': ['error', {
        patterns: [{
          group: ['**/apps/main/src/**'],
          message: 'Cross-app imports are not allowed. Use @numina/* shared packages instead.',
        }],
      }],
    },
  },
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // Prevent cross-app imports from adult frontend
      'no-restricted-imports': ['error', {
        patterns: [{
          group: ['**/apps/main/src/**'],
          message: 'Cross-app imports are not allowed. Use @numina/* shared packages instead.',
        }],
      }],
    },
  },
)
