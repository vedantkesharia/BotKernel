import "./InvestigationReports.css";
import {Link} from "react-router-dom";
import {useEffect,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {get,post,type InvestigationResult} from "./api";
import {Panel,SectionHeading,Time} from "./ui";

const findingGroups = [
  { key: "VERIFIED_FACT", label: "Verified facts" },
  { key: "DETERMINISTIC_INFERENCE", label: "Deterministic inferences" },
  { key: "HYPOTHESIS", label: "Hypotheses · further verification required" },
] as const;

function evidenceLink(actionId: string, resource: string) {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(actionId)) return <code>{actionId}</code>;
  return <Link to={`/app/graph?${new URLSearchParams({ action: actionId, resource })}`}><code>{actionId}</code></Link>;
}

function EvidenceFindings({ findings, resource }: { findings: NonNullable<InvestigationResult["report"]>["findings"]; resource: string }) {
  return <div className="finding-groups">{findingGroups.map(group => {
    const matching = findings.filter(finding => finding.classification === group.key);
    if (!matching.length) return null;
    return <details open={group.key === "HYPOTHESIS"} className={`finding-group finding-${group.key.toLowerCase()}`} key={group.key}>
      <summary className="finding-group-heading"><h3>{group.label}</h3><span>{matching.length}</span></summary>
      {matching.map((finding, index) => <article className="finding-item" key={`${group.key}-${index}`}>
        <p>{finding.description}</p>
        {finding.supporting_actions.length > 0 && <div><small>Supporting</small>{finding.supporting_actions.map(id => <span key={id}>{evidenceLink(id, resource)}</span>)}</div>}
        {finding.contradicting_actions.length > 0 && <div><small>Contradicting</small>{finding.contradicting_actions.map(id => <span key={id}>{evidenceLink(id, resource)}</span>)}</div>}
      </article>)}
    </details>;
  })}</div>;
}

export function InvestigationReports({incidentId}:{incidentId:number}) {
  const qc=useQueryClient(); const [selected,setSelected]=useState<string | null>(null);
  const storageKey=`botkernel-investigation-pending-${incidentId}`;
  const reportStorageKey=`${storageKey}-report`;
  const reports=useQuery({queryKey:["investigations",incidentId],queryFn:()=>get<InvestigationResult[]>(`/incidents/${incidentId}/investigations`),refetchInterval:query=>query.state.data?.some(r=>r.status==="RUNNING")?3000:false});
  const analyze=useMutation({mutationFn:async()=>{
    const key=sessionStorage.getItem(storageKey) ?? crypto.randomUUID(); sessionStorage.setItem(storageKey,key);
    const result=await post<InvestigationResult>(`/incidents/${incidentId}/investigations`,{idempotency_key:key,provider:"deterministic_mock"});
    if (result.status==="RUNNING") sessionStorage.setItem(reportStorageKey,result.id);
    else { sessionStorage.removeItem(storageKey); sessionStorage.removeItem(reportStorageKey); }
    return result;
  },onSuccess:async result=>{setSelected(result.id); await qc.invalidateQueries({queryKey:["investigations",incidentId]});}});
  useEffect(()=>{
    const pendingId=sessionStorage.getItem(reportStorageKey);
    if (pendingId && reports.data?.some(r=>r.id===pendingId && r.status!=="RUNNING")) { sessionStorage.removeItem(storageKey); sessionStorage.removeItem(reportStorageKey); }
  },[reports.data,reportStorageKey,storageKey]);
  const report=reports.data?.find(r=>r.id===selected) ?? reports.data?.[0];
  const analysis=report?.report?.ai_analysis;
  const usage=report?.report?.usage;
  const bedrockCompleted=report?.provider==="bedrock" && analysis?.status==="COMPLETE";
  const providerLabel=!report?"NO SAVED REPORT":report.provider==="bedrock"
    ? bedrockCompleted
      ? `BEDROCK · ${report.report?.model_id ?? "MODEL UNKNOWN"} · ${usage?.input_tokens ?? "?"}/${usage?.output_tokens ?? "?"} TOKENS`
      : `BEDROCK · ${analysis?.status ?? "INFERENCE NOT RECORDED"}`
    : `${report.provider.toUpperCase()} · NO LLM`;
  const reportDescription=report?.provider==="bedrock"
    ? bedrockCompleted
      ? "Bedrock hypotheses are advisory; deterministic evidence remains authoritative."
      : "Bedrock was selected, but no completed inference is recorded. Deterministic evidence remains authoritative."
    : "Deterministic analysis — no LLM used";
  return <Panel className="investigation-report-panel"><SectionHeading eyebrow="EVIDENCE ANALYSIS" title="Saved investigations" detail={reportDescription} aside={<span className="analysis-actions"><span className="provider-label">{providerLabel}</span><button disabled={analyze.isPending || reports.data?.some(r=>r.status==="RUNNING")} onClick={()=>analyze.mutate()}>{analyze.isPending?"Analyzing...":"Analyze Incident"}</button></span>}/>
    {reports.isLoading && <p>Loading investigations...</p>}{reports.isError && <p role="alert">Could not load investigations: {reports.error.message}</p>}
    {analyze.isError && <p role="alert">Analysis failed: {analyze.error.message}. Retry uses the same request key.</p>}
    {reports.data?.length===0 && <p className="muted">No saved investigations for this incident.</p>}
    {reports.data && reports.data.length>0 && <label>Saved report <select value={report?.id ?? ""} onChange={e=>setSelected(e.target.value)}>{reports.data.map(r=><option key={r.id} value={r.id}>{r.status} / {r.id.slice(0,8)}</option>)}</select></label>}
    {report && <div className="investigation-report-content"><p><strong>{report.status}</strong> - {report.provider} - <Time value={report.created_at}/></p>{report.status==="RUNNING" && <p>Investigation is running.</p>}{report.status==="FAILED" && <p role="alert">Investigation failed: {report.error_category ?? "unknown"}.</p>}
      {report.report && <><p>{report.report.conclusion}</p><p>Resource: {report.report.resource} - Agents: {report.report.contributing_agents.join(", ") || "not recorded"}</p><p>{report.report.uncertainty}</p>
      {report.provider==="bedrock" && <section className="ai-investigation" aria-label="Bedrock-assisted analysis"><h3>AI-assisted analysis / advisory</h3><p>Provider: {report.provider} / model: {report.report.model_id ?? "not invoked"} / usage: {JSON.stringify(report.report.usage ?? {})}</p>{report.report.ai_analysis?.status==="COMPLETE"?<><p>{report.report.ai_analysis.explanation}</p><h4>Possible hypotheses</h4>{report.report.ai_analysis.hypotheses.map((item,index)=><p key={index}>{item}</p>)}<p>{report.report.ai_analysis.cross_agent_analysis}</p><p>{report.report.ai_analysis.instability_mechanism}</p><h4>Supporting references</h4>{report.report.ai_analysis.supporting_references.map(ref=><p key={ref}>{ref.startsWith("incident:")?<code>{ref}</code>:<Link to={`/graph?${new URLSearchParams({action:ref,resource:report.report!.resource}).toString()}`}><code>{ref}</code></Link>}</p>)}<h4>Uncertainties and missing evidence</h4>{[...report.report.ai_analysis.contradictory_or_missing_evidence,...report.report.ai_analysis.confidence_caveats].map((item,index)=><p key={index}>{item}</p>)}<h4>Preventive suggestions (require human approval)</h4>{report.report.ai_analysis.preventive_actions.map((item,index)=><p key={index}>{item}</p>)}</>:<p>{report.report.ai_analysis?.explanation ?? "AI reasoning unavailable or abstained."}</p>}<strong>Advisory only. Human approval is required; no remediation was executed.</strong></section>}
      {(report.report.evidence_warnings.length>0 || report.report.missing_references.length>0) && <p role="alert">Evidence limitations: {[...report.report.evidence_warnings,...report.report.missing_references].join(", ")}</p>}
      <h3>Committed effect timeline</h3><ol className="investigation-timeline">{[...report.report.effects].sort((a,b)=>a.version-b.version).map(e=><li key={e.action_id}><span className="effect-timeline-marker"/><div className="effect-timeline-copy"><Time value={e.observed_at}/><strong>{e.agent} · version {e.version}</strong><span>Capacity {e.before_capacity} → {e.after_capacity}</span>{evidenceLink(e.action_id,report.report!.resource)}</div></li>)}</ol>
      <h3>Evidence classification</h3><EvidenceFindings findings={report.report.findings} resource={report.report.resource}/>
      <p>Recommendation: {report.report.recommendation}</p><p>{report.report.human_approval_required ? "Human approval required for any proposed action." : "Approval requirement not indicated."}</p></>}
    </div>}
  </Panel>;
}
