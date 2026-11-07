import { useCallback, useEffect, useRef, useState } from 'react'

/** Runs an async function when `deps` change. Ignores answers that arrive after a newer request. */
export function useAsync(fn, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled })
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    if (!enabled) { setState({ data: null, error: null, loading: false }); return undefined }
    let live = true
    setState((s) => ({ ...s, loading: true, error: null }))
    Promise.resolve()
      .then(() => fnRef.current())
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}

/** Wraps a submit handler: tracks loading, and reports errors through `onError`. */
export function useAction(onError) {
  const [loading, setLoading] = useState(false)
  const run = useCallback(async (fn) => {
    setLoading(true)
    try { return await fn() } catch (e) { onError?.(e); return undefined } finally { setLoading(false) }
  }, [onError])
  return [run, loading]
}
