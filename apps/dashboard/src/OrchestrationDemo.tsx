import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Activity, ArrowDown, ArrowRight, Check, CircleDot, Database, GitBranch, Network, ShieldCheck, Workflow } from "lucide-react";

const scenes = [
  { label: "Observe", title: "One resource. Two objectives.", copy: "Both agents read the same simulated service state, while keeping their own objective and checkpoint.", nodes: ["cost", "performance", "resource"] },
  { label: "Propose", title: "Independent proposals can disagree.", copy: "Cost proposes a reduction. Performance may recommend more capacity when modeled latency rises.", nodes: ["cost", "performance"] },
  { label: "Admit", title: "The gateway owns admission.", copy: "Version, quota, policy and active holds are checked before PostgreSQL commits the reservation and outbox row.", nodes: ["gateway"] },
  { label: "Deliver", title: "Accepted work becomes durable work.", copy: "The publisher sends the outbox event to Kafka. Workers process at least once and reconcile simulator receipts.", nodes: ["outbox", "worker"] },
  { label: "Commit", title: "Effects get a versioned record.", copy: "Only a committed worker effect changes simulated capacity and advances the authoritative resource version.", nodes: ["effect", "resource"] },
  { label: "Contain", title: "The controller sees the interaction.", copy: "Cross-agent reversal evidence can trigger a selective hold and a bounded recovery check.", nodes: ["controller"] },
  { label: "Investigate", title: "Operators can inspect the evidence.", copy: "The read-only investigator links facts and deterministic inferences to persisted actions, effects and transitions.", nodes: ["investigator", "effect"] },
];

export function OrchestrationDemo() {
  const [step, setStep] = useState(0);
  const reduced = useReducedMotion();
  const scene = scenes[step];
  const active = (name: string) => scene.nodes.includes(name);
  return <section className="orchestration-demo" aria-label="Interactive illustrative execution flow">
    <div className="demo-toolbar"><span className="demo-kicker"><i/> BOTKERNEL SYSTEM MODEL</span><span>Illustrative · not live telemetry</span></div>
    <div className="demo-canvas">
      <svg className="demo-wires" viewBox="0 0 720 300" preserveAspectRatio="none" aria-hidden="true">
        <path className={step <= 1 ? "wire active" : "wire"} d="M105 72 C150 72 163 120 207 142"/>
        <path className={step <= 1 ? "wire active" : "wire"} d="M105 116 C150 116 164 140 207 148"/>
        <path className={step === 2 ? "wire active" : "wire"} d="M285 145 H344"/>
        <path className={step === 3 ? "wire active" : "wire"} d="M408 145 H465"/>
        <path className={step === 3 || step === 4 ? "wire active" : "wire"} d="M526 145 H581"/>
        <path className={step >= 5 ? "wire active" : "wire"} d="M614 179 C614 214 556 228 506 242"/>
        <path className={step === 6 ? "wire active" : "wire"} d="M548 251 H602"/>
      </svg>
      <div className={`demo-agent demo-cost ${active("cost") ? "is-active" : ""}`}><span>C</span><b>Cost</b><small>minimize spend</small></div>
      <div className={`demo-agent demo-performance ${active("performance") ? "is-active" : ""}`}><span>P</span><b>Performance</b><small>protect latency</small></div>
      <div className={`demo-node demo-resource ${active("resource") ? "is-active" : ""}`}><Activity/><span><b>Shared resource</b><small>simulated capacity</small></span></div>
      <div className={`demo-node demo-gateway ${active("gateway") ? "is-active" : ""}`}><ShieldCheck/><span><b>Admission</b><small>policy + reservation</small></span></div>
      <div className={`demo-node demo-outbox ${active("outbox") ? "is-active" : ""}`}><Database/><span><b>PostgreSQL</b><small>transactional outbox</small></span></div>
      <div className={`demo-node demo-worker ${active("worker") ? "is-active" : ""}`}><Workflow/><span><b>Kafka worker</b><small>at-least-once delivery</small></span></div>
      <div className={`demo-node demo-effect ${active("effect") ? "is-active" : ""}`}><GitBranch/><span><b>Committed effect</b><small>versioned evidence</small></span></div>
      <div className={`demo-node demo-controller ${active("controller") ? "is-active" : ""}`}><CircleDot/><span><b>Stability control</b><small>selective intervention</small></span></div>
      <div className={`demo-node demo-investigator ${active("investigator") ? "is-active" : ""}`}><Network/><span><b>Investigation</b><small>read-only report</small></span></div>
      {!reduced && <motion.span key={step} className="demo-event-pulse" initial={{ opacity: 0, scale: .3 }} animate={{ opacity: [0, 1, 0], scale: [0.4, 1.35, 1.8] }} transition={{ duration: .7 }} style={{ left: `${13 + step * 11}%`, top: step < 2 ? "33%" : step < 5 ? "49%" : "82%" }} aria-hidden="true"/>}
      <div className="demo-canvas-note"><span>Shared state</span><ArrowRight size={13}/><span>Validated execution</span><ArrowRight size={13}/><span>Collective outcome</span></div>
    </div>
    <div className="demo-story" aria-live="polite"><div><span className="demo-step-label">0{step + 1} / 07 · {scene.label}</span><h2>{scene.title}</h2><p>{scene.copy}</p></div><span className="demo-story-mark"><Check size={16}/></span></div>
    <div className="demo-stepper" role="group" aria-label="Illustrative system stages">
      {scenes.map((item, index) => <button key={item.label} aria-pressed={step === index} aria-label={`${index + 1}. ${item.label}`} onClick={() => setStep(index)}><span>{String(index + 1).padStart(2, "0")}</span><b>{item.label}</b></button>)}
    </div>
  </section>;
}

export function CapabilityBento() {
  return <div className="capability-bento">
    <article className="bento-orchestration"><span className="bento-label">01 / ORCHESTRATION</span><div className="mini-workflow">{["Observe", "Analyze", "Submit", "Reconcile"].map((label, index) => <span key={label}><i>{String(index + 1).padStart(2, "0")}</i>{label}</span>)}</div><h3>Independent agents.<br/>Shared consequences.</h3><p>Separate LangGraph workflows operate through one deterministic gateway.</p></article>
    <article className="bento-execution"><span className="bento-label">02 / EXECUTION</span><div className="mini-receipts"><span>Proposal <Check size={14}/></span><span>Outbox <Check size={14}/></span><span>Worker receipt <Check size={14}/></span></div><h3>Retries keep their context.</h3><p>At-least-once delivery with idempotent simulator receipts.</p></article>
    <article className="bento-evidence"><span className="bento-label">03 / EFFECT GRAPH</span><div className="mini-versions"><span>v₁</span><i/><span>v₂</span><i/><span>v₃</span></div><h3>Every change leaves a trail.</h3><p>Committed effects and inferred reversals remain distinguishable.</p></article>
    <article className="bento-investigation"><span className="bento-label">04 / INVESTIGATION</span><div className="mini-findings"><span><i/> VERIFIED FACT</span><span><i/> DETERMINISTIC INFERENCE</span><span><i/> HYPOTHESIS</span></div><h3>An explanation you can inspect.</h3><p>Read-only reports cite committed evidence. Recommendations stay advisory.</p></article>
  </div>;
}
