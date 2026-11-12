import { signIn } from "./auth-helper";
import {expect,test} from "@playwright/test";

test("investigates persisted incident and opens verified graph evidence", async ({page}) => {
  const errors:string[]=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("console",message=>{if(message.type()==="error") errors.push(message.text())});
  await page.goto("/incidents");
  await signIn(page);
  await expect(page.getByRole("button",{name:"Analyze Incident"})).toBeVisible();
  const posted=page.waitForResponse(r=>r.url().includes("/investigations") && r.request().method()==="POST");
  await page.getByRole("button",{name:"Analyze Incident"}).click();
  const response=await posted; expect(response.status()).toBe(200);
  const data=await response.json(); expect(data.status).toBe("COMPLETE");
  const action:string=data.report.effects[0].action_id;
  await expect(page.getByText("Deterministic analysis — no LLM used")).toBeVisible();
  await expect(page.getByText(data.report.conclusion)).toBeVisible();
  await page.reload();
  await signIn(page);
  await expect(page.getByText(data.report.conclusion)).toBeVisible();
  await page.getByRole("link",{name:action}).first().click();
  await expect(page).toHaveURL(/\/graph\?/);
  const graphEvidence = page.locator(".graph-inspector .inspect-id").filter({ hasText: `action:${action}` })
    .or(page.getByRole("status").filter({ hasText: /referenced action is not in this graph window/i }));
  await expect(graphEvidence.first()).toBeVisible();
  await page.reload();
  await signIn(page);
  await expect(graphEvidence.first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("missing graph evidence is explained",async({page})=>{
  await page.goto("/graph?action=00000000-0000-0000-0000-000000000000&resource=ui-validation");
  await signIn(page);
  await expect(page.getByText(/referenced action is not in this graph window/i)).toBeVisible();
});

test("saved Bedrock report shows actual provider, model, usage and advisory hypotheses", async ({page}) => {
  const actionId="00000000-0000-0000-0000-000000000001";
  const report={
    id:"00000000-0000-0000-0000-000000000042",incident_id:42,status:"COMPLETE",
    provider:"bedrock",created_at:"2026-11-11T12:00:00Z",error_category:null,
    report:{
      outcome:"COMPLETE",resource:"acceptance-resource",conclusion:"Committed changes were observed.",
      contributing_agents:["cost","performance"],uncertainty:"Temporal association is not causal proof.",
      recommendation:"Human review only.",human_approval_required:true,evidence_warnings:[],
      missing_references:[],model_id:"us.amazon.nova-micro-v1:0",
      usage:{provider:"bedrock",model_id:"us.amazon.nova-micro-v1:0",input_tokens:321,output_tokens:88,invocations:1},
      ai_analysis:{
        status:"COMPLETE",explanation:"The supplied committed effects show opposing changes.",
        hypotheses:["Independent objectives may have contributed; this is not causal proof."],
        cross_agent_analysis:"Two agents are represented in the evidence.",
        instability_mechanism:"Opposing changes may indicate a reversal pattern.",
        supporting_references:[actionId,"incident:42"],contradictory_or_missing_evidence:[],
        preventive_actions:["Review with an operator."],confidence_caveats:["Correlation is not causation."],
      },
      effects:[{action_id:actionId,agent:"cost",resource:"acceptance-resource",version:1,
        before_capacity:5,after_capacity:4,observed_at:"2026-11-11T11:59:00Z"}],
      findings:[
        {classification:"VERIFIED_FACT",description:"A committed capacity change is recorded.",supporting_actions:[actionId],contradicting_actions:[]},
        {classification:"HYPOTHESIS",description:"Independent objectives may have contributed.",supporting_actions:[actionId],contradicting_actions:[]},
      ],
    },
  };
  await page.route("**/api/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith("/health")) return route.fulfill({json:{status:"ok",mode:"local"}});
    if(path.endsWith("/ready")) return route.fulfill({json:{status:"ready"}});
    if(path.endsWith("/incidents/42/investigations")) return route.fulfill({json:[report]});
    if(path.endsWith("/incidents")) return route.fulfill({json:[{
      id:42,resource:"acceptance-resource",score:0.9,status:"VERIFIED",
      opened_at:"2026-11-11T11:00:00Z",hold_until:"2026-11-11T11:01:00Z",
      intervention_count:1,recurrence_count:0,healthy_samples:3,evidence:{},
      operator_actions:[],
    }]});
    if(path.endsWith("/actions")) return route.fulfill({json:[]});
    return route.fulfill({json:[]});
  });
  await page.setViewportSize({width:390,height:844});
  await page.goto("/app/incidents");
  await signIn(page);
  await expect(page.locator(".provider-label")).toContainText("BEDROCK");
  await expect(page.locator(".provider-label")).toContainText("us.amazon.nova-micro-v1:0");
  await expect(page.locator(".provider-label")).toContainText("321/88 TOKENS");
  await expect(page.getByText("Bedrock hypotheses are advisory; deterministic evidence remains authoritative.")).toBeVisible();
  await expect(page.getByText("Verified facts")).toBeVisible();
  await expect(page.getByText("Hypotheses · further verification required")).toBeVisible();
  await expect(page.getByText("DETERMINISTIC · NO LLM")).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
