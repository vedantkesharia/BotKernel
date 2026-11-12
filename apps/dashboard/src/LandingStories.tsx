import { useState, type PointerEvent } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { Activity, ArrowDownRight, ArrowRight, Bot, Check, Database, GitBranch, Radio, Search, Shield, Workflow } from "lucide-react";

const journey = [
  { title: "Observe", owner: "Agent runtime", detail: "Agents read bounded telemetry and their own objective context.", icon: Activity, evidence: "Telemetry snapshot" },
  { title: "Propose", owner: "LangGraph workflow", detail: "A provider returns a validated decision or a no-op.", icon: Bot, evidence: "Typed proposal" },
  { title: "Admit", owner: "FastAPI + PostgreSQL", detail: "The gateway checks policy, versions, quota and active holds.", icon: Shield, evidence: "Reservation + outbox" },
  { title: "Execute", owner: "Kafka + worker", detail: "At-least-once delivery is reconciled through simulator receipts.", icon: Workflow, evidence: "Committed receipt" },
  { title: "Evaluate", owner: "Stability controller", detail: "The controller evaluates committed relationships and recovery evidence.", icon: Radio, evidence: "Incident transitions" },
  { title: "Investigate", owner: "Read-only workflow", detail: "Reports cite persisted actions and effects; recommendations remain advisory.", icon: Search, evidence: "Validated references" },
];

function updateSpotlight(event: PointerEvent<HTMLElement>) {
  const bounds = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty("--spot-x", `${event.clientX - bounds.left}px`);
  event.currentTarget.style.setProperty("--spot-y", `${event.clientY - bounds.top}px`);
}

function resetSpotlight(event: PointerEvent<HTMLElement>) {
  event.currentTarget.style.setProperty("--spot-x", "-320px");
  event.currentTarget.style.setProperty("--spot-y", "-320px");
}

export function ConflictStory() {
  const [contained, setContained] = useState(false);
  const reduced = useReducedMotion();
  const values = contained ? [4, 3, 5, 5, 5] : [4, 3, 5, 4, 6];
  return <section className="conflict-section" aria-labelledby="conflict-title">
    <div className="conflict-copy"><span className="landing-eyebrow">THE COORDINATION PROBLEM</span><h2 id="conflict-title">Good decisions can<br/><em>add up to a bad system.</em></h2><p>Independent agents can optimize different objectives against the same resource. The result is visible only when their committed effects are evaluated together.</p>
      <div className="conflict-toggle" role="group" aria-label="Illustrative coordination response"><button type="button" aria-pressed={!contained} onClick={() => setContained(false)}>Independent changes</button><button type="button" aria-pressed={contained} onClick={() => setContained(true)}>Controller response</button></div>
      <p className="conflict-caption" aria-live="polite">{contained ? "Illustrative response: a selective hold pauses the contributing agent while the controller checks recovery." : "Illustrative sequence: Cost reduces capacity; Performance later scales up; repeated reversals create coordination risk."}</p>
    </div>
    <div className="conflict-visual spotlight-surface" onPointerMove={updateSpotlight} onPointerLeave={resetSpotlight}>
      <div className="conflict-visual-head"><span>SHARED RESOURCE / SERVICE-A</span><span>ILLUSTRATIVE VERSIONS</span></div>
      <div className="conflict-agents"><span><b>C</b> Cost <small>reduce spend</small></span><ArrowDownRight size={16}/><span><b>P</b> Performance <small>protect latency</small></span></div>
      <svg viewBox="0 0 600 220" role="img" aria-label={`Illustrative capacity changes ${values.join(", ")}`} className="conflict-chart">
        {[35, 80, 125, 170].map(y => <line key={y} x1="40" x2="580" y1={y} y2={y} className="chart-grid-line"/>)}
        <motion.path d={values.map((value, index) => `${index ? "L" : "M"}${55 + index * 120} ${195 - value * 26}`).join(" ")} className={contained ? "chart-line chart-contained" : "chart-line"} transition={{ duration: reduced ? 0 : .35 }} />
        {values.map((value, index) => <g key={`${value}-${index}`}><circle cx={55 + index * 120} cy={195 - value * 26} r="5" className={index === 1 || index === 2 ? "chart-point chart-conflict" : "chart-point"}/><text x={55 + index * 120} y="213" textAnchor="middle">v{index + 4}</text></g>)}
        {!contained && <path d="M175 75 Q235 12 295 65" className="reversal-arc"/>}
      </svg>
      <div className={`conflict-resolution ${contained ? "is-contained" : ""}`}><span className="resolution-mark">{contained ? <Check size={14}/> : <GitBranch size={14}/>}</span><span><b>{contained ? "Selective hold · recovery check" : "Cross-agent reversal pattern"}</b><small>{contained ? "Controller policy remains authoritative" : "Observed effects · inferred relationship"}</small></span><span className="resolution-state">{contained ? "CONTAINED" : "DETECTED"}</span></div>
      <small className="illustrative-note">Conceptual simulator sequence. It is not a live control-plane feed.</small>
    </div>
  </section>;
}

export function ArchitectureJourney() {
  const [selected, setSelected] = useState(0);
  const reduced = useReducedMotion();
  const item = journey[selected];
  const Icon = item.icon;
  return <section className="journey-section" id="architecture" aria-labelledby="journey-title">
    <div className="journey-heading"><span className="landing-eyebrow">A TRACEABLE PATH</span><h2 id="journey-title">From proposal<br/>to verified outcome.</h2><p>Each boundary has an owner and a record. Select a step to see where the responsibility moves.</p></div>
    <div className="journey-layout">
      <div className="journey-list" role="group" aria-label="Execution lifecycle">
        {journey.map((step, index) => <button key={step.title} aria-pressed={selected === index} onClick={() => setSelected(index)}><span>{String(index + 1).padStart(2, "0")}</span><b>{step.title}</b><small>{step.owner}</small><ArrowRight size={15}/></button>)}
      </div>
      <motion.div key={selected} className="journey-detail spotlight-surface" onPointerMove={updateSpotlight} onPointerLeave={resetSpotlight} aria-live="polite" initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .22 }}>
        <div className="journey-detail-top"><span className="journey-icon"><Icon size={21}/></span><span>RESPONSIBILITY / {String(selected + 1).padStart(2, "0")}</span></div>
        <h3>{item.title}</h3><p>{item.detail}</p>
        <div className="journey-record"><Database size={15}/><span><small>INSPECTABLE RECORD</small><b>{item.evidence}</b></span><Check size={14}/></div>
        <div className="journey-track" aria-hidden="true"><span style={{ width: `${((selected + 1) / journey.length) * 100}%` }}/></div>
        <div className="journey-foot"><span>BOTKERNEL EXECUTION MODEL</span><span>{selected + 1} / {journey.length}</span></div>
      </motion.div>
    </div>
  </section>;
}

const previewTabs = [
  { label: "Mission control", route: "/app", icon: Activity, title: "Operational overview", detail: "Readiness · actions · incidents · simulated resources", kind: "overview" },
  { label: "Agent fleet", route: "/app/agents", icon: Bot, title: "Independent runtimes", detail: "Heartbeat evidence · decision snapshots · ledger outcomes", kind: "fleet" },
  { label: "Effect graph", route: "/app/graph", icon: GitBranch, title: "Versioned effects", detail: "Observed modifications · inferred relationships", kind: "graph" },
  { label: "Investigations", route: "/app/incidents", icon: Search, title: "Evidence-led analysis", detail: "Verified facts · deterministic inferences · hypotheses", kind: "investigation" },
];

function PreviewSurface({ kind }: { kind: string }) {
  return <div className={`preview-surface preview-${kind}`} aria-label="Illustrative console layout preview">
    <div className="preview-side"><span className="preview-brand-mark">BK</span><i/><i/><i/><i/></div>
    <div className="preview-main"><div className="preview-top"><span/><span/><span/></div><div className="preview-title-line"/><div className="preview-kpis"><i/><i/><i/></div>
      {kind === "graph" ? <div className="preview-network"><span/><i/><span/><i/><span/></div> : kind === "fleet" ? <div className="preview-fleet"><i/><i/><i/><i/></div> : kind === "investigation" ? <div className="preview-evidence"><i/><i/><i/></div> : <div className="preview-bars"><i/><i/><i/><i/><i/><i/><i/></div>}
      <small>LAYOUT PREVIEW · LIVE DATA LOADS IN CONSOLE</small>
    </div>
  </div>;
}

export function ConsolePreview() {
  const [selected, setSelected] = useState(0);
  const item = previewTabs[selected];
  return <section className="console-preview-section" aria-labelledby="console-preview-title">
    <div className="preview-heading"><div><span className="landing-eyebrow">INSIDE THE CONSOLE</span><h2 id="console-preview-title">Operational evidence,<br/><em>not dashboard theater.</em></h2></div><p>The console reads BotKernel's API. These previews show structure only; no sample metrics or live records are embedded here.</p></div>
    <div className="preview-layout"><nav className="preview-tabs" role="group" aria-label="Console section previews">{previewTabs.map((tab, index) => { const TabIcon = tab.icon; return <button aria-pressed={selected === index} key={tab.label} onClick={() => setSelected(index)}><TabIcon size={16}/><span>{tab.label}</span><ArrowRight size={14}/></button>; })}</nav>
      <div className="preview-panel spotlight-surface" onPointerMove={updateSpotlight} onPointerLeave={resetSpotlight} aria-live="polite"><div className="preview-panel-copy"><span>API-BACKED VIEW</span><h3>{item.title}</h3><p>{item.detail}</p><Link to={item.route}>Open {item.label.toLowerCase()} <ArrowRight size={15}/></Link></div><PreviewSurface kind={item.kind}/></div>
    </div>
  </section>;
}
