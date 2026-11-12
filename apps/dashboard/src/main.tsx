import React, { Component, lazy, Suspense, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { Activity, Network, ShieldAlert, FlaskConical, Users, RefreshCw, Menu, Radio, Command } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetDescription, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { Action, Agent, Resource, Incident, RuntimeHealth } from "./api";
import { clearOperatorToken, get, hasOperatorToken, login, onUnauthorized } from "./api";
import { Pill } from "./ui";
import { Landing } from "./landing";
import "@xyflow/react/dist/style.css";
import "./style.css";
import "./experiments.css";
import "./neutral.css";

const Overview = lazy(() => import("./overview").then(m => ({ default: m.Overview })));
const Fleet = lazy(() => import("./fleet").then(m => ({ default: m.Fleet })));
const GraphView = lazy(() => import("./graph").then(m => ({ default: m.GraphView })));
const Investigations = lazy(() => import("./incidents").then(m => ({ default: m.Investigations })));
const Experiments = lazy(() => import("./experiments").then(m => ({ default: m.Experiments })));
const createQueryClient = () => new QueryClient({ defaultOptions: { queries: { retry: 1, refetchInterval: 10000, refetchOnWindowFocus: false } } });
const queryClient = createQueryClient();

const nav = [
  { url: "/app", name: "Mission control", icon: Activity },
  { url: "/app/agents", name: "Agent fleet", icon: Users },
  { url: "/app/graph", name: "Effect graph", icon: Network },
  { url: "/app/incidents", name: "Investigations", icon: ShieldAlert },
  { url: "/app/experiments", name: "Experiment lab", icon: FlaskConical },
];
const titles: Record<string, [string, string, string]> = {
  "/app": ["01 / SYSTEM", "Mission control", "The live operating picture for coordinated agents."],
  "/app/agents": ["02 / FLEET", "Agent fleet", "Independent processes, shared consequences."],
  "/app/graph": ["03 / EVIDENCE", "Effect graph", "Trace committed changes and inferred reversals."],
  "/app/incidents": ["04 / RESPONSE", "Investigations", "Follow the evidence from detection to operator decision."],
  "/app/experiments": ["05 / RESEARCH", "Experiment lab", "Compare coordination strategies on identical virtual workloads."],
};

class Boundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  render() {
    return this.state.error
      ? <div className="alert-error" role="alert">This view could not render. Reload the page to retry.</div>
      : this.props.children;
  }
}

function Navigation({ onNavigate, activeIncidents, runtime }: { onNavigate: () => void; activeIncidents: number; runtime?: RuntimeHealth }) {
  const isAwsDemo = runtime?.deployment_target === "aws-demo";
  const runtimeMode = runtime?.cloud_mode ?? runtime?.mode ?? "mode unknown";
  return <aside className="rail" aria-label="Primary navigation">
    <div className="brand-block">
      <NavLink to="/app" onClick={onNavigate} className="brand-mark">
        <span className="brand-glyph"><span/><span/><span/><span/></span>
        <span><strong>BotKernel</strong><small>COLLECTIVE RELIABILITY</small></span>
      </NavLink>
    </div>
    <div className="rail-caption">WORKSPACE <span>01</span></div>
    <div className="workspace-chip"><span className="workspace-icon">BK</span><span><b>{isAwsDemo ? "Private AWS demo" : "Local operations"}</b><small>{runtime ? `${runtimeMode} / ${runtime.resource_source ?? "resource source unknown"}` : "Runtime status unavailable"}</small></span></div>
    <div className="rail-caption">OPERATE</div>
    <nav>{nav.map(({ url, name, icon: Icon }) =>
      <NavLink key={url} end to={url} onClick={onNavigate} className={({ isActive }) => `rail-link ${isActive ? "active" : ""}`}>
        <Icon size={17} strokeWidth={1.7}/><span>{name}</span>{url === "/app/incidents" && activeIncidents > 0 && <i className="nav-alert"/>}
      </NavLink>
    )}</nav>
    <details className="environment-details"><summary><Radio size={14}/>{isAwsDemo ? "AWS demo" : "Local"}<span>{runtime ? "Connected" : "Unknown"}</span></summary><dl><dt>Source</dt><dd>{runtime?.resource_source ?? "Simulator"}</dd><dt>Mode</dt><dd>{runtimeMode}</dd><dt>Infrastructure actions</dt><dd>Disabled</dd><dt>Access</dt><dd>Authenticated operator</dd></dl></details>
  </aside>;
}

function App({ onSignOut }: { onSignOut: () => void }) {
  const { pathname } = useLocation();
  const path = pathname === "/app" ? "/app" : pathname;
  const [mobileOpen, setMobileOpen] = useState(false);
  const reduced = useReducedMotion();
  const qc = useQueryClient();
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => get<Agent[]>("/agents") });
  const runtime = useQuery({ queryKey: ["health"], queryFn: () => get<RuntimeHealth>("/health"), refetchInterval: 20000 });
  const actions = useQuery({ queryKey: ["actions"], queryFn: () => get<Action[]>("/actions") });
  const resources = useQuery({ queryKey: ["resources"], queryFn: () => get<Resource[]>("/resources") });
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: () => get<Incident[]>("/incidents") });
  const ready = useQuery({ queryKey: ["ready"], queryFn: () => get<{ status: string }>("/ready"), refetchInterval: 20000 });
  const meta = titles[path] ?? titles["/app"];
  const stale = [agents, actions, resources, incidents, runtime].some(q => q.isError);
  const activeIncidents = incidents.data?.filter(i => ["HOLD", "VERIFYING", "ESCALATED"].includes(i.status)).length ?? 0;
  const required = path === "/app" ? [agents, actions, resources, incidents] : path === "/app/agents" ? [agents, actions] : path === "/app/incidents" ? [incidents, actions] : [];
  const unavailable = required.some(query => query.data === undefined && query.isError);
  const awaiting = required.some(query => query.data === undefined && query.isPending);
  return <div className="app-frame">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="desktop-navigation"><Navigation onNavigate={() => {}} activeIncidents={activeIncidents} runtime={runtime.data}/></div>
    <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
      <SheetContent side="left" className="mobile-navigation" showCloseButton>
        <SheetTitle className="sr-only">Primary navigation</SheetTitle>
        <SheetDescription className="sr-only">Navigate BotKernel views.</SheetDescription>
        <Navigation onNavigate={() => setMobileOpen(false)} activeIncidents={activeIncidents} runtime={runtime.data}/>
      </SheetContent>
    <div className="app-main">
      <header className="topbar">
        <div className="top-left">
          <SheetTrigger asChild><Button variant="ghost" size="icon" className="mobile-menu" aria-label="Open navigation"><Menu size={20}/></Button></SheetTrigger>
          <span className="top-workspace">WORKSPACE / LOCAL OPERATIONS</span><span className="top-slash">/</span><b>{meta[1]}</b>
        </div>
        <div className="top-right">
          <Pill tone={ready.isSuccess ? "good" : "warn"}>{ready.isPending ? "Connecting" : ready.isError ? "Disconnected" : "Connected"}</Pill>
          <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" className="icon-button" aria-label="Refresh data" onClick={() => qc.invalidateQueries()}><RefreshCw size={16}/></Button></TooltipTrigger><TooltipContent>Refresh operational data</TooltipContent></Tooltip>
          <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" className="icon-button" aria-label="Sign out" onClick={onSignOut}><Command size={16}/></Button></TooltipTrigger><TooltipContent>Sign out</TooltipContent></Tooltip>
        </div>
      </header>
      <main className="page" id="main-content" tabIndex={-1}>
        <motion.div key={path} initial={reduced ? false : { opacity: 0, y: 9 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .28 }} className="page-content">
          <div className="page-intro"><div><div className="overline page-index"><span className="index-line"/>{meta[0]}</div><h1>{meta[1]}</h1><p>{meta[2]}</p></div><div className="page-intro-right"><span className="live-label"><span className="live-pulse"/> {runtime.data ? `${(runtime.data.deployment_target ?? "local").toUpperCase()} / ${(runtime.data.cloud_mode ?? runtime.data.mode ?? "unknown").toUpperCase()}` : "RUNTIME STATUS UNKNOWN"}</span><span className="time-note">API health checked / resource telemetry is simulated</span></div></div>
          {stale && !unavailable && <div className="connection-notice" role="status">Some data is stale. Last received values remain visible.<Button variant="ghost" size="sm" onClick={() => qc.invalidateQueries()}>Retry</Button></div>}
          {unavailable ? <section className="connection-empty" role="alert"><Radio size={24}/><h2>{path === "/app/agents" ? "Unable to load agents" : "Operational data unavailable"}</h2><p>We could not reach the required API. Counts and incident status are unknown.</p><Button variant="outline" onClick={() => qc.invalidateQueries()}>Retry connection</Button></section> : awaiting ? <div role="status" className="loading-panel">Loading operational data<Skeleton className="route-skeleton"/></div> : <Boundary key={path}><Suspense fallback={<div className="loading-panel" role="status">Loading operational view...<Skeleton className="route-skeleton"/></div>}>
            {path === "/app" && <Overview agents={agents.data ?? []} actions={actions.data ?? []} resources={resources.data ?? []} incidents={incidents.data ?? []} runtime={runtime.data} readiness={ready.data} loading={agents.isPending || actions.isPending || resources.isPending || incidents.isPending || runtime.isPending || ready.isPending}/>}
            {path === "/app/agents" && <Fleet agents={agents.data ?? []} actions={actions.data ?? []} incidents={incidents.data ?? []} loading={agents.isPending}/>}
            {path === "/app/graph" && <GraphView/>}
            {path === "/app/incidents" && <Investigations incidents={incidents.data ?? []} actions={actions.data ?? []}/>}
            {path === "/app/experiments" && <Experiments/>}
          </Suspense></Boundary>}
          <footer><span>BOTKERNEL / {(runtime.data?.deployment_target && runtime.data.deployment_target !== "local" ? runtime.data.deployment_target : runtime.data?.mode ?? runtime.data?.deployment_target ?? "CONTROL PLANE UNKNOWN").toUpperCase()}</span><span>Evidence is observed; causal links require investigation.</span></footer>
        </motion.div>
      </main>
    </div>
    </Sheet>
  </div>;
}

function OperatorAccess() {
  const [authenticated, setAuthenticated] = useState(hasOperatorToken);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [consoleClient, setConsoleClient] = useState(createQueryClient);

  function signOut(message = "") {
    clearOperatorToken();
    void consoleClient.cancelQueries();
    consoleClient.clear();
    setConsoleClient(createQueryClient());
    setAuthenticated(false);
    setToken("");
    setError(message);
  }

  useEffect(() => onUnauthorized(() => signOut("Your access is no longer valid. Sign in again.")), [consoleClient]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await login(token);
      setToken("");
      setAuthenticated(true);
    } catch (failure) {
      setError(failure instanceof Error && failure.message.includes("401")
        ? "Invalid operator credential." : "Unable to verify access. Check the gateway configuration and connection.");
    } finally {
      setPending(false);
    }
  }

  if (authenticated) return <QueryClientProvider client={consoleClient}><App onSignOut={() => signOut()}/></QueryClientProvider>;
  return <main className="operator-access">
    <form className="operator-access-card panel" onSubmit={submit}>
      <div className="overline">BOTKERNEL / PRIVATE OPERATIONS</div>
      <h1>Operator access</h1>
      <p>Enter your operator credential to open the operations console.</p>
      <label htmlFor="operator-token">Operator credential</label>
      <input id="operator-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} required />
      {error && <div className="alert-error" role="alert">{error}</div>}
      <Button type="submit" disabled={pending}>{pending ? "Verifying..." : "Sign in"}</Button>
      <a href="/">Return to overview</a>
    </form>
  </main>;
}

function RouteRoot() {
  const { pathname, search, hash } = useLocation();
  const legacy = new Set(["/agents", "/graph", "/incidents", "/experiments"]);
  if (pathname === "/") return <Landing/>;
  if (legacy.has(pathname)) return <Navigate to={`/app${pathname}${search}${hash}`} replace/>;
  if (pathname === "/app" || pathname.startsWith("/app/")) return <OperatorAccess/>;
  return <Navigate to="/" replace/>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><QueryClientProvider client={queryClient}><TooltipProvider><BrowserRouter><RouteRoot/></BrowserRouter></TooltipProvider></QueryClientProvider></React.StrictMode>,
);
