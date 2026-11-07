import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion'
import { Activity, BarChart3, FlaskConical, GitCompare, Rocket, Sparkles } from 'lucide-react'

const STEPS = [
  { id: 'build', icon: Sparkles, title: 'Build', text: 'Write a prompt, pick any model and run it. Compare two setups side by side and rate the answers.' },
  { id: 'version', icon: GitCompare, title: 'Version', text: 'Every save becomes an immutable version. Diff any two, restore an old one as a new version.' },
  { id: 'test', icon: FlaskConical, title: 'Test', text: 'Upload a CSV or JSONL dataset and run a prompt version across every row, with train and eval splits.' },
  { id: 'evaluate', icon: BarChart3, title: 'Evaluate', text: 'Score outputs with objective metrics. Model-judge scores are kept separate and labelled as opinions.' },
  { id: 'deploy', icon: Rocket, title: 'Deploy', text: 'Publish a validated version to development, staging or production behind a project-scoped API key.' },
  { id: 'observe', icon: Activity, title: 'Observe', text: 'Track errors, latency percentiles, tokens, estimated cost and quality, with alerts you configure.' },
]
const rise = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } }

function BuildPanel() {
  const full = 'Summarise this support ticket in one sentence: {{ticket}}'
  const [n, setN] = useState(0)
  useEffect(() => { const t = setInterval(() => setN((v) => (v < full.length ? v + 1 : v)), 32); return () => clearInterval(t) }, [full.length])
  return (
    <div className="lp-panel">
      <div className="lp-row"><span className="lp-chip">OpenAI · gpt-4.1-mini</span><span className="lp-chip alt">Gemini · 2.5 Flash</span><span className="lp-chip alt">Anthropic · Haiku</span></div>
      <div className="lp-mock-input mono">{full.slice(0, n)}<span className="lp-caret" /></div>
      <motion.div {...rise} transition={{ delay: 1.2 }} className="lp-mock-output">
        <b>Customer reports a duplicate charge and wants a refund.</b>
        <span className="faint small">412 ms · 38 tokens · ★★★★☆</span>
      </motion.div>
    </div>
  )
}
function VersionPanel() {
  return (
    <div className="lp-panel">
      <div className="lp-timeline">
        {['v1', 'v2', 'v3'].map((v, i) => (
          <motion.div key={v} className={`lp-vnode ${i === 2 ? 'on' : ''}`} {...rise} transition={{ delay: i * 0.25 }}>{v}</motion.div>
        ))}
      </div>
      <div className="lp-diff mono">
        <motion.div {...rise} transition={{ delay: 0.5 }} className="diff-del">- Summarise the ticket.</motion.div>
        <motion.div {...rise} transition={{ delay: 0.8 }} className="diff-add">+ Summarise the ticket in one sentence.</motion.div>
        <motion.div {...rise} transition={{ delay: 1.1 }} className="diff-add">+ Do not include personal data.</motion.div>
      </div>
      <motion.span {...rise} transition={{ delay: 1.4 }} className="lp-chip">History is never rewritten</motion.span>
    </div>
  )
}
function TestPanel() {
  const rows = [['How do I reset my password?', 'train'], ['Where is my invoice?', 'eval'], ['Cancel my plan', 'eval'], ['Update my address', 'validation']]
  return (
    <div className="lp-panel">
      {rows.map(([q, s], i) => (
        <motion.div key={q} className="lp-datarow" {...rise} transition={{ delay: i * 0.22 }}>
          <span>{q}</span><span className={`lp-split ${s}`}>{s}</span>
        </motion.div>
      ))}
      <div className="lp-progress"><motion.div initial={{ width: 0 }} animate={{ width: '100%' }} transition={{ duration: 2.2, delay: 0.6 }} /></div>
      <span className="faint small">Running prompt v3 on every row…</span>
    </div>
  )
}
function EvaluatePanel() {
  const bars = [['exact_match', 82, 'objective'], ['json_valid', 96, 'objective'], ['llm_judge', 68, 'model judgment']]
  return (
    <div className="lp-panel">
      {bars.map(([name, pct, kind], i) => (
        <div key={name} className="lp-bar-row">
          <div className="row-between"><span className="mono small">{name}</span><span className={`badge ${kind === 'objective' ? 'success' : 'warning'}`}>{kind}</span></div>
          <div className="lp-bar"><motion.span initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 1, delay: 0.2 + i * 0.25 }} /></div>
        </div>
      ))}
      <span className="faint small">A judge score is an opinion, not a measurement.</span>
    </div>
  )
}
function DeployPanel() {
  const lanes = ['development', 'staging', 'production']
  return (
    <div className="lp-panel">
      {lanes.map((l, i) => (
        <div key={l} className="lp-lane"><span className="small muted">{l}</span>
          <motion.span className="lp-vchip" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.4 }}>v{i + 1}</motion.span></div>
      ))}
      <motion.pre {...rise} transition={{ delay: 1.5 }} className="lp-curl mono">{`POST /v1/deployments/{id}/invoke
Authorization: Bearer llmops_••••••••`}</motion.pre>
    </div>
  )
}
function ObservePanel() {
  return (
    <div className="lp-panel">
      <div className="row"><span className="lp-kpi"><b>1.2%</b> error rate</span><span className="lp-kpi"><b>842 ms</b> p95</span><span className="lp-kpi"><b>$0.31</b> est. cost</span></div>
      <svg viewBox="0 0 300 90" className="lp-spark" aria-hidden="true">
        <motion.path d="M0 70 C 30 60, 50 30, 80 40 S 130 75, 160 50 S 220 10, 300 25" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.6 }} />
      </svg>
      <motion.div {...rise} transition={{ delay: 1.5 }} className="notice warning"><span>Quality dropped between v2 and v3. Review before promoting.</span></motion.div>
    </div>
  )
}
const PANELS = { build: BuildPanel, version: VersionPanel, test: TestPanel, evaluate: EvaluatePanel, deploy: DeployPanel, observe: ObservePanel }

export default function Lifecycle() {
  const reduce = useReducedMotion()
  const ref = useRef(null)
  const visible = useInView(ref, { amount: 0.4 })
  const [active, setActive] = useState(0)
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    if (reduce || paused || !visible) return undefined
    const t = setTimeout(() => setActive((a) => (a + 1) % STEPS.length), 6500)
    return () => clearTimeout(t)
  }, [active, paused, visible, reduce])
  const Panel = PANELS[STEPS[active].id]
  return (
    <div className="lp-lifecycle" ref={ref} onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="lp-steps" role="tablist" aria-label="Product lifecycle">
        {STEPS.map((s, i) => (
          <button key={s.id} role="tab" aria-selected={i === active} className={`lp-step ${i === active ? 'active' : ''}`}
            onClick={() => { setActive(i); setPaused(true) }} onFocus={() => setPaused(true)}>
            <span className="lp-step-icon"><s.icon size={18} /></span>
            <span><b>{i + 1}. {s.title}</b>{i === active && <motion.span className="lp-step-text" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>{s.text}</motion.span>}</span>
            {i === active && !reduce && !paused && visible && <motion.i className="lp-step-timer" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 6.5, ease: 'linear' }} />}
          </button>
        ))}
      </div>
      <div className="lp-stage" role="tabpanel">
        <AnimatePresence mode="wait">
          <motion.div key={STEPS[active].id} initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}><Panel /></motion.div>
        </AnimatePresence>
        <span className="lp-caption">Illustrative preview</span>
      </div>
    </div>
  )
}
