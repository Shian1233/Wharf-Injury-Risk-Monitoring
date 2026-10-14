const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8001';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'}),errors=[],results=[];
 page.on('pageerror',e=>errors.push(e.message));
 const check=async(name,fn)=>{await fn();results.push({name,passed:true})};
 try{
  await page.goto(BASE+'/agent');await page.waitForSelector('#report-form');
  await check('设计样式使用内容哈希，页面保留四个真实概览',async()=>{
   assert.match(await page.locator('link[href*="/design.css"]').getAttribute('href'),/\?v=/);
   assert.equal(await page.locator('.overview-card').count(),4);
   assert.equal(await page.locator('.report-paper').getAttribute('aria-hidden'),null);
   assert.equal(await page.locator('.report-illustration').getAttribute('aria-hidden'),'true');
  });
  await check('报告历史移除状态标签且保留可用操作',async()=>{
   await page.locator('[data-action="report-history"]').click();await page.waitForSelector('.history-row');
   assert.equal(await page.locator('.history-row .badge').count(),0);
   assert(!/待业务审核|规则文本草稿/.test(await page.locator('.modal-body').innerText()));
   assert((await page.locator('.history-row strong').count())>0);
   await page.keyboard.press('Escape');
  });
  await check('常用桌面高度直接显示仿真操作，左右面板对齐',async()=>{
   await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.model-run-footer');
   for(const [width,height] of [[1440,900],[1920,1080],[1024,900],[768,1024]]){
    await page.setViewportSize({width,height});await page.waitForTimeout(80);
    const boxes=await page.evaluate(()=>{
     const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {y:r.y,bottom:r.bottom,height:r.height}};
     return {workspace:rect('.workspace-body'),left:rect('.model-structure-panel'),right:rect('.model-parameters-panel'),button:rect('.model-run-footer .btn')};
    });
    assert(Math.abs(boxes.left.y-boxes.right.y)<1&&Math.abs(boxes.left.bottom-boxes.right.bottom)<1);
    assert(boxes.button.bottom<=boxes.workspace.bottom+1,JSON.stringify({width,height,boxes}));
   }
  });
  await check('窄屏可滚动至指标、生成按钮和报告预览',async()=>{
   await page.setViewportSize({width:393,height:852});await page.getByRole('tab',{name:'报告生成',exact:true}).click();await page.waitForSelector('#report-form');
   await page.locator('.report-submit').scrollIntoViewIfNeeded();await page.getByRole('button',{name:'应用模型',exact:true}).click();
   await page.waitForSelector('.application-model-menu');await page.keyboard.press('Escape');
   await page.locator('.report-empty').scrollIntoViewIfNeeded();
   assert(await page.locator('.report-empty').isVisible());
   assert(await page.evaluate(()=>document.querySelector('.main').scrollWidth<=innerWidth));
  });
  assert.deepEqual(errors,[]);
  const result={passed:results.length,results,browserErrors:errors,base_url:BASE};
  fs.writeFileSync(path.resolve(__dirname,'../docs/design-edition-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
