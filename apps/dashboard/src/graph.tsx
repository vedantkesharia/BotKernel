import { useEffect, useMemo, useState } from "react";
import {useSearchParams} from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useReducedMotion } from "motion/react";
import { Background, Controls, ReactFlow, Handle, Position, MarkerType, type NodeProps, type Node } from "@xyflow/react";
import { Network, Search, Focus, GitCompareArrows, Database, Box, Eye, SlidersHorizontal, ChevronDown, Check } from "lucide-react";
import { Select } from "radix-ui";
import { get, type Graph, type Incident } from "./api";
import { Empty, Panel, Time } from "./ui";

type GraphNode = Node<{ label: string; kind: string; vertical: boolean }>;

function EvidenceNode({ data, selected }: NodeProps<GraphNode>) {
  const Icon = data.kind === "agent" ? Network : data.kind === "resource" ? Database : Box;
  return <div className={`evidence-node kind-${data.kind} ${selected ? "selected" : ""}`}>
    <Handle type="target" position={data.vertical ? Position.Top : Position.Left}/><div className="node-symbol"><Icon size={18}/></div>
    <div><small>{data.kind.toUpperCase()}</small><strong>{data.label}</strong></div><Handle type="source" position={data.vertical ? Position.Bottom : Position.Right}/>
  </div>;
}
const nodeTypes = { evidence: EvidenceNode };

function GraphSelect({ label, value, options, onChange, icon }: {
  label: string; value: string; options: { value: string; label: string }[];
  onChange: (value: string) => void; icon: React.ReactNode;
}) {
  return <Select.Root value={value} onValueChange={onChange}>
    <Select.Trigger className="graph-select-trigger" aria-label={label}>
      {icon}<Select.Value/><Select.Icon><ChevronDown size={14}/></Select.Icon>
    </Select.Trigger>
    <Select.Portal>
      <Select.Content className="graph-select-content" position="popper" sideOffset={6} collisionPadding={12}>
        <Select.Viewport className="graph-select-viewport">
          {options.map(option => <Select.Item className="graph-select-item" value={option.value} key={option.value}>
            <Select.ItemText>{option.label}</Select.ItemText>
            <Select.ItemIndicator><Check size={14}/></Select.ItemIndicator>
          </Select.Item>)}
        </Select.Viewport>
      </Select.Content>
    </Select.Portal>
  </Select.Root>;
}

export function GraphView() {
  const [params] = useSearchParams();
  const rawAction=params.get("action") ?? "";
  const linkedAction=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(rawAction) ? rawAction.toLowerCase() : "";
  const rawResource=params.get("resource") ?? "";
  const linkedResource=rawResource.length<=100 && /^[a-zA-Z0-9_-]+$/.test(rawResource) ? rawResource : "";
  const [windowSeconds, setWindowSeconds] = useState(3600);
  const [filter, setFilter] = useState("");
  const [chosen, setChosen] = useState<{ type: "node" | "edge"; id: string } | null>(linkedAction ? {type:"node",id:`action:${linkedAction}`} : null);
  const [incidentId, setIncidentId] = useState("");
  const [mobile, setMobile] = useState(() => window.matchMedia("(max-width: 700px)").matches);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 700px)");
    const update = () => setMobile(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const reduced = useReducedMotion();
  const graph = useQuery({ queryKey: ["graph", windowSeconds, linkedResource], queryFn: () => get<Graph>(`/graph?${new URLSearchParams({window:String(windowSeconds),...(linkedResource ? {resource:linkedResource} : {})})}`), refetchInterval: 10000 });
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: () => get<Incident[]>("/incidents"), refetchInterval: 10000 });
  const activeIncident = incidents.data?.find(incident => String(incident.id) === incidentId);
  const visible = useMemo(() => {
    const raw = graph.data;
    const highlighted = new Set((activeIncident?.evidence?.last_detection ?? activeIncident?.evidence?.origin ?? activeIncident?.evidence?.latest)?.actions ?? []);
    const matches = raw?.nodes.filter(node => !filter || node.label.toLowerCase().includes(filter.toLowerCase()) || node.id.toLowerCase().includes(filter.toLowerCase())) ?? [];
    const included = new Set(matches.map(node => node.id));
    if (filter && raw) {
      for (const edge of raw.edges) {
        if (included.has(edge.source) || included.has(edge.target)) {
          included.add(edge.source);
          included.add(edge.target);
        }
      }
    }
    const counts: Record<string, number> = { agent: 0, action: 0, resource: 0 };
    const filteredNodes = (raw?.nodes ?? []).filter(node => included.has(node.id));
    const agentTotal = filteredNodes.filter(node => node.kind === "agent").length;
    const actionTotal = filteredNodes.filter(node => node.kind === "action").length;
    const nodes = filteredNodes.map(node => {
      const index = counts[node.kind] ?? 0;
      counts[node.kind] = index + 1;
      const column = node.kind === "agent" ? 0 : node.kind === "action" ? 1 + (index % 2) : 3;
      const row = node.kind === "action" ? Math.floor(index / 2) : index;
      return {
        id: node.id, selected: chosen?.type === "node" && chosen.id === node.id, type: "evidence", data: { label: node.label, kind: node.kind, vertical: mobile },
        position: mobile
          ? { x: 0, y: (node.kind === "agent" ? index : node.kind === "action" ? agentTotal + index : agentTotal + actionTotal + index) * 78 }
          : { x: column === 0 ? 0 : column === 3 ? 820 : column === 1 ? 280 : 540, y: row * 78 + (node.kind === "action" ? 8 : 0) },
        className: highlighted.has(node.id.replace("action:", "")) ? "incident-node" : "",
      };
    });
    const edges = (raw?.edges ?? []).filter(edge => included.has(edge.source) && included.has(edge.target)).map(edge => ({
      ...edge,
      animated: !reduced && highlighted.has(edge.target.replace("action:", "")),
      markerEnd: { type: MarkerType.ArrowClosed, color: edge.inferred ? "#e4b477" : "#b2c8b3" },
      style: { stroke: edge.inferred ? "#e4b477" : "#91a799", strokeWidth: edge.inferred ? 2 : 1.4, strokeDasharray: edge.inferred ? "5 5" : undefined },
    }));
    return { nodes, edges };
  }, [graph.data, filter, activeIncident, reduced, chosen, mobile]);
  const selectedEffect = chosen?.type === "node" ? graph.data?.evidence.find(effect => `action:${effect.action_id}` === chosen.id) : undefined;
  const selectedEdge = chosen?.type === "edge" ? graph.data?.edges.find(edge => edge.id === chosen.id) : undefined;

  return <div className="graph-workspace">
    <div className="graph-toolbar">
      <div className="toolbar-title"><span className="overline">EVIDENCE EXPLORER</span><strong>{graph.data?.nodes.length ?? "?"} nodes <span>/</span> {graph.data?.edges.length ?? "?"} relationships</strong></div>
      <label className="search-field"><Search size={15}/><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Agent, resource, action ID" aria-label="Filter graph nodes"/></label>
      <GraphSelect label="Graph time window" value={String(windowSeconds)} onChange={value => setWindowSeconds(Number(value))} icon={<SlidersHorizontal size={15}/>} options={[{value:"300",label:"Last 5 minutes"},{value:"900",label:"Last 15 minutes"},{value:"3600",label:"Last hour"}]}/>
      <GraphSelect label="Highlight incident" value={incidentId || "all"} onChange={value => setIncidentId(value === "all" ? "" : value)} icon={<Focus size={15}/>} options={[{value:"all",label:"All evidence"},...(incidents.data ?? []).map(incident => ({value:String(incident.id),label:`Incident #${incident.id} / ${incident.resource}`}))]}/>
    </div>
    {linkedAction && !graph.isPending && !graph.isError && !graph.data?.evidence.some(effect=>effect.action_id===linkedAction) && <div role="status" className="graph-notice">The referenced action is not in this graph window. Choose a wider window (up to one hour); older or truncated evidence may be unavailable.</div>}
    {graph.isError && <div className="alert-error" role="alert">Graph evidence could not load: {graph.error.message}</div>}
    {graph.data?.truncated && <div className="graph-notice" role="status">Graph limited to 1,000 committed effects; narrow the time window to inspect more precisely.</div>}
    <div className="graph-layout">
      <div className="graph-stage">
        <div className="stage-caption"><span className="stage-kicker"><span/> COMMITTED EFFECT GRAPH</span><span>{windowSeconds / 60} MIN WINDOW</span></div>
        <div className={`graph ${visible.nodes.length < 8 ? "graph-sparse" : ""}`} aria-label="Effect graph canvas">
          <ReactFlow key={`${mobile}-${windowSeconds}-${visible.nodes.map(node => node.id).join("|")}`} fitView fitViewOptions={{ padding: .28, minZoom: mobile ? .75 : .65, maxZoom: 1.15 }} minZoom={.16} maxZoom={1.6} nodes={visible.nodes} edges={visible.edges} nodeTypes={nodeTypes} onNodeClick={(_, node) => setChosen({ type: "node", id: node.id })} onEdgeClick={(_, edge) => setChosen({ type: "edge", id: edge.id })} onPaneClick={() => setChosen(null)} colorMode="dark">
            <Background color="#41483d" gap={28} size={1}/><Controls showInteractive={false}/>
          </ReactFlow>
          {!graph.isPending && !graph.isError && !visible.nodes.length && <div className="graph-empty"><Empty title="No evidence in view" detail={filter ? "No committed effects match this filter. Clear it to see the graph." : "Choose a wider window or run the local bounded demo to create committed effects."}/></div>}
        </div>
        <div className="graph-legend"><span><i className="legend-observed"/> OBSERVED</span><span><i className="legend-inferred"/> INFERRED REVERSAL</span><span><i className="legend-incident"/> INCIDENT EVIDENCE</span></div>
      </div>
      <Panel className="graph-inspector">
        <span className="overline">EVIDENCE INSPECTOR</span>
        {chosen ? <>
          <div className="inspect-icon"><Eye size={22}/></div><h2>{chosen.type === "node" ? chosen.id.split(":")[0].toUpperCase() : selectedEdge?.kind ?? "RELATIONSHIP"}</h2><p className="inspect-id">{chosen.id}</p>
          {selectedEffect ? <div className="inspect-facts"><div><span>Agent</span><b>{selectedEffect.agent}</b></div><div><span>Resource</span><b>{selectedEffect.resource}</b></div><div><span>Capacity</span><b>{selectedEffect.before_capacity} to {selectedEffect.after_capacity}</b></div><div><span>Modeled latency</span><b>{selectedEffect.latency} ms</b></div><div><span>Committed</span><b><Time value={selectedEffect.observed_at}/></b></div></div>
            : selectedEdge ? <><p className="muted">{selectedEdge.inferred ? "Directional reversal inferred from successive committed changes. This is correlation, not causal proof." : "Relationship derived from a committed action record."}</p><div className="inspect-facts"><div><span>Source</span><b>{selectedEdge.source}</b></div><div><span>Target</span><b>{selectedEdge.target}</b></div></div></>
              : <p className="muted">{graph.data?.nodes.find(node => node.id === chosen.id)?.label}</p>}
        </> : <div className="inspector-empty"><GitCompareArrows size={31}/><h2>Trace a connection</h2><p>Select a node or edge to inspect its committed evidence and relationship type.</p></div>}
        <div className="inspector-foot">{graph.data?.evidence.length ?? 0} committed effects in window<br/>Temporal association is not causal proof.</div>
      </Panel>
    </div>
    <div className="selection" aria-live="polite">{chosen ? `Selected ${chosen.type}: ${chosen.id}` : "Select a node or edge to inspect evidence."}</div>
  </div>;
}
