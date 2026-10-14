const {chromium}=require('playwright');
const assert=require('assert/strict');
const fs=require('fs'),path=require('path');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8001';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[],saved=[];
 page.on('pageerror',e=>errors.push(e.message));
 const report={id:'review-preview-test',title:'全国工贸安全生产风险研判及预测分析报告',created_at:'2026-10-14T00:00:00+08:00',body_hanzi:5200,count:104,status:'已生成',parameters:{industry:'工贸',region:'',start:'2011-11-10',end:'2026-07-01',months:3,scenario:'基准场景',indicators:['事故总数']},llm:{status:'generated'}};
 await page.route('**/api/reports',route=>route.request().method()==='GET'?route.fulfill({contentType:'application/json',body:JSON.stringify([report])}):route.continue());
 await page.route('**/api/reports/review-preview-test/html',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>报告</title><h1>风险研判与预测分析报告</h1>'}));
 await page.route('**/api/reports/review-preview-test/review',async route=>{const body=route.request().postDataJSON();saved.push(body);await route.fulfill({contentType:'application/json',body:JSON.stringify({...body,updated_at:'2026-10-14T00:10:00+08:00',updated_by:'test'})})});
 try{
  await page.goto(BASE+'/agent');await page.waitForSelector('#report-form');assert.equal(await page.locator('.identity-mark').count(),0);
  await page.getByRole('button',{name:'查看记录',exact:true}).click();await page.getByRole('button',{name:'打开',exact:true}).click();
  await page.waitForSelector('.report-frame');assert(await page.locator('.report-frame').isVisible());
  assert.equal(await page.locator('.report-status').count(),0);assert(!(await page.locator('.report-preview').innerText()).includes('待业务审核'));
  assert.equal(await page.locator('#report-review-form').count(),1);
  const directory=path.resolve(__dirname,'results');fs.mkdirSync(directory,{recursive:true});
  await page.screenshot({path:path.join(directory,'report-preview-review.png'),fullPage:true});
  await page.locator('#review-conclusion').fill('结论经现场复核后采用');await page.locator('#review-indicators').fill('指标方向和量纲已验证');
  await page.getByRole('button',{name:'保存验证',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.toast')?.textContent.includes('专家验证已保存'));
  assert.deepEqual(saved[0],{conclusion:'结论经现场复核后采用',indicator_validation:'指标方向和量纲已验证'});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:4,checks:['页头无盾牌','报告直接预览','矮版专家验证表单','验证意见保存'],errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
