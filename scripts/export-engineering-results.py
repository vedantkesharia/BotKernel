"""Curate NEW local measurements; never overwrite raw runs or prior exports."""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from botkernel.benchmark_analysis import analyze


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data)


def dump(path,value):
    write(path,json.dumps(value,indent=2,allow_nan=False).encode())


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(values):
    values=[v for v in values if v is not None]
    return {'n':len(values),'median':statistics.median(values) if values else None,
            'min':min(values) if values else None,'max':max(values) if values else None}


def role(name):
    for r in ('api','publisher','worker','postgres','kafka','redis'):
        if name.endswith('-'+r+'-1'):return r
    return 'other'


def mib(text):
    match=re.match(r'([0-9.]+)([KMG]?i?B)',text.strip())
    if not match:return None
    scales={'B':1/1024**2,'kB':1000/1024**2,'KB':1000/1024**2,'KiB':1/1024,
            'MB':1000**2/1024**2,'MiB':1,'GB':1000**3/1024**2,'GiB':1024}
    return float(match[1])*scales[match[2]]


def export_comparison(source,out):
    plan=json.loads((source/'plan.json').read_text())
    records=[];groups=defaultdict(list);hashes=defaultdict(set)
    for path in sorted(source.glob('*/environment.json')):
        env=json.loads(path.read_text());assert env['status']=='COMPLETE'
        env['source_sha256']={k.replace('\\','/'):v for k,v in env['source_sha256'].items()}
        parent=path.parent;raw_path=next(parent.glob('*/raw.json'))
        raw=json.loads(raw_path.read_text());summary=raw['summary']
        assert summary['confirmed_effects']==summary['requested']
        assert all(r['state']=='SUCCEEDED' and r['receipts']==r['effects']==1 and r['published']
                   for r in summary['authoritative_rows'])
        assert all(r['version']==r['effect_count']==r['max_effect_version'] for r in summary['resource_versions'])
        spans=[]
        for p in sorted((parent/'telemetry').glob('*.jsonl')):
            spans.extend(json.loads(line) for line in p.read_text().splitlines() if line)
        stage=analyze(raw,spans)
        resources=[]
        for sample in json.loads((parent/'docker-stats.json').read_text()):
            resources.append({'monotonic':sample['monotonic'],'sampling_seconds':sample.get('sampling_seconds'),
                'containers':[{'role':role(r['Name']),'cpu_percent_one_core':float(r['CPUPerc'].strip('%')),
                               'memory_mib':mib(r['MemUsage'].split('/')[0])}
                              for r in sample.get('containers',[])]})
        record={'label':env['label'],'poll_seconds':env['poll_seconds'],'repeat':env['repeat'],
                'actions':summary['requested'],'concurrency':summary['concurrency'],
                'confirmed_effects':summary['confirmed_effects'],'total_effects_with_warmup':len(summary['authoritative_rows']),
                'effects_per_second':summary['confirmed_effects_per_second'],'admission_ms':summary['admission_ms'],
                'completion_ms':summary['completion_ms'],'measurement_seconds':summary['measurement_seconds'],
                'environment':summary['environment'],'memory_available_before_bytes':env['memory_available_before_bytes'],
                'stage_metrics':stage['metrics'],'stage_coverage':stage['stage_coverage'],
                'source_sha256':env['source_sha256'],'docker_stats':resources,
                'evidence_dir':'execution/'+parent.name,'raw_sha256':digest(raw_path)}
        target=out/record['evidence_dir']
        write(target/'raw.json.gz',gzip.compress(raw_path.read_bytes(),mtime=0))
        write(target/'spans.jsonl.gz',gzip.compress(('\n'.join(json.dumps(x,separators=(',',':')) for x in spans)+'\n').encode(),mtime=0))
        dump(target/'stage-analysis.json',stage)
        dump(target/'resources.json',resources)
        records.append(record);groups[(record['actions'],record['concurrency'],record['poll_seconds'])].append(record)
        for filename in ('worker.py','core.py','api.py','observability.py','real_benchmark.py','benchmark_runtime.py'):
            hashes[filename].add(env['source_sha256']['botkernel/'+filename])
    assert len(records)==18 and all(len(v)==3 for v in groups.values())
    assert all(len(v)==1 for v in hashes.values()),'Measured runtime source changed between conditions'
    aggregate=[]
    for (n,c,poll),runs in sorted(groups.items()):
        aggregate.append({'actions':n,'concurrency':c,'poll_seconds':poll,'runs':3,
            'effects_per_second':describe([r['effects_per_second'] for r in runs]),
            'admission_ms':{p:describe([r['admission_ms'][p] for r in runs]) for p in ('p50','p95','p99')},
            'completion_ms':{p:describe([r['completion_ms'][p] for r in runs]) for p in ('p50','p95','p99')},
            'stage_metrics':{name:{p:describe([r['stage_metrics'][name][p] for r in runs])
                                  for p in ('p50','p95','p99')} for name in runs[0]['stage_metrics']}})
    result={'plan':plan,'measured_effects':sum(r['confirmed_effects'] for r in records),
            'effects_including_warmup':sum(r['total_effects_with_warmup'] for r in records),
            'recorded_runtime_hashes':{k:next(iter(v)) for k,v in hashes.items()},'groups':aggregate,'runs':records,
            'limitations':['Shared WSL2 Docker host,12virtual CPUs,7.58GiB engine RAM; competing historical containers remained running.',
                '3short runs per cell,24-80actions each; median and min/max are descriptive, not confidence intervals.',
                'Completion includes50ms polling; stage percentiles overlap and must not be added.',
                'Outbox wait is a cross-process span-boundary proxy: negative observations retained, not literal negative queue time.',
                'Docker samples cover API/publisher/worker/shared infrastructure, warmup/client startup/end; exclude client container and other host processes.',
                'Concurrent diagram-browser review overlapped later runs; interleaving does not remove shared-host noise.',
                'No independent post-load drain-duration measurement; authoritative end state proves submitted outboxes published.',
                'Unimported fault helper files changed during runs; six measured runtime modules had identical recorded hashes.']}
    dump(out/'execution-summary.json',result)
    with (out/'execution-summary.csv').open('x',newline='') as stream:
        w=csv.writer(stream);w.writerow(['actions','clients','poll_ms','repeats','effects_per_second_median','effects_per_second_min','effects_per_second_max','admission_p50_ms','admission_p95_ms','admission_p99_ms','completion_p50_ms','completion_p95_ms','completion_p99_ms'])
        for g in aggregate:w.writerow([g['actions'],g['concurrency'],g['poll_seconds']*1000,3,*[g['effects_per_second'][p] for p in ('median','min','max')],*[g['admission_ms'][p]['median'] for p in ('p50','p95','p99')],*[g['completion_ms'][p]['median'] for p in ('p50','p95','p99')]])
    return result


def export_faults(source,out):
    cases=[]
    for p in sorted(source.glob('*/*/recovery.json')):
        d=json.loads(p.read_text());after=d['after_recovery']
        assert after['state']=='SUCCEEDED' and after['receipts']==after['effects']==after['version']==1
        if 'case' not in d:d['case']='receipt_crash_and_duplicate'
        target=out/'faults'/p.parent.name;dump(target/'recovery.json',d)
        events=[]
        for log in p.parent.glob('*.log'):
            for line in log.read_text(errors='replace').splitlines():
                try:row=json.loads(line)
                except ValueError:continue
                events.append({k:row[k] for k in ('timestamp','event','action.id','trace_id','service','botkernel.outcome') if k in row})
        write(target/'events.jsonl',('\n'.join(json.dumps(e,separators=(',',':')) for e in events)+'\n').encode())
        cases.append(d)
    assert len(cases)==5 and len({c['action_id'] for c in cases})==5
    result={'cases':cases,'unresolved':0,'unique_effects':5,'notes':['3receipt-crash repeats;1publisher-crash and1pause case; timing boundaries differ.','Each receipt case injects1acknowledged duplicate; publisher case replays after ACK-before-outbox-commit crash.']}
    dump(out/'fault-summary.json',result)


def export_controller(sources,out):
    runs=[];groups=defaultdict(list);seeds=set();digests=defaultdict(set)
    for source in sources:
        raw_path=source/'raw.json';d=json.loads(raw_path.read_text());assert not seeds.intersection(d['seeds']);seeds.update(d['seeds'])
        write(out/'controller'/d['run_id']/'raw.json.gz',gzip.compress(raw_path.read_bytes(),mtime=0))
        runs+=d['runs']
        for r in d['runs']:
            groups[(r['scenario'],r['mode'])].append(r);digests[(r['scenario'],r['seed'])].add(r['input_digest'])
    assert len(seeds)==10 and len(runs)==240 and all(len(s)==1 for s in digests.values())
    results=[]
    for (scenario,mode),rows in sorted(groups.items()):
        totals={key:sum(r[key] for r in rows) for key in ['episode_true_positives','episode_false_positives','episode_false_negatives','tp','fp','fn','tn','alert_onsets_outside_truth','unmatched_alerts_overlapping_truth']}
        tp,fp,fn=(totals[k] for k in ('episode_true_positives','episode_false_positives','episode_false_negatives'))
        means={k:{'n':sum(r[k] is not None for r in rows),'mean':statistics.mean(r[k] for r in rows if r[k] is not None) if any(r[k] is not None for r in rows) else None} for k in ['oscillating_resource_changes','intervention_count','mean_episode_detection_delay_ticks','time_to_recovery_ticks','sustained_stabilization_success','incident_recurrences','application_latency_p95_ms','logical_actions_per_virtual_second','containment_active_ticks']}
        results.append({'scenario':scenario,'mode':mode,'seeds':len(rows),'totals':totals,'means':means,
            'episode_precision':tp/(tp+fp) if tp+fp else None,'episode_recall':tp/(tp+fn) if tp+fn else None,
            'tick_false_positive_rate':totals['fp']/(totals['fp']+totals['tn']) if totals['fp']+totals['tn'] else None})
    dump(out/'controller-summary.json',{'kind':'virtual_simulation','seeds':sorted(seeds),'duration_ticks':120,'scenario_policy_runs':240,'groups':results,'note':'Identical predeclared inputs per seed across3policies; episode precision penalizes fragmentation, not just false onsets.'})
    with (out/'controller-summary.csv').open('x',newline='') as stream:
        w=csv.writer(stream);w.writerow(['scenario','policy','seeds','episode_precision','episode_recall','false_onsets','tick_false_positive_rate','reversals_mean','interventions_mean','modeled_p95_ms','logical_actions_per_virtual_second'])
        for r in results:w.writerow([r['scenario'],r['mode'],r['seeds'],r['episode_precision'],r['episode_recall'],r['totals']['alert_onsets_outside_truth'],r['tick_false_positive_rate'],*[r['means'][k]['mean'] for k in ('oscillating_resource_changes','intervention_count','application_latency_p95_ms','logical_actions_per_virtual_second')]])


def plot(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4));fig.set_facecolor('#faf9fc')
    for ax in axes:ax.set_facecolor('#faf9fc');ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    for i,poll in enumerate((.2,.02)):
        groups=sorted([g for g in result['groups'] if g['poll_seconds']==poll],key=lambda x:x['actions'])
        for ax,metric in zip(axes,('effects_per_second','completion_p95')):
            values=[g['effects_per_second'] if metric=='effects_per_second' else g['completion_ms']['p95'] for g in groups]
            med=[v['median'] for v in values];lo=[v['median']-v['min'] for v in values];hi=[v['max']-v['median'] for v in values]
            ax.bar([n+(i-.5)*.32 for n in range(3)],med,width=.30,color=('#34313d','#8054be')[i],label=f'{poll*1000:.0f}ms poll',yerr=[lo,hi],capsize=3)
    axes[0].set_ylabel('Confirmed unique effects / second');axes[1].set_ylabel('Completion p95 (milliseconds)')
    for ax in axes:ax.set_xticks(range(3),['24 actions / 1 client','48 / 4','80 / 8']);ax.legend(frameon=False,fontsize=9)
    fig.suptitle('Publisher polling tradeoff on a shared local host',fontsize=14,fontweight='bold')
    fig.text(.5,.015,'Median of 3 runs; whiskers show min–max. Not peak capacity or production SLOs.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.94));fig.savefig(path,format='svg',metadata={'Date':None});plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--comparison',required=True,type=Path);p.add_argument('--faults',required=True,type=Path);p.add_argument('--controllers',nargs=2,required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    result=export_comparison(args.comparison,args.output);export_faults(args.faults,args.output);export_controller(args.controllers,args.output)
    plot(result,args.output/'polling-tradeoff.svg')
    manifest={str(f.relative_to(args.output)):digest(f) for f in args.output.rglob('*') if f.is_file()}
    dump(args.output/'SHA256.json',manifest)
    print(json.dumps({'runs':18,'measured_effects':result['measured_effects'],'with_warmup':result['effects_including_warmup'],'output':str(args.output)}))


if __name__=='__main__':main()
