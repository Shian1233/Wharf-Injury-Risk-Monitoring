const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const assert=require('assert/strict');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8000';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:943},reducedMotion:'reduce'}),errors=[],results=[];
 page.on('pageerror',e=>errors.push(e.message));
 const check=async(name,fn)=>{await fn();results.push({name,passed:true})};
 const directory=path.resolve(__dirname,'results');fs.mkdirSync(directory,{recursive:true});
 try{
  await page.goto(BASE+'/agent');await page.waitForSelector('#report-form');
  await check('预测两行与页内指标不弹窗',async()=>{
   assert.equal(await page.locator('.report-advanced,.more-menu,[data-action=select-indicators]').count(),0);
   await page.screenshot({path:path.join(directory,'inline-report-desktop.png')});
   await page.locator('[data-indicator-group="4"]').click();
   const input=page.locator('input[name=indicators]').first(),selected=await input.isChecked();await input.setChecked(!selected);
   const name=await input.getAttribute('value');await page.locator('[data-indicator-group="1"]').click();await page.locator('[data-indicator-group="4"]').click();
   assert.equal(await page.locator('input[name=indicators]').filter({visible:true}).first().isChecked(),!selected);
   await page.locator('.parameter-toggle').click();await page.locator('[data-report-param="production_pressure"]').fill('1.25');
   await page.getByRole('tab',{name:'数据库管理',exact:true}).click();await page.getByRole('tab',{name:'报告生成',exact:true}).click();
   assert.equal(await page.locator('[data-report-param="production_pressure"]').inputValue(),'1.25');assert.equal(await page.getByRole('dialog').count(),0);
   await page.locator('#reset-report-params').click();assert.equal(await page.locator('[data-report-param="production_pressure"]').inputValue(),'1');
   await page.locator('.parameter-toggle').click();await page.locator('[data-indicator-group="4"]').scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(directory,'inline-indicators-desktop.png')});
  });
  await check('六行业结构不同且使用固定模型',async()=>{
   await page.getByRole('tab',{name:'SD模型库',exact:true}).click();const structures=[];
   for(const industry of ['煤矿','金属非金属矿山','石油天然气开采','化工','烟花爆竹','工贸']){
    await page.locator('[data-model-industry]').filter({hasText:new RegExp('^'+industry+'$')}).click();
    await page.waitForFunction(i=>document.querySelector('.risk-model-graph')?.getAttribute('aria-label')===i+'隐患治理反馈模型',industry);
    structures.push(await page.locator('.factor-chip').allTextContents());
    assert.equal(await page.locator('[data-param]:not(:disabled)').count(),industry==='工贸'?7:industry==='金属非金属矿山'?5:4);
    assert(await page.locator('.graph-node').count()<=11);
   }
   assert.equal(new Set(structures.map(x=>JSON.stringify(x))).size,6);
   await page.locator('[data-graph-node="hazard_pressure"]').focus();
   assert.equal(await page.getByRole('dialog').count(),0);assert.equal(await page.locator('[data-edit-variable],.graph-source,#model-select').count(),0);
   assert(!/初值来自|初值与权重来自/.test(await page.locator('.model-canvas').innerText()));
   await page.screenshot({path:path.join(directory,'industry-model-desktop.png')});
  });
  await check('曲线页面简洁且计算保留可追溯证据',async()=>{
   const response=page.waitForResponse(r=>r.url().endsWith('/api/simulations')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'运行仿真',exact:true}).click();const result=await(await response).json();await page.waitForSelector('#simulation-chart svg');
   assert.equal(await page.locator('.simulation-evidence').count(),0);
   assert(result.sd_evidence.channels.some(c=>c.evidence.length>0));
   assert(result.scenarios.every(s=>s.points.length===61));
  });
  await check('触屏记录行紧凑并按高度分页',async()=>{
   const mobile=await browser.newContext({viewport:{width:393,height:850},isMobile:true,hasTouch:true,reducedMotion:'reduce'});const p=await mobile.newPage();
   try{
    await p.goto(BASE+'/agent');await p.getByRole('tab',{name:'数据库管理',exact:true}).click();await p.waitForSelector('.records-table tbody tr');
    await p.waitForTimeout(350);
    assert.equal(await p.locator('.records-table tbody tr').count(),Number(await p.locator('.pagination').getAttribute('data-page-size')));
    const heights=await p.locator('.records-table tbody tr').evaluateAll(rows=>rows.map(r=>r.getBoundingClientRect().height));assert(heights.every(h=>h<=56),JSON.stringify(heights));
    const operations=await p.locator('.records-table .actions').first().evaluate(e=>({height:e.clientHeight,wrap:getComputedStyle(e).flexWrap}));assert.equal(operations.wrap,'nowrap');assert(operations.height<=40);
    await p.locator('.records-table').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(directory,'compact-records-mobile.png')});
    assert.equal(await p.getByRole('button',{name:'使用说明',exact:true}).count(),1);
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.main').scrollWidth<=innerWidth));
   }finally{await mobile.close()}
  });
  await check('全部页面多宽度与减少动效',async()=>{
   for(const width of [320,393,768,1024,1440]){
    await page.setViewportSize({width,height:943});
    for(const view of ['数据库管理','SD模型库','报告生成']){
     await page.getByRole('tab',{name:view,exact:true}).click();
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.querySelector('.main').scrollWidth<=innerWidth),view+width);
     assert.equal(await page.locator('.rail-tools>button').count(),3);
    }
   }
   assert.equal(await page.locator('.business-tab').first().evaluate(e=>getComputedStyle(e).transitionDuration),'0s');
  });
  assert.deepEqual(errors,[]);const result={passed:results.length,results,browserErrors:errors,base_url:BASE};
  fs.writeFileSync(path.resolve(__dirname,'../docs/inline-workbench-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
