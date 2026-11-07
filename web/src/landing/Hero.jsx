import { motion, useReducedMotion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowRight, Play } from 'lucide-react'

const WORDS = ['Ship', 'LLM', 'features', 'you', 'can']
const NODES = [
  { label: 'Prompt', x: 70, y: 70 }, { label: 'Dataset', x: 250, y: 40 }, { label: 'Experiment', x: 430, y: 90 },
  { label: 'Evaluate', x: 440, y: 220 }, { label: 'Deploy', x: 250, y: 270 }, { label: 'Monitor', x: 80, y: 230 },
]
const PATH = 'M70 70 C 150 10, 190 10, 250 40 S 380 130, 430 90 S 520 190, 440 220 S 330 300, 250 270 S 120 300, 80 230 S 40 120, 70 70'

function Pipeline({ reduce }) {
  return (
    <div className="lp-pipeline" aria-hidden="true">
      <svg viewBox="0 0 520 330" role="img">
        <defs>
          <linearGradient id="lp-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--accent)" /><stop offset="1" stopColor="var(--accent-2)" />
          </linearGradient>
          <filter id="lp-glow"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <motion.path d={PATH} fill="none" stroke="url(#lp-g)" strokeWidth="2" strokeDasharray="5 7" strokeLinecap="round"
          initial={{ pathLength: reduce ? 1 : 0, opacity: 0.2 }} animate={{ pathLength: 1, opacity: 0.8 }} transition={{ duration: 2.4, ease: 'easeInOut' }} />
        {NODES.map((n, i) => (
          <motion.g key={n.label} initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: reduce ? 0 : 0.5 + i * 0.22, type: 'spring', stiffness: 160, damping: 14 }}
            style={{ transformOrigin: `${n.x}px ${n.y}px` }}>
            <circle cx={n.x} cy={n.y} r="22" fill="var(--surface)" stroke="url(#lp-g)" strokeWidth="2" />
            <text x={n.x} y={n.y + 4} textAnchor="middle" className="lp-node-num">{i + 1}</text>
            <text x={n.x} y={n.y + (n.y > 150 ? 44 : -32)} textAnchor="middle" className="lp-node-label">{n.label}</text>
          </motion.g>
        ))}
        {!reduce && (
          <circle r="6" fill="var(--accent)" filter="url(#lp-glow)">
            <animateMotion dur="9s" repeatCount="indefinite" path={PATH} />
          </circle>
        )}
      </svg>
      <motion.div className="lp-float f1" animate={reduce ? {} : { y: [0, -8, 0] }} transition={{ duration: 5, repeat: Infinity }}>
        <span className="dot ok" /> v3 · exact_match <b>0.91</b>
      </motion.div>
      <motion.div className="lp-float f2" animate={reduce ? {} : { y: [0, 8, 0] }} transition={{ duration: 6, repeat: Infinity }}>
        p95 latency <b>842 ms</b>
      </motion.div>
      <motion.div className="lp-float f3" animate={reduce ? {} : { y: [0, -6, 0] }} transition={{ duration: 7, repeat: Infinity }}>
        production → <b>v3</b>
      </motion.div>
      <span className="lp-caption">Illustration with sample values</span>
    </div>
  )
}

export default function Hero() {
  const reduce = useReducedMotion()
  return (
    <header className="lp-hero">
      <div className="lp-orb o1" /><div className="lp-orb o2" /><div className="lp-orb o3" /><div className="lp-grid" />
      <div className="lp-container lp-hero-inner">
        <div className="lp-hero-copy">
          <motion.span className="lp-eyebrow" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <span className="dot" /> LLMOps for prompts, models and deployments
          </motion.span>
          <h1 className="lp-h1">
            {WORDS.map((w, i) => (
              <motion.span key={w + i} className="lp-word" initial={{ opacity: 0, y: reduce ? 0 : 24 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: reduce ? 0 : 0.1 + i * 0.07, duration: 0.5 }}>{w}&nbsp;</motion.span>
            ))}
            <motion.span className="lp-word lp-gradient-text" initial={{ opacity: 0, y: reduce ? 0 : 24 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reduce ? 0 : 0.5, duration: 0.5 }}>prove&nbsp;works.</motion.span>
          </h1>
          <motion.p className="lp-lead" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: reduce ? 0 : 0.7 }}>
            One workspace to write prompts, test them against your own data, score the results, publish a
            versioned API, and keep watching quality, speed and cost after launch.
          </motion.p>
          <motion.div className="lp-cta" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduce ? 0 : 0.85 }}>
            <Link className="btn btn-primary btn-lg" to="/app">Open the workspace <ArrowRight size={18} /></Link>
            <a className="btn btn-lg" href="#lifecycle"><Play size={16} /> See how it works</a>
          </motion.div>
          <motion.div className="lp-providers" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: reduce ? 0 : 1.1 }}>
            <span className="faint small">Works with</span>
            {['Google Gemini', 'OpenAI', 'Anthropic', 'Your own API key'].map((p) => <span key={p} className="lp-chip">{p}</span>)}
          </motion.div>
        </div>
        <Pipeline reduce={reduce} />
      </div>
    </header>
  )
}
