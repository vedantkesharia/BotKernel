import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Search, ArrowUpRight, Activity, CircleAlert, Radio, Eye, Workflow } from "lucide-react";
import type { Agent, Action, Incident } from "./api";
import { Empty, Panel, Pill, SectionHeading } from "./ui";

export function Fleet({ agents, actions, incidents, loading }: {
  agents: Agent[]; actions: Action[]; incidents: Incident[]; loading: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [scope, setScope] = useState<"all" | "recent" | "stale" | "decisions">("all");
  const rows = useMemo(() => agents.filter(agent => {
    const matchesText = agent.id.toLowerCase().includes(filter.toLowerCase());
    const matchesScope = scope === "all" || (scope === "recent" && agent.healthy) || (scope === "stale" && !agent.healthy) || (scope === "decisions" && Boolean(agent.latest_decision));
    return matchesText && matchesScope;
  }), [agents, filter, scope]);
  const current = rows.find(agent => agent.id === selected) ?? rows[0];
  const activity = actions.filter(action => action.agent === current?.id);
  const linked = incidents.filter(incident =>
    (incident.evidence?.last_detection ?? incident.evidence?.origin ?? incident.evidence?.latest)?.agents?.includes(current?.id ?? ""),
  );
  const role = current?.id.toLowerCase() === "cost" ? "Cost" : current?.id.toLowerCase() === "performance" ? "Performance" : "Agent";
  const identityLabel = role === "Agent" ? "AGENT IDENTITY" : `${role.toUpperCase()} AGENT`;
  const decision = current?.latest_decision;
  const providerLabel = !decision ? "Provider not recorded" : decision.provider === "bedrock" ? `Amazon Bedrock${decision.model_id ? ` · ${decision.model_id}` : ""}` : decision.provider === "ollama_local" ? `Local model${decision.model_id ? ` · ${decision.model_id}` : ""}` : "Deterministic policy";
  const decisionOutcome = decision?.gateway_approved ? (decision.effect_committed ? "Effect committed" : decision.action_status ?? "Accepted · ledger status unavailable") : decision?.decision === "NO_OP" ? "No action submitted" : decision?.error_category ? `Not admitted · ${decision.error_category}` : "No gateway-approved action recorded";
  return <div className="fleet-workspace">
    <Panel className="fleet-list">
      <SectionHeading eyebrow="REGISTRY" title="Agent identities" detail="Registry and heartbeat evidence" aside={<span className="count-chip">{agents.length} REGISTERED</span>}/>
      <div className="fleet-summary" aria-label="Agent registry summary">
        <div><Radio size={14}/><span><b>{agents.filter(agent => agent.healthy).length}</b><small>Recent heartbeat</small></span></div>
        <div><Activity size={14}/><span><b>{agents.filter(agent => agent.latest_decision).length}</b><small>Decision snapshots</small></span></div>
      </div>
      <label className="search-field"><Search size={16}/><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Search agent identity" aria-label="Search agents"/></label>
      <div className="fleet-filters" role="group" aria-label="Filter agent identities">
        {(["all", "recent", "stale", "decisions"] as const).map(option => <button key={option} type="button" aria-pressed={scope === option} className={scope === option ? "active" : ""} onClick={() => setScope(option)}>{option === "all" ? "All" : option === "recent" ? "Recent" : option === "stale" ? "Stale" : "Has decision"}</button>)}
      </div>
      <div className="fleet-rows">
        {rows.map(agent => {
          const recent = actions.filter(action => action.agent === agent.id);
          const outcome = agent.latest_decision?.action_status ?? (agent.latest_decision?.decision === "NO_OP" ? "NO OP" : agent.latest_decision?.decision ?? "No decision");
          return <button className={`fleet-row ${current?.id === agent.id ? "selected" : ""}`} key={agent.id} onClick={() => setSelected(agent.id)} aria-pressed={current?.id === agent.id}>
            <span className="agent-avatar"><Bot size={20}/></span>
            <span className="fleet-row-copy"><strong>{agent.id}</strong><small>{agent.latest_decision ? `${agent.latest_decision.provider}${agent.latest_decision.model_id ? ` · ${agent.latest_decision.model_id}` : ""}` : `${recent.length} ledger actions · no decision snapshot`}</small><span className="fleet-row-outcome">{outcome}</span></span>
            <span className={`agent-led ${agent.healthy ? "online" : ""}`} title={agent.healthy ? "Heartbeat received within the registry freshness window" : "Heartbeat is older than the registry freshness window"}/><ArrowUpRight size={14} className="row-arrow"/>
          </button>;
        })}
        {!loading && rows.length === 0 && <Empty title="No agents found" detail="Try a different identity or start a local simulator."/>}
      </div>
    </Panel>
    <div className="fleet-detail">{current ? <>
      <Panel className="identity-panel">
        <div className="identity-orbit"><Bot size={37}/><span className={current.healthy ? "orbit-live" : ""}/></div>
        <span className="overline">{identityLabel} / REGISTERED ID</span><h2>{current.id}</h2>
        <div className="identity-state"><Pill tone={current.healthy ? "good" : "warn"}>{current.healthy ? "HEARTBEAT RECENT" : "HEARTBEAT STALE"}</Pill><span>{providerLabel}</span></div>
        {!current.latest_decision && <p className="agent-kind-note">No decision snapshot is available from the status cache.</p>}
        <div className="identity-stats">
          <div><span>Last heartbeat</span><strong className="heartbeat-time"><time title={current.heartbeat}>{current.heartbeat ? new Intl.DateTimeFormat(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(new Date(current.heartbeat)) : "Not recorded"}</time></strong></div>
          <div><span>Actions in ledger window</span><strong>{activity.length}</strong></div>
          <div><span>Resources touched</span><strong>{new Set(activity.map(action => action.resource)).size}</strong></div>
          <div><span>Related incidents</span><strong>{linked.length}</strong></div>
        </div>
      </Panel>
      <Panel className="agent-workflow">
        <div className="decision-card-heading"><div><span className="overline">LATEST DECISION SNAPSHOT</span><h3>{decision?.decision.replaceAll("_", " ") ?? "No snapshot available"}</h3><p>Redis status cache · action outcome verified from the gateway ledger when linked</p></div><Pill tone={decision?.gateway_approved ? "good" : decision?.error_category ? "warn" : "neutral"}>{providerLabel}</Pill></div>
        {decision ? <>
          <div className="decision-facts">
            <div><span>Recommendation</span><b>{decision.decision === "PROPOSE" ? `${decision.proposed_delta > 0 ? "+" : ""}${decision.proposed_delta} capacity` : decision.decision === "NO_OP" ? "No capacity change" : "No valid proposal"}</b><small>{decision.resource || "Resource not reported"}</small></div>
            <div><span>Gateway / ledger outcome</span><b>{decisionOutcome}</b><small>{decision.action_id ? <Link to={`/graph?${new URLSearchParams({action:decision.action_id})}`}>Inspect action {decision.action_id.slice(0,8)} ↗</Link> : "No action ID in snapshot"}</small></div>
            <div><span>Decision time</span><b>Not supplied</b><small>The status snapshot has no decision timestamp.</small></div>
          </div>
          {decision.error_category && <div className="decision-error" role="status"><CircleAlert size={14}/><span>{decision.error_category}</span></div>}
          <details className="decision-evidence"><summary><Eye size={14}/> Reason, evidence & uncertainty</summary><p>{decision.reason || "No provider explanation was recorded."}</p><div className="decision-references"><span>References</span>{decision.evidence_references.length ? decision.evidence_references.map((reference,index)=>{
            const resource=reference.startsWith("resource:")?reference.slice("resource:".length):null;
            const action=reference.startsWith("action:")?reference.slice("action:".length):null;
            const href=resource?`/graph?${new URLSearchParams({resource})}`:action?`/graph?${new URLSearchParams({action})}`:null;
            return <span key={`${reference}-${index}`}>{href?<Link to={href}>{reference}</Link>:reference}</span>;
          }):<small>No evidence references supplied.</small>}</div>{decision.uncertainties.length>0&&<div className="decision-uncertainties"><b>Uncertainty</b><span>{decision.uncertainties.join(" · ")}</span></div>}{decision.input_tokens!==null||decision.output_tokens!==null?<small className="decision-usage">Inference usage: {decision.input_tokens??"?"} input / {decision.output_tokens??"?"} output tokens</small>:null}</details>
        </> : <div className="decision-missing"><CircleAlert size={15}/><span>This API response has no decision snapshot. The action list below remains the authoritative ledger view.</span></div>}
        <div className="workflow-contract"><div><span className="overline">EXECUTION WORKFLOW</span><small>Definition only · live stage timing is not available</small></div><Workflow size={15}/></div>
        <div className="workflow-rail" aria-label="Defined agent workflow: Observe, Analyze, Propose, Submit, Reconcile">{["Observe","Analyze","Propose","Submit","Reconcile"].map((step,index)=><div key={step}><span>{index+1}</span><b>{step}</b></div>)}</div>
      </Panel>
      <Panel className="agent-history">
        <SectionHeading eyebrow="POSTGRESQL ACTION LEDGER" title="Recent actions" detail="Authoritative execution outcomes"/>
        {activity.length ? activity.slice(0, 12).map(action => <div className="history-row" key={action.id}>
          <span className="history-icon"><Activity size={15}/></span>
          <div><strong>{action.resource}</strong><small><time title={action.created_at}>{new Intl.DateTimeFormat(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(new Date(action.created_at))}</time> / <Link to={`/graph?${new URLSearchParams({action:action.id})}`}>{action.id.slice(0,8)}</Link></small></div>
          <Pill tone={action.state === "SUCCEEDED" ? "good" : action.state === "FAILED" ? "danger" : "warn"}>{action.state}</Pill>
        </div>) : <Empty title="No recent actions" detail="This identity has no actions in the latest ledger window."/>}
      </Panel>
    </> : <Panel><Empty title="Select an agent" detail="Choose a registered identity to inspect its activity."/></Panel>}</div>
  </div>;
}
