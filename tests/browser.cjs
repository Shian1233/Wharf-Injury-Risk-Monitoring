const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8000';
const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');
const root=path.resolve(__dirname,'..');const outputs=process.env.QA_OUTPUT||path.join(root,'tests/results');fs.mkdirSync(outputs,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_BINARY||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const results=[];const errors=[];let reportSubmissions=0;const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
  page.on('request',r=>{if(r.method()==='POST' && r.url().endsWith('/api/reports'))reportSubmissions++});
  page.on('pageerror',e=>errors.push(e.message));
  const check=async(name,fn)=>{try{await fn();results.push({name,passed:true})}catch(e){results.push({name,passed:false,error:e.message});throw e}};
  const chartData=selector=>page.locator(selector+' svg').evaluate(svg=>({
    low:Number(svg.dataset.yMin),high:Number(svg.dataset.yMax),precision:Number(svg.dataset.yPrecision),horizon:Number(svg.dataset.xMax),
    left:Number(svg.dataset.plotLeft),right:Number(svg.dataset.plotRight),top:Number(svg.dataset.plotTop),bottom:Number(svg.dataset.plotBottom),
    width:svg.viewBox.baseVal.width,height:svg.viewBox.baseVal.height,
    series:[...svg.querySelectorAll('polyline')].map(line=>({name:line.dataset.scenario,values:JSON.parse(line.dataset.values),
      coordinates:[...line.points].map(p=>({x:p.x,y:p.y})),dashed:line.hasAttribute('stroke-dasharray')}))
  }));
  const verifyChart=(chart,expected)=>{
    if(JSON.stringify(chart.series.map(s=>s.values))!==JSON.stringify(expected))throw new Error('Chart differs from saved simulation values');
    const values=expected.flat().map(p=>p.risk_index),range=chart.high-chart.low;
    if(chart.low>Math.min(...values)||chart.high<Math.max(...values))throw new Error('Chart clips real values');
    if(chart.horizon!==Math.max(...expected.flat().map(p=>p.month)))throw new Error('Incorrect actual time horizon');
    chart.series.forEach(series=>series.coordinates.forEach((point,i)=>{
      const risk=chart.high-(point.y-chart.top)/(chart.bottom-chart.top)*range;
      const month=(point.x-chart.left)/(chart.right-chart.left)*chart.horizon;
      if(Math.abs(risk-series.values[i].risk_index)>range/(chart.bottom-chart.top)*.001+1e-6||Math.abs(month-series.values[i].month)>chart.horizon/(chart.right-chart.left)*.001+1e-6)throw new Error('Plotted coordinates alter simulation result');
    }));
  };
  let chartExpected,currentSimulation;
  try{
    await check('广场整页跳转至独立智能体',async()=>{await page.goto(BASE);await page.evaluate(()=>window.galleryDocument=true);await page.getByRole('link').filter({hasText:'安全生产风险研判与预测'}).click();await page.waitForSelector('#report-form');if(!page.url().endsWith('/agent'))throw new Error('Wrong route');if(await page.evaluate(()=>Boolean(window.galleryDocument)))throw new Error('Expected a new page document');if(await page.locator('#sidebar,#drawer-toggle,.breadcrumb').count()||/中国矿业大学|鼎安大模型/.test(await page.locator('body').innerText()))throw new Error('Platform shell retained');const bounds=await page.locator('.main').boundingBox();if(bounds.x!==0||bounds.width!==1440)throw new Error('Agent does not occupy the whole viewport')});
    await page.screenshot({path:path.join(outputs,'report-desktop.png'),fullPage:true});
    await check('参考布局与真实业务概览',async()=>{
      const overview=await (await page.request.get(BASE+'/api/overview')).json();
      if(!await page.locator('.workbench-heading p').innerText())throw new Error('Title subtitle missing');
      if(await page.locator('.workbench-heading h1').innerText()!=='全国安全生产风险智能研判与预测'||await page.locator('.overview-card').count()!==4)throw new Error('Reference header or four overview cards missing');
      const first=await page.locator('[data-metric=data]').innerText();
      if(!first.includes(overview.total_records.toLocaleString('zh-CN'))||!first.includes((overview.bytes/1e6).toFixed(2)+' MB'))throw new Error('Overview does not show actual imported sample');
      for(const [metric,key] of [['industries','industry_count'],['models','model_count'],['reports','report_count']])if(await page.locator(`[data-metric=${metric}] strong`).innerText()!==overview[key].toLocaleString('zh-CN'))throw new Error('Overview mismatch: '+metric);
      const heading=await page.locator('.workbench-identity').boundingBox(),cards=await page.locator('.overview-cards').boundingBox(),rail=await page.locator('.agent-navigation').boundingBox(),config=await page.locator('.report-config').boundingBox(),tools=await page.locator('.rail-tools').boundingBox(),preview=await page.locator('.report-preview').boundingBox();
      if(Math.abs(heading.x+heading.width/2-720)>1||heading.y+heading.height>cards.y||cards.y+cards.height>rail.y||rail.x+rail.width>config.x||config.x+config.width>preview.x||tools.x+tools.width>config.x||tools.y<rail.y+rail.height||Math.abs(tools.y+tools.height-preview.y-preview.height)>12)throw new Error('Header, overview, navigation, configuration, tools or preview not arranged as reference');
      const choose=await page.getByRole('button',{name:'应用模型',exact:true}).boundingBox(),generate=await page.getByRole('button',{name:'一键生成',exact:true}).boundingBox();
      if(Math.abs(choose.y-generate.y)>1||choose.x+choose.width>generate.x||generate.y+generate.height>1100)throw new Error('Model selection and generation footer incorrect');
      if(await page.locator('.agent-navigation').getAttribute('aria-orientation')!=='vertical')throw new Error('Desktop business navigation not vertical');
    });
    await check('应用模型下拉、SD选择与业务导航键盘',async()=>{
      await page.locator('#industry').selectOption('化工');
      const selected=await page.locator('#report-model').inputValue(),models=await (await page.request.get(BASE+'/api/models')).json();
      if(!models.some(m=>m.id===selected&&m.industry==='化工')||!await page.locator('.report-section').filter({hasText:'预测设置'}).locator('#report-model').count())throw new Error('SD model not in prediction settings for selected industry');
      const config=await (await page.request.get(BASE+'/api/config')).json();
      await page.getByRole('button',{name:'应用模型',exact:true}).click();
      if(await page.getByRole('listbox',{name:'选择应用模型'}).getByRole('option').count()!==config.llm.models.length)throw new Error('Application model catalog mismatch');
      await page.keyboard.press('End');await page.keyboard.press('Enter');
      if(await page.getByRole('button',{name:'应用模型',exact:true}).getAttribute('title')!==config.llm.models.at(-1).id||await page.locator('#report-model').inputValue()!==selected)throw new Error('Application selection changed SD model or did not apply');
      await page.getByRole('button',{name:'应用模型',exact:true}).click();await page.keyboard.press('Escape');
      if(await page.locator('.application-model-menu').count()||!await page.getByRole('button',{name:'应用模型',exact:true}).evaluate(e=>e===document.activeElement))throw new Error('Dropdown focus did not restore');
      await page.locator('#industry').selectOption('工贸');await page.getByRole('tab',{name:'报告生成',exact:true}).focus();
      await page.keyboard.press('ArrowUp');await page.waitForSelector('.model-canvas');
      await page.waitForFunction(()=>document.activeElement?.dataset.nav==='models');
      await page.keyboard.press('Home');await page.waitForSelector('.data-table');
      await page.waitForFunction(()=>document.activeElement?.dataset.nav==='database');
      await page.keyboard.press('End');await page.waitForSelector('#report-form');
      await page.waitForFunction(()=>document.activeElement?.dataset.nav==='reports');
    });
    await check('报告指标与参数直接在页面配置',async()=>{
      if(await page.getByText('更多设置',{exact:true}).count()||await page.getByRole('button',{name:'选择指标',exact:true}).count())throw new Error('Removed controls remain');
      for(let i=0;i<6;i++){await page.locator(`[data-indicator-group="${i}"]`).click();if(await page.locator('#indicator-group-toggle').innerText()==='全选本类')await page.locator('#indicator-group-toggle').click()}
      if(await page.locator('#indicator-count').innerText()!=='已选 66 项'||await page.getByRole('dialog').count())throw new Error('Inline selection did not persist across categories');
      await page.getByRole('button',{name:'设置参数',exact:false}).click();await page.locator('[data-report-param="production_pressure"]').fill('1.1');
      await page.locator('#reset-report-params').click();if(await page.locator('[data-report-param="production_pressure"]').inputValue()!=='1')throw new Error('Parameter reset failed');
      const months=await page.locator('#months').boundingBox(),model=await page.locator('#report-model').boundingBox(),scenario=await page.locator('#scenario').boundingBox(),button=await page.locator('.parameter-toggle').boundingBox();
      if(Math.abs(months.y-model.y)>1||Math.abs(scenario.y-button.y)>1||scenario.y<=months.y)throw new Error('Prediction rows not arranged as requested');
    });
    await check('数据库列表与原字段',async()=>{await page.getByRole('tab',{name:'数据库管理'}).click();await page.waitForSelector('.data-table tbody tr');const row=page.locator('.data-table tbody tr').first();await row.getByRole('button',{name:'查看',exact:true}).click();await page.getByRole('dialog').waitFor();if(await page.locator('#record-form .field').count()!==33)throw new Error('original fields not preserved');await page.keyboard.press('Escape')});
    await check('自适应条数与翻页不重复',async()=>{
      await page.waitForTimeout(350);
      const size=Number(await page.locator('.pagination').getAttribute('data-page-size'));
      const expected=await (await page.request.get(BASE+`/api/data/accidents?limit=${size}&offset=0`)).json();
      const codes=()=>page.locator('.data-table tbody tr td:first-child').allTextContents();
      const first=await codes();
      if(first.length!==size||JSON.stringify(first)!==JSON.stringify(expected.items.map(r=>r['编号'])))throw new Error('First page does not match actual records');
      await page.locator('[data-page=next]').click();await page.waitForFunction(()=>document.querySelector('.pagination .actions span').textContent.startsWith('2 /'));
      const second=await codes();if(second.length!==size||second.some(c=>first.includes(c)))throw new Error('Pagination repeats records');
      const paging=await page.locator('.pagination').innerText();if(!paging.includes('2 / '+Math.ceil(expected.total/size)))throw new Error('Adaptive page count wrong');
      await page.locator('[data-page=prev]').click();await page.waitForFunction(()=>document.querySelector('.pagination .actions span').textContent.startsWith('1 /'));
      if(JSON.stringify(await codes())!==JSON.stringify(first))throw new Error('Previous page differs');
    });
    await page.screenshot({path:path.join(outputs,'database-desktop.png'),fullPage:true});
    await check('上传与编辑入口',async()=>{await page.getByRole('button',{name:'上传数据',exact:true}).click();await page.waitForSelector('#upload-file');await page.keyboard.press('Escape');await page.locator('[data-edit]').first().click();await page.waitForSelector('#record-form');await page.keyboard.press('Escape');await page.getByRole('button',{name:'字段',exact:true}).click();await page.getByRole('button',{name:'应用',exact:true}).click()});
    await check('日期筛选与四表查询',async()=>{await page.getByRole('button',{name:'时间范围',exact:true}).click();await page.locator('#data-start').fill('2024-01-01');await page.locator('#data-end').fill('2024-12-31');await page.getByRole('button',{name:'应用',exact:true}).click();await page.waitForSelector('.data-table tbody tr');for(const dataset of ['enterprises','climate','economy']){await page.locator(`[data-dataset="${dataset}"]`).click();await page.waitForSelector('.empty');await page.locator('#data-q').fill('查询测试');await page.getByRole('button',{name:'筛选',exact:true}).click();await page.waitForSelector('.empty')}await page.locator('[data-dataset="accidents"]').click();await page.waitForSelector('.data-table tbody tr')});
    await check('六行业模型及真实仿真',async()=>{await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.model-canvas');const left=await page.locator('.model-structure-panel').boundingBox(),right=await page.locator('.model-parameters-panel').boundingBox();if(Math.abs(left.y-right.y)>1)throw new Error('SD columns not aligned');for(const industry of ['煤矿','金属非金属矿山','石油天然气开采','化工','烟花爆竹','工贸']){await page.locator('[data-model-industry]').filter({hasText:industry}).click();await page.waitForFunction(i=>document.querySelector('.risk-model-graph')?.getAttribute('aria-label')===i+'隐患治理反馈模型',industry);if(industry==='工贸')await page.locator('#sim-months').selectOption('6');await page.getByRole('button',{name:'运行仿真',exact:true}).click();await page.waitForSelector('#simulation-chart');if(!await page.locator('#simulation-chart polyline').count())throw new Error(industry+' simulation missing')} });
    await check('曲线范围、真实坐标与历史悬停',async()=>{
      const exportPath=await page.locator('.simulation-results a[download]').getAttribute('href'),id=exportPath.split('/')[3];
      const saved=await (await page.request.get(BASE+'/api/simulations')).json();
      currentSimulation=saved.find(s=>s.id===id);if(!currentSimulation)throw new Error('Saved simulation not found');
      chartExpected=currentSimulation.scenarios.map(s=>s.points.map(p=>({month:p.month,risk_index:p.risk_index})));
      let chart=await chartData('#simulation-chart');verifyChart(chart,chartExpected);
      const values=chartExpected.flat().map(p=>p.risk_index);
      if(chart.low<=0||(Math.max(...values)-Math.min(...values))/(chart.high-chart.low)<.5)throw new Error('Adaptive chart still contains excessive whitespace');
      await page.locator('.simulation-results').getByRole('button',{name:'从零开始',exact:true}).click();
      if((await chartData('#simulation-chart')).low!==0)throw new Error('Zero origin mode failed');
      await page.locator('.simulation-results').getByRole('button',{name:'自适应',exact:true}).click();
      await page.waitForFunction(()=>document.querySelector('#compare-simulation')?.options.length>1);
      const comparison=saved.find(s=>s.model_id===currentSimulation.model_id&&s.id!==id&&s.scenarios[0].points.at(-1).month<currentSimulation.scenarios[0].points.at(-1).month);
      if(!comparison)throw new Error('Actual shorter historical baseline required');
      await page.locator('#compare-simulation').selectOption(comparison.id);
      chartExpected.push(comparison.scenarios[0].points.map(p=>({month:p.month,risk_index:p.risk_index})));
      chart=await chartData('#simulation-chart');verifyChart(chart,chartExpected);
      if(chart.series.length!==4||chart.series.filter(s=>s.dashed).length!==1||!chart.series.at(-1).dashed)throw new Error('Historical baseline not dashed');
      await page.locator('#simulation-chart').scrollIntoViewIfNeeded();
      const bounds=await page.locator('#simulation-chart svg').boundingBox(),month=currentSimulation.scenarios[0].points.at(-1).month;
      await page.mouse.move(bounds.x+chart.right-1,bounds.y+(chart.top+chart.bottom)/2);
      const tooltip=page.locator('#simulation-chart .chart-tooltip');await tooltip.waitFor({state:'visible'});
      if(await tooltip.locator('strong').innerText()!==month+'月'||(await tooltip.innerText()).includes('历史基准'))throw new Error('Tooltip extrapolates shorter historical result');
      for(const scenario of currentSimulation.scenarios){const value=scenario.points.find(p=>p.month===month).risk_index.toFixed(Math.max(2,chart.precision));if(!(await tooltip.innerText()).includes(value))throw new Error('Hover does not display real result')}
      await page.mouse.move(0,0);await tooltip.waitFor({state:'hidden'});
      await page.locator('.simulation-results').screenshot({path:path.join(outputs,'curve-adaptive.png')});
    });
    await check('曲线放大、同步缩放与移动端尺寸',async()=>{
      const expand=page.getByRole('button',{name:'放大查看',exact:true});await expand.click();
      await page.waitForSelector('#expanded-simulation-chart svg');const dialog=page.getByRole('dialog');
      await page.waitForTimeout(150);let bounds=await dialog.boundingBox(),plot=await page.locator('#expanded-simulation-chart').boundingBox();
      if(bounds.width<1440*.94||bounds.height<1100*.94||plot.height<1100*.7)throw new Error('Expanded chart does not use viewport');
      verifyChart(await chartData('#expanded-simulation-chart'),chartExpected);
      await dialog.getByRole('button',{name:'从零开始',exact:true}).click();
      for(const host of ['#simulation-chart','#expanded-simulation-chart'])if((await chartData(host)).low!==0)throw new Error('Scale state not synchronized');
      await dialog.getByRole('button',{name:'自适应',exact:true}).click();
      await dialog.screenshot({path:path.join(outputs,'curve-expanded.png')});
      for(const width of [393,320]){
        await page.setViewportSize({width,height:850});await page.waitForTimeout(150);
        const sizes=await dialog.evaluate(e=>({scroll:e.scrollWidth,width:e.clientWidth,body:e.querySelector('.modal-body').scrollWidth,bodyWidth:e.querySelector('.modal-body').clientWidth,plot:e.querySelector('.simulation-plot').clientWidth,document:document.documentElement.scrollWidth}));
        const chart=await chartData('#expanded-simulation-chart');verifyChart(chart,chartExpected);
        plot=await page.locator('#expanded-simulation-chart').boundingBox();
        if(sizes.scroll>sizes.width||sizes.body>sizes.bodyWidth||sizes.document>width||chart.width!==sizes.plot||plot.height<300)throw new Error(width+' enlarged overflow/unused area: '+JSON.stringify(sizes));
        await dialog.screenshot({path:path.join(outputs,'curve-expanded-'+width+'.png')});
      }
      await page.keyboard.press('Escape');if(await dialog.count())throw new Error('Expanded chart did not close');
      if(!await expand.evaluate(e=>document.activeElement===e))throw new Error('Focus not restored to expand button');
      await page.setViewportSize({width:1440,height:1100});
    });
    await page.screenshot({path:path.join(outputs,'models-desktop.png'),fullPage:true});
    await check('固定模型无版本或维护按钮',async()=>{if(await page.locator('#model-select,.model-toolbar,[data-edit-variable],.graph-source').count())throw new Error('Model maintenance controls retained');for(const name of ['版本','编辑模型','导入模型','校验','保存参数'])if(await page.getByRole('button',{name,exact:true}).count())throw new Error(name+' should not appear');});
    await page.getByRole('tab',{name:'报告生成',exact:true}).click();await page.waitForSelector('#report-form');
    await check('多断点无页面横向溢出',async()=>{for(const width of [1920,1440,1024,768,767,393,320]){await page.setViewportSize({width,height:1000});await page.waitForTimeout(150);const sizes=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth,content:document.querySelector('.main').scrollWidth,main:document.querySelector('.main').clientWidth,brand:getComputedStyle(document.documentElement).getPropertyValue('--iflyv-brand-primary')}));if(sizes.scroll>width||sizes.content>sizes.main+1)throw new Error(width+' overflow '+JSON.stringify(sizes));if(width===320||width===1440)await page.screenshot({path:path.join(outputs,'report-'+width+'.png'),fullPage:true})}});
    await check('H5独立工作台功能切换与键盘',async()=>{await page.setViewportSize({width:393,height:850});if(await page.locator('#sidebar,#drawer-toggle').count())throw new Error('Platform drawer retained');await page.getByRole('tab',{name:'数据库管理',exact:true}).click();await page.waitForSelector('.data-table');await page.getByRole('tab',{name:'SD模型库',exact:true}).click();await page.waitForSelector('.model-canvas');await page.getByRole('tab',{name:'报告生成',exact:true}).click();await page.waitForSelector('#report-form');await page.getByRole('button',{name:'界面设置',exact:true}).click();await page.getByRole('dialog').waitFor();if(/DeepSeek|LLM|deepseek-chat|PostgreSQL|运行日志|验收记录/i.test(await page.getByRole('dialog').innerText()))throw new Error('Administrative details visible in preferences');await page.keyboard.press('Escape');if(await page.getByRole('dialog').count())throw new Error('Escape failed to close settings');if(!await page.getByRole('button',{name:'界面设置',exact:true}).evaluate(e=>document.activeElement===e))throw new Error('Focus not restored');await page.locator('.main').evaluate(e=>e.scrollTop=0);await page.screenshot({path:path.join(outputs,'agent-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1100})});
    await check('面向师生的界面偏好',async()=>{await page.getByRole('button',{name:'界面设置',exact:true}).click();await page.waitForSelector('.preference-list');if(await page.getByRole('dialog').getByText('访问权限').count())throw new Error('Access administration retained');await page.keyboard.press('Escape')});
    await check('业务页面与配置预览布局',async()=>{
      if(/DeepSeek|LLM|A4 · 七章结构/i.test(await page.locator('body').evaluate(e=>{const clone=e.cloneNode(true);clone.querySelectorAll('.application-model-button,.application-model-menu').forEach(n=>n.remove());return clone.textContent}))||await page.locator('.section-index').count())throw new Error('Implementation annotations remain');
      const config=await page.locator('.report-config').boundingBox(),preview=await page.locator('.report-preview').boundingBox();
      if(preview.width<config.width*1.5||Math.abs(config.y-preview.y)>1)throw new Error('Report layout proportions incorrect');
      const submit=await page.getByRole('button',{name:'一键生成',exact:true}).boundingBox();if(submit.y+submit.height>1100)throw new Error('Submit action outside viewport');
      for(const name of ['数据库管理','SD模型库','报告生成']){
        await page.getByRole('tab',{name,exact:true}).click();
        if(await page.locator('.agent-rail .rail-tools').count()!==1||await page.locator('.report-side-tools').count()||await page.getByRole('button',{name:'查看记录',exact:true}).count()!==1)throw new Error('Permanent left actions missing in '+name);
        for(const width of [320,768,1024,1440]){
          await page.setViewportSize({width,height:1100});
          const sizes=await page.evaluate(()=>({page:document.documentElement.scrollWidth,main:document.querySelector('.main').scrollWidth,width:innerWidth}));
          if(sizes.page>width||sizes.main>width)throw new Error(name+' overflow at '+width);
        }
      }
      await page.getByRole('button',{name:'查看记录',exact:true}).click();await page.locator('[data-open-report]').first().click();await page.waitForSelector('.report-frame');await page.locator('.report-frame').contentFrame().locator('body').waitFor();
      const reportId=await page.locator('.report-frame').evaluate(e=>e.getAttribute('src').split('/')[3]);const saved=(await (await page.request.get(BASE+'/api/reports')).json()).find(r=>r.id===reportId);if(saved.parameters.industry!==await page.locator('#industry').inputValue()||await page.locator('#indicator-count').innerText()!=='已选 '+saved.parameters.indicators.length+' 项')throw new Error('Historical report configuration not restored');
      await page.screenshot({path:path.join(outputs,'report-preview-desktop.png'),fullPage:true});
    });
    await check('智能体报告请求与指标保留',async()=>{
      const probe=await browser.newPage({viewport:{width:1440,height:1100}});let payload;
      try{
        await probe.route('**/api/reports',async route=>{if(route.request().method()!=='POST')return route.continue();payload=route.request().postDataJSON();return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'测试请求已拦截，未创建报告'})})});
        await probe.goto(BASE+'/agent');await probe.waitForSelector('#report-form');
        if(await probe.locator('[name=use_llm]').count())throw new Error('Provider option exposed');
        await probe.locator('#industry').selectOption('化工');const selectedModel=await probe.locator('#report-model').inputValue();await probe.getByRole('button',{name:'应用模型',exact:true}).click();await probe.getByRole('option',{name:'deepseek-v4-pro',exact:true}).click();
        await probe.getByRole('button',{name:'一键生成',exact:true}).click();await probe.waitForSelector('#toast:not([hidden])');
        if(payload?.use_llm!==true||payload.indicators.length!==12||payload.model_id!==selectedModel||payload.industry!=='化工'||payload.llm_model!=='deepseek-v4-pro'||!payload.start||!payload.end)throw new Error('Agent generation payload incomplete');
        if(!await probe.getByRole('button',{name:'一键生成',exact:true}).isEnabled())throw new Error('Failed submission not recoverable');
      }finally{await probe.close()}
    });
    await check('报告进度连续、守实且完成后预览',async()=>{
      const probe=await browser.newPage({viewport:{width:1440,height:943}});let calls=0;
      const reports=await (await page.request.get(BASE+'/api/reports')).json(),report=reports[0];
      const job={id:'qa-smooth-progress',status:'running',progress:10,stage:'查询与统计'};
      try{
        await probe.route('**/api/reports',route=>route.request().method()==='POST'?route.fulfill({contentType:'application/json',body:JSON.stringify(job)}):route.continue());
        await probe.route('**/api/jobs/qa-smooth-progress',async route=>{
          calls++;const progress=calls===1?55:calls===2?85:100;
          await probe.evaluate(n=>window.qaLimit=n,progress);
          await route.fulfill({contentType:'application/json',body:JSON.stringify({...job,progress,status:calls>=3?'completed':'running',stage:calls>=3?'执行完成':'智能体正在生成报告',result:calls>=3?report:undefined})});
        });
        await probe.goto(BASE+'/agent');await probe.waitForSelector('#report-form');
        await probe.evaluate(()=>{
          window.qaSamples=[];window.qaLimit=10;window.qaFillChanged=false;let fill=null;
          function sample(){
            const node=document.querySelector('#report-job .progress-bar div');
            if(node){if(fill&&fill!==node)window.qaFillChanged=true;fill=node;
              const v=Number(node.style.transform.match(/scaleX\(([^)]+)\)/)?.[1])*100;
              window.qaSamples.push({value:v,label:Number(document.querySelector('#report-job .progress-label strong').textContent.replace('%','')),limit:window.qaLimit});
            }
            if(!window.qaStop)requestAnimationFrame(sample);
          }requestAnimationFrame(sample);
        });
        await probe.getByRole('button',{name:'一键生成',exact:true}).click();await probe.waitForSelector('.report-frame');
        const saved=await probe.evaluate(()=>{window.qaStop=true;return {samples:window.qaSamples,changed:window.qaFillChanged}});
        if(saved.changed||saved.samples.length<30)throw new Error('Progress fill recreated or too few animation frames');
        if(new Set(saved.samples.filter(p=>p.limit===55&&p.value>10&&p.value<55).map(p=>p.label)).size<10)throw new Error('Progress jumped to 55 instead of animating');
        let prev=0;for(const p of saved.samples){if(p.value<prev-.001||p.value>p.limit+.001||Math.abs(p.value-p.label)>=1.001||p.label===100&&p.limit!==100)throw new Error('Progress regressed, fabricated completion or label disagrees');prev=p.value}
        if(await probe.locator('.report-frame').getAttribute('src')!=='/api/reports/'+report.id+'/html')throw new Error('Completed report preview not opened');
      }finally{await probe.close()}
    });
    await check('任务切页进度保留与失败恢复',async()=>{
      const probe=await browser.newPage({viewport:{width:1440,height:943}});let calls=0;
      const job={id:'qa-failed-progress',status:'running',progress:55,stage:'智能体正在生成报告'};
      try{
        await probe.route('**/api/reports',route=>route.request().method()==='POST'?route.fulfill({contentType:'application/json',body:JSON.stringify(job)}):route.continue());
        await probe.route('**/api/jobs/qa-failed-progress',route=>{calls++;return route.fulfill({contentType:'application/json',body:JSON.stringify({...job,status:calls>=2?'failed':'running',error:'测试任务失败'})})});
        await probe.goto(BASE+'/agent');await probe.waitForSelector('#report-form');await probe.getByRole('button',{name:'一键生成',exact:true}).click();
        await probe.waitForFunction(()=>Number(document.querySelector('.progress-label strong')?.textContent.replace('%',''))===55);
        await probe.getByRole('tab',{name:'数据库管理',exact:true}).click();await probe.waitForSelector('.data-table');
        await probe.getByRole('tab',{name:'报告生成',exact:true}).click();await probe.waitForSelector('#report-job .progress-bar');
        if(await probe.locator('#report-job .progress-label strong').innerText()!=='55%')throw new Error('Switching views reset job progress');
        await probe.waitForSelector('#report-job .notice:not([hidden])');
        await probe.waitForFunction(()=>!document.querySelector('#report-form button[type=submit]').disabled);
        if(await probe.locator('#report-job .progress-label strong').innerText()!=='55%')throw new Error('Failed job claimed completion');
      }finally{await probe.close()}
    });
    await check('旧版未版本化脚本缓存隔离',async()=>{
      const probe=await browser.newPage();let staleRequests=0;
      try{
        await probe.route('**/assets/app.js*',async route=>{
          if(!new URL(route.request().url()).searchParams.has('v')){staleRequests++;await route.fulfill({contentType:'text/javascript',body:"document.querySelector('#drawer-toggle').innerHTML='旧导航';"})}
          else await route.continue();
        });
        await probe.goto(BASE+'/agent');await probe.waitForSelector('#report-form');
        if(staleRequests)throw new Error('Unversioned stale module requested');
        for(let i=0;i<2;i++){await probe.reload();await probe.waitForSelector('#report-form')}
      }finally{await probe.close()}
    });
    for(const failure of ['script-load','script-execute','api'])await check({'script-load':'脚本加载失败与重试恢复','script-execute':'脚本执行异常与重试恢复','api':'接口初始化失败与重试恢复'}[failure],async()=>{
      const probe=await browser.newPage();let failing=true;
      try{
        await probe.route(failure==='api'?'**/api/config':'**/assets/app.js*',async route=>{
          if(!failing)return route.continue();
          if(failure==='script-load')return route.abort('failed');
          if(failure==='script-execute')return route.fulfill({contentType:'text/javascript',body:"document.querySelector('#drawer-toggle').innerHTML='旧导航';"});
          return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'初始化接口暂时不可用'})});
        });
        await probe.goto(BASE+'/agent');
        await probe.getByRole('button',{name:'重新加载',exact:true}).waitFor();
        if(!await probe.locator('#startup-message').innerText())throw new Error('Blank startup failure');
        failing=false;await probe.getByRole('button',{name:'重新加载',exact:true}).click();
        await probe.waitForSelector('#report-form');
        if(!new URL(probe.url()).searchParams.has('_reload'))throw new Error('Retry did not refresh document');
      }finally{await probe.close()}
    });
    if(reportSubmissions)throw new Error('Non-submit buttons triggered report generation');
    if(errors.length)throw new Error('Browser errors: '+errors.join(';'));
    console.log(JSON.stringify({passed:results.length,results,browserErrors:errors},null,2));
  }catch(e){console.error(e.message);await page.screenshot({path:path.join(outputs,'failure.png'),fullPage:true});process.exitCode=1}
  finally{fs.writeFileSync(path.join(root,'docs/browser-results.json'),JSON.stringify({results,browserErrors:errors},null,2));await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
