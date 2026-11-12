import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowUpRight, Network, ShieldAlert, Zap, Server, Clock3 } from "lucide-react";
import { Link } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import type { Action, Agent, Resource, Incident, RuntimeHealth } from "./api";
import { Empty, Panel, Pill, SectionHeading, Time } from "./ui";

function actionBuckets(actions: Action[]) {
  const events = actions.map(action => ({ action, time: Date.parse(action.created_at) }))
    .filter(event => Number.isFinite(event.time));
  if (!events.length) return [];
  const last = Math.max(...events.map(event => event.time));
  const bucketMs = 10 * 60 * 1000;
  const end = Math.floor(last / bucketMs) * bucketMs;
  return Array.from({ length: 6 }, (_, index) => {
    const start = end - (5 - index) * bucketMs;
    const bucket = events.filter(event => event.time >= start && event.time < start + bucketMs);
    return {
      label: new Date(start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      succeeded: bucket.filter(event => event.action.state === "SUCCEEDED").length,
      other: bucket.filter(event => event.action.state !== "SUCCEEDED").length,
    };
  });
}

export function Overview({ agents, resources, actions, incidents, runtime, readiness, loading }: {
  agents: Agent[]; resources: Resource[]; actions: Action[]; incidents: Incident[]; runtime?: RuntimeHealth; readiness?: { status?: string; redis?: string }; loading: boolean;
}) {
  if (loading) return <div className="overview-loading" role="status">Loading control plane data<Skeleton className="route-skeleton"/></div>;
  const active = actions.filter(action => ["RESERVED", "DISPATCHED", "OUTCOME_UNKNOWN"].includes(action.state));
  const open = incidents.filter(incident => ["HOLD", "VERIFYING", "ESCALATED"].includes(incident.status));
  const healthy = agents.filter(agent => agent.healthy).length;
  const series = actionBuckets(actions);
  const databaseAndKafkaReady = readiness?.status === "ready";
  const apiHealthy = runtime?.status === "ok";

  const succeeded=actions.filter(a=>a.state==='SUCCEEDED').length;
  const failed=actions.filter(a=>a.state==='FAILED'||a.state==='ESCALATED').length;
  return <div className="command-overview">
    <div className="command-kpis">{[["Recent heartbeats",healthy,`${agents.length} registered identities`],["Succeeded",succeeded,`${failed} failed or escalated in ledger window`],["Active incidents",open.length,`${incidents.length} recorded incidents`],["In progress",active.length,"Current ledger window"]].map(([label,value,note])=><Panel key={label} className="command-kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></Panel>)}</div>
    <div className="command-primary"><Panel className="command-chart"><SectionHeading title="Execution activity" detail="10-minute buckets ending at the latest action"/>{series.length?<div style={{height:250}}><ResponsiveContainer width="100%" height="100%"><BarChart data={series}><CartesianGrid vertical={false} stroke="#303036"/><XAxis dataKey="label" tickLine={false} axisLine={false} stroke="#90909a" fontSize={11}/><YAxis allowDecimals={false} tickLine={false} axisLine={false} stroke="#90909a" fontSize={11} width={25}/><Tooltip contentStyle={{background:'#202024',border:'1px solid #44444d',borderRadius:8}}/><Bar dataKey="succeeded" name="Succeeded" fill="#b8c9bf" radius={[4,4,0,0]} isAnimationActive={false}/><Bar dataKey="other" name="Other states" fill="#c8a778" radius={[4,4,0,0]} isAnimationActive={false}/></BarChart></ResponsiveContainer></div>:<Empty title="No action activity" detail="The ledger returned no actions."/>}<small className="command-note">Latest 200 records. Creation timestamps, not measured throughput.</small></Panel>
    <Panel className="command-services"><SectionHeading title="Service readiness"/><div>{[['FastAPI',apiHealthy?'Healthy':'Unknown'],['PostgreSQL',databaseAndKafkaReady?'Ready':'Unknown'],['Kafka',databaseAndKafkaReady?'Reachable':'Unknown'],['Redis','Advisory'],['Controller','Not independently measured']].map(([name,status])=><div className="service-row" key={name}><span>{name}</span><span><i className={['Healthy','Ready','Reachable'].includes(status)?'good':''}/>{status}</span></div>)}</div><details><summary>Environment details</summary><p>{runtime?.deployment_target??'Local'} / simulator resources. Infrastructure actions are disabled.</p></details></Panel></div>
    <div className="command-secondary"><Panel className="hero-panel command-incidents"><SectionHeading title="Incident response" aside={<Link to="/app/incidents">View all <ArrowUpRight size={13}/></Link>}/>{incidents.length?incidents.slice(0,3).map(i=><Link className="response-row" to="/app/incidents" key={i.id}><ShieldAlert size={17}/><span><b>{i.resource}</b><small>#{i.id} ? {i.intervention_count} interventions ? {i.recurrence_count} recurrences</small></span><Pill tone={['HOLD','ESCALATED'].includes(i.status)?'warn':'good'}>{i.status}</Pill></Link>):<Empty title="No incidents recorded" detail="The controller has not recorded an incident."/>}</Panel>
    <Panel><SectionHeading title="Resource allocation" detail="Simulated capacity, committed PostgreSQL state"/>{resources.map(r=><div className="allocation-row" key={r.id}><div><b>{r.id}</b><span>{r.capacity} units <small>v{r.version}</small></span></div><div className="allocation-track"><span style={{width:`${resources.reduce((n,x)=>n+x.capacity,0)?r.capacity/resources.reduce((n,x)=>n+x.capacity,0)*100:0}%`}}/></div></div>)}<small className="command-note">Share of total allocated simulator capacity.</small></Panel></div>
    <Panel className="command-ledger"><SectionHeading title="Recent execution" aside={<Link to="/app/agents">Agent fleet <ArrowUpRight size={13}/></Link>}/><div className="ledger-table">{actions.slice(0,7).map(a=><div className="ledger-table-row" key={a.id}><span className="ledger-agent"><span>{a.agent.slice(0,1).toUpperCase()}</span>{a.agent}</span><span>{a.resource}</span><Pill tone={a.state==='SUCCEEDED'?'good':'warn'}>{a.state}</Pill><small><Time value={a.created_at}/></small><Link aria-label={`Inspect action ${a.id}`} to={`/app/graph?${new URLSearchParams({action:a.id,resource:a.resource})}`}><ArrowUpRight size={16}/></Link></div>)}</div></Panel>
  </div>;
}
