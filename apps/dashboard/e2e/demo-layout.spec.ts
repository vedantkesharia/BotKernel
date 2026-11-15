import {expect,test} from '@playwright/test';
import {signIn} from './auth-helper';

// Use a retained, read-only preview API. No operator operation is submitted.
for(const [label,width,height] of [['desktop',1440,900],['tablet',834,1112],['mobile',390,844]] as const){
  test(`retained evidence and operator form remain readable on ${label}`,async({page},testInfo)=>{
    await page.setViewportSize({width,height});
    const errors:string[]=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=500)errors.push(`${r.status()} ${r.url()}`)});
    await page.route('**/api/**',route=>route.request().method()==='GET'?route.continue():route.abort());
    await page.goto('/app/incidents');await signIn(page);
    await expect(page.locator('.incident-row').first()).toBeVisible();
    const rationale=page.getByLabel('Decision rationale');await expect(rationale).toBeVisible();
    await expect(page.getByText('AUTHENTICATED OPERATOR CONTROL',{exact:true})).toBeVisible();
    const button=page.getByRole('button',{name:'Resolve incident',exact:true});
    await expect(button).toBeDisabled();
    const geometry=await page.evaluate(()=>{
      const input=document.querySelector('#operator-reason')!,label=document.querySelector('label[for="operator-reason"]')!,button=document.querySelector('.operator-form button')!;
      const a=input.getBoundingClientRect(),b=label.getBoundingClientRect(),c=button.getBoundingClientRect();
      return {labelGap:a.top-b.bottom,buttonGap:c.top-a.bottom,widthGap:Math.abs(a.width-c.width),rows:[...document.querySelectorAll('.incident-row')].map(e=>{const t=e.querySelector('strong')!,arrow=e.querySelector('svg')!;return {right:t.getBoundingClientRect().right,arrow:arrow.getBoundingClientRect().left,title:t.getAttribute('title')}})};
    });
    expect(geometry.labelGap).toBeGreaterThanOrEqual(10);expect(geometry.labelGap).toBeLessThanOrEqual(12);
    expect(geometry.buttonGap).toBeGreaterThanOrEqual(16);expect(geometry.buttonGap).toBeLessThanOrEqual(20);
    expect(geometry.widthGap).toBeLessThanOrEqual(1);
    for(const row of geometry.rows){expect(row.right).toBeLessThanOrEqual(row.arrow);expect(row.title).toBeTruthy()}
    await rationale.fill('Reviewed retained evidence for this layout check.');
    await expect(button).toBeEnabled();await rationale.focus();await page.keyboard.press('Tab');await expect(button).toBeFocused();
    await expect(page.locator('.investigation-report-content')).toBeVisible();
    await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo(0,0)});
    await page.screenshot({path:testInfo.outputPath(`incident-form-${label}.png`),fullPage:true});
    for(const route of ['/app','/app/agents','/app/graph','/app/experiments']){
      await page.goto(route);await signIn(page);
      const content=route==='/app'?'.command-overview':route.endsWith('/agents')?'.fleet-workspace':route.endsWith('/experiments')?'.experiment-layout':'.graph-workspace';
      if(!route.endsWith('/graph'))await expect(page.locator(content)).toBeVisible();
      await expect(page.getByText('Loading recorded evaluations',{exact:true})).toHaveCount(0);
      if(route.endsWith('/agents')){
        const fits=await page.locator('.identity-panel').evaluate(panel=>{const p=panel.getBoundingClientRect();return [...panel.querySelectorAll('.identity-stats>div')].every(card=>{const c=card.getBoundingClientRect();return c.left>=p.left&&c.right<=p.right})});
        expect(fits).toBe(true);
      }
      if(route.endsWith('/graph')){await expect(page.getByRole('combobox',{name:'Graph time window'})).toContainText('Last 7 days');await expect(page.locator('.react-flow__node').first()).toBeVisible()}
      await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:testInfo.outputPath(`${route.split('/').pop()}-${label}.png`),fullPage:true});
    }
    expect(errors).toEqual([]);
  });
}
