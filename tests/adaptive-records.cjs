const {chromium}=require('playwright');const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8000';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1554,height:1300},reducedMotion:'reduce'}),results=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));const check=async(name,fn)=>{await fn();results.push({name,passed:true})};
 const settle=async()=>{await page.waitForTimeout(350);await page.waitForFunction(()=>{const viewport=document.querySelector('.records-viewport'),table=document.querySelector('.records-table'),row=table?.querySelector('tbody tr');if(!row)return false;const gap=viewport.clientHeight-table.getBoundingClientRect().height;return gap>=-1&&gap<row.getBoundingClientRect().height+1})};
 try{
  await page.goto(BASE+'/agent');await page.getByRole('tab',{name:'数据库管理',exact:true}).click();await settle();
  await check('大屏按可用高度增加条目且分页贴底',async()=>{
   const sizes=[];
   for(const height of [900,1100,1300]){
    await page.setViewportSize({width:1554,height});await settle();
    const size=Number(await page.locator('.pagination').getAttribute('data-page-size'));sizes.push(size);assert.equal(await page.locator('.records-table tbody tr').count(),size);
    const panel=await page.locator('.database-panel').boundingBox(),workspace=await page.locator('.workspace-body').boundingBox(),pagination=await page.locator('.pagination').boundingBox();
    assert(Math.abs(panel.y+panel.height-workspace.y-workspace.height)<2);assert(panel.y+panel.height-pagination.y-pagination.height<20);
   }
   assert(sizes[0]<sizes[1]&&sizes[1]<sizes[2]&&sizes[2]>10);await page.screenshot({path:path.resolve(__dirname,'results/adaptive-records-desktop.png')});
  });
  await check('改变高度保留当前记录位置及未提交筛选输入',async()=>{
   await page.locator('[data-page="next"]').click();await page.waitForFunction(()=>document.querySelector('.pagination .actions span').textContent.startsWith('2 /'));
   const anchor=await page.locator('.records-table tbody tr td:first-child').first().innerText();await page.locator('#data-q').fill('未提交检索条件');
   await page.setViewportSize({width:1554,height:1040});await settle();assert.equal(await page.locator('#data-q').inputValue(),'未提交检索条件');
   assert((await page.locator('.records-table tbody tr td:first-child').allTextContents()).includes(anchor));
   const size=Number(await page.locator('.pagination').getAttribute('data-page-size')),label=await page.locator('.pagination .actions span').innerText(),index=Number(label.split('/')[0])-1;
   const expected=await(await page.request.get(BASE+`/api/data/accidents?limit=${size}&offset=${size*index}`)).json();assert.deepEqual(await page.locator('.records-table tbody tr td:first-child').allTextContents(),expected.items.map(r=>r['编号']));
  });
  await check('末页和空表保留分页位置且不填造记录',async()=>{
   await page.locator('#data-q').fill('');await page.getByRole('button',{name:'筛选',exact:true}).click();await settle();
   let count=0;while(await page.locator('[data-page="next"]').isEnabled()){
    const before=await page.locator('.pagination .actions span').innerText();await page.locator('[data-page="next"]').click();await page.waitForFunction(old=>document.querySelector('.pagination .actions span').textContent!==old,before);assert(++count<60);
   }
   assert(await page.locator('.records-table tbody tr').count()>0);assert((await page.locator('.records-table tbody tr').count())<=Number(await page.locator('.pagination').getAttribute('data-page-size')));
   await page.locator('[data-dataset="enterprises"]').click();await page.waitForSelector('.empty');assert.equal(await page.locator('.records-table tbody tr').count(),0);assert(await page.locator('[data-page="next"]').isDisabled());
  });
  await check('离开数据页后未完成查询不会重绘新页面',async()=>{
   await page.locator('[data-dataset="accidents"]').click();await settle();
   let release,started;const received=new Promise(resolve=>started=resolve),gate=new Promise(resolve=>release=resolve);
   await page.route('**/api/data/accidents?*',async route=>{started();await gate;await route.continue()},{times:1});
   await page.setViewportSize({width:1554,height:1200});await received;
   await page.getByRole('tab',{name:'报告生成',exact:true}).click();await page.waitForSelector('#report-form');
   await page.evaluate(()=>window.currentReportForm=document.querySelector('#report-form'));
   const response=page.waitForResponse(r=>r.url().includes('/api/data/accidents?'));release();await response;await page.waitForTimeout(200);
   assert(await page.evaluate(()=>window.currentReportForm===document.querySelector('#report-form')));
  });
  assert.deepEqual(errors,[]);const result={passed:results.length,results,browserErrors:errors,base_url:BASE};fs.writeFileSync(path.resolve(__dirname,'../docs/adaptive-records-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
