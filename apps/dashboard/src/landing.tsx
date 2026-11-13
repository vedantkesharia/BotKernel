import { Link } from "react-router-dom";
import { ArrowDown, ArrowRight, ShieldCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { ArchitectureJourney, ConflictStory, ConsolePreview } from "./LandingStories";
import { CapabilityBento, OrchestrationDemo } from "./OrchestrationDemo";
import "./landing.css";
import "./landing-refinements.css";

function Brand() {
  return <Link className="landing-brand" to="/" aria-label="BotKernel home"><span className="landing-mark"><i/><i/><i/><i/></span><span>BotKernel</span></Link>;
}

export function Landing() {
  const reduced = useReducedMotion();
  return <div className="landing-page">
    <a className="landing-skip" href="#landing-main">Skip to content</a>
    <header className="landing-nav">
      <Brand/>
      <nav aria-label="Landing page navigation"><a href="#platform">Platform</a><a href="#architecture">Architecture</a><a href="#safety">Safety model</a></nav>
      <Link className="landing-nav-cta" to="/app">Launch console <ArrowRight size={15}/></Link>
    </header>
    <main id="landing-main">
      <section className="landing-hero">
        <motion.div className="hero-copy" initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .4 }}>
          <div className="landing-eyebrow"><span/> COLLECTIVE RELIABILITY FOR AUTONOMOUS SYSTEMS</div>
          <h1>Autonomy needs<br/><em>a control plane.</em></h1>
          <p>Independent agents. Shared consequences. BotKernel makes every action traceable and collective instability containable.</p>
          <div className="hero-actions"><Link className="button-primary" to="/app">Launch console <ArrowRight size={16}/></Link><a className="button-secondary" href="#coordination">See the failure mode <ArrowDown size={15}/></a></div>
          <div className="hero-assurance"><ShieldCheck size={15}/><span>Gateway-admitted actions · durable evidence · human-reviewed recovery</span></div>
        </motion.div>
        <motion.div className="hero-visual" initial={reduced ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .45, delay: .06 }}><OrchestrationDemo/></motion.div>
        <div className="hero-index" aria-hidden="true"><span>BOTKERNEL / SYSTEM MODEL</span><span>01 — 07</span></div>
      </section>

      <section className="principle-strip" aria-label="Core design principles">
        <div><span>01</span><b>PostgreSQL owns correctness</b></div><div><span>02</span><b>Kafka delivery is at least once</b></div><div><span>03</span><b>Effects are idempotent and evidenced</b></div><div><span>04</span><b>Controller policy stays deterministic</b></div>
      </section>

      <div id="coordination"><ConflictStory/></div>

      <section className="landing-section platform-section" id="platform">
        <div className="section-intro"><span className="landing-eyebrow">THE PLATFORM</span><h2>Reliability is a property<br/>of the whole system.</h2><p>One traceable path connects agent decisions, durable effects and the control response.</p></div>
        <CapabilityBento/>
      </section>

      <ArchitectureJourney/>
      <ConsolePreview/>

      <section className="safety-section" id="safety">
        <div className="safety-card"><span className="landing-eyebrow">SAFETY BY AUTHORITY</span><h2>Reasoning can recommend.<br/><em>Policy decides.</em></h2><p>Deterministic Cost and Performance policies are the default. Bedrock is optional and has not been used for live inference. Model output cannot bypass admission, controller holds or the operator boundary.</p><div className="safety-tags"><span>LOCAL-FIRST</span><span>SIMULATOR ONLY</span><span>NO AUTO-REMEDIATION</span></div></div>
        <div className="safety-aside"><div><b>Evidence, not theater.</b><p>Facts, deterministic graph inferences and hypotheses stay separate. Correlation is never presented as proven causation.</p></div><div><b>Recovery is explicit.</b><p>Outbox delivery, worker receipts, leases and agent checkpoints make retry boundaries inspectable.</p></div><div><b>Cloud access stays private.</b><p>The optional AWS demo is private and reached through SSM. Operator authentication does not make the API suitable for public exposure.</p></div></div>
      </section>

      <section className="landing-cta"><div><span className="landing-eyebrow">EXPLORE THE OPERATING SYSTEM</span><h2>Bring the whole system into view.</h2><p>Inspect the local control plane, action ledger, committed effects and investigations.</p></div><Link className="button-primary" to="/app">Launch console <ArrowRight size={16}/></Link></section>
    </main>
    <footer className="landing-footer"><Brand/><span>Distributed AgentOps · simulator telemetry · local-first control</span><a href="#landing-main">Back to top ↑</a></footer>
  </div>;
}
