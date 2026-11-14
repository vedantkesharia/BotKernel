import { useLayoutEffect, useRef, useState } from "react";
import { Activity, Check, CircleDot, Database, GitBranch, Network, RadioTower, ShieldCheck, Workflow } from "lucide-react";

const scenes = [
  { label: "Observe", title: "One resource. Two objectives.", copy: "Both agents read the same simulated service state, while keeping their own objective and checkpoint.", nodes: ["cost", "performance", "resource"] },
  { label: "Propose", title: "Independent proposals can disagree.", copy: "Cost proposes a reduction. Performance may recommend more capacity when modeled latency rises.", nodes: ["cost", "performance", "gateway"] },
  { label: "Admit", title: "The gateway owns admission.", copy: "Version, quota, policy and active holds are checked before PostgreSQL commits the reservation and outbox row.", nodes: ["gateway", "outbox"] },
  { label: "Deliver", title: "Accepted work becomes durable work.", copy: "The publisher sends the outbox event to Kafka. Workers process at least once and reconcile simulator receipts.", nodes: ["outbox", "publisher", "worker"] },
  { label: "Commit", title: "Effects get a versioned record.", copy: "Only a committed worker effect changes simulated capacity and advances the authoritative resource version.", nodes: ["worker", "effect", "resource"] },
  { label: "Contain", title: "The controller sees the interaction.", copy: "Cross-agent reversal evidence can trigger a selective hold and a bounded recovery check.", nodes: ["effect", "controller"] },
  { label: "Investigate", title: "Operators can inspect the evidence.", copy: "The read-only investigator links facts and deterministic inferences to persisted actions, effects and transitions.", nodes: ["controller", "investigator", "effect"] },
];

type Anchor = "left" | "right" | "top" | "bottom";
type EdgeKind = "curve" | "branch" | "branch-trunk" | "feedback";
type DiagramEdge = {
  id: string;
  source: string;
  target: string;
  activeStep: number;
  from: Anchor;
  to: Anchor;
  fromAt?: number;
  toAt?: number;
  kind?: EdgeKind;
};

const diagramEdges: DiagramEdge[] = [
  { id: "resource-branch-trunk", source: "resource", target: "resource", activeStep: 0, from: "right", to: "right", kind: "branch-trunk" },
  { id: "resource-cost", source: "resource", target: "cost", activeStep: 0, from: "right", to: "left", kind: "branch" },
  { id: "resource-performance", source: "resource", target: "performance", activeStep: 0, from: "right", to: "left", kind: "branch" },
  { id: "cost-admission", source: "cost", target: "gateway", activeStep: 1, from: "right", to: "left", fromAt: 0.85, toAt: 0.25 },
  { id: "performance-admission", source: "performance", target: "gateway", activeStep: 1, from: "right", to: "left", fromAt: 0.15, toAt: 0.75 },
  { id: "admission-postgres", source: "gateway", target: "outbox", activeStep: 2, from: "right", to: "left" },
  { id: "postgres-publisher", source: "outbox", target: "publisher", activeStep: 3, from: "right", to: "left" },
  { id: "publisher-worker", source: "publisher", target: "worker", activeStep: 3, from: "bottom", to: "top" },
  { id: "worker-effect", source: "worker", target: "effect", activeStep: 4, from: "left", to: "right" },
  { id: "effect-controller", source: "effect", target: "controller", activeStep: 5, from: "bottom", to: "top", fromAt: 0.52, toAt: 0.48 },
  { id: "controller-investigator", source: "controller", target: "investigator", activeStep: 6, from: "left", to: "right" },
  { id: "effect-resource", source: "effect", target: "resource", activeStep: 4, from: "bottom", to: "top", fromAt: 0.15, kind: "feedback" },
];

type Bounds = { left: number; right: number; top: number; bottom: number };
type Point = { x: number; y: number };
type EdgeGeometry = {
  path: string;
  start: Point;
  targetAnchor?: Point;
  tip?: Point;
  base?: Point;
  tangent?: Point;
  arrowPoints?: string;
  tailPath?: string;
};
type WireLayout = { width: number; height: number; edges: Record<string, EdgeGeometry> };

const arrowGap = 2.5;
const arrowLength = 8;
const arrowHalfWidth = 3.25;

function relativeBounds(canvas: DOMRect, rect: DOMRect): Bounds {
  return { left: rect.left - canvas.left, right: rect.right - canvas.left, top: rect.top - canvas.top, bottom: rect.bottom - canvas.top };
}

function anchor(rect: Bounds, side: Anchor, position = 0.5): Point {
  const offset = Math.min(1, Math.max(0, position));
  if (side === "left") return { x: rect.left, y: rect.top + (rect.bottom - rect.top) * offset };
  if (side === "right") return { x: rect.right, y: rect.top + (rect.bottom - rect.top) * offset };
  if (side === "top") return { x: rect.left + (rect.right - rect.left) * offset, y: rect.top };
  return { x: rect.left + (rect.right - rect.left) * offset, y: rect.bottom };
}

function outward(side: Anchor): Point {
  if (side === "left") return { x: -1, y: 0 };
  if (side === "right") return { x: 1, y: 0 };
  if (side === "top") return { x: 0, y: -1 };
  return { x: 0, y: 1 };
}

function offset(point: Point, direction: Point, distance: number): Point {
  return { x: point.x + direction.x * distance, y: point.y + direction.y * distance };
}

function arrowheadPoints(tip: Point, tangent: Point) {
  const length = Math.hypot(tangent.x, tangent.y);
  const direction = { x: tangent.x / length, y: tangent.y / length };
  const normal = { x: -direction.y, y: direction.x };
  const base = offset(tip, direction, -arrowLength);
  const first = offset(base, normal, arrowHalfWidth);
  const second = offset(base, normal, -arrowHalfWidth);
  return `${tip.x},${tip.y} ${first.x},${first.y} ${second.x},${second.y}`;
}

function directedEdge(pathToBase: (base: Point) => string, start: Point, targetAnchor: Point, targetSide: Anchor, solidTail = false): EdgeGeometry {
  const targetNormal = outward(targetSide);
  const tangent = { x: -targetNormal.x, y: -targetNormal.y };
  const tip = offset(targetAnchor, targetNormal, arrowGap);
  const base = offset(tip, tangent, -arrowLength);
  const tailStart = offset(base, tangent, -4);
  return {
    path: pathToBase(base),
    start,
    targetAnchor,
    tip,
    base,
    tangent,
    arrowPoints: arrowheadPoints(tip, tangent),
    tailPath: solidTail ? `M ${tailStart.x} ${tailStart.y} L ${base.x} ${base.y}` : undefined,
  };
}

function curvePath(start: Point, end: Point, from: Anchor, to: Anchor) {
  const horizontal = from === "left" || from === "right";
  const span = Math.abs(horizontal ? end.x - start.x : end.y - start.y);
  const reach = Math.max(1, Math.min(28, span * 0.45));
  const fromNormal = outward(from);
  const toNormal = outward(to);
  const beforeEnd = offset(end, toNormal, 5);
  const control1 = { x: start.x + fromNormal.x * reach, y: start.y + fromNormal.y * reach };
  const control2 = { x: beforeEnd.x + toNormal.x * reach, y: beforeEnd.y + toNormal.y * reach };
  return `M ${start.x} ${start.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${beforeEnd.x} ${beforeEnd.y} L ${end.x} ${end.y}`;
}

function agentAdmissionPath(start: Point, base: Point) {
  const span = base.x - start.x;
  const reach = Math.min(18, span * 0.42);
  return `M ${start.x} ${start.y} C ${start.x + reach} ${start.y}, ${base.x - reach} ${base.y}, ${base.x} ${base.y}`;
}

function getBranchPaths(resource: Bounds, cost: Bounds, performance: Bounds) {
  const paths: Record<string, EdgeGeometry> = {};
  const stackBelow = resource.bottom < Math.min(cost.top, performance.top);

  if (stackBelow) {
    const source = anchor(resource, "bottom");
    const costEnd = anchor(cost, "top");
    const performanceEnd = anchor(performance, "top");
    const splitY = source.y + Math.min(6, (Math.min(costEnd.y, performanceEnd.y) - source.y) * 0.22);
    paths["resource-branch-trunk"] = {
      path: `M ${source.x} ${source.y} V ${splitY} M ${Math.min(costEnd.x, performanceEnd.x)} ${splitY} H ${Math.max(costEnd.x, performanceEnd.x)}`,
      start: source,
    };
    const costStart = { x: costEnd.x, y: splitY };
    const performanceStart = { x: performanceEnd.x, y: splitY };
    paths["resource-cost"] = directedEdge(base => `M ${costStart.x} ${costStart.y} V ${base.y}`, costStart, costEnd, "top");
    paths["resource-performance"] = directedEdge(base => `M ${performanceStart.x} ${performanceStart.y} V ${base.y}`, performanceStart, performanceEnd, "top");
    return paths;
  }

  const source = anchor(resource, "right");
  const costEnd = anchor(cost, "left");
  const performanceEnd = anchor(performance, "left");
  const branchX = source.x + Math.min(6, (Math.min(costEnd.x, performanceEnd.x) - source.x) * 0.22);
  const trunkTop = Math.min(source.y, costEnd.y, performanceEnd.y);
  const trunkBottom = Math.max(source.y, costEnd.y, performanceEnd.y);
  paths["resource-branch-trunk"] = {
    path: `M ${source.x} ${source.y} H ${branchX} M ${branchX} ${trunkTop} V ${trunkBottom}`,
    start: source,
  };
  const costStart = { x: branchX, y: costEnd.y };
  const performanceStart = { x: branchX, y: performanceEnd.y };
  paths["resource-cost"] = directedEdge(base => `M ${costStart.x} ${costStart.y} H ${base.x}`, costStart, costEnd, "left");
  paths["resource-performance"] = directedEdge(base => `M ${performanceStart.x} ${performanceStart.y} H ${base.x}`, performanceStart, performanceEnd, "left");
  return paths;
}

function roundedPolyline(points: Point[], radius: number) {
  const cleanPoints = points.filter((point, index) => index === 0 || Math.hypot(point.x - points[index - 1].x, point.y - points[index - 1].y) > 0.5);
  if (cleanPoints.length < 2) return "";
  let path = `M ${cleanPoints[0].x} ${cleanPoints[0].y}`;
  for (let index = 1; index < cleanPoints.length - 1; index += 1) {
    const previous = cleanPoints[index - 1];
    const current = cleanPoints[index];
    const next = cleanPoints[index + 1];
    const incomingLength = Math.hypot(current.x - previous.x, current.y - previous.y);
    const outgoingLength = Math.hypot(next.x - current.x, next.y - current.y);
    const corner = Math.min(radius, incomingLength / 2, outgoingLength / 2);
    if (corner < 0.5) {
      path += ` L ${current.x} ${current.y}`;
      continue;
    }
    const before = {
      x: current.x - (current.x - previous.x) / incomingLength * corner,
      y: current.y - (current.y - previous.y) / incomingLength * corner,
    };
    const after = {
      x: current.x + (next.x - current.x) / outgoingLength * corner,
      y: current.y + (next.y - current.y) / outgoingLength * corner,
    };
    path += ` L ${before.x} ${before.y} Q ${current.x} ${current.y} ${after.x} ${after.y}`;
  }
  const last = cleanPoints[cleanPoints.length - 1];
  return `${path} L ${last.x} ${last.y}`;
}

function feedbackPath(canvasWidth: number, source: Bounds, target: Bounds, nextRow: Bounds) {
  const start = anchor(source, "bottom", 0.15);
  const targetAnchor = anchor(target, "top");
  const laneY = Math.max(start.y + 12, nextRow.top - 20);
  const routeRight = nextRow.left < source.left;
  const railX = routeRight
    ? canvasWidth - Math.min(8, (canvasWidth - target.right) / 2)
    : Math.min(8, target.left / 2);
  return directedEdge(base => {
    const approachY = Math.max(4, base.y - 14);
    return roundedPolyline([
      start,
      { x: start.x, y: laneY },
      { x: railX, y: laneY },
      { x: railX, y: approachY },
      { x: base.x, y: approachY },
      base,
    ], 10);
  }, start, targetAnchor, "top", true);
}

function responsiveAnchors(edge: DiagramEdge, source: Bounds, target: Bounds): [Anchor, Anchor] {
  const horizontalOverlap = Math.min(source.right, target.right) > Math.max(source.left, target.left);
  const targetBelow = target.top >= source.bottom;
  const sourceBelow = source.top >= target.bottom;
  if (edge.id === "cost-admission" && horizontalOverlap) return ["bottom", "top"];
  if (edge.id === "performance-admission" && targetBelow) return ["bottom", "top"];
  if (edge.id === "postgres-publisher" && targetBelow) return ["bottom", "top"];
  if (edge.id === "publisher-worker" && target.left >= source.right) return ["right", "left"];
  if (edge.id === "worker-effect" && targetBelow) return ["bottom", "top"];
  if (edge.id === "effect-controller" && target.left < source.left && !sourceBelow && !targetBelow) return ["left", "right"];
  if (edge.id === "controller-investigator" && targetBelow) return ["bottom", "top"];
  return [edge.from, edge.to];
}

function getWireGeometry(canvas: DOMRect, source: DOMRect, target: DOMRect, edge: DiagramEdge, nextRow?: DOMRect): EdgeGeometry {
  const from = relativeBounds(canvas, source);
  const to = relativeBounds(canvas, target);
  if (edge.kind === "feedback") {
    return nextRow
      ? feedbackPath(canvas.width, from, to, relativeBounds(canvas, nextRow))
      : { path: "", start: { x: 0, y: 0 } };
  }

  const [fromSide, toSide] = responsiveAnchors(edge, from, to);
  const start = anchor(from, fromSide, edge.fromAt);
  const targetAnchor = anchor(to, toSide, edge.toAt);
  const agentToAdmission = (edge.id === "cost-admission" || edge.id === "performance-admission") &&
    fromSide === "right" && toSide === "left";
  return directedEdge(
    base => agentToAdmission ? agentAdmissionPath(start, base) : curvePath(start, base, fromSide, toSide),
    start, targetAnchor, toSide,
  );
}

export function OrchestrationDemo() {
  const [step, setStep] = useState(0);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [wireLayout, setWireLayout] = useState<WireLayout>({ width: 0, height: 0, edges: {} });
  const scene = scenes[step];
  const active = (name: string) => scene.nodes.includes(name);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const update = () => {
      const bounds = canvas.getBoundingClientRect();
      const edges: Record<string, EdgeGeometry> = {};
      const nodes = new Map<string, { element: HTMLElement; bounds: Bounds }>(Array.from(canvas.querySelectorAll<HTMLElement>("[data-node]")).map(node => [
        node.dataset.node ?? "",
        { element: node, bounds: relativeBounds(bounds, node.getBoundingClientRect()) },
      ] as const));
      const resource = nodes.get("resource")?.bounds;
      const cost = nodes.get("cost")?.bounds;
      const performance = nodes.get("performance")?.bounds;
      if (resource && cost && performance) Object.assign(edges, getBranchPaths(resource, cost, performance));

      for (const edge of diagramEdges) {
        if (edge.kind === "branch" || edge.kind === "branch-trunk") continue;
        const source = nodes.get(edge.source)?.element;
        const target = nodes.get(edge.target)?.element;
        if (!source || !target) continue;
        const nextRow = edge.kind === "feedback"
          ? [...nodes.values()]
            .map(node => node.element.getBoundingClientRect())
            .filter(rect => rect.top >= source.getBoundingClientRect().bottom)
            .sort((left, right) => left.top - right.top)[0]
          : undefined;
        edges[edge.id] = getWireGeometry(bounds, source.getBoundingClientRect(), target.getBoundingClientRect(), edge, nextRow);
      }
      setWireLayout({ width: bounds.width, height: bounds.height, edges });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(canvas);
    canvas.querySelectorAll<HTMLElement>("[data-node]").forEach(node => observer.observe(node));
    window.addEventListener("resize", update);
    return () => { observer.disconnect(); window.removeEventListener("resize", update); };
  }, [step]);

  return <section className="orchestration-demo" aria-label="Interactive illustrative execution flow">
    <div className="demo-toolbar"><span className="demo-kicker"><i/> BOTKERNEL SYSTEM MODEL</span><span>Illustrative · not live telemetry</span></div>
    <div className="demo-canvas" ref={canvasRef}>
      <svg className="demo-wires" viewBox={`0 0 ${wireLayout.width} ${wireLayout.height}`} preserveAspectRatio="none" aria-hidden="true">
        {diagramEdges.map(edge => {
          const geometry = wireLayout.edges[edge.id];
          return <path
            key={edge.id}
            data-edge={edge.id}
            data-source={edge.source}
            data-target={edge.target}
            className={`demo-wire${step === edge.activeStep ? " is-active" : ""}${edge.kind === "feedback" ? " is-feedback" : ""}`}
            d={geometry?.path ?? ""}
          />;
        })}
        {diagramEdges.map(edge => {
          const geometry = wireLayout.edges[edge.id];
          return geometry?.tailPath
            ? <path key={`${edge.id}-tail`} className={`demo-wire-feedback-tail${step === edge.activeStep ? " is-active" : ""}`} d={geometry.tailPath}/>
            : null;
        })}
        {diagramEdges.map(edge => {
          const geometry = wireLayout.edges[edge.id];
          return geometry?.arrowPoints
            ? <polygon
              key={`${edge.id}-arrow`}
              data-arrow-for={edge.id}
              data-source={edge.source}
              data-target={edge.target}
              className={`demo-arrowhead${step === edge.activeStep ? " is-active" : ""}${edge.kind === "feedback" ? " is-feedback" : ""}`}
              points={geometry.arrowPoints}
            />
            : null;
        })}
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
