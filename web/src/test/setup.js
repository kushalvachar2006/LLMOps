import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

// jsdom lacks these browser APIs that the UI uses.
class Observer { observe() {} unobserve() {} disconnect() {} }
globalThis.IntersectionObserver = globalThis.IntersectionObserver || Observer
globalThis.ResizeObserver = globalThis.ResizeObserver || Observer
window.matchMedia = window.matchMedia || ((q) => ({
  matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
}))
window.scrollTo = () => {}

afterEach(() => { vi.unstubAllGlobals() })
