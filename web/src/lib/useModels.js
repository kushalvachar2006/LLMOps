import { api } from './api'
import { useAsync } from './hooks'

let cached = null
/** The model catalog changes rarely, so it is fetched once per page load. */
export function loadModels() {
  if (!cached) cached = api.models().catch((e) => { cached = null; throw e })
  return cached
}
export const useModels = () => useAsync(() => loadModels(), [])
export function modelInfo(catalog, providerId, modelId) {
  return catalog?.providers.find((p) => p.id === providerId)?.models.find((m) => m.id === modelId) || null
}
