const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8001';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[],results=[];
 page.on('pageerror',e=>errors.push(e.message));
 const check=async(name,fn)=>{await fn();results.push({name,passed:true});console.log('PASS '+name)};
 let model,result,saved,versions;
 try{
  await page.goto(BASE+'/agent');await page.waitForSelector('#report-form');
  const models=await(await page.request.get(BASE+'/api/models')).json();model=models.find(m=>m.industry==='工贸'&&m.profile_version==='industry-feedback/3.0');assert(model);
  await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.feedback-graph');
  await check('六行业分别显示专业因素与闭环结构',async()=>{
   const labels=[];
   for(const m of models.filter(m=>m.profile_version==='industry-feedback/3.0')){
    await page.locator(`[data-model-industry="${m.industry}"]`).click();await page.waitForFunction(i=>document.querySelector('.feedback-graph')?.getAttribute('aria-label')===i+'隐患治理反馈模型',m.industry);
    const text=await page.locator('.feedback-graph').textContent();assert(text.includes('隐患形成速度')&&text.includes('滞后事故信息'));
    for(const label of Object.values(m.feature_labels))assert(text.includes(label.replace('风险','')));
    labels.push(text);assert.equal(await page.locator('[data-action="edit-sd-model"]').count(),1);
   }
   assert.equal(new Set(labels).size,6);
   await page.locator('[data-model-industry="工贸"]').click();await page.waitForFunction(()=>document.querySelector('.feedback-graph')?.getAttribute('aria-label').startsWith('工贸'));
   const graphText=await page.locator('.feedback-graph').textContent();assert(!graphText.includes('工贸专业因素'));
   assert((await page.locator('.feedback-graph .graph-polarity').count())>=10);
   const paths=await page.locator('.feedback-graph .graph-edge').evaluateAll(items=>items.map(item=>item.getAttribute('d')));
   assert(paths.every(d=>!/C|Q/.test(d)));
   const factorCount=model.variables.filter(v=>v.role==='factor').length;
   assert.equal(await page.locator('.feedback-layout-medium .factor-collector path').count(),factorCount+1);
   assert.equal(await page.locator('.feedback-layout-medium .graph-edge[data-edge-source="factor_load"]').count(),2);
  });
  await check('左右底部对齐、一屏显示多行规则并可展开完整公式',async()=>{
   const box=await page.locator('.model-rules-table').evaluate(e=>({h:e.clientHeight,sh:e.scrollHeight,rows:e.querySelectorAll('tbody tr').length,max:getComputedStyle(e).maxHeight}));
   assert(box.h>=285&&box.h<=325&&box.rows>=14&&box.sh>box.h);
   const alignment=await page.evaluate(()=>{const l=document.querySelector('.model-structure-panel').getBoundingClientRect(),r=document.querySelector('.model-parameters-panel').getBoundingClientRect(),w=document.querySelector('.workspace-body');return {delta:Math.abs(l.bottom-r.bottom),overflow:w.scrollHeight-w.clientHeight}});
   assert(alignment.delta<1&&alignment.overflow<=2);
   await page.locator('[data-action="expand-model-rules"]').click();await page.waitForSelector('.full-model-rule');
   assert.equal(await page.locator('.full-model-rule').count(),model.variables.length);await page.keyboard.press('Escape');
   assert(await page.locator('[data-action="run-simulation"]').isVisible());
   await page.screenshot({path:'tests/results/feedback-rules-expanded.png'});
   await page.locator('.workspace-body').evaluate(e=>e.scrollTop=0);
  });
  await check('三场景实际计算、四类曲线与数值一致',async()=>{
   const response=page.waitForResponse(r=>r.url().endsWith('/api/simulations')&&r.request().method()==='POST');
   await page.locator('[data-action="run-simulation"]').click();result=await(await response).json();assert.equal(result.scenarios[0].points.length,61);
   await page.waitForSelector('#simulation-chart svg');
   for(const metric of ['risk_index','accident_intensity','hazard_pressure','cumulative_load']){
    await page.locator('[data-chart-metric]').selectOption(metric);
    const series=await page.locator('#simulation-chart polyline').evaluateAll(els=>els.map(e=>JSON.parse(e.dataset.values)));
    for(let i=0;i<3;i++)assert.deepEqual(series[i],result.scenarios[i].points.map(p=>({month:p.month,risk_index:p[metric]})));
   }
   await page.locator('[data-chart-metric]').selectOption('risk_index');
   assert.equal(await page.locator('.sd-scenario-summaries article').count(),3);
   assert((await page.locator('.sd-limit-note').innerText()).includes('暂不预测事故起数'));
   await page.locator('.simulation-results').scrollIntoViewIfNeeded();await page.screenshot({path:'tests/results/feedback-simulation.png'});
  });
  await check('放大、悬停及导出保留真实采样',async()=>{
   await page.locator('[data-action="expand-chart"]').click();await page.waitForSelector('#expanded-simulation-chart svg');
   await page.locator('.modal [data-chart-metric]').selectOption('accident_intensity');
   const svg=page.locator('#expanded-simulation-chart svg'),box=await svg.boundingBox();
   const point=await svg.evaluate(e=>({x:Number(e.dataset.plotLeft)+(Number(e.dataset.plotRight)-Number(e.dataset.plotLeft))*.35/3,y:(Number(e.dataset.plotTop)+Number(e.dataset.plotBottom))/2}));
   await page.mouse.move(box.x+point.x,box.y+point.y);await page.waitForSelector('#expanded-simulation-chart .chart-tooltip:not([hidden])');
   const text=await page.locator('#expanded-simulation-chart .chart-tooltip').innerText();assert(text.includes('0.35月'));
   for(const s of result.scenarios)assert(text.includes(s.points.find(p=>p.month===.35).accident_intensity.toFixed(2)));
   await page.keyboard.press('Escape');
   const csv=await(await page.request.get(BASE+`/api/simulations/${result.id}/export`)).text();assert(csv.includes('hazard_formation')&&csv.includes('accident_intensity'));
  });
  await check('依据可追溯事故编号与原因片段',async()=>{
   await page.locator('[data-action="factor-evidence"]').click();await page.waitForSelector('.sd-evidence-records article');
   assert((await page.locator('.sd-evidence-records blockquote').count())>0);assert((await page.locator('.sd-evidence-records').innerText()).includes('命中'));
   await page.keyboard.press('Escape');
  });
  // Browser save requests are intercepted to avoid changing the live user's model.
  // Real persistence, optimistic locking and restore are tested against an isolated DB in pytest.
  versions=[structuredClone(model)];
  await page.route(`**/api/models/${model.id}`,async route=>{
   if(route.request().method()!=='PUT')return route.continue();
   saved=route.request().postDataJSON();saved.version+=1;versions.push(structuredClone(saved));
   await route.fulfill({contentType:'application/json',body:JSON.stringify(saved)});
  });
  await page.route(`**/api/models/${model.id}/versions`,r=>r.fulfill({contentType:'application/json',body:JSON.stringify(versions)}));
  await check('中文表单修改名称、公式、关系及参数并校验保存',async()=>{
   await page.locator('[data-action="edit-sd-model"]').click();await page.waitForSelector('.sd-editor-modal');
   assert.equal(await page.locator('.modal textarea').count(),0);
   await page.locator('#sd-variable-label').fill('隐患压力测试名称');
   const flowIndex=model.variables.findIndex(v=>v.name==='hazard_formation');await page.locator(`[data-edit-variable="${flowIndex}"]`).click();
   while(await page.locator('[data-remove-token]').count())await page.locator('[data-remove-token]').first().click();
   await page.locator('#sd-add-variable').selectOption('formation_rate');await page.locator('#sd-insert-variable').click();
   await page.locator('[data-insert-token="*"]').click();
   await page.locator('#sd-add-variable').selectOption('production_pressure');await page.locator('#sd-insert-variable').click();
   await page.locator('[data-editor-tab="parameters"]').click();await page.locator('[data-edit-param="formation_rate"]').fill('0.09');
   await page.locator('[data-action="check-sd-model"]').click();await page.waitForFunction(()=>document.querySelector('#sd-editor-status')?.textContent.includes('通过'));
   await page.locator('[data-editor-tab="variables"]').click();await page.screenshot({path:'tests/results/feedback-editor.png'});
   await page.locator('[data-action="save-sd-model"]').click();await page.waitForSelector('.sd-editor-modal',{state:'detached'});
   assert.equal(saved.variables[0].label,'隐患压力测试名称');assert.equal(saved.parameters.formation_rate.value,.09);
   assert(!saved.variables.find(v=>v.name==='hazard_formation').formula.includes('factor_load'));
   await page.waitForFunction(()=>!document.querySelector('[data-edge-source="factor_load"][data-edge-target="hazard_formation"]'));
  });
  await check('可恢复原模型并保留版本选择',async()=>{
   await page.locator('[data-action="edit-sd-model"]').click();await page.locator('[data-action="model-history"]').click();await page.waitForSelector('[data-restore-model]');
   await page.locator(`[data-restore-model="${model.version}"]`).click();await page.waitForSelector('.sd-version-list',{state:'detached'});
   assert.equal(saved.variables[0].label,model.variables[0].label);
   assert.equal(saved.variables.find(v=>v.name==='hazard_formation').formula,model.variables.find(v=>v.name==='hazard_formation').formula);
  });
  await check('窄屏规则、编辑和行业切换不横向撑破页面',async()=>{
   for(const width of [393,320]){
    await page.setViewportSize({width,height:900});await page.locator('.model-rules').scrollIntoViewIfNeeded();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert(!overflow);
    await page.locator('[data-action="edit-sd-model"]').click();await page.waitForSelector('.sd-editor-modal');
    assert(await page.locator('[data-action="save-sd-model"]').isVisible());await page.keyboard.press('Escape');
   }
  });
  assert.deepEqual(errors,[]);const output={base:BASE,checks:results.length,results,errors};
  fs.writeFileSync('docs/feedback-browser-results.json',JSON.stringify(output,null,2));console.log(JSON.stringify(output));
 }catch(e){await page.screenshot({path:'tests/results/feedback-failure.png'});console.error(e);process.exitCode=1}finally{await browser.close()}
})();
