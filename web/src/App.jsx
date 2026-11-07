import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import { LoadingBlock } from './components/ui'

const Landing = lazy(() => import('./landing/Landing'))
const pages = {
  overview: lazy(() => import('./pages/Overview')),
  projects: lazy(() => import('./pages/Projects')),
  playground: lazy(() => import('./pages/Playground')),
  prompts: lazy(() => import('./pages/Prompts')),
  datasets: lazy(() => import('./pages/Datasets')),
  experiments: lazy(() => import('./pages/Experiments')),
  evaluations: lazy(() => import('./pages/Evaluations')),
  deployments: lazy(() => import('./pages/Deployments')),
  monitoring: lazy(() => import('./pages/Monitoring')),
  settings: lazy(() => import('./pages/Settings')),
}

export default function App() {
  return (
    <Suspense fallback={<div className="page"><LoadingBlock /></div>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<pages.overview />} />
          {Object.entries(pages).filter(([k]) => k !== 'overview').map(([k, Page]) => (
            <Route key={k} path={k} element={<Page />} />
          ))}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
