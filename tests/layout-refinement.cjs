const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8000';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'}),errors=[],results=[];
 page.on('pageerror',e=>errors.push(e.message));
 const check=async(name,fn)=>{await fn();results.push({name,passed:true})};
 const directory=path.resolve(__dirname,'results');fs.mkdirSync(directory,{recursive:true});
 try{
  await page.goto(BASE+'/agent');await page.waitForSelector('#report-form');
  await check('原始资料为首个独立标签且不占用记录列表',async()=>{
   await page.getByRole('tab',{name:'数据库管理',exact:true}).click();await page.waitForSelector('.records-table');
   await page.waitForTimeout(350);
   const tabOverflow=await page.locator('.database-panel>.dataset-tabs').evaluate(e=>({overflowY:getComputedStyle(e).overflowY,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight}));
   assert.equal(tabOverflow.overflowY,'hidden');
   assert.equal(await page.locator('[data-dataset]').first().getAttribute('data-dataset'),'files');
   assert.equal(await page.locator('.file-list').count(),0);
   await page.locator('[data-page="next"]').click();await page.waitForFunction(()=>document.querySelector('.pagination')?.textContent.includes('2 /'));
   const secondPage=await page.locator('.records-table tbody').innerText();
   await page.locator('[data-dataset="files"]').click();await page.waitForSelector('.file-list');
   assert.equal(await page.locator('.records-table,#data-q').count(),0);assert(await page.locator('.file-row').count()>0);
   await page.locator('[data-file-preview]').first().click();await page.waitForSelector('.document-text');await page.keyboard.press('Escape');
   await page.getByRole('button',{name:'上传资料',exact:true}).click();await page.waitForSelector('#upload-file');await page.keyboard.press('Escape');
   await page.screenshot({path:path.join(directory,'raw-files-tab.png')});
   await page.locator('[data-dataset="files"]').focus();await page.keyboard.press('ArrowRight');await page.waitForSelector('.records-table');
   assert.equal(await page.locator('.records-table tbody').innerText(),secondPage);
  });
  await check('计算规则完整展开且始终位于模型图下',async()=>{
   await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.model-rules');
   for(const industry of ['煤矿','工贸']){
    await page.locator(`[data-model-industry="${industry}"]`).click();await page.waitForFunction(i=>document.querySelector('.risk-model-graph')?.getAttribute('aria-label')===i+'隐患治理反馈模型',industry);
    const diagram=await page.locator('.model-canvas').boundingBox(),rules=await page.locator('.model-rules').boundingBox();assert(rules.y>=diagram.y+diagram.height);
    const left=await page.locator('.model-structure-panel').boundingBox(),right=await page.locator('.model-parameters-panel').boundingBox(),body=await page.locator('.workspace-body').boundingBox();
    assert(Math.abs(left.y-right.y)<1&&Math.abs(left.height-right.height)<1);const rulesHeight=await page.locator('.model-rules-table').evaluate(e=>e.clientHeight);assert(rulesHeight>=285&&rulesHeight<=325);
    const text=await page.locator('.model-rules').innerText();assert(text.includes('变量与计算规则')&&!/risk_index|management_initial|production_pressure/.test(text));
   }
   await page.screenshot({path:path.join(directory,'model-rules-full-height.png')});
  });
  await check('61个真实采样点绘制、悬停与导出一致',async()=>{
   const response=page.waitForResponse(r=>r.url().endsWith('/api/simulations')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'运行仿真',exact:true}).click();const result=await(await response).json();await page.waitForSelector('#simulation-chart svg');
   assert.equal(result.sampling_interval_months,.05);assert(result.scenarios.every(s=>s.points.length===61));
   assert.equal(await page.locator('.simulation-evidence,.risk-breakdown').count(),0);
   for(let i=0;i<3;i++){
    const plotted=JSON.parse(await page.locator('#simulation-chart polyline').nth(i).getAttribute('data-values'));
    assert.deepEqual(plotted,result.scenarios[i].points.map(p=>({month:p.month,risk_index:p.risk_index})));
   }
   const csv=await page.request.get(BASE+`/api/simulations/${result.id}/export`);assert.equal((await csv.text()).trim().split(/\r?\n/).length,184);
   await page.locator('[data-action="expand-chart"]').click();await page.waitForSelector('#expanded-simulation-chart svg');
   const svg=page.locator('#expanded-simulation-chart svg'),box=await svg.boundingBox(),coords=await svg.evaluate(e=>({left:+e.dataset.plotLeft,right:+e.dataset.plotRight,top:+e.dataset.plotTop,bottom:+e.dataset.plotBottom}));
   await page.mouse.move(box.x+coords.left+(coords.right-coords.left)*.35/3,box.y+(coords.top+coords.bottom)/2);
   const tooltip=page.locator('#expanded-simulation-chart .chart-tooltip');await tooltip.waitFor({state:'visible'});const text=await tooltip.innerText();assert(text.includes('0.35月'));
   for(const scenario of result.scenarios)assert(text.includes(scenario.points.find(p=>p.month===.35).risk_index.toFixed(2)));
   await page.mouse.move(0,0);await page.screenshot({path:path.join(directory,'dense-simulation-expanded.png')});await page.keyboard.press('Escape');
  });
  await check('窄屏标签、计算规则与曲线保持可用',async()=>{
   for(const width of [320,393,768,1024,1920]){
    await page.setViewportSize({width,height:1100});await page.getByRole('tab',{name:'数据库管理',exact:true}).click();await page.locator('[data-dataset="files"]').click();await page.waitForSelector('.file-list');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.main').scrollWidth<=innerWidth));
    await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.model-rules');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.main').scrollWidth<=innerWidth));
   }
  });
  assert.deepEqual(errors,[]);const result={passed:results.length,results,browserErrors:errors,base_url:BASE,samples_per_month:20};
  fs.writeFileSync(path.resolve(__dirname,'../docs/layout-refinement-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
