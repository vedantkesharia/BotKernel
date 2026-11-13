import { useState, type PointerEvent, type ReactNode } from "react";
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
] as const;

type PreviewKind = typeof previewTabs[number]["kind"];

function PreviewFrame({ kind, children }: { kind: PreviewKind; children: ReactNode }) {
  const sectionName = previewTabs.find(tab => tab.kind === kind)?.label ?? "Console";
  return <div className={`preview-surface preview-${kind}`} role="img" aria-label={`${sectionName} illustrative preview, not live telemetry`}>
    <aside className="preview-side" aria-hidden="true"><span className="preview-brand-mark">BK</span><i/><i/><i/><i/><i/></aside>
    <div className="preview-main">
      <div className="preview-topbar"><span>BOTKERNEL <i/> {sectionName.toUpperCase()}</span><b>ILLUSTRATIVE</b></div>
      {children}
      <div className="preview-disclaimer">Illustrative preview · no live metrics or records</div>
    </div>
  </div>;
}

function OverviewPreview() {
  return <div className="preview-overview">
    <div className="preview-overview-heading"><span>MISSION CONTROL</span><small>OPERATIONAL SURFACE</small></div>
    <div className="preview-overview-cards">
      <div><small>READINESS</small><b><i className="preview-outline-dot"/> Service checks</b><span>API · database · stream</span></div>
      <div><small>ACTION LEDGER</small><b><Database size={12}/> Durable records</b><span>Proposal to receipt</span></div>
      <div><small>RESOURCE STATE</small><b><Activity size={12}/> Simulated capacity</b><span>Versioned observations</span></div>
    </div>
    <div className="preview-chart-card">
      <div className="preview-card-heading"><span>RESOURCE TREND</span><small>EXAMPLE SHAPE</small></div>
      <svg className="preview-chart" viewBox="0 0 640 116" preserveAspectRatio="none" aria-hidden="true">
        {[22, 52, 82].map(y => <line key={y} x1="0" x2="640" y1={y} y2={y}/>)}
        <path d="M12 72 C70 68 78 43 132 48 S207 80 265 63 S344 36 397 50 S486 76 536 49 S591 40 628 31"/>
        <path className="preview-chart-secondary" d="M12 91 C84 86 110 81 166 82 S242 91 302 78 S380 70 438 77 S535 68 628 72"/>
        {[132, 265, 397, 536].map((x, index) => <circle key={x} cx={x} cy={[48, 63, 50, 49][index]} r="3.5"/> )}
      </svg>
      <div className="preview-chart-labels"><span>Capacity history</span><span>Versioned state</span></div>
    </div>
    <div className="preview-activity-strip"><span>ACTIVITY PATH</span><i/><b>Action</b><i/><b>Receipt</b><i/><b>Effect</b></div>
  </div>;
}

function FleetPreview() {
  const agents = [
    { initial: "C", name: "Cost agent", detail: "Spend objective", evidence: "Decision snapshot" },
    { initial: "P", name: "Performance agent", detail: "Latency objective", evidence: "Decision snapshot" },
    { initial: "I", name: "Investigator", detail: "Read-only workflow", evidence: "Evidence references" },
  ];
  return <div className="preview-fleet-view">
    <div className="preview-view-heading"><span>AGENT FLEET</span><small>IDENTITY · WORKFLOW · PROVENANCE</small></div>
    <div className="preview-fleet-list">{agents.map(agent => <div className="preview-agent-row" key={agent.name}>
      <span className="preview-agent-mark">{agent.initial}</span>
      <span className="preview-agent-copy"><b>{agent.name}</b><small>{agent.detail}</small></span>
      <span className="preview-agent-evidence"><small>INSPECTABLE</small><b>{agent.evidence}</b></span>
      <span className="preview-agent-arrow"><ArrowRight size={13}/></span>
    </div>)}</div>
    <div className="preview-fleet-foot"><span>Workflow boundaries</span><span>Persisted provenance</span><span>Advisory analysis</span></div>
  </div>;
}

function GraphPreview() {
  return <div className="preview-graph-view">
    <div className="preview-view-heading"><span>EFFECT GRAPH</span><small>OBSERVED + INFERRED</small></div>
    <svg className="preview-graph-svg" viewBox="0 0 640 178" aria-hidden="true">
      <defs><marker id="preview-graph-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z"/></marker></defs>
      <path className="preview-edge-observed" d="M132 83 H246" markerEnd="url(#preview-graph-arrow)"/>
      <path className="preview-edge-observed" d="M324 83 H438" markerEnd="url(#preview-graph-arrow)"/>
      <path className="preview-edge-inferred" d="M478 106 C466 154 286 154 250 106" markerEnd="url(#preview-graph-arrow)"/>
      <g className="preview-graph-node" transform="translate(48 55)"><rect width="84" height="56" rx="8"/><text x="42" y="24">AGENT</text><text x="42" y="39">proposal</text></g>
      <g className="preview-graph-node preview-graph-node-focus" transform="translate(246 55)"><rect width="84" height="56" rx="8"/><text x="42" y="24">EFFECT</text><text x="42" y="39">committed</text></g>
      <g className="preview-graph-node" transform="translate(438 55)"><rect width="84" height="56" rx="8"/><text x="42" y="24">RESOURCE</text><text x="42" y="39">versioned</text></g>
      <text className="preview-edge-label" x="188" y="70">OBSERVED</text>
      <text className="preview-edge-label preview-edge-label-inferred" x="354" y="151">INFERRED RELATIONSHIP</text>
    </svg>
    <div className="preview-graph-legend"><span><i/>Committed evidence</span><span><i/>Inferred relationship</span><small>Example topology · not operational records</small></div>
  </div>;
}

function InvestigationPreview() {
  return <div className="preview-investigation-view">
    <div className="preview-investigation-heading"><span><small>INVESTIGATION</small><b>Evidence-linked report</b></span><span className="preview-advisory-badge">ADVISORY ONLY</span></div>
    <div className="preview-evidence-list">
      <div className="preview-evidence-row"><span className="preview-evidence-icon"><Database size={13}/></span><span><small>VERIFIED FACT</small><b>Committed effect reference</b><em>Action · effect · resource version</em></span><Check size={14}/></div>
      <div className="preview-evidence-row"><span className="preview-evidence-icon"><GitBranch size={13}/></span><span><small>DETERMINISTIC INFERENCE</small><b>Cross-agent relationship</b><em>Linked to persisted evidence</em></span><ArrowRight size={13}/></div>
      <div className="preview-evidence-row"><span className="preview-evidence-icon preview-hypothesis-icon"><Search size={13}/></span><span><small>HYPOTHESIS</small><b>Operator-reviewed context</b><em>Citations validated · no action executed</em></span><Shield size={13}/></div>
    </div>
  </div>;
}

function PreviewSurface({ kind }: { kind: PreviewKind }) {
  return <PreviewFrame kind={kind}>
    {kind === "overview" ? <OverviewPreview/> : kind === "fleet" ? <FleetPreview/> : kind === "graph" ? <GraphPreview/> : <InvestigationPreview/>}
  </PreviewFrame>;
}

export function ConsolePreview() {
  const [selected, setSelected] = useState(0);
  const reduced = useReducedMotion();
  const item = previewTabs[selected];
  return <section className="console-preview-section" aria-labelledby="console-preview-title">
    <div className="preview-heading"><div><span className="landing-eyebrow">INSIDE THE CONSOLE</span><h2 id="console-preview-title">Operational evidence,<br/><em>not dashboard theater.</em></h2></div><p>The console reads BotKernel's API. These previews show structure only; no sample metrics or live records are embedded here.</p></div>
    <div className="preview-layout"><nav className="preview-tabs" role="group" aria-label="Console section previews">{previewTabs.map((tab, index) => { const TabIcon = tab.icon; return <button type="button" aria-pressed={selected === index} key={tab.label} onClick={() => setSelected(index)}><TabIcon size={16}/><span>{tab.label}</span><ArrowRight size={14}/></button>; })}</nav>
      <div className="preview-panel spotlight-surface" onPointerMove={updateSpotlight} onPointerLeave={resetSpotlight} aria-live="polite"><div className="preview-panel-copy"><span>ILLUSTRATIVE CONSOLE PREVIEW</span><h3>{item.title}</h3><p>{item.detail}</p><Link to={item.route}>Open {item.label.toLowerCase()} <ArrowRight size={15}/></Link></div><motion.div key={item.kind} className="preview-stage" initial={reduced ? false : { opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : .2 }}><PreviewSurface kind={item.kind}/></motion.div></div>
    </div>
  </section>;
}
