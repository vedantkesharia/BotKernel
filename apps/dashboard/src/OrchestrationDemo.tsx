import { useLayoutEffect, useRef, useState } from "react";
import { Activity, Check, CircleDot, Database, GitBranch, Network, ShieldCheck, Workflow } from "lucide-react";

const scenes = [
  { label: "Observe", title: "One resource. Two objectives.", copy: "Both agents read the same simulated service state, while keeping their own objective and checkpoint.", nodes: ["cost", "performance", "resource"] },
  { label: "Propose", title: "Independent proposals can disagree.", copy: "Cost proposes a reduction. Performance may recommend more capacity when modeled latency rises.", nodes: ["cost", "performance"] },
  { label: "Admit", title: "The gateway owns admission.", copy: "Version, quota, policy and active holds are checked before PostgreSQL commits the reservation and outbox row.", nodes: ["gateway"] },
  { label: "Deliver", title: "Accepted work becomes durable work.", copy: "The publisher sends the outbox event to Kafka. Workers process at least once and reconcile simulator receipts.", nodes: ["outbox", "worker"] },
  { label: "Commit", title: "Effects get a versioned record.", copy: "Only a committed worker effect changes simulated capacity and advances the authoritative resource version.", nodes: ["effect", "resource"] },
  { label: "Contain", title: "The controller sees the interaction.", copy: "Cross-agent reversal evidence can trigger a selective hold and a bounded recovery check.", nodes: ["controller"] },
  { label: "Investigate", title: "Operators can inspect the evidence.", copy: "The read-only investigator links facts and deterministic inferences to persisted actions, effects and transitions.", nodes: ["investigator", "effect"] },
];

type DiagramRoute = "feedback" | "stability";

const diagramEdges: { id: string; source: string; target: string; activeStep: number; route?: DiagramRoute }[] = [
  { id: "resource-cost", source: "resource", target: "cost", activeStep: 0 },
  { id: "resource-performance", source: "resource", target: "performance", activeStep: 0 },
  { id: "cost-admission", source: "cost", target: "gateway", activeStep: 1 },
  { id: "performance-admission", source: "performance", target: "gateway", activeStep: 1 },
  { id: "admission-postgres", source: "gateway", target: "outbox", activeStep: 2 },
  { id: "postgres-worker", source: "outbox", target: "worker", activeStep: 3 },
  { id: "worker-effect", source: "worker", target: "effect", activeStep: 4 },
  { id: "effect-resource", source: "effect", target: "resource", activeStep: 4, route: "feedback" },
  { id: "effect-controller", source: "effect", target: "controller", activeStep: 5, route: "stability" },
  { id: "controller-investigator", source: "controller", target: "investigator", activeStep: 6 },
];

type WireLayout = { width: number; height: number; paths: Record<string, string> };

function getWirePath(canvas: DOMRect, source: DOMRect, target: DOMRect, route?: DiagramRoute) {
  const from = {
    left: source.left - canvas.left,
    right: source.right - canvas.left,
    top: source.top - canvas.top,
    bottom: source.bottom - canvas.top,
  };
  const to = {
    left: target.left - canvas.left,
    right: target.right - canvas.left,
    top: target.top - canvas.top,
    bottom: target.bottom - canvas.top,
  };
  const fromX = (from.left + from.right) / 2;
  const fromY = (from.top + from.bottom) / 2;
  const toX = (to.left + to.right) / 2;
  const toY = (to.top + to.bottom) / 2;

  if (route === "stability") {
    const inset = Math.min(14, (from.right - from.left) * 0.18, (to.right - to.left) * 0.18);
    const startX = from.left + inset;
    const endX = (to.left + to.right) / 2;
    const startY = from.bottom;
    const endY = to.top;
    const curve = Math.min(24, Math.max(0, endY - startY) * 0.45);
    return `M ${startX} ${startY} C ${startX} ${startY + curve}, ${endX} ${endY - curve}, ${endX} ${endY}`;
  }
  if (route === "feedback" && toY < fromY - 8) {
    const routeX = canvas.width - 6;
    return `M ${from.right} ${fromY} H ${routeX} V ${toY} H ${to.right}`;
  }
  if (route === "feedback") {
    const routeY = Math.max(5, Math.min(from.top, to.top) - 12);
    return `M ${fromX} ${from.top} V ${routeY} H ${toX} V ${to.top}`;
  }

  const xOverlap = Math.min(from.right, to.right) - Math.max(from.left, to.left);
  const yOverlap = Math.min(from.bottom, to.bottom) - Math.max(from.top, to.top);
  const vertical = (xOverlap > 0 && yOverlap <= 0) || (xOverlap <= 0 && yOverlap <= 0 && Math.abs(toY - fromY) > Math.abs(toX - fromX));

  if (vertical) {
    const direction = toY >= fromY ? 1 : -1;
    const startX = Math.max(from.left + 8, Math.min(from.right - 8, toX));
    const endX = Math.max(to.left + 8, Math.min(to.right - 8, startX));
    const startY = direction > 0 ? from.bottom : from.top;
    const endY = direction > 0 ? to.top : to.bottom;
    const curve = Math.min(42, Math.abs(endY - startY) * 0.42);
    return `M ${startX} ${startY} C ${startX} ${startY + direction * curve}, ${endX} ${endY - direction * curve}, ${endX} ${endY}`;
  }

  const direction = toX >= fromX ? 1 : -1;
  const startY = Math.max(from.top + 8, Math.min(from.bottom - 8, toY));
  const endY = Math.max(to.top + 8, Math.min(to.bottom - 8, startY));
  const startX = direction > 0 ? from.right : from.left;
  const endX = direction > 0 ? to.left : to.right;
  const curve = Math.min(42, Math.abs(endX - startX) * 0.42);
  return `M ${startX} ${startY} C ${startX + direction * curve} ${startY}, ${endX - direction * curve} ${endY}, ${endX} ${endY}`;
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
        if (source && target) paths[edge.id] = getWirePath(bounds, source.getBoundingClientRect(), target.getBoundingClientRect(), edge.route);
      }
      setWireLayout({ width: bounds.width, height: bounds.height, paths });
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(canvas);
    window.addEventListener("resize", update);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  return <section className="orchestration-demo" aria-label="Interactive illustrative execution flow">
    <div className="demo-toolbar"><span className="demo-kicker"><i/> BOTKERNEL SYSTEM MODEL</span><span>Illustrative · not live telemetry</span></div>
    <div className="demo-canvas" ref={canvasRef}>
      <svg className="demo-wires" viewBox={`0 0 ${wireLayout.width} ${wireLayout.height}`} aria-hidden="true">
        <defs><marker id="demo-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 8 4 L 0 8 z"/></marker></defs>
        {diagramEdges.map(edge => <path key={edge.id} data-edge={edge.id} className={`demo-wire${step === edge.activeStep ? " is-active" : ""}${edge.route === "feedback" ? " is-feedback" : ""}`} d={wireLayout.paths[edge.id] ?? ""} markerEnd="url(#demo-arrow)"/>)}
      </svg>
      <div className="demo-grid">
        <div className={`demo-node demo-resource ${active("resource") ? "is-active" : ""}`} data-node="resource"><Activity/><span><b>Shared resource</b><small>simulated capacity</small></span></div>
        <div className={`demo-agent demo-cost ${active("cost") ? "is-active" : ""}`} data-node="cost"><span>C</span><span><b>Cost</b><small>minimize spend</small></span></div>
        <div className={`demo-agent demo-performance ${active("performance") ? "is-active" : ""}`} data-node="performance"><span>P</span><span><b>Performance</b><small>protect latency</small></span></div>
        <div className={`demo-node demo-gateway ${active("gateway") ? "is-active" : ""}`} data-node="gateway"><ShieldCheck/><span><b>Admission</b><small>policy + reservation</small></span></div>
        <div className={`demo-node demo-outbox ${active("outbox") ? "is-active" : ""}`} data-node="outbox"><Database/><span><b>PostgreSQL</b><small>transactional outbox</small></span></div>
        <div className={`demo-node demo-worker ${active("worker") ? "is-active" : ""}`} data-node="worker"><Workflow/><span><b>Kafka worker</b><small>at-least-once delivery</small></span></div>
        <div className={`demo-node demo-effect ${active("effect") ? "is-active" : ""}`} data-node="effect"><GitBranch/><span><b>Committed effect</b><small>versioned evidence</small></span></div>
        <div className={`demo-node demo-controller ${active("controller") ? "is-active" : ""}`} data-node="controller"><CircleDot/><span><b>Stability control</b><small>selective intervention</small></span></div>
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
