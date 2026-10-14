const fs=require('fs');
const {chromium}=require('playwright');
(async()=>{
  const edge=process.env.BROWSER_BINARY || (process.platform==='win32'?'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe':undefined);
  const browser=await chromium.launch({headless:true,...(edge && fs.existsSync(edge)?{executablePath:edge}:{})});
  try{
    const page=await browser.newPage({viewport:{width:794,height:1123}});
    await page.route(/https?:\/\//,route=>route.abort());
    await page.setContent(fs.readFileSync(process.argv[2],'utf8'),{waitUntil:'load'});
    await page.emulateMedia({media:'print'});
    if(await page.locator('[data-echart]').count())await page.waitForFunction(()=>window.__reportChartsReady===true);
    await page.evaluate(()=>document.fonts.ready);
    await page.waitForTimeout(150);
    await page.pdf({path:process.argv[3],format:'A4',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:true,
      headerTemplate:'<div></div>',footerTemplate:'<div style="width:100%;text-align:center;font-size:9px;color:#666"><span class="pageNumber"></span></div>'});
  }finally{await browser.close()}
})().catch(e=>{process.stderr.write(e.message);process.exit(1)});
