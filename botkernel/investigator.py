"""Read-only deterministic investigation over incident-linked committed effects."""
from typing import TypedDict, Any, Literal
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy import text
from langgraph.graph import StateGraph, START, END
from botkernel.core import engine
from botkernel.effect_relationships import is_contiguous_reversal

class Finding(BaseModel):
    classification: Literal["VERIFIED_FACT", "DETERMINISTIC_INFERENCE", "HYPOTHESIS"]
    description: str = Field(max_length=500)
    supporting_actions: list[str] = Field(default_factory=list, max_length=100)
    contradicting_actions: list[str] = Field(default_factory=list, max_length=100)

class Investigation(BaseModel):
    investigation_id: str
    incident_id: int
    timestamp: datetime
    status: str
    resource: str
    provider: str = "deterministic_mock"
    outcome: Literal["COMPLETE", "INSUFFICIENT_EVIDENCE"]
    contributing_agents: list[str]
    evidence_warnings: list[str]
    effects: list[dict[str, Any]]
    reversals: list[list[str]]
    transitions: list[dict[str, Any]]
    missing_references: list[str]
    conclusion: str
    recommendation: str
    findings: list[Finding] = Field(default_factory=list, max_length=200)
    human_approval_required: bool = True
    uncertainty: str = "Direction reversals are correlations, not proof of causation."
    model_id: str | None = None
    usage: dict[str, int | str | None] = Field(default_factory=dict)
    ai_analysis: dict[str, Any] | None = None

class State(TypedDict, total=False):
    incident_id: int
    provider: str
    run_id: str
    incident: dict
    refs: list[str]
    effects: list[dict]
    transitions: list[dict]
    reversals: list[list[str]]
    missing: list[str]
    report: dict
    warnings: list[str]

def load(state):
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        c.execute(text("SET LOCAL statement_timeout = '5s'"))
        row=c.execute(text("SELECT id,resource,status,score,evidence FROM incidents WHERE id=:id"),{'id':state['incident_id']}).mappings().first()
        if not row: raise ValueError("incident not found")
        transitions=[dict(x) for x in c.execute(text("SELECT transition,occurred_at,score FROM incident_transitions WHERE incident_id=:id ORDER BY id LIMIT 100"),{'id':state['incident_id']}).mappings()]
    incident=dict(row); evidence=incident['evidence']; warnings=[]; refs=[]
    if not isinstance(evidence,dict):
        evidence={}; warnings.append('Malformed incident evidence')
    for key in ('origin','last_detection'):
        snapshot=evidence.get(key)
        if snapshot is None: continue
        if not isinstance(snapshot,dict) or not isinstance(snapshot.get('actions',[]),list):
            warnings.append('Malformed '+key+' action references'); continue
        for ref in snapshot.get('actions',[]):
            if isinstance(ref,str): refs.append(ref)
            else: warnings.append('Malformed action reference')
    refs=list(dict.fromkeys(refs))
    if len(refs)>100: warnings.append('Action references truncated')
    if len(transitions)==100: warnings.append('Transitions may be truncated')
    if not transitions: warnings.append('No transition history')
    return {'incident':incident,'refs':refs[:100],'transitions':transitions,'warnings':warnings}

def retrieve(state):
    from uuid import UUID
    valid=[]
    for ref in state['refs']:
        try: valid.append(str(UUID(ref)))
        except (ValueError,TypeError): pass
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        c.execute(text("SET LOCAL statement_timeout = '5s'"))
        effects=[dict(x) for x in c.execute(text("SELECT e.action_id,e.agent,e.resource,e.version,e.before_capacity,e.after_capacity,e.latency,e.observed_at,a.state FROM effects e JOIN actions a ON a.id=e.action_id WHERE e.resource=:resource AND CAST(e.action_id AS text)=ANY(:refs) ORDER BY e.version LIMIT 100"),{'resource':state['incident']['resource'],'refs':valid}).mappings()]
    for e in effects: e['action_id']=str(e['action_id'])
    return {'effects':effects,'missing':[r for r in state['refs'] if r not in {e['action_id'] for e in effects}]}

def correlate(state):
    effects=state['effects']; pairs=[]; warnings=list(state.get('warnings',[]))
    for a,b in zip(effects,effects[1:]):
        if is_contiguous_reversal(a,b):
            pairs.append([a['action_id'],b['action_id']])
    if any(b['version'] != a['version'] + 1 or b['before_capacity'] != a['after_capacity'] for a,b in zip(effects,effects[1:])):
        warnings.append('Effect history has a version or capacity gap')
    return {'reversals':pairs,'warnings':warnings}

def report(state):
    enough=bool(state['reversals']) and not state['missing'] and not state['warnings'] and all(e['state']=='SUCCEEDED' for e in state['effects'])
    findings=[Finding(classification='VERIFIED_FACT',description='Committed resource capacity change.',supporting_actions=[e['action_id']]) for e in state['effects']]
    findings += [Finding(classification='DETERMINISTIC_INFERENCE',description='Consecutive cross-agent changes reversed direction.',supporting_actions=pair) for pair in state['reversals']]
    if enough:
        findings.append(Finding(classification='HYPOTHESIS',description='Independent agent objectives may contribute to the observed oscillation; further verification is required.',supporting_actions=state['reversals'][0]))
    result=Investigation(findings=findings,outcome='COMPLETE' if enough else 'INSUFFICIENT_EVIDENCE',contributing_agents=sorted({e['agent'] for e in state['effects']}),evidence_warnings=state['warnings'],investigation_id=str(uuid4()),incident_id=state['incident_id'],timestamp=datetime.now(timezone.utc),status=state['incident']['status'],resource=state['incident']['resource'],effects=state['effects'],reversals=state['reversals'],transitions=state['transitions'],missing_references=state['missing'],conclusion="Opposing cross-agent changes were observed." if enough else "Insufficient verified evidence for a cross-agent reversal conclusion.",recommendation="Review the controller hold and committed evidence before any action." if enough else "Review missing evidence; no remediation is recommended.")
    return {'report':result.model_dump(mode='json')}

def ai_assist(state):
    report=state['report']
    provider=state.get('provider','deterministic_mock')
    if provider!='bedrock':
        return {'report':report}
    report['provider']='bedrock'
    if report['outcome']!='COMPLETE' or report['evidence_warnings'] or report['missing_references']:
        report['ai_analysis']={
            'status':'INSUFFICIENT_EVIDENCE','explanation':'AI reasoning abstained because deterministic evidence is incomplete.',
            'hypotheses':[],'cross_agent_analysis':'','instability_mechanism':'',
            'supporting_references':[],'contradictory_or_missing_evidence':report['evidence_warnings']+report['missing_references'],
            'preventive_actions':[],'confidence_caveats':['No Bedrock inference was invoked.'],
        }
        report['usage']={'invocations':0,'input_tokens':0,'output_tokens':0}
        return {'report':report}
    from botkernel.bedrock import BedrockConverse, BedrockProviderError, InvestigationAnalysis
    effects=report['effects'][:20]
    transitions=report['transitions'][:20]
    payload={
        'incident':{'id':report['incident_id'],'status':report['status'],'resource':report['resource'],'score':state['incident']['score']},
        'effects':effects,'transitions':transitions,'reversals':report['reversals'][:20],
        'agents':report['contributing_agents'],'evidence_gaps':report['evidence_warnings']+report['missing_references'],
        'deterministic_findings':[item for item in report['findings'] if item['classification']!='HYPOTHESIS'],
    }
    valid_refs={f"incident:{report['incident_id']}"}|{item['action_id'] for item in effects}
    action_refs=valid_refs-{f"incident:{report['incident_id']}"}
    system=(
        'You are an advisory incident analyst. Use only supplied evidence. Do not execute tools, '
        'write SQL, propose automated remediation, or state speculation as fact. Return JSON matching '
        'the schema. Supporting references must be exact supplied action IDs or incident:<id>. '
        'All hypotheses remain hypotheses; causal direction reversals are not proof.'
    )
    try:
        analysis,usage=BedrockConverse().invoke_json(
            run_id=state.get('run_id',report['investigation_id']),system=system,payload=payload,
            response_type=InvestigationAnalysis,
        )
    except BedrockProviderError:
        raise
    if (
        any(ref not in valid_refs for ref in analysis.supporting_references)
        or _contains_unrecognized_reference(analysis.model_dump(),valid_refs)
        or (analysis.hypotheses and not any(
            ref in action_refs for ref in analysis.supporting_references
        ))
    ):
        raise BedrockProviderError('invalid_evidence_reference')
    report['model_id']=usage['model_id']
    report['usage']={key:usage.get(key) for key in ('provider','model_id','input_tokens','output_tokens','invocations')}
    report['ai_analysis']={'status':'COMPLETE',**analysis.model_dump()}
    for hypothesis in analysis.hypotheses:
        report['findings'].append({
            'classification':'HYPOTHESIS','description':hypothesis,
            'supporting_actions':[ref for ref in analysis.supporting_references if ref in valid_refs and not ref.startswith('incident:')],
            'contradicting_actions':[],
        })
    return {'report':report}

def _contains_unrecognized_reference(value, allowed):
    import re
    pattern=re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\bincident:\d+\b",re.IGNORECASE)
    if isinstance(value,str): return any(match.group(0).lower() not in {item.lower() for item in allowed} for match in pattern.finditer(value))
    if isinstance(value,dict): return any(_contains_unrecognized_reference(item,allowed) for item in value.values())
    if isinstance(value,(list,tuple)): return any(_contains_unrecognized_reference(item,allowed) for item in value)
    return False

g=StateGraph(State)
for name,fn in [('load_incident',load),('retrieve_effects',retrieve),('correlate',correlate),('report',report),('ai_assist',ai_assist)]: g.add_node(name,fn)
g.add_edge(START,'load_incident'); g.add_edge('load_incident','retrieve_effects'); g.add_edge('retrieve_effects','correlate'); g.add_edge('correlate','report'); g.add_edge('report','ai_assist'); g.add_edge('ai_assist',END)
investigation_graph=g.compile()
