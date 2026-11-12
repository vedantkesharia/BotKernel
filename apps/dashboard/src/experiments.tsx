import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Evaluation, EvaluationSummary, get, post } from "./api";
import { Button } from "@/components/ui/button";

const scenarios = [
  ["oscillation", "Cost / performance oscillation"],
  ["healthy_scaling", "Healthy traffic ramp"],
  ["simultaneous_resources", "Independent resources"],
  ["overlapping_remediation", "Overlapping remediation"],
  ["cascade", "Cascading degradation"],
  ["recurrence", "Incident recurrence"],
  ["temporary_spike", "Temporary load spike"],
  ["worker_failure", "Execution worker failure"],
] as const;

const colors: Record<string, string> = { independent: "#c5c7bd", basic: "#e5b878", collective: "#a5e5c4" };
const fmt = (metric: EvaluationSummary[keyof EvaluationSummary] | undefined, digits = 2) => {
  if (!metric || typeof metric !== "object" || !("mean" in metric) || metric.mean === null) return "n/a";
  return Number(metric.mean).toFixed(digits);
};

export function Experiments() {
  const queryClient = useQueryClient();
  const [scenario, setScenario] = useState<(typeof scenarios)[number][0]>("oscillation");
  const [seedsInput, setSeedsInput] = useState("17,23,41");
  const [duration, setDuration] = useState(120);
  const [selectedId, setSelectedId] = useState("");
  const [formError, setFormError] = useState("");
  const history = useQuery({ queryKey: ["experiments"], queryFn: () => get<Evaluation[]>("/experiments") });
  const experiment = useQuery({
    queryKey: ["experiment", selectedId],
    queryFn: () => get<Evaluation>(`/experiments/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  useEffect(() => {
    if (!selectedId && history.data?.length) setSelectedId(history.data[0].run_id);
  }, [history.data, selectedId]);
  const start = useMutation({
    mutationFn: (body: { scenario: string; seeds: number[]; duration: number }) => post<Evaluation>("/experiments", body),
    onSuccess: async (result) => {
      setSelectedId(result.run_id);
      setFormError("");
      await queryClient.invalidateQueries({ queryKey: ["experiments"] });
      await queryClient.setQueryData(["experiment", result.run_id], result);
    },
  });

  const chartData = useMemo(() => {
    const points = experiment.data?.time_series ?? [];
    const byTick = new Map<number, Record<string, number>>();
    for (const point of points) {
      const row = byTick.get(point.tick) ?? { tick: point.tick };
      row[point.mode] = point.application_latency_ms;
      byTick.set(point.tick, row);
    }
    return [...byTick.values()].sort((a, b) => a.tick - b.tick);
  }, [experiment.data]);
  const harmfulRanges = useMemo(() => {
    const points = experiment.data?.time_series ?? [];
    const truth = [...new Set(points.filter((point) => point.ground_truth_harmful).map((point) => point.tick))].sort((a, b) => a - b);
    const ranges: { start: number; stop: number }[] = [];
    for (const tick of truth) {
      const last = ranges[ranges.length - 1];
      if (last && last.stop + 1 === tick) last.stop = tick;
      else ranges.push({ start: tick, stop: tick });
    }
    return ranges;
  }, [experiment.data]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const seeds = seedsInput.split(",").map((value) => Number(value.trim()));
    if (seeds.length < 1 || seeds.length > 5 || seeds.some((value) => !Number.isInteger(value) || value < 0 || value > 1_000_000) || new Set(seeds).size !== seeds.length) {
      setFormError("Enter 1–5 unique integer seeds between 0 and 1,000,000.");
      return;
    }
    if (!Number.isInteger(duration) || duration < 120 || duration > 180) {
      setFormError("Duration must be between 120 and 180 virtual seconds.");
      return;
    }
    setFormError("");
    start.mutate({ scenario, seeds, duration });
  }

  const selectedSummary = experiment.data?.summaries ?? [];
  return <div className="experiment-layout">
    <article className="experiment-launch">
      <div className="card-title"><div><p className="eyebrow">RESEARCH PROTOCOL / 01</p><h2>Configure a run</h2><p className="muted">One schedule. Three coordination strategies. Comparable virtual outcomes.</p></div><span className="status">SIMULATOR ONLY</span></div>
      <form className="experiment-form" onSubmit={submit}>
        <label>Scenario<select value={scenario} onChange={(event) => setScenario(event.target.value as (typeof scenarios)[number][0])}>{scenarios.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label>Random seeds<input value={seedsInput} onChange={(event) => setSeedsInput(event.target.value)} aria-label="Random seeds" /></label>
        <label>Duration (virtual seconds)<input type="number" min={120} max={180} step={10} value={duration} onChange={(event) => setDuration(Number(event.target.value))} aria-label="Duration (virtual seconds)" /></label>
        <div className="mode-legend">{Object.entries({ independent: "Independent agents", basic: "Locks + fixed cooldown", collective: "Collective controller" }).map(([id, label]) => <span key={id}><i style={{ background: colors[id] }} />{label}</span>)}</div>
        <Button type="submit" disabled={start.isPending}>{start.isPending ? "Running bounded comparison..." : "Run three-mode comparison"}</Button>
      </form>
      <p className="fine-print">{duration} virtual seconds per seed. The experiment runs the deterministic simulator only; no PostgreSQL/Kafka load is generated.</p>
      {formError && <p className="error" role="alert">{formError}</p>}
      {start.isError && <p className="error" role="alert">Experiment failed: {start.error.message}</p>}
    </article>

    <article className="experiment-history">
      <div className="card-title"><div><h2>Saved comparisons</h2><p className="muted">Persisted JSON and CSV runs from the backend.</p></div><button type="button" onClick={() => history.refetch()}>Refresh</button></div>
      {history.isError && <p className="error" role="alert">Unable to load saved experiments: {history.error.message}</p>}
      {history.isPending && <div className="skeleton" role="status">Loading recorded evaluations</div>}
      {!history.isPending && history.data?.length === 0 && <p className="empty">No experiment results have been recorded.</p>}
      <div className="saved-runs">{history.data?.map((run) => <button type="button" className={run.run_id === selectedId ? "saved-run selected" : "saved-run"} key={run.run_id} onClick={() => setSelectedId(run.run_id)}><b>{run.scenario}</b><small>{new Date(run.created_at).toLocaleString()} / {run.seeds.length} seeds</small></button>)}</div>
    </article>

    {experiment.isError && <article className="error" role="alert">Unable to load this result: {experiment.error.message}</article>}
    {experiment.data && <section className="experiment-results" aria-label="Experiment results">
      <div className="card-title"><div><p className="eyebrow">VIRTUAL SIMULATION OUTPUT</p><h2>{scenarios.find(([id]) => id === experiment.data?.scenario)?.[1] ?? experiment.data.scenario}</h2><p className="muted">Run {experiment.data.run_id} / seeds {experiment.data.seeds.join(", ")} / {experiment.data.duration_ticks} virtual seconds</p></div><div className="downloads">{Object.entries(experiment.data.artifacts).map(([name, path]) => <a key={name} href={`/api${path}`} download>{name}</a>)}</div></div>
      <div className="strategy-snapshots">{selectedSummary.map(row=><article key={row.mode}><div><i style={{background:colors[row.mode]}}/><b>{row.mode_label}</b></div><strong>{fmt(row.application_latency_p95_ms,1)}<small>ms p95 / simulated</small></strong><dl><div><dt>Interventions</dt><dd>{fmt(row.intervention_count,1)}</dd></div><div><dt>Oscillations</dt><dd>{fmt(row.oscillating_resource_changes,1)}</dd></div><div><dt>False-positive occupancy</dt><dd>{fmt(row.false_positive_rate)}</dd></div></dl></article>)}</div>
      <article className="chart-card"><div className="card-title"><div><h3>Application latency by virtual second</h3><p className="muted">Mean across selected seeds; shaded spans are scenario ground truth.</p></div><span className="unit">milliseconds / simulated</span></div>
        <div className="experiment-chart"><ResponsiveContainer><LineChart data={chartData} margin={{ top: 16, right: 24, left: 8, bottom: 4 }}><CartesianGrid stroke="#3b4038" strokeDasharray="4 4" /><XAxis dataKey="tick" interval="preserveStartEnd" minTickGap={28} stroke="#a5aba0" tickLine={false} /><YAxis stroke="#a5aba0" tickLine={false} width={66} label={{ value: "Latency (ms)", angle: -90, position: "insideLeft", fill: "#a5aba0" }} /><Tooltip contentStyle={{ background: "#222420", border: "1px solid #4b5148", borderRadius: 8 }} /><Legend />{harmfulRanges.map((range) => <ReferenceArea key={`${range.start}-${range.stop}`} x1={range.start} x2={range.stop} fill="#b55745" fillOpacity={0.12} />)}<Line key="independent" isAnimationActive={false} type="monotone" dataKey="independent" name="Independent" stroke={colors.independent} dot={false} strokeWidth={2} /><Line key="basic" isAnimationActive={false} type="monotone" dataKey="basic" name="Locks + cooldown" stroke={colors.basic} dot={false} strokeWidth={2} /><Line key="collective" isAnimationActive={false} type="monotone" dataKey="collective" name="Collective controller" stroke={colors.collective} dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer></div><p className="chart-caption">Horizontal axis: virtual seconds</p>
      </article>
      <article className="table-card"><div className="card-title"><div><h3>Strategy comparison</h3><p className="muted">Precision, recall, F1 and FP rate describe tick-level alarm occupancy, not incident triggers. Means and 95% normal-approximation intervals across seeds.</p></div></div>
        <MobileComparison rows={selectedSummary}/><div className="table-scroll"><table><thead><tr><th>Strategy</th><th>Precision</th><th>Recall</th><th>F1</th><th>FP rate</th><th>Oscillations</th><th>Interventions</th><th>Stabilization</th><th>App p95 ms</th></tr></thead><tbody>{selectedSummary.map((row) => <tr key={row.mode}><th><span className="strategy-dot" style={{ background: colors[row.mode] }} />{row.mode_label}</th><td>{fmt(row.precision)}<small>{interval(row.precision)}</small></td><td>{fmt(row.recall)}<small>{interval(row.recall)}</small></td><td>{fmt(row.f1)}<small>{interval(row.f1)}</small></td><td>{fmt(row.false_positive_rate)}</td><td>{fmt(row.oscillating_resource_changes, 1)}</td><td>{fmt(row.intervention_count, 1)}</td><td>{fmt(row.sustained_stabilization_success, 1)}</td><td>{fmt(row.application_latency_p95_ms, 1)}</td></tr>)}</tbody></table></div><p className="table-hint">Swipe horizontally to inspect all recorded measures. Confidence intervals require multiple distinct outcomes.</p>
      </article>
      <p className="fine-print">Admission/dispatch percentiles, CPU and memory are not measured by this discrete-event simulation. Downloaded raw artifacts include per-tick outcomes and effects; no backend throughput or production-performance claim is implied.</p>
    </section>}
  </div>;
}

function MobileComparison({ rows }: { rows: EvaluationSummary[] }) {
  const measures: { label: string; key: keyof EvaluationSummary; digits?: number }[] = [
    { label: "Precision", key: "precision" },
    { label: "Recall", key: "recall" },
    { label: "F1", key: "f1" },
    { label: "False positive rate", key: "false_positive_rate" },
    { label: "Oscillations", key: "oscillating_resource_changes", digits: 1 },
    { label: "Interventions", key: "intervention_count", digits: 1 },
    { label: "Stabilization", key: "sustained_stabilization_success", digits: 1 },
    { label: "App p95 / virtual ms", key: "application_latency_p95_ms", digits: 1 },
  ];
  return <div className="mobile-comparison">{rows.map((row) => <article className="mobile-strategy" key={row.mode}>
    <div className="mobile-strategy-title"><span className="strategy-dot" style={{ background: colors[row.mode] }} /><strong>{row.mode_label}</strong></div>
    <div className="mobile-metric-grid">{measures.map(({ label, key, digits }) => <div key={key}><span>{label}</span><strong>{fmt(row[key], digits)}</strong></div>)}</div>
  </article>)}</div>;
}

function interval(metric: EvaluationSummary[keyof EvaluationSummary]) {
  if (!metric || typeof metric !== "object" || !("ci95_low" in metric) || metric.ci95_low === null || metric.ci95_high === null) return "95% CI not estimable";
  return `95% CI ${Number(metric.ci95_low).toFixed(2)}–${Number(metric.ci95_high).toFixed(2)}`;
}
