import reactHooks from 'eslint-plugin-react-hooks'

const browser = Object.fromEntries(
  ['window', 'document', 'navigator', 'localStorage', 'sessionStorage', 'fetch', 'console', 'setTimeout',
    'clearTimeout', 'setInterval', 'clearInterval', 'FileReader', 'URL', 'Headers', 'AbortController',
    'IntersectionObserver', 'requestAnimationFrame', 'cancelAnimationFrame', 'CustomEvent', 'Event',
    'matchMedia', 'URLSearchParams', 'Intl', 'HTMLElement', 'Blob', 'FormData'].map((n) => [n, 'readonly']),
)

export default [
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: browser,
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
]
