"""Explicit local benchmark; retain new DBs/topics and stop only owned apps."""
import argparse
import copy
import math
import re
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def command(args, *, env=None, timeout=120):
    result = subprocess.run(args, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args[:5]}\n{result.stderr[-1500:]}")
    return result.stdout


def memory_available(postgres):
    text = command(['docker', 'exec', postgres, 'cat', '/proc/meminfo'])
    return int(next(line.split()[1] for line in text.splitlines() if line.startswith('MemAvailable:'))) * 1024


def sample_stats(names, stop, rows):
    while not stop.is_set():
        started = time.monotonic()
        try:
            raw = command(['docker', 'stats', '--no-stream', '--format', '{{json .}}', *names], timeout=15)
            rows.append({'monotonic': started, 'sampling_seconds': time.monotonic() - started,
                         'containers': [json.loads(line) for line in raw.splitlines() if line.strip()]})
        except Exception as error:
            rows.append({'monotonic': started, 'error_type': type(error).__name__})
        stop.wait(0.5)


def one_run(plan, count, concurrency, repeat, session):
    suffix = uuid.uuid4().hex[:12]
    project = 'bkpubbench-' + suffix
    database = 'bk_benchmark_' + suffix
    output = session / f"{plan.label}-n{count}-c{concurrency}-r{repeat}-{suffix}"
    output.mkdir()
    available = memory_available(plan.infrastructure_project + '-postgres-1')
    if available < 650 * 1024**2:
        raise RuntimeError('Less than 650 MiB available; refusing new apps without stopping unrelated projects')
    env = {**os.environ, 'BOTKERNEL_BENCHMARK_NETWORK': plan.infrastructure_project + '_default',
           'BOTKERNEL_BENCHMARK_IMAGE': plan.image, 'BENCHMARK_RESULTS_ROOT': str(output),
           'BENCHMARK_DATABASE': database, 'BENCHMARK_TOPIC': 'bkpubbench_' + suffix,
           'BENCHMARK_GROUP': 'bkpubbench_' + suffix, 'BENCHMARK_API_ALIAS': project + '-api',
           'BOTKERNEL_OPERATOR_TOKEN': secrets.token_urlsafe(48),
           'OUTBOX_POLL_INTERVAL_SECONDS': str(plan.poll_seconds)}
    base = ['docker', 'compose', '-p', project, '-f', 'benchmarks/compose.shared-system.yaml']
    def compose(*args, timeout=120):
        return command(base + list(args), env=env, timeout=timeout)
    metadata = {'kind': 'fault-matrix' if plan.recovery else 'closed-loop-throughput', 'project': project, 'database': database, 'topic': env['BENCHMARK_TOPIC'],
                'group': env['BENCHMARK_GROUP'], 'label': plan.label, 'actions': 5 if plan.recovery else count,
                'concurrency': concurrency, 'repeat': repeat, 'poll_seconds': plan.poll_seconds,
                'memory_available_before_bytes': available, 'shared_infrastructure': plan.infrastructure_project,
                'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (ROOT/'botkernel').glob('*.py')},
                'status': 'PREPARED'}
    (output/'environment.json').write_text(json.dumps(metadata, indent=2))
    stats, stop, sampler = [], threading.Event(), None
    try:
        command(['docker', 'exec', plan.infrastructure_project+'-postgres-1', 'createdb', '-U', 'botkernel', database])
        compose('run', '--rm', '--no-deps', 'benchmark', 'python', '-c',
                "from botkernel.core import initialize; initialize(); "
                "import os;from confluent_kafka.admin import AdminClient,NewTopic;"
                "a=AdminClient({'bootstrap.servers':os.environ['KAFKA_BOOTSTRAP_SERVERS']});"
                "[f.result(15) for f in a.create_topics([NewTopic(os.environ['KAFKA_TOPIC'],num_partitions=3,replication_factor=1)]).values()]")
        compose('up', '-d', 'api', 'publisher', 'worker')
        compose('run', '--rm', '--no-deps', 'benchmark', 'python', '-c',
                "import os,time,httpx;url=os.environ['BOTKERNEL_BENCHMARK_API_URL']+'/ready';"
                "\nfor i in range(40):\n try:\n  r=httpx.get(url,timeout=3);r.raise_for_status();break\n except Exception:\n  time.sleep(.5)\nelse: raise RuntimeError('private API not ready')")
        names = compose('ps', '-q', 'api', 'publisher', 'worker').split()
        names += [plan.infrastructure_project+'-'+service+'-1' for service in ('postgres','kafka','redis')]
        sampler = threading.Thread(target=sample_stats, args=(names,stop,stats), daemon=True)
        sampler.start()
        metadata['status'] = 'RUNNING'
        if plan.recovery:
            compose('stop', 'worker')
            for fault_repeat in range(3):
                text=compose('run','--rm','--no-deps','faults','python','-m','botkernel.real_benchmark_recovery',timeout=140)
                (output/f'worker-recovery-{fault_repeat+1}.json').write_text(text)
            compose('stop','publisher')
            for mode in ('publisher_crash','publisher_pause'):
                text=compose('run','--rm','--no-deps','faults','python','-m','botkernel.benchmark_failures','--mode',mode,timeout=140)
                (output/(mode+'.json')).write_text(text)
        else:
            text = compose('run', '--rm', '--no-deps', 'benchmark', 'python', '-m', 'botkernel.real_benchmark',
                           '--actions', str(count), '--concurrency', str(concurrency), '--warmup', '1', timeout=240)
            (output/'client-output.json').write_text(text)
        metadata['status'] = 'COMPLETE'
    except BaseException as error:
        metadata['status'] = 'FAILED'
        metadata['error_type'] = type(error).__name__
        (output/'failure.txt').write_text(str(error))
        raise
    finally:
        stop.set()
        if sampler:
            sampler.join(timeout=20)
        (output/'docker-stats.json').write_text(json.dumps(stats, indent=2))
        try:
            (output/'services.log').write_text(compose('logs', '--no-color', timeout=30))
            compose('down', '--timeout', '15', timeout=60)  # external network and all data retained
        finally:
            (output/'environment.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps({'directory':str(output.relative_to(ROOT)), 'status':metadata['status']}), flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--recovery',action='store_true',help='3 receipt/duplicate recoveries plus publisher crash/pause; no throughput workload')
    parser.add_argument('--infrastructure-project',default='bk-final-regression')
    parser.add_argument('--image',default='bk-final-regression-tests:latest')
    parser.add_argument('--actions',nargs='+',type=int,default=[24,48,80])
    parser.add_argument('--concurrency',nargs='+',type=int,default=[1,4,8])
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--poll-seconds',type=float,default=.2)
    parser.add_argument('--label',default='baseline')
    parser.add_argument('--compare-poll-seconds',type=float,default=None)
    args=parser.parse_args()
    if not args.execute:
        parser.error('--execute is required; this creates only NEW benchmark databases/topics/apps')
    if (len(args.actions)!=len(args.concurrency) or not 1<=args.repeats<=5
        or any(not 1<=c<=min(n,10) or n>200 for n,c in zip(args.actions,args.concurrency))):
        parser.error('bounded paired counts/concurrency required; <=200 actions, <=10 clients, <=5 repeats')
    if any(not math.isfinite(v) or not .01<=v<=5 for v in [args.poll_seconds]+([] if args.compare_poll_seconds is None else [args.compare_poll_seconds])):
        parser.error('poll intervals must be finite and between .01 and 5 seconds')
    if args.recovery and (args.repeats!=1 or len(args.actions)!=1 or args.compare_poll_seconds is not None):
        parser.error('recovery requires --repeats 1 and one actions/concurrency pair, no comparison')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',args.label) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,50}',args.infrastructure_project):
        parser.error('safe bounded label/infrastructure project names required')
    session=ROOT/'benchmarks/results' / ('portfolio-'+uuid.uuid4().hex)
    session.mkdir()
    (session/'plan.json').write_text(json.dumps(vars(args),indent=2))
    print('Predeclared session '+str(session.relative_to(ROOT)),flush=True)
    for repeat in range(1,args.repeats+1):
        for n,c in zip(args.actions,args.concurrency):
            variants=[args.poll_seconds]+([] if args.compare_poll_seconds is None else [args.compare_poll_seconds])
            if repeat%2==0: variants.reverse()
            for interval in variants:
                variant=copy.copy(args)
                variant.poll_seconds=interval
                variant.label=args.label if args.compare_poll_seconds is None else f'{args.label}-{interval*1000:.0f}ms'
                one_run(variant,n,c,repeat,session)


if __name__=='__main__':
    main()
