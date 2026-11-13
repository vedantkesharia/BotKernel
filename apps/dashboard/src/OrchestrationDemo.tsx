import { useLayoutEffect, useRef, useState } from "react";
import { Activity, Check, CircleDot, Database, GitBranch, Network, RadioTower, ShieldCheck, Workflow } from "lucide-react";

const scenes = [
  { label: "Observe", title: "One resource. Two objectives.", copy: "Both agents read the same simulated service state, while keeping their own objective and checkpoint.", nodes: ["cost", "performance", "resource"] },
  { label: "Propose", title: "Independent proposals can disagree.", copy: "Cost proposes a reduction. Performance may recommend more capacity when modeled latency rises.", nodes: ["cost", "performance"] },
  { label: "Admit", title: "The gateway owns admission.", copy: "Version, quota, policy and active holds are checked before PostgreSQL commits the reservation and outbox row.", nodes: ["gateway"] },
  { label: "Deliver", title: "Accepted work becomes durable work.", copy: "The publisher sends the outbox event to Kafka. Workers process at least once and reconcile simulator receipts.", nodes: ["outbox", "publisher", "worker"] },
  { label: "Commit", title: "Effects get a versioned record.", copy: "Only a committed worker effect changes simulated capacity and advances the authoritative resource version.", nodes: ["effect", "resource"] },
  { label: "Contain", title: "The controller sees the interaction.", copy: "Cross-agent reversal evidence can trigger a selective hold and a bounded recovery check.", nodes: ["controller"] },
  { label: "Investigate", title: "Operators can inspect the evidence.", copy: "The read-only investigator links facts and deterministic inferences to persisted actions, effects and transitions.", nodes: ["investigator", "effect"] },
];

type Anchor = "left" | "right" | "top" | "bottom";
type DiagramEdge = { id: string; source: string; target: string; activeStep: number; from: Anchor; to: Anchor; feedback?: boolean };

const diagramEdges: DiagramEdge[] = [
  { id: "resource-cost", source: "resource", target: "cost", activeStep: 0, from: "right", to: "left" },
  { id: "resource-performance", source: "resource", target: "performance", activeStep: 0, from: "right", to: "left" },
  { id: "cost-admission", source: "cost", target: "gateway", activeStep: 1, from: "right", to: "left" },
  { id: "performance-admission", source: "performance", target: "gateway", activeStep: 1, from: "right", to: "left" },
  { id: "admission-postgres", source: "gateway", target: "outbox", activeStep: 2, from: "right", to: "left" },
  { id: "postgres-publisher", source: "outbox", target: "publisher", activeStep: 3, from: "right", to: "left" },
  { id: "publisher-worker", source: "publisher", target: "worker", activeStep: 3, from: "bottom", to: "top" },
  { id: "worker-effect", source: "worker", target: "effect", activeStep: 4, from: "left", to: "right" },
  { id: "effect-controller", source: "effect", target: "controller", activeStep: 5, from: "bottom", to: "top" },
  { id: "controller-investigator", source: "controller", target: "investigator", activeStep: 6, from: "left", to: "right" },
  { id: "effect-resource", source: "effect", target: "resource", activeStep: 4, from: "right", to: "top", feedback: true },
];

type Bounds = { left: number; right: number; top: number; bottom: number };
type WireLayout = { width: number; height: number; paths: Record<string, string> };

function relativeBounds(canvas: DOMRect, rect: DOMRect): Bounds {
  return { left: rect.left - canvas.left, right: rect.right - canvas.left, top: rect.top - canvas.top, bottom: rect.bottom - canvas.top };
}

function anchor(rect: Bounds, side: Anchor) {
  const x = (rect.left + rect.right) / 2;
  const y = (rect.top + rect.bottom) / 2;
  if (side === "left") return { x: rect.left, y };
  if (side === "right") return { x: rect.right, y };
  if (side === "top") return { x, y: rect.top };
  return { x, y: rect.bottom };
}

function getWirePath(canvas: DOMRect, source: DOMRect, target: DOMRect, edge: DiagramEdge) {
  const from = relativeBounds(canvas, source);
  const to = relativeBounds(canvas, target);
  const mobileAnchors: Record<string, [Anchor, Anchor]> = {
    "resource-cost": ["bottom", "top"], "resource-performance": ["bottom", "top"],
    "cost-admission": ["bottom", "top"], "performance-admission": ["bottom", "top"],
    "admission-postgres": ["right", "left"], "postgres-publisher": ["bottom", "top"],
    "publisher-worker": ["right", "left"], "worker-effect": ["bottom", "top"],
    "effect-controller": ["left", "right"], "controller-investigator": ["bottom", "top"],
  };
  const [fromSide, toSide] = canvas.width < 520 && mobileAnchors[edge.id] ? mobileAnchors[edge.id] : [edge.from, edge.to];
  const start = anchor(from, fromSide);
  const end = anchor(to, toSide);

  if (edge.feedback) {
    const railX = canvas.width - 12;
    const resourceX = (to.left + to.right) / 2;
    if (canvas.width < 520) {
      const effectY = (from.top + from.bottom) / 2;
      return `M ${from.right} ${effectY} H ${railX} V 5 H ${resourceX} V ${to.top}`;
    }
    const laneY = Math.min(canvas.height - 88, from.bottom + 20);
    const railY = canvas.height - 14;
    const radius = 12;
    return `M ${start.x} ${start.y} V ${laneY - radius} Q ${start.x} ${laneY} ${start.x + radius} ${laneY} H ${railX - radius} Q ${railX} ${laneY} ${railX} ${laneY + radius} V ${railY - radius} Q ${railX} ${railY} ${railX - radius} ${railY} H ${resourceX + radius} Q ${resourceX} ${railY} ${resourceX} ${railY - radius} V ${end.y}`;
  }

  if (fromSide === "left" || fromSide === "right") {
    const direction = fromSide === "right" ? 1 : -1;
    const reach = Math.max(30, Math.abs(end.x - start.x) * .52);
    return `M ${start.x} ${start.y} C ${start.x + direction * reach} ${start.y}, ${end.x - direction * reach} ${end.y}, ${end.x} ${end.y}`;
  }
  const direction = fromSide === "bottom" ? 1 : -1;
  const reach = Math.max(28, Math.abs(end.y - start.y) * .5);
  return `M ${start.x} ${start.y} C ${start.x} ${start.y + direction * reach}, ${end.x} ${end.y - direction * reach}, ${end.x} ${end.y}`;
}

export function OrchestrationDemo() {
  const [step, setStep] = useState(0);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [wireLayout, setWireLayout] = useState<WireLayout>({ width: 0, height: 0, paths: {} });
  const scene = scenes[step];
  const active = (name: string) => scene.nodes.includes(name);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const update = () => {
      const bounds = canvas.getBoundingClientRect();
      const paths: Record<string, string> = {};
      for (const edge of diagramEdges) {
        const source = canvas.querySelector<HTMLElement>(`[data-node="${edge.source}"]`);
        const target = canvas.querySelector<HTMLElement>(`[data-node="${edge.target}"]`);
        if (source && target) paths[edge.id] = getWirePath(bounds, source.getBoundingClientRect(), target.getBoundingClientRect(), edge);
      }
      setWireLayout({ width: bounds.width, height: bounds.height, paths });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(canvas);
    window.addEventListener("resize", update);
    return () => { observer.disconnect(); window.removeEventListener("resize", update); };
  }, []);

  return <section className="orchestration-demo" aria-label="Interactive illustrative execution flow">
    <div className="demo-toolbar"><span className="demo-kicker"><i/> BOTKERNEL SYSTEM MODEL</span><span>Illustrative · not live telemetry</span></div>
    <div className="demo-canvas" ref={canvasRef}>
      <svg className="demo-wires" viewBox={`0 0 ${wireLayout.width} ${wireLayout.height}`} aria-hidden="true">
        <defs><marker id="demo-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>
        {diagramEdges.map(edge => <path key={edge.id} data-edge={edge.id} className={`demo-wire${step === edge.activeStep ? " is-active" : ""}${edge.feedback ? " is-feedback" : ""}`} d={wireLayout.paths[edge.id] ?? ""} markerEnd="url(#demo-arrow)"/>)}
      </svg>
      <span className="demo-zone demo-zone-agents">Independent agents</span>
      <span className="demo-zone demo-zone-execution">Durable execution</span>
      <span className="demo-zone demo-zone-reliability">Collective reliability</span>
      <div className="demo-diagram">
        <div className={`demo-node demo-resource ${active("resource") ? "is-active" : ""}`} data-node="resource"><Activity/><span><b>Shared resource</b><small>simulated telemetry</small></span></div>
        <div className={`demo-agent demo-cost ${active("cost") ? "is-active" : ""}`} data-node="cost"><span>C</span><span><b>Cost agent</b><small>minimize spend</small></span></div>
        <div className={`demo-agent demo-performance ${active("performance") ? "is-active" : ""}`} data-node="performance"><span>P</span><span><b>Performance agent</b><small>protect latency</small></span></div>
        <div className={`demo-node demo-gateway ${active("gateway") ? "is-active" : ""}`} data-node="gateway"><ShieldCheck/><span><b>Admission</b><small>policy + reservation</small></span></div>
        <div className={`demo-node demo-outbox ${active("outbox") ? "is-active" : ""}`} data-node="outbox"><Database/><span><b>PostgreSQL</b><small>transactional outbox</small></span></div>
        <div className={`demo-node demo-publisher ${active("publisher") ? "is-active" : ""}`} data-node="publisher"><RadioTower/><span><b>Publisher + Kafka</b><small>at-least-once transport</small></span></div>
        <div className={`demo-node demo-worker ${active("worker") ? "is-active" : ""}`} data-node="worker"><Workflow/><span><b>Worker</b><small>receipt reconciliation</small></span></div>
        <div className={`demo-node demo-effect ${active("effect") ? "is-active" : ""}`} data-node="effect"><GitBranch/><span><b>Committed effect</b><small>versioned evidence</small></span></div>
        <div className={`demo-node demo-controller ${active("controller") ? "is-active" : ""}`} data-node="controller"><CircleDot/><span><b>Stability controller</b><small>selective intervention</small></span></div>
        <div className={`demo-node demo-investigator ${active("investigator") ? "is-active" : ""}`} data-node="investigator"><Network/><span><b>Investigation</b><small>read-only report</small></span></div>
      </div>
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
