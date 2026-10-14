const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const assert=require('assert/strict');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8000';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:943},reducedMotion:'reduce'});const errors=[],results=[];let saves=0,simulation;
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='PUT'&&r.url().includes('/api/models/'))saves++});
 const check=async(name,fn)=>{await fn();results.push({name,passed:true})};
 try{
  await page.goto(BASE+'/agent');
  if(await page.locator('#login-credential').count()){
   assert(process.env.QA_PASSWORD,'QA_PASSWORD is required when access protection is enabled');
   await page.locator('#login-credential').fill(process.env.QA_PASSWORD);await page.getByRole('button',{name:'登录',exact:true}).click();
  }
  await page.waitForSelector('#report-form');
  await check('各行业仅一个固定模型且不显示版本',async()=>{
   for(const industry of ['煤矿','金属非金属矿山','石油天然气开采','化工','烟花爆竹','工贸']){
    await page.locator('#industry').selectOption(industry);assert.equal(await page.locator('#report-model option').count(),1);
    assert(!/V\d|初始/.test(await page.locator('#report-model').innerText()));
   }
   await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.model-canvas');
   for(const action of ['import-model','export-model','model-versions','edit-model','validate-model','save-variables'])assert.equal(await page.locator(`[data-action="${action}"]`).count(),0);
   assert.equal(await page.locator('.graph-source,[data-edit-variable],#model-select,.model-toolbar').count(),0);
  });
  await check('情景输入保留与恢复默认不修改固定模型',async()=>{
   const input=page.locator('[data-param="production_pressure"]');await input.fill('1.3');
   await page.getByRole('tab',{name:'报告生成',exact:true}).click();await page.getByRole('tab',{name:'SD模型库',exact:true}).click();assert.equal(await input.inputValue(),'1.3');
   await page.getByRole('button',{name:'恢复默认',exact:true}).click();assert.equal(await input.inputValue(),'1');assert.equal(saves,0);
  });
  await check('模型图关系可聚焦且不出现代码或编辑弹窗',async()=>{
   await page.locator('[data-graph-node="hazard_pressure"]').first().focus();assert(await page.locator('.graph-edge.connected').count()>0);
   await page.keyboard.press('Enter');assert.equal(await page.getByRole('dialog').count(),0);
   assert(!/height_risk|production_pressure|初值来自|初值与权重/.test(await page.locator('.model-canvas').innerText()));
  });
  await check('固定模型真实仿真且计算规则保持展示',async()=>{
   await page.locator('[data-param="production_pressure"]').fill('1.1');
   const response=page.waitForResponse(r=>r.url().endsWith('/api/simulations')&&r.request().method()==='POST');
   const rules=await page.locator('.model-rules').innerText();
   await page.getByRole('button',{name:'运行仿真',exact:true}).click();simulation=await(await response).json();await page.waitForSelector('#simulation-chart');
   assert.equal(await page.locator('.model-rules').innerText(),rules);assert.equal(await page.locator('.risk-breakdown').count(),0);
   assert.equal(await page.locator('[data-param="production_pressure"]').inputValue(),'1.1');assert.equal(saves,0);
   await page.waitForSelector('[data-compare-simulation] option', {state:'attached'});assert(!/^V\d/m.test(await page.locator('[data-compare-simulation]').innerText()));
  });
  await check('循环使用说明和界面设置直接打开',async()=>{
   assert.equal(await page.locator('.rail-tools>button').count(),3);
   await page.getByRole('button',{name:'使用说明',exact:true}).click();assert.equal(await page.locator('[data-help-step]').count(),4);assert.equal(await page.locator('.help-slide').count(),1);await page.keyboard.press('Escape');
   assert(await page.getByRole('button',{name:'使用说明',exact:true}).evaluate(e=>document.activeElement===e));
   await page.getByRole('button',{name:'界面设置',exact:true}).click();await page.waitForSelector('.preference-list');await page.keyboard.press('Escape');
  });
  await check('报告刷新恢复进度且正文直接完成',async()=>{
   const probe=await browser.newPage({viewport:{width:1440,height:943},reducedMotion:'reduce'});let polls=0;
   const reports=await(await page.request.get(BASE+'/api/reports')).json(),sample=reports.find(r=>['generated','completed'].includes(r.llm?.status))||reports[0];
   const job={id:'qa-fixed-model-report',kind:'report',status:'running',progress:55,stage:'智能体正在生成报告'};
   await probe.route('**/api/reports',route=>route.request().method()==='POST'?route.fulfill({contentType:'application/json',body:JSON.stringify(job)}):route.continue());
   await probe.route('**/api/jobs/qa-fixed-model-report',route=>{polls++;return route.fulfill({contentType:'application/json',body:JSON.stringify(polls<3?job:{...job,status:'completed',progress:100,result:{...sample,llm:{status:'failed',error:'报告文字格式不完整，请重新生成'}}})})});
   try{
    await probe.goto(BASE+'/agent');
    if(await probe.locator('#login-credential').count()){
     await probe.locator('#login-credential').fill(process.env.QA_PASSWORD);await probe.getByRole('button',{name:'登录',exact:true}).click();
    }
    await probe.waitForSelector('#report-form');await probe.getByRole('button',{name:'一键生成',exact:true}).click();await probe.waitForSelector('.progress-label');
    await probe.reload();await probe.waitForSelector('.progress-label');await probe.waitForSelector('.report-frame');assert.equal(await probe.locator('.report-generation-notice').count(),0);assert(await probe.getByRole('button',{name:/^(报告验证|查看验证)$/}).isEnabled());
    assert.equal(await probe.evaluate(()=>sessionStorage.getItem('risk-agent:report-job:')),null);
   }finally{await probe.close()}
  });
  assert.deepEqual(errors,[]);const result={passed:results.length,results,browserErrors:errors,base_url:BASE,model_save_requests:saves};
  fs.writeFileSync(path.resolve(__dirname,'../docs/fixed-model-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
