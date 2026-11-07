import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { animate, AnimatePresence, motion, useInView, useReducedMotion, useScroll, useSpring } from 'framer-motion'
import {
  Activity, ArrowRight, BadgeCheck, BarChart3, ChevronRight, Code2, Database, DollarSign, FlaskConical, GitCompare,
  Lock, Menu, Moon, Rocket, ScrollText, ShieldCheck, Sparkles, Sun, X,
} from 'lucide-react'
import { useTheme } from '../context/providers'
import Hero from './Hero'
import Lifecycle from './Lifecycle'
import './landing.css'

function Reveal({ children, delay = 0, className }) {
  const reduce = useReducedMotion()
  return (
    <motion.div className={className} initial={{ opacity: 0, y: reduce ? 0 : 28 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-70px' }} transition={{ duration: 0.55, delay }}>{children}</motion.div>
  )
}

function CountUp({ to, suffix = '' }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  const [n, setN] = useState(reduce ? to : 0)
  useEffect(() => {
    if (!inView || reduce) return undefined
    const c = animate(0, to, { duration: 1.4, ease: 'easeOut', onUpdate: (v) => setN(Math.round(v)) })
    return () => c.stop()
  }, [inView, to, reduce])
  return <span ref={ref}>{n}{suffix}</span>
}

/** A card with a soft light that follows the pointer. */
function Spotlight({ icon: Icon, title, children }) {
  const ref = useRef(null)
  const move = (e) => {
    const r = ref.current.getBoundingClientRect()
    ref.current.style.setProperty('--mx', `${e.clientX - r.left}px`)
    ref.current.style.setProperty('--my', `${e.clientY - r.top}px`)
  }
  return (
    <motion.div ref={ref} className="lp-card" onMouseMove={move} whileHover={{ y: -4 }} transition={{ type: 'spring', stiffness: 300, damping: 22 }}>
      <span className="lp-card-icon"><Icon size={20} /></span><h3>{title}</h3><p className="muted">{children}</p>
    </motion.div>
  )
}

function Nav() {
  const { theme, toggle } = useTheme()
  const [open, setOpen] = useState(false)
  const { scrollYProgress } = useScroll()
  const progress = useSpring(scrollYProgress, { stiffness: 120, damping: 30 })
  const links = [['why', 'Why'], ['lifecycle', 'How it works'], ['features', 'Features'], ['developers', 'For developers'], ['principles', 'Principles'], ['faq', 'FAQ']]
  return (
    <nav className="lp-nav" aria-label="Main">
      <motion.div className="lp-progress-bar" style={{ scaleX: progress }} />
      <div className="lp-container lp-nav-inner">
        <Link to="/" className="brand"><span className="brand-mark"><svg width="16" height="16" viewBox="0 0 32 32" aria-hidden><path d="M8 22V10l8 6 8-6v12" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /></svg></span>LLMOps Platform</Link>
        <div className={`lp-links ${open ? 'open' : ''}`}>
          {links.map(([id, label]) => <a key={id} href={`#${id}`} onClick={() => setOpen(false)}>{label}</a>)}
        </div>
        <div className="row">
          <button className="btn btn-ghost btn-icon" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
          <Link className="btn btn-primary btn-sm" to="/app">Open workspace</Link>
          <button className="btn btn-ghost btn-icon lp-burger" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu" aria-expanded={open}>
            {open ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </div>
    </nav>
  )
}

const PROBLEMS = [
  { icon: ScrollText, problem: 'A small prompt edit changes behaviour, and nobody notices.',
    fix: 'Every save is an immutable version you can diff, compare and restore. Nothing is overwritten.' },
  { icon: FlaskConical, problem: '"It looked good in the demo" is not a test.',
    fix: 'Run a prompt across your own dataset and score every answer. AI-judge scores are labelled as opinions.' },
  { icon: Activity, problem: 'Errors, slowness and cost show up after launch.',
    fix: 'Traces, latency percentiles, token use, cost estimates and alerts keep you ahead of the invoice.' },
]
const FEATURES = [
  [Sparkles, 'Prompt Playground', 'Pick any provider and model, bring your own key, compare two setups side by side, rate answers.'],
  [GitCompare, 'Prompt Registry', 'Numbered immutable versions with diffs, restore, and the evaluation results of each.'],
  [Database, 'Datasets', 'CSV and JSONL uploads with schema checks, required fields, train/validation/eval splits and fingerprints.'],
  [FlaskConical, 'Experiments', 'Run a prompt version over a dataset version and keep every input, output, latency and token count.'],
  [BarChart3, 'Evaluations', 'Exact match, similarity, JSON validity, keywords, length and an optional AI judge, each with stated limits.'],
  [Rocket, 'Deployments', 'Validated versions, three environments, promotion, rollback, and an authenticated API.'],
  [Activity, 'Monitoring', 'Dashboards for errors, p50/p95/p99 latency, tokens and quality trends, with configurable alerts.'],
  [DollarSign, 'Cost estimates', 'You enter the prices. Costs are computed from recorded tokens and clearly marked as estimates.'],
]
const SNIPPETS = {
  curl: `curl -X POST https://your-host/v1/deployments/$DEPLOYMENT_ID/invoke \\
  -H "Authorization: Bearer $LLMOPS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"inputs": {"ticket": "My card was charged twice"}, "environment": "production"}'`,
  JavaScript: `const res = await fetch(\`\${HOST}/v1/deployments/\${ID}/invoke\`, {
  method: 'POST',
  headers: { Authorization: \`Bearer \${KEY}\`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ inputs: { ticket }, environment: 'production' }),
})
const { output, usage, request_id } = await res.json()`,
  Python: `import requests

r = requests.post(
    f"{HOST}/v1/deployments/{ID}/invoke",
    headers={"Authorization": f"Bearer {KEY}"},
    json={"inputs": {"ticket": ticket}, "environment": "production"},
    timeout=60,
)
print(r.json()["output"])`,
}
const FAQ = [
  ['Do I need an API key to try it?', 'Not for a first look: the mock provider works offline with no key. To call real models, paste your own Gemini, OpenAI or Anthropic key in the app (kept in memory), or have the server admin configure one.'],
  ['Is my prompt text stored?', 'By default only metadata is stored: timing, token counts, model and status. Prompt and response text is saved only if the server enables it, and it is masked for emails, phone numbers and key-like text first. You can also set automatic deletion.'],
  ['Which models are supported?', 'Google Gemini, OpenAI and Anthropic, plus any custom model ID you type. The built-in model list is curated and may lag new releases, which is why custom IDs are allowed.'],
  ['Can I run it on my own machine?', 'Yes. Docker Compose starts the web app, the API and a local MongoDB. You can also point it at MongoDB Atlas.'],
  ['Does a good score mean the answer is true?', 'No. Metrics measure agreement with a reference, format or simple rules. A model-judge score is an opinion. Keep human review for anything important.'],
]

function Faq() {
  const [open, setOpen] = useState(0)
  return (
    <div className="lp-faq">
      {FAQ.map(([q, a], i) => (
        <div key={q} className={`lp-faq-item ${open === i ? 'open' : ''}`}>
          <button aria-expanded={open === i} onClick={() => setOpen(open === i ? -1 : i)}>{q}<ChevronRight size={18} /></button>
          <AnimatePresence initial={false}>
            {open === i && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
              style={{ overflow: 'hidden' }}><p className="muted">{a}</p></motion.div>}
          </AnimatePresence>
        </div>
      ))}
    </div>
  )
}

function Developers() {
  const [tab, setTab] = useState('curl')
  const code = SNIPPETS[tab]
  const reduce = useReducedMotion()
  const [n, setN] = useState(code.length)
  useEffect(() => {
    if (reduce) { setN(code.length); return undefined }
    setN(0)
    const t = setInterval(() => setN((v) => (v >= code.length ? v : v + 3)), 14)
    return () => clearInterval(t)
  }, [code, reduce])
  return (
    <div className="lp-dev">
      <Reveal>
        <div className="lp-terminal">
          <div className="lp-term-tabs" role="tablist">
            {Object.keys(SNIPPETS).map((k) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{k}</button>)}
          </div>
          <pre aria-label={`${tab} example`}><code>{code.slice(0, n)}{n < code.length && <span className="lp-caret" />}</code></pre>
        </div>
      </Reveal>
      <Reveal delay={0.1} className="lp-dev-points">
        <h3>A real API, not a demo</h3>
        {[['Project-scoped API keys', 'Shown once, stored only as a hash, revocable instantly.'],
          ['Three environments', 'Promote or roll back between development, staging and production.'],
          ['Limits built in', 'Request size caps, per-key rate limits and strict input validation.'],
          ['Safe errors', 'Callers get a generic message and a request ID, never provider internals.']].map(([t, d]) => (
          <div key={t} className="lp-point"><BadgeCheck size={18} /><div><b>{t}</b><p className="muted small">{d}</p></div></div>
        ))}
      </Reveal>
    </div>
  )
}

export default function Landing() {
  return (
    <div className="lp">
      <Nav />
      <Hero />
      <section className="lp-section" id="why">
        <div className="lp-container">
          <Reveal><span className="lp-kicker">Why this exists</span>
            <h2 className="lp-h2">LLM apps fail <span className="lp-gradient-text">quietly</span>.</h2>
            <p className="lp-sub muted">Models are probabilistic and prompts are code that nobody reviews. Without versions, tests and monitoring, teams find out about regressions from their users. This project exists to make building with LLMs as evidence-driven as the rest of software.</p></Reveal>
          <div className="grid grid-3" style={{ marginTop: 36 }}>
            {PROBLEMS.map((p, i) => (
              <Reveal key={p.problem} delay={i * 0.1}>
                <div className="lp-problem">
                  <p className="lp-problem-q"><p.icon size={20} />{p.problem}</p>
                  <div className="lp-arrow"><ArrowRight size={16} /></div>
                  <p className="lp-problem-a">{p.fix}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>
      <section className="lp-section alt" id="lifecycle">
        <div className="lp-container">
          <Reveal><span className="lp-kicker">How it works</span>
            <h2 className="lp-h2">One loop, from idea to production and back.</h2>
            <p className="lp-sub muted">Pick a step to explore it. Each stage feeds the next, and monitoring tells you what to improve.</p></Reveal>
          <Reveal delay={0.1}><Lifecycle /></Reveal>
        </div>
      </section>
      <section className="lp-stats">
        <div className="lp-container grid grid-4">
          {[[3, '', 'model providers'], [6, '', 'built-in evaluators'], [3, '', 'deployment environments'], [100, '%', 'of versions immutable']].map(([n, s, l]) => (
            <Reveal key={l}><div className="lp-stat"><b><CountUp to={n} suffix={s} /></b><span className="muted">{l}</span></div></Reveal>
          ))}
        </div>
      </section>
      <section className="lp-section" id="features">
        <div className="lp-container">
          <Reveal><span className="lp-kicker">Features</span><h2 className="lp-h2">Everything in one workspace.</h2>
            <p className="lp-sub muted">Simple on the surface, with the detail available when you need it.</p></Reveal>
          <div className="grid grid-4 lp-features">
            {FEATURES.map(([icon, t, d], i) => <Reveal key={t} delay={(i % 4) * 0.07}><Spotlight icon={icon} title={t}>{d}</Spotlight></Reveal>)}
          </div>
        </div>
      </section>
      <section className="lp-section alt" id="developers">
        <div className="lp-container">
          <Reveal><span className="lp-kicker">For developers</span><h2 className="lp-h2">Call your best prompt like any other API.</h2>
            <p className="lp-sub muted">Publish a validated version, hand out a key, and your app gets the output, token usage and a request ID.</p></Reveal>
          <Developers />
        </div>
      </section>
      <section className="lp-section" id="principles">
        <div className="lp-container">
          <Reveal><span className="lp-kicker">Principles</span><h2 className="lp-h2">Built to be honest with you.</h2></Reveal>
          <div className="grid grid-4" style={{ marginTop: 32 }}>
            {[[Lock, 'Your keys stay yours', 'Model keys you paste are used for your requests and never saved or shown again. Server keys never reach the browser.'],
              [ScrollText, 'History is never rewritten', 'Prompt, dataset and deployment versions are append-only, so every result can be traced to what produced it.'],
              [ShieldCheck, 'Metrics with their limits', 'Each evaluator states what it cannot tell you. No score is presented as proof of truth.'],
              [Code2, 'Private by default', 'Prompt text is not stored unless enabled, stored text is masked, and retention can be automatic.']].map(([I, t, d], i) => (
              <Reveal key={t} delay={i * 0.08}><div className="lp-principle"><I size={22} /><h3>{t}</h3><p className="muted">{d}</p></div></Reveal>
            ))}
          </div>
        </div>
      </section>
      <section className="lp-section alt">
        <div className="lp-container">
          <Reveal><span className="lp-kicker">Who it is for</span><h2 className="lp-h2">Anyone who ships or studies LLM behaviour.</h2></Reveal>
          <Reveal delay={0.1}>
            <div className="lp-audience">
              {['Prompt engineers', 'ML and platform engineers', 'Product teams adding AI features', 'Researchers comparing models', 'Students learning LLMOps'].map((a) => <span key={a} className="lp-chip big">{a}</span>)}
            </div>
          </Reveal>
        </div>
      </section>
      <section className="lp-section" id="faq">
        <div className="lp-container lp-narrow">
          <Reveal><span className="lp-kicker">FAQ</span><h2 className="lp-h2">Good questions.</h2></Reveal>
          <Reveal delay={0.1}><Faq /></Reveal>
        </div>
      </section>
      <section className="lp-cta-band">
        <div className="lp-container">
          <Reveal><h2 className="lp-h2">Ready to see your prompts the way your users do?</h2>
            <p className="lp-sub muted">Open the workspace, create a project and run your first prompt in a minute. The mock provider needs no key.</p>
            <div className="lp-cta" style={{ justifyContent: 'center', marginTop: 24 }}>
              <Link className="btn btn-primary btn-lg" to="/app">Open the workspace <ArrowRight size={18} /></Link>
              <Link className="btn btn-lg" to="/app/playground">Try the Playground</Link>
            </div></Reveal>
        </div>
      </section>
      <footer className="lp-footer">
        <div className="lp-container row-between">
          <span className="faint small">LLMOps Platform · Illustrations on this page use sample data.</span>
          <div className="row small"><Link to="/app">Workspace</Link><a href="#why">Why</a><a href="#features">Features</a><a href="#faq">FAQ</a></div>
        </div>
      </footer>
    </div>
  )
}
