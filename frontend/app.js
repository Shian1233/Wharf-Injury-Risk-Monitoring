import {createSdWorkbench, isFeedback, scenarioParameters, FEEDBACK_PROFILE} from './sd-workbench.js';
const $=(s,root=document)=>root.querySelector(s);
const $$=(s,root=document)=>[...root.querySelectorAll(s)];
const H5=window.matchMedia('(max-width: 767.98px)');
let dataResizeObserver=null,dataFitTimer=0,dataLoadSequence=0;
const BASE=$('meta[name=app-base]')?.content.replace(/\/$/,'')||'';
const localURL=u=>BASE&&u.startsWith('/')&&!u.startsWith(BASE+'/')?BASE+u:u;
function prefixLinks(root){if(!BASE)return;for(const e of $$('[href^="/"],[src^="/"]',root)){for(const attr of ['href','src']){const v=e.getAttribute(attr);if(v?.startsWith('/'))e.setAttribute(attr,localURL(v))}}}
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const userMessage=v=>String(v??'').replace(/DeepSeek组织报告文字/gi,'智能体正在生成报告').replace(/DeepSeek/gi,'智能体').replace(/\bLLM\b/gi,'智能体').replace(/报告文字不是有效JSON/g,'报告文字格式不完整，请重新生成');
const shapes={
  book:'<path d="M12 6c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Zm0 0v15"/><path d="M6 9h3m6 0h3M6 13h3m6 0h3"/>',
  loader:'<path d="M21 12a9 9 0 1 1-6.2-8.55"/>',
  industry:'<circle cx="12" cy="12" r="2.6"/><circle cx="12" cy="3.5" r="1.5"/><circle cx="19.4" cy="7.7" r="1.5"/><circle cx="19.4" cy="16.3" r="1.5"/><circle cx="12" cy="20.5" r="1.5"/><circle cx="4.6" cy="16.3" r="1.5"/><circle cx="4.6" cy="7.7" r="1.5"/><path d="M12 9.4V5m2.3 5.7 3.8-2.2m-3.8 4.8 3.8 2.2M12 14.6V19m-2.3-5.7-3.8 2.2m3.8-4.8L5.9 8.5"/>',
  gallery:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  model:'<rect x="9" y="2" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="16" y="16" width="6" height="6" rx="1"/><path d="M12 8v4H5v4m7-4h7v4"/>',
  report:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z"/><path d="M14 2v6h6M8 12h8M8 16h6"/>',
  shield:'<path d="M12 2 3 6v6c0 6 9 10 9 10s9-4 9-10V6l-9-4Z"/><path d="m8 12 3 3 5-6"/>',
  columns:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
  settings:'<path d="M4 7h5m5 0h6M4 17h9m5 0h2"/><rect x="9" y="4" width="5" height="6" rx="1"/><rect x="13" y="14" width="5" height="6" rx="1"/>',
  chat:'<path d="M20 16a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v11Z"/><path d="M7 8h9M7 12h6"/>',
  back:'<path d="m14 6-6 6 6 6"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',plus:'<path d="M12 4v16M4 12h16"/>',
  upload:'<path d="M12 16V3m-5 5 5-5 5 5M3 16v5h18v-5"/>',download:'<path d="M12 3v13m-5-5 5 5 5-5M3 18v3h18v-3"/>',
  search:'<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>',close:'<path d="m6 6 12 12M18 6 6 18"/>',
  history:'<path d="M3 9a9 9 0 1 1 0 6M3 3v6h6M12 7v6l4 2"/>',play:'<path d="m8 4 12 8-12 8V4Z"/>',
  check:'<path d="m4 12 5 5L20 6"/>',menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  file:'<path d="M14 2H6v20h12V6l-4-4Z"/><path d="M14 2v5h5M8 12h6M8 16h6"/>',chart:'<path d="M3 3v18h18M6 16l4-7 5 3 5-8"/>',
  edit:'<path d="m16 3 5 5-12 12-6 1 1-6L16 3ZM13 6l5 5"/>',eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',chevron:'<path d="m8 10 4 4 4-4"/>',expand:'<path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5"/>',
};
const icon=(name)=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shapes[name]||shapes.file}</svg>`;
const btn=(text,action,cls='',symbol='')=>`<button type="button" class="btn ${cls}" data-action="${action}">${symbol?icon(symbol):''}${text}</button>`;
const badge=(text,cls='')=>`<span class="badge ${cls}">${esc(text)}</span>`;
const bytes=(n)=>n>=1e12?(n/1e12).toFixed(2)+' TB':n>=1e9?(n/1e9).toFixed(2)+' GB':n>=1e6?(n/1e6).toFixed(2)+' MB':n>=1e3?(n/1e3).toFixed(1)+' KB':n+' B';
const time=v=>v?new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'';
let state={parametersOpen:false,view:location.pathname.endsWith('/agent')?'reports':'gallery',config:null,overview:null,models:[],reports:[],dataset:'accidents',pageSize:10,rows:[],total:0,page:0,files:[],model:null,modelValidation:null,simulation:null,report:null,
  filters:{industry:'工贸',region:'',start:'',end:'',q:''},dataFilters:{industry:'',region:'',start:'',end:'',q:''},selected:new Set(),months:3,scenario:'基准场景',parameters:{},history:[],chatSession:'',chatMessages:[],llmModel:'',busy:false,chartMode:'auto',chartComparison:null,simulationHistory:[]};
let previousFocus=null,modalOnClose=null,polling=new Set();
let sdUI;
let applicationMenu=null,applicationTrigger=null;
const progressViews=new Map();
let progressFrame=0;
const content=$('#content');
function toast(message){const e=$('#toast');e.textContent=userMessage(message);e.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>e.hidden=true,4500)}
async function api(path,options={}){
  const res=await fetch(BASE+'/api'+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers}});
  const type=res.headers.get('content-type')||'';const value=type.includes('json')?await res.json():await res.text();
  if(!res.ok){if(res.status===401)loginModal();throw new Error(typeof value.detail==='string'?friendlyModelError(value.detail,state.model||{parameters:{},variables:[]}):Array.isArray(value.detail)?'填写内容未通过校验，请检查必填项、数值和日期范围':'请求未完成，请稍后重试')}
  return value;
}
const post=(path,body)=>api(path,{method:'POST',body:JSON.stringify(body)});
const download=url=>{const a=document.createElement('a');a.href=localURL(url);a.download='';document.body.append(a);a.click();a.remove()};
function field(label,key,value,type='text',attrs=''){return `<div class="field"><label for="${key}">${label}</label><input id="${key}" name="${key}" type="${type}" value="${esc(value)}" ${attrs}></div>`}
function select(label,key,values,value,emptyLabel=''){return `<div class="field"><label for="${key}">${label}</label><select id="${key}" name="${key}">${emptyLabel?`<option value="">${emptyLabel}</option>`:''}${values.map(v=>`<option value="${esc(typeof v==='object'?v.value:v)}" ${(typeof v==='object'?v.value:v)===value?'selected':''}>${esc(typeof v==='object'?v.label:v)}</option>`).join('')}</select></div>`}
function section(title){return `<div class="section-title"><h3>${title}</h3></div>`}
function empty(title,subtitle='',symbol='database'){return `<div class="empty">${icon(symbol)}<strong>${title}</strong>${subtitle?`<div>${esc(subtitle)}</div>`:''}</div>`}
function modal(title,body,footer='',wide=false){
  closeModal();previousFocus=document.activeElement;
  $('#modal-host').innerHTML=`<div class="modal-backdrop"><section class="modal ${wide?'wide':''}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-header"><h2 id="modal-title">${esc(title)}</h2><button class="icon-btn" data-action="close-modal" aria-label="关闭">${icon('close')}</button></div><div class="modal-body">${body}</div>${footer?`<div class="modal-footer">${footer}</div>`:''}</section></div>`;
  prefixLinks($('#modal-host'));
  $('.modal-backdrop').onclick=e=>{if(e.target===e.currentTarget)closeModal()};$('.modal [data-action="close-modal"]').onclick=closeModal;
  $('.modal').querySelector('input,button,select,textarea')?.focus();
}
function closeModal(){if(modalOnClose){modalOnClose();modalOnClose=null}$('#modal-host').innerHTML='';previousFocus?.focus?.();previousFocus=null}
function confirmModal(message,fn){modal('确认操作',`<p>${esc(message)}</p>`,btn('取消','cancel')+btn('确认','confirm','primary'));$('.modal [data-action="cancel"]').onclick=closeModal;$('.modal [data-action="confirm"]').onclick=async()=>{try{await fn();closeModal()}catch(e){toast(e.message)}}}
function header(){return `<header class="workbench-heading"><div class="workbench-identity"><h1><span>全国安全生产风险</span><span>智能研判与预测</span></h1></div><p>数据驱动风险研判，智能辅助安全决策</p></header>`}
function panelTitle(title,symbol){return `<div class="panel-title"><span class="panel-title-icon" aria-hidden="true">${icon(symbol)}</span><h2>${esc(title)}</h2></div>`}
function reportEmpty(){return `<div class="report-empty"><div class="report-illustration" aria-hidden="true"><div class="report-paper-back"></div><div class="report-paper"><div class="paper-masthead">${icon('shield')}<span>安全生产 · 风险研判</span></div><div class="paper-title">风险研判<br>与预测分析报告</div><div class="paper-rule"></div><div class="paper-section"><span>01</span><div><b>风险概览</b><i></i><i></i></div></div><div class="paper-section"><span>02</span><div><b>趋势预测</b><i></i></div></div><div class="paper-section"><span>03</span><div><b>防控建议</b><i></i></div></div><div class="paper-footer">${icon('report')}<span>分析 · 预测 · 决策</span></div></div></div><div class="report-empty-caption"><h3>让数据，形成判断</h3><p>完成左侧配置，生成风险研判与预测分析报告</p></div></div>`}
function overviewCards(){
  const o=state.overview,n=v=>Number(v||0).toLocaleString('zh-CN');
  return `<section class="overview-cards" aria-label="业务概览">
    <article class="overview-card" data-metric="data"><i class="overview-icon" aria-hidden="true">${icon('database')}</i><span>数据量与条目数</span><div class="data-metric-values"><div><strong>${n(o.total_records)}</strong><small>条</small></div><span class="storage-size">${bytes(o.bytes)}</span></div></article>
    <article class="overview-card" data-metric="industries"><i class="overview-icon" aria-hidden="true">${icon('industry')}</i><span>覆盖行业</span><div><strong>${n(o.industry_count)}</strong><small>个</small></div></article>
    <article class="overview-card" data-metric="models"><i class="overview-icon" aria-hidden="true">${icon('model')}</i><span>仿真模型</span><div><strong>${n(o.model_count)}</strong><small>个</small></div></article>
    <article class="overview-card" data-metric="reports"><i class="overview-icon" aria-hidden="true">${icon('report')}</i><span>研判报告</span><div><strong>${n(o.report_count)}</strong><small>份</small></div></article>
  </section>`;
}
function tabs(){return `<nav class="agent-navigation" role="tablist" aria-label="智能体功能" aria-orientation="${H5.matches?'horizontal':'vertical'}">${[['database','数据库管理','database'],['models','SD模型库','model'],['reports','报告生成','report']].map(([k,l,s])=>`<button type="button" role="tab" aria-selected="${state.view===k}" tabindex="${state.view===k?'0':'-1'}" class="business-tab ${state.view===k?'active':''}" data-nav="${k}">${icon(s)}<span>${l}</span></button>`).join('')}</nav>`}
function workbenchTools(extraClass=''){
  return `<section class="workbench-tools ${extraClass}" aria-label="相关操作">${btn('查看记录','report-history','','history')}${btn('使用说明','help','','book')}${btn('系统设置','settings','','settings')}</section>`;
}
function render(){
  if(!state.config||!state.overview)return;
  simulationResizeObserver?.disconnect();
  dataResizeObserver?.disconnect();clearTimeout(dataFitTimer);
  closeApplicationModels();
  const viewChanged=content.dataset.view!==state.view;
  content.dataset.view=state.view;
  const agent=state.view!=='gallery';
  content.classList.toggle('agent-content',agent);
  content.innerHTML=agent?`${header()}${overviewCards()}<div class="agent-workspace"><aside class="agent-rail">${tabs()}${workbenchTools('rail-tools')}</aside><div class="workspace-body">${state.view==='reports'?reportsView():state.view==='database'?databaseView():modelsView()}</div></div><footer class="workbench-footer">内容由智能体生成，请结合业务核验</footer>`:galleryView();
  if(viewChanged)$('.workspace-body',content)?.classList.add('view-enter');
  prefixLinks(content);
  $$('[data-nav]',content).forEach(e=>e.onclick=()=>navigate(e.dataset.nav));
  $$('[data-action]',content).forEach(e=>e.onclick=()=>{const menu=e.closest('.more-menu');if(menu){menu.open=false;$('summary',menu).focus()}action(e.dataset.action,e)});
  if(state.view==='reports')bindReport();if(state.view==='database')bindDatabase();if(state.view==='models')bindModels();
  for(const entry of progressViews.values())paintJobProgress(entry);
}
async function refresh(){state.overview=await api('/overview');state.reports=await api('/reports')}
async function navigate(view){
  if(view!=='database'){dataLoadSequence++;dataResizeObserver?.disconnect();clearTimeout(dataFitTimer)}
  state.view=view;if(view==='gallery')history.pushState({},'',localURL('/'));else history.pushState({},'',localURL('/agent'));
  if(view==='database')await loadData(false);if(view==='models'){if(!state.model)state.model=fixedModel(state.filters.industry)||state.models[0];await loadModelValidation()}
  render();$('.main').scrollTop=0;if($('.workspace-body'))$('.workspace-body').scrollTop=0;
}
function galleryView(){return `<div class="gallery-tabs"><h1>官方智能体 <span class="muted" style="font-family:inherit;font-size:18px;font-weight:400">1</span></h1></div><div class="toolbar"><div class="dataset-tabs" style="margin:0"><span class="dataset-tab active">全部</span><span class="dataset-tab">安全生产</span></div></div><div class="agent-grid"><a class="agent-card" href="/agent" target="_top"><div class="agent-art"><svg viewBox="0 0 440 230" fill="none" aria-hidden="true"><path d="M68 185h307M89 156l61-32 52 11 55-65 68 27 47-44" stroke="#788BB0" stroke-width="2"/><path d="M89 178 150 152l52 7 55-54 68 11 47-20V185H89Z" fill="#CED7E9" opacity=".6"/><circle cx="220" cy="111" r="58" fill="white"/><path d="m220 67-34 13v26c0 28 34 47 34 47s34-19 34-47V80l-34-13Z" fill="#ECF0F8" stroke="#1E3264" stroke-width="2.5"/><path d="m203 108 12 12 23-27" stroke="#1E3264" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="89" cy="156" r="6" fill="#23B283"/><circle cx="372" cy="53" r="6" fill="#1E3264"/><rect x="58" y="49" width="65" height="28" rx="6" fill="white"/><path d="M71 63h39" stroke="#A2B0CD" stroke-width="4" stroke-linecap="round"/><rect x="322" y="153" width="74" height="32" rx="6" fill="white"/><path d="M336 169h46" stroke="#23B283" stroke-width="4" stroke-linecap="round"/></svg></div><div class="agent-card-body"><h2>安全生产风险研判与预测</h2><p>事故数据分析、风险演化仿真与研判报告生成</p><div class="agent-card-footer">${badge('应急管理')}<span style="color:var(--brand)">进入智能体 ${icon('arrow')}</span></div></div></a></div>`}
function fixedModel(industry){return state.models.find(m=>m.industry===industry&&m.model_family===FEEDBACK_PROFILE)||state.models.find(m=>m.industry===industry)}
function reportExpertReview(report){
  const review=report.expert_review||{};
  return `<form id="report-review-form" class="report-review"><div class="report-review-heading"><h3>研判及预测结论与指标专家验证</h3><span>${review.updated_at?'已保存':'待填写'}</span></div><div class="report-review-row"><label><span>研判及预测结论</span><textarea id="review-conclusion" maxlength="4000" rows="2" placeholder="填写对报告主要结论的业务研判">${esc(review.conclusion||'')}</textarea></label><label><span>指标专家验证</span><textarea id="review-indicators" maxlength="4000" rows="2" placeholder="填写指标合理性、验证意见及调整建议">${esc(review.indicator_validation||'')}</textarea></label><button class="btn primary" type="submit">保存验证</button></div></form>`;
}
function reportsView(){
  const industry=state.filters.industry;
  const models=[fixedModel(industry)].filter(Boolean);
  state.reportModel=(models.find(m=>m.id===state.reportModel)||models[0])?.id||'';
  const selectedModel=models.find(m=>m.id===state.reportModel),manualParams=scenarioParameters(selectedModel);
  const preview=state.report
    ? `<iframe class="report-frame" title="正式报告预览" src="/api/reports/${state.report.id}/html" sandbox="allow-same-origin"></iframe><div class="report-result-footer"><span class="muted">${state.report.count}条事故 · ${state.report.body_hanzi}字</span><div class="actions">${btn('HTML','download-html','','download')}${btn('PDF','download-pdf','primary','download')}</div></div>${state.report.llm?.status==='failed'?`<div class="notice report-generation-notice"><div><strong>当前为分析草稿</strong><p>${esc(userMessage(state.report.llm.error||'报告文字生成未完成'))}</p></div>${btn('重新生成','retry-report','','report')}</div>`:''}${reportExpertReview(state.report)}`
    : `${reportEmpty()}`;
  return `<div class="report-workspace"><div class="report-side">
    <section class="panel report-config" aria-label="报告配置"><form id="report-form">
      <div class="report-form-body"><div class="config-heading">${panelTitle('报告配置','settings')}</div>
        <section class="report-section">${section('分析范围')}<div class="report-fields">
          ${select('行业','industry',state.config.industries,industry)}
          ${select('地区','region',state.overview.regions,state.filters.region,'全国')}
          ${field('开始日期','start',state.filters.start,'date','required')}
          ${field('结束日期','end',state.filters.end,'date','required')}
        </div></section>
        <label class="check coverage-check"><input type="checkbox" name="coverage_confirmed" ${state.coverageConfirmed?'checked':''}>已完整采集所选范围的事故数据</label>
        <section class="report-section prediction-section">${section('预测设置')}<div class="report-fields">
          ${select('预测周期','months',[1,3,6,12,24,36].map(x=>({value:String(x),label:x+'个月'})),String(state.months))}
          <div class="field"><label for="report-model">SD仿真模型</label><select id="report-model" name="model_id" title="${esc(selectedModel?.name||'')}">${models.map(m=>`<option value="${esc(m.id)}" ${m.id===state.reportModel?'selected':''}>${esc(m.industry)}风险模型</option>`).join('')}</select></div>
          ${select('仿真场景','scenario',['基准场景','生产压力增大','安全投入减少'],state.scenario)}
          <div class="field scenario-parameter-field"><label>模型参数</label><button type="button" class="btn parameter-toggle" aria-controls="report-parameters" aria-expanded="${state.parametersOpen!==false}">${icon('settings')}设置参数 ${icon('chevron')}</button></div>
        </div><div id="report-parameters" class="inline-parameters" ${state.parametersOpen===false?'hidden':''}>
          <div class="parameter-caption"><span>情景参数</span><button type="button" class="btn link sm" id="reset-report-params">恢复默认</button></div><div class="report-fields">${manualParams.map(([k,p],i)=>`<div class="field"><label for="report-param-${i}">${esc(p.label)}</label><div class="parameter-control">${sdUI.input(k,p,state.parameters[k]??p.value,'data-report-param','report-param-'+i)}${p.unit?`<span class="parameter-unit">${esc(p.unit)}</span>`:''}</div></div>`).join('')}</div>
        </div></section>
        <section class="report-section report-indicators"><div class="section-title"><h3>报告指标</h3><span id="indicator-count">已选 ${state.selected.size} 项</span></div><div id="inline-indicators">${inlineIndicators()}</div></section>
      </div>
      <div class="report-submit"><button type="button" class="btn application-model-button" data-action="select-application-model" aria-label="应用模型" aria-haspopup="listbox" aria-expanded="false" aria-controls="application-model-options" title="${esc(state.llmModel)}"><span>${esc(state.llmModel||'模型选择')}</span>${icon('chevron')}</button><button class="btn primary" type="submit" ${state.busy?'disabled':''}>${state.busy?'<span class="loading-mark" aria-hidden="true">'+icon('loader')+'</span>':icon('report')}${state.busy?'正在生成…':'一键生成'}</button></div>
    </form></section></div>
    <section class="panel report-preview" aria-label="报告预览"><div class="panel-head">${panelTitle('报告预览','report')}</div><div id="report-job"></div>${preview}</section>
  </div>`;
}
function bindReport(){
  const form=$('#report-form');
  form.addEventListener('change',e=>{
    const name=e.target.name;
    if(['industry','region','start','end'].includes(name)){
      state.filters[name]=e.target.value;
      if(name==='industry'){state.parameters={};render()}
    }
    if(name==='months')state.months=Number(e.target.value);
    if(name==='scenario')state.scenario=e.target.value;
    if(name==='model_id'){state.reportModel=e.target.value;state.parameters={};render()}
    if(name==='coverage_confirmed')state.coverageConfirmed=e.target.checked;
  });
  bindInlineIndicators();
  $('.parameter-toggle',form).onclick=e=>{if(state.parametersOpen!==false){const invalid=$$('[data-report-param]',form).find(i=>!i.checkValidity());if(invalid){invalid.reportValidity();return}}state.parametersOpen=state.parametersOpen===false;$('#report-parameters').hidden=!state.parametersOpen;e.currentTarget.setAttribute('aria-expanded',String(state.parametersOpen))};
  $('#reset-report-params').onclick=()=>{state.parameters={};const m=state.models.find(m=>m.id===state.reportModel);$$('[data-report-param]',form).forEach(i=>i.value=m.parameters[i.dataset.reportParam].value)};
  $$('[data-report-param]',form).forEach(i=>i.oninput=()=>{if(i.value!==''&&i.checkValidity())state.parameters[i.dataset.reportParam]=Number(i.value)});
  const reviewForm=$('#report-review-form');
  if(reviewForm)reviewForm.onsubmit=async e=>{e.preventDefault();const button=$('button[type=submit]',reviewForm);try{button.disabled=true;button.textContent='保存中…';const expert_review=await api('/reports/'+state.report.id+'/review',{method:'PATCH',body:JSON.stringify({conclusion:$('#review-conclusion').value,indicator_validation:$('#review-indicators').value})});state.report.expert_review=expert_review;render();toast('专家验证已保存')}catch(err){button.disabled=false;button.textContent='保存验证';toast(err.message)}};
  form.onsubmit=async e=>{
    e.preventDefault();
    const submit=$('button[type=submit]',form);
    const finish=finishReportGeneration;
    try{
      if(!state.selected.size){toast('请至少选择一项报告指标');$('.report-indicators').scrollIntoView({block:'nearest'});return}
      const currentParameters={};for(const i of $$('[data-report-param]',form)){if(!i.checkValidity()){state.parametersOpen=true;$('#report-parameters').hidden=false;i.reportValidity();return}currentParameters[i.dataset.reportParam]=Number(i.value)}state.parameters=currentParameters;
      const fd=new FormData(form);
      const body={...state.filters,industry:fd.get('industry'),region:fd.get('region'),start:fd.get('start'),end:fd.get('end'),months:Number(fd.get('months')),scenario:fd.get('scenario'),model_id:fd.get('model_id'),parameters:state.parameters,indicators:[...state.selected],use_llm:true,llm_model:state.llmModel,coverage_confirmed:fd.has('coverage_confirmed')};
      state.busy=true;submit.disabled=true;submit.innerHTML='<span class="loading-mark" aria-hidden="true">'+icon('loader')+'</span>正在生成…';
      const job=await post('/reports',body);
      rememberReportJob({id:job.id,parameters:body});
      watchReportJob(job);
    }catch(err){finish();toast(err.message)}
  };
}
const REPORT_JOB_KEY='risk-agent:report-job:'+BASE;
function rememberReportJob(value){try{if(value)sessionStorage.setItem(REPORT_JOB_KEY,JSON.stringify(value));else sessionStorage.removeItem(REPORT_JOB_KEY)}catch{}}
function finishReportGeneration(){rememberReportJob(null);state.busy=false;const current=$('#report-form button[type=submit]');if(current){current.disabled=false;current.innerHTML=icon('report')+'一键生成'}}
function watchReportJob(job){
  watchJob(job,'#report-job',async result=>{
    state.report=result;finishReportGeneration();render();
    toast(result.llm?.status==='failed'?'已生成分析草稿，报告文字需要重新生成':'分析报告已生成');
    try{await refresh();if(state.report?.id===result.id)render()}catch{toast('报告已生成，概览更新失败，可稍后刷新')}
  },finishReportGeneration);
}
async function resumeReportJob(){
  let saved;try{saved=JSON.parse(sessionStorage.getItem(REPORT_JOB_KEY)||'null')}catch{return}
  if(!saved?.id||!saved.parameters)return;
  try{
    const job=await api('/jobs/'+encodeURIComponent(saved.id)),p=saved.parameters;
    for(const key of ['industry','region','start','end'])if(p[key]!==undefined)state.filters[key]=p[key];
    state.months=p.months||state.months;state.scenario=p.scenario||state.scenario;state.reportModel=p.model_id||state.reportModel;
    state.parameters=p.parameters||{};state.selected=new Set(p.indicators||[...state.selected]);state.coverageConfirmed=Boolean(p.coverage_confirmed);
    if(state.config.llm.models.some(m=>m.id===p.llm_model))state.llmModel=p.llm_model;
    state.busy=true;render();watchReportJob(job);
  }catch{rememberReportJob(null);toast('上次任务状态暂不可用，可在任务记录中查看')}
}
function closeApplicationModels(restoreFocus=false){
  applicationMenu?.remove();applicationMenu=null;
  const trigger=applicationTrigger;applicationTrigger=null;
  trigger?.setAttribute('aria-expanded','false');
  if(restoreFocus)trigger?.focus();
}
function openApplicationModels(trigger){
  if(applicationMenu){closeApplicationModels(true);return}
  const models=state.config.llm.models||[];
  if(!models.length){toast('暂无可用的应用模型');return}
  applicationTrigger=trigger;trigger.setAttribute('aria-expanded','true');
  const menu=document.createElement('div');applicationMenu=menu;
  menu.id='application-model-options';menu.className='application-model-menu';
  menu.setAttribute('role','listbox');menu.setAttribute('aria-label','选择应用模型');
  menu.innerHTML=models.map(m=>`<button type="button" role="option" aria-selected="${m.id===state.llmModel}" data-llm-model="${esc(m.id)}"><span>${esc(m.label||m.id)}</span>${m.id===state.llmModel?icon('check'):''}</button>`).join('');
  document.body.append(menu);
  const r=trigger.getBoundingClientRect(),width=Math.min(232,innerWidth-32);
  menu.style.width=width+'px';menu.style.left=Math.max(16,Math.min(r.left,innerWidth-width-16))+'px';
  const height=menu.offsetHeight;
  menu.style.top=Math.max(16,Math.min(r.top>=height+24?r.top-height-8:r.bottom+8,innerHeight-height-16))+'px';
  const options=$$('[role=option]',menu);
  options.forEach(option=>option.onclick=()=>{
    state.llmModel=option.dataset.llmModel;
    $('span',trigger).textContent=models.find(m=>m.id===state.llmModel)?.label||state.llmModel;
    trigger.title=state.llmModel;closeApplicationModels(true);
  });
  menu.onkeydown=e=>{
    const i=options.indexOf(document.activeElement);
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeApplicationModels(true);return}
    if(e.key==='Tab'){closeApplicationModels(true);return}
    const next=e.key==='ArrowDown'?(i+1)%options.length:e.key==='ArrowUp'?(i-1+options.length)%options.length:e.key==='Home'?0:e.key==='End'?options.length-1:-1;
    if(next>=0){e.preventDefault();options[next].focus()}
  };
  (options.find(o=>o.dataset.llmModel===state.llmModel)||options[0]).focus();
}
document.addEventListener('pointerdown',e=>{if(applicationMenu&&!applicationMenu.contains(e.target)&&!applicationTrigger?.contains(e.target))closeApplicationModels()});
document.addEventListener('scroll',e=>{if(applicationMenu&&!applicationMenu.contains(e.target))closeApplicationModels()},true);
let resizingTimer;
window.addEventListener('resize',()=>{closeApplicationModels();document.documentElement.classList.add('is-resizing');clearTimeout(resizingTimer);resizingTimer=setTimeout(()=>document.documentElement.classList.remove('is-resizing'),80)});
function inlineIndicators(){
  const groups=state.config.indicator_groups,active=state.indicatorGroup||0;
  const short=['基础条件','事故特征','事故致因','事故后果','风险预测','风险治理'];
  return `<div class="indicator-categories" role="tablist" aria-label="指标分类">${groups.map((g,i)=>`<button type="button" role="tab" aria-selected="${i===active}" tabindex="${i===active?0:-1}" data-indicator-group="${i}" title="${esc(g.name)}">${short[i]}<span>${g.items.filter(x=>state.selected.has(x)).length}</span></button>`).join('')}</div><div class="inline-indicator-actions"><span>${esc(groups[active].name.replace(/^\d+\. /,''))}</span><button type="button" class="btn link sm" id="indicator-group-toggle">${groups[active].items.every(x=>state.selected.has(x))?'清空本类':'全选本类'}</button></div><div class="inline-indicator-options" role="group" aria-label="${esc(groups[active].name)}">${groups[active].items.map(x=>`<label class="check"><input type="checkbox" name="indicators" value="${esc(x)}" ${state.selected.has(x)?'checked':''}><span>${esc(x)}</span></label>`).join('')}</div>`;
}
function bindInlineIndicators(){
  const host=$('#inline-indicators');
  const redraw=()=>{host.innerHTML=inlineIndicators();$('#indicator-count').textContent='已选 '+state.selected.size+' 项';bindInlineIndicators()};
  $$('[data-indicator-group]',host).forEach(b=>{
    b.onclick=()=>{state.indicatorGroup=Number(b.dataset.indicatorGroup);redraw();$(`[data-indicator-group="${state.indicatorGroup}"]`,host).focus()};
    b.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();state.indicatorGroup=e.key==='Home'?0:e.key==='End'?5:(Number(b.dataset.indicatorGroup)+(e.key==='ArrowRight'?1:5))%6;redraw();$(`[data-indicator-group="${state.indicatorGroup}"]`,host).focus()};
  });
  $$('input[name=indicators]',host).forEach(i=>i.onchange=()=>{i.checked?state.selected.add(i.value):state.selected.delete(i.value);const value=i.value;redraw();$$('input[name=indicators]',host).find(x=>x.value===value)?.focus()});
  $('#indicator-group-toggle').onclick=()=>{const items=state.config.indicator_groups[state.indicatorGroup||0].items,clear=items.every(x=>state.selected.has(x));items.forEach(x=>clear?state.selected.delete(x):state.selected.add(x));redraw();$('#indicator-group-toggle').focus()};
}

function defaultColumns(){return {accidents:['编号','事故名称','行业','省份','发生时间','事故等级'],enterprises:['记录编号','企业名称','行业','省份','统计期','生产状态'],climate:['记录编号','省份','统计日期','数据类型','平均温度（℃）','预警等级'],economy:['记录编号','省份','统计期','行政层级','地区生产总值（亿元）','生产安全事故数']}[state.dataset]}
function databaseTabs(){
  const active=state.databaseSection==='files'?'files':state.dataset;
  return `<div class="dataset-tabs" role="tablist" aria-label="数据分类">${[{id:'files',label:'原始资料'},...state.config.schemas].map(s=>`<button role="tab" aria-selected="${active===s.id}" aria-controls="database-panel" tabindex="${active===s.id?'0':'-1'}" id="dataset-${s.id}" class="dataset-tab ${active===s.id?'active':''}" data-dataset="${s.id}">${s.label} <span class="muted">${s.id==='files'?state.files.length:state.overview.counts[s.id]}</span></button>`).join('')}</div>`;
}
function databaseView(){
  if(state.databaseSection==='files')return `<section class="panel database-panel"><div class="database-heading">${panelTitle('数据资源','database')}</div>${databaseTabs()}<div id="database-panel" role="tabpanel" aria-labelledby="dataset-files" class="file-list"><div class="panel-head"><span class="muted">共 ${state.files.length} 份资料</span><div class="actions">${btn('核验存储','storage-verify','','check')}${btn('上传资料','upload','','upload')}</div></div>${state.files.length?state.files.map(f=>`<div class="file-row"><div class="file-info">${icon('file')}<div><div class="file-name" title="${esc(f.NAME)}">${esc(f.NAME)}</div><div class="file-meta">${bytes(f.SIZE_BYTES)} · ${time(f.CREATED_AT)}</div></div></div><div class="actions"><button class="btn link sm" data-file-preview="${f.ID}">预览</button><a class="btn link sm" href="/api/files/${f.ID}/download" download>下载</a><button class="btn link sm danger" data-file-delete="${f.ID}">删除</button></div></div>`).join(''):empty('暂无原始资料','支持PDF、Word、HTML和图片','file')}</div></section>`;
  const columns=state.columns?.[state.dataset]||defaultColumns();const s=state.config.schemas.find(s=>s.id===state.dataset);
  return `<section class="panel database-panel"><div class="database-heading">${panelTitle('数据资源','database')}</div>${databaseTabs()}<div id="database-panel" role="tabpanel" aria-labelledby="dataset-${state.dataset}"><div class="toolbar"><div class="toolbar-filters"><input id="data-q" class="search" placeholder="搜索名称或编号" value="${esc(state.dataFilters.q)}" aria-label="搜索名称或编号"><select id="data-industry" aria-label="筛选行业" ${['climate','economy'].includes(state.dataset)?'disabled':''}><option value="">全部行业</option>${state.config.industries.map(i=>`<option ${i===state.dataFilters.industry?'selected':''}>${i}</option>`).join('')}</select><select id="data-region" aria-label="筛选地区"><option value="">全国</option>${state.overview.regions.map(i=>`<option ${i===state.dataFilters.region?'selected':''}>${esc(i)}</option>`).join('')}</select>${btn('时间范围','data-dates',state.dataFilters.start||state.dataFilters.end?'soft':'')}${btn('筛选','data-filter','','search')}</div><div class="actions">${btn('字段','columns','','columns')}${btn('下载','export-data','','download')}${btn('新增','new-record','','plus')}${btn('上传数据','upload','primary','upload')}</div></div>${state.rows.length?`<div class="table-wrap records-viewport"><table class="data-table records-table"><thead><tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}<th>操作</th></tr></thead><tbody>${state.rows.map((r,i)=>`<tr>${columns.map(c=>`<td class="truncate" title="${esc(r[c])}">${esc(r[c]??'—')}</td>`).join('')}<td><div class="actions"><button class="btn link sm" data-record="${i}">查看</button><button class="btn link sm" data-edit="${i}">编辑</button><button class="btn link sm danger" data-delete="${i}">删除</button></div></td></tr>`).join('')}</tbody></table></div>`:empty('暂无'+s.label,'上传Excel或CSV后导入数据')}<div class="pagination" data-page-size="${state.pageSize}"><span class="muted">共 ${state.total} 条 · 每页${state.pageSize}条</span><div class="actions"><button class="btn sm" data-page="prev" ${state.page===0?'disabled':''}>上一页</button><span>${state.page+1} / ${Math.max(1,Math.ceil(state.total/state.pageSize))}</span><button class="btn sm" data-page="next" ${(state.page+1)*state.pageSize>=state.total?'disabled':''}>下一页</button></div></div></div></section>`;
}
async function loadData(redraw=true){
  const sequence=++dataLoadSequence;
  if(state.databaseSection==='files'){const files=await api('/files');if(sequence!==dataLoadSequence)return;state.files=files;if(redraw&&state.view==='database')render();return}
  const qs=new URLSearchParams({...state.dataFilters,limit:state.pageSize,offset:state.page*state.pageSize});
  const [data,files]=await Promise.all([api(`/data/${state.dataset}?${qs}`),api('/files')]);
  if(sequence!==dataLoadSequence)return;
  state.rows=data.items;state.total=data.total;state.files=files;
  if(state.page>0&&state.page*state.pageSize>=state.total){state.page=Math.max(0,Math.ceil(state.total/state.pageSize)-1);return loadData(redraw)}
  if(redraw&&state.view==='database')render();
}
function observeDataCapacity(){
  const viewport=$('.records-viewport');if(!viewport)return;
  const fit=async()=>{
    if(state.view!=='database'||state.databaseSection==='files'||!viewport.isConnected)return;
    const row=$('tbody tr',viewport),header=$('thead',viewport);if(!row||!header)return;
    const capacity=Math.max(1,Math.min(200,Math.floor((viewport.clientHeight-header.getBoundingClientRect().height+.5)/row.getBoundingClientRect().height)));
    if(capacity===state.pageSize)return;
    const firstIndex=state.page*state.pageSize;state.pageSize=capacity;state.page=Math.floor(firstIndex/capacity);
    try{await loadData()}catch(e){toast(e.message)}
  };
  dataResizeObserver=new ResizeObserver(()=>{clearTimeout(dataFitTimer);dataFitTimer=setTimeout(fit,100)});
  dataResizeObserver.observe(viewport);
}

function bindDatabase(){
  $$('[data-dataset]').forEach(e=>{
    e.onclick=async()=>{state.databaseSection=e.dataset.dataset==='files'?'files':'records';if(state.databaseSection==='records'&&state.dataset!==e.dataset.dataset){state.dataset=e.dataset.dataset;state.dataFilterDraft=null;state.dataFilters={industry:'',region:'',start:'',end:'',q:''};state.page=0}await loadData();$(`[data-dataset="${e.dataset.dataset}"]`)?.focus()};
    e.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const tabs=$$('[data-dataset]'),i=tabs.indexOf(e),next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length;tabs[next].click()};
  });
  $$('[data-record]').forEach(e=>e.onclick=()=>recordModal(state.rows[Number(e.dataset.record)],true));$$('[data-edit]').forEach(e=>e.onclick=()=>recordModal(state.rows[Number(e.dataset.edit)],false));
  $$('[data-delete]').forEach(e=>e.onclick=()=>{const r=state.rows[Number(e.dataset.delete)];confirmModal('删除这条记录？历史报告保留其计算快照。',async()=>{await api(`/data/${state.dataset}/${r._id}`,{method:'DELETE'});await refresh();await loadData()})});
  $$('[data-page]').forEach(e=>e.onclick=async()=>{state.page+=e.dataset.page==='next'?1:-1;await loadData()});
  $$('[data-file-preview]').forEach(e=>e.onclick=async()=>{const p=await api(`/files/${e.dataset.filePreview}/preview`);modal('资料预览',`<div class="document-text">${esc(p.text||p.ocr_status||'尚未提取文字')}</div>`)});
  $$('[data-file-delete]').forEach(e=>e.onclick=()=>confirmModal('删除原始文件及其导入的结构化记录？',async()=>{await api('/files/'+e.dataset.fileDelete,{method:'DELETE'});await refresh();await loadData()}));
  if($('#data-q')){
    for(const key of ['q','industry','region']){const input=$('#data-'+key);if(state.dataFilterDraft?.[key]!=null)input.value=state.dataFilterDraft[key];input.addEventListener('input',()=>{state.dataFilterDraft=state.dataFilterDraft||{};state.dataFilterDraft[key]=input.value})}
    $('#data-q').onkeydown=e=>{if(e.key==='Enter')action('data-filter')};
  }
  observeDataCapacity();
}
function recordModal(row={},readOnly=false){
  const schema=state.config.schemas.find(s=>s.id===state.dataset);const fields=schema.fields;
  modal(readOnly?'记录详情':row._id?'编辑记录':'新增记录',`<form id="record-form" class="record-form">${fields.map((f,i)=>`<div class="field"><label for="rec-${i}" title="${esc(schema.field_paths[i])}">${esc(f)}</label>${String(row[f]||'').length>150||/原因|经过|整改|备注|说明|救援/.test(f)?`<textarea id="rec-${i}" name="${esc(f)}" ${readOnly?'readonly':''}>${esc(row[f])}</textarea>`:`<input id="rec-${i}" name="${esc(f)}" value="${esc(row[f])}" ${readOnly?'readonly':''}>`}</div>`).join('')}</form>`,readOnly?'':btn('保存','save-record','primary'),true);
  if(!readOnly)$('[data-action="save-record"]',$('.modal')).onclick=async()=>{try{const data=Object.fromEntries([...new FormData($('#record-form'))].map(([k,v])=>[k,v===''?null:v]));if(row._id)await api(`/data/${state.dataset}/${row._id}`,{method:'PUT',body:JSON.stringify({data,version:row._version})});else await post(`/data/${state.dataset}`,data);closeModal();await refresh();await loadData();toast('记录已保存')}catch(e){toast(e.message)}};
}
async function uploadModal(){
  modal('上传与导入',`<div class="field" style="margin-bottom:16px"><label>CSV目标数据集</label><select id="upload-dataset">${state.config.schemas.map(s=>`<option value="${s.id}" ${s.id===state.dataset?'selected':''}>${s.label}</option>`).join('')}</select></div><div class="dropzone" id="dropzone">${icon('upload')}<h3>选择文件或拖拽到此处</h3><p class="muted">Excel、CSV、PDF、Word、HTML、图片</p><input type="file" id="upload-file" accept=".xlsx,.csv,.pdf,.docx,.html,.htm,.png,.jpg,.jpeg,.tiff,.txt"></div><div id="upload-status" style="margin-top:16px"></div>`);
  const zone=$('#dropzone');zone.ondragover=e=>{e.preventDefault();zone.classList.add('drag')};zone.ondragleave=()=>zone.classList.remove('drag');zone.ondrop=e=>{e.preventDefault();zone.classList.remove('drag');if(e.dataTransfer.files[0])sendUpload(e.dataTransfer.files[0])};$('#upload-file').onchange=e=>{if(e.target.files[0])sendUpload(e.target.files[0])};
}
async function sendUpload(file){
  const host=$('#upload-status');try{host.innerHTML='<div class="info-note">正在上传 '+esc(file.name)+'…</div>';const fd=new FormData();fd.append('file',file);fd.append('dataset',$('#upload-dataset').value);const result=await api('/uploads',{method:'POST',body:fd});if(result.duplicate){host.innerHTML=`<div class="info-note">${esc(result.message)}</div>`;return}
    watchJob(result.job,'#upload-status',stage=>{
      if(!$('#upload-status'))return;
      if(stage.raw){$('#upload-status').innerHTML='<div class="info-note">原始资料已保存</div>';refresh().then(()=>{if(state.view==='database')loadData()});return}
      $('#upload-status').innerHTML=`<div class="info-note">解析完成：${stage.valid} 条可导入，${stage.rejected} 条未通过校验</div><div class="actions" style="margin-top:16px">${btn('确认导入','commit-import','primary')}${stage.rejected?`<a class="btn" href="/api/imports/${stage.id}/errors" download>错误清单</a>`:''}</div><div class="table-wrap" style="margin-top:16px"><table class="data-table"><thead><tr><th>数据集</th><th>条数</th></tr></thead><tbody>${Object.entries(stage.counts).map(([k,v])=>`<tr><td>${state.config.schemas.find(s=>s.id===k).label}</td><td>${v}</td></tr>`).join('')}</tbody></table></div>${Object.entries(stage.previews).map(([k,rows])=>`<details style="margin-top:16px"><summary>${state.config.schemas.find(s=>s.id===k).label} · 预览</summary>${importPreview(rows)}</details>`).join('')}`;
      $('[data-action="commit-import"]',$('.modal')).onclick=async e=>{try{e.currentTarget.disabled=true;const j=await post('/imports/'+stage.id+'/commit',{});watchJob(j,'#upload-status',async result=>{if($('#upload-status'))$('#upload-status').innerHTML=`<div class="info-note">导入 ${result.imported} 条，重复 ${result.duplicate} 条，校验未通过 ${result.rejected} 条</div>`;await refresh();if(state.view==='database')await loadData();toast('数据导入完成')})}catch(e){toast(e.message)}};
    });
  }catch(e){if(host)host.innerHTML=`<div class="notice">${esc(e.message)}</div>`}
}
// Translate model expressions for people; identifiers remain internal to the saved model.
const MATH_LABELS={min:'最小值',max:'最大值',abs:'绝对值',exp:'指数函数',log:'自然对数',sqrt:'平方根',sin:'正弦',cos:'余弦'};
const MATH_SIGNS={'+':'＋','-':'−','*':'×','/':'÷','**':'幂','(':'（',')':'）',',':'，'};
function expressionTokens(value){return String(value??'').match(/(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_\u4e00-\u9fff][A-Za-z_0-9\u4e00-\u9fff]*|\*\*|[^\s]/g)||[]}
function modelLabels(model){
  const names={time:'仿真时间',...MATH_LABELS};
  Object.entries(model.parameters||{}).forEach(([k,p],i)=>names[k]=p.label&&p.label!==k?p.label:/[\u4e00-\u9fff]/.test(k)?k:'参数 '+(i+1));
  (model.variables||[]).forEach((v,i)=>names[v.name]=v.label&&v.label!==v.name?v.label:/[\u4e00-\u9fff]/.test(v.name)?v.name:'风险变量 '+(i+1));
  return names;
}
function expressionLabel(token,model){return modelLabels(model)[token]||MATH_SIGNS[token]||(/^[-+]?\d|^\.\d/.test(token)?token:'未识别项')}
function readableExpression(value,model){return expressionTokens(value).map(t=>expressionLabel(t,model)).join(' ')}
function friendlyModelError(message,model){
  const labels=modelLabels(model);
  return String(message).replace(/[A-Za-z_][A-Za-z_0-9]*/g,key=>labels[key]||({stock:'风险存量',aux:'计算指标'}[key])||key)
    .replace('模型需提供risk_index输出','请保留综合风险指数作为模型输出');
}
function displayTable(headers,rows,cls=''){
  return rows.length?`<div class="table-wrap ${cls}"><table class="data-table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${esc(cell??'—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:empty('暂无记录');
}
function importPreview(rows){const columns=[...new Set(rows.flatMap(r=>Object.keys(r)))].filter(k=>!k.startsWith('_'));return displayTable(columns,rows.map(r=>columns.map(k=>r[k])),'import-preview')}
function modelSummary(model){
  const labels=modelLabels(model);
  return `<div class="model-summary"><h3>${esc(model.name)}</h3><p class="muted">${esc(model.industry)} · V${model.version} · ${esc(model.status||'待校验')}</p>${model.description?`<p>${esc(model.description)}</p>`:''}<h3>模型参数</h3>${displayTable(['参数','取值方式','数值','单位'],Object.entries(model.parameters).map(([k,p])=>[labels[k],p.calibrate?'按事故报告计算':'手动设置',p.calibrate?'运行时计算':p.value,p.unit||'—']))}<h3>风险变量</h3>${displayTable(['变量','类型','计算规则'],model.variables.map(v=>[labels[v.name],v.type==='stock'?'风险存量':'计算指标',readableExpression(v.type==='stock'?v.rate:v.formula,model)]),'model-rules-table')}</div>`;
}
function calibrationTable(result){
  const model=state.models.find(m=>m.id===result.model_id)||state.model,labels=model?modelLabels(model):{};
  return displayTable(['参数','计算值','样本依据','计算方式'],(result.calibration||[]).map(p=>[labels[p.parameter]||p.field||'模型参数',p.status==='insufficient'?'未估计':Number(p.value).toFixed(2),p.denominator!=null?`${p.numerator} / ${p.denominator}`:'用户设置',p.reason||p.method]));
}
function evidenceSteps(trace){return `<ul class="evidence-steps">${(trace||[]).map(t=>{
  const p=t.parameters||{},scope=[p.industry,p.region,p.start&&p.end?`${p.start} 至 ${p.end}`:'',p.months?`${p.months} 个月`:''].filter(Boolean).join(' · ');
  const name={query_risk_evidence:'查询事故数据',run_sd_simulation:'计算风险演化'}[t.tool]||'研判分析';
  return `<li><div><strong>${name}</strong><span>${t.status==='failed'?'未完成':t.result_count!=null?`${t.result_count} 条事故`:'已完成'}</span></div>${scope?`<p>${esc(scope)}</p>`:''}${t.error?`<p>${esc(userMessage(t.error))}</p>`:''}</li>`;
}).join('')}</ul>`}
function modelsView(){
  const m=fixedModel(state.model?.industry||state.filters.industry);state.model=m;if(!m)return empty('尚未接入模型');const industry=m.industry;
  const parameters=state.modelParameters?.[m.id]||{};
  return `<div class="model-page"><div class="industry-tags">${state.config.industries.map(i=>`<button class="btn ${industry===i?'active':''}" data-model-industry="${i}">${i}</button>`).join('')}</div><div class="model-workspace"><section class="panel model-structure-panel"><div class="panel-head">${panelTitle(industry+'风险模型','model')}${btn('调整模型','edit-sd-model','','edit')}</div><div class="model-canvas">${modelGraph(m,state.modelValidation?.edges||[])}</div>${modelRules(m)}</section><section class="panel model-parameters-panel"><div class="panel-head">${panelTitle('情景参数','settings')}${btn('恢复默认','reset-model-params','link')}</div>${scenarioParameters(m).map(([k,p])=>`<div class="parameter-row"><label for="sim-param-${esc(k)}">${esc(modelLabels(m)[k])}</label><div class="parameter-control">${sdUI.input(k,p,parameters[k]??p.value,'data-param','sim-param-'+k)}${p.unit?`<span class="parameter-unit">${esc(p.unit)}</span>`:''}</div></div>`).join('')}<section class="simulation-settings"><div class="section-divider"></div><h3 style="margin-bottom:16px">仿真设置</h3><div class="form-grid">${select('地区','sim-region',state.overview.regions,state.filters.region,'全国')}${select('预测周期','sim-months',[1,3,6,12,24,36].map(x=>({value:String(x),label:x+'个月'})),String(state.months))}${field('分析开始','sim-start',state.filters.start,'date')}${field('分析结束','sim-end',state.filters.end,'date')}</div><div class="form-footer model-run-footer">${btn('运行仿真','run-simulation','primary','play')}</div></section></section></div>${state.simulation?simulationPanel():''}</div>`;
}
function modelRules(model){
  const labels=modelLabels(model);
  return `<section class="model-rules"><div class="model-rules-heading"><h3>变量与计算规则</h3>${btn('展开规则','expand-model-rules','link sm','expand')}</div>${displayTable(['变量','类型','计算规则'],model.variables.map(v=>{
    let rule=readableExpression(v.type==='stock'?v.rate:v.formula,model);
    if(model.profile_version==='industry-report/2.0'&&v.type==='stock'&&v.name!=='management_risk')rule='以同类事故占比确定初值，结合生产压力、管理变化及可用趋势调整目标，按调整时间演化并扣减安全治理作用。';
    if(model.profile_version==='industry-report/2.0'&&v.name==='risk_index')rule='行业风险加权值 × 80% ＋ 管理风险 × 20%';
    return [labels[v.name],v.role==='flow'?'流量':v.type==='stock'?'存量':v.role==='factor'?'专业因素':'计算指标',rule];
  }),'model-rules-table')}</section>`;
}

function modelGraph(model,edges){
  if(isFeedback(model))return sdUI.graph(model,edges);
  const stocks=model.variables.filter(v=>v.type==='stock'),aux=model.variables.filter(v=>v.type==='aux');
  const height=Math.max(320,stocks.length*44+65,aux.length*68+65,Object.values(model.parameters).filter(p=>!p.calibrate).length*52+70),labels=modelLabels(model),positions={};
  const controls=Object.entries(model.parameters).filter(([,p])=>!p.calibrate).map(([name,p])=>({name,label:labels[name],type:'parameter'}));
  const nodes=[...controls,...stocks,...aux];
  controls.forEach((n,i)=>positions[n.name]={x:24,y:52+i*52,width:148});
  stocks.forEach((n,i)=>positions[n.name]={x:260,y:52+i*44,width:166});
  aux.forEach((n,i)=>positions[n.name]={x:510,y:52+i*68,width:154});
  const visibleEdges=edges.filter(e=>positions[e.source]&&positions[e.target]&&e.source!==e.target);
  return `<svg class="risk-model-graph" viewBox="0 0 694 ${height}" role="img" aria-label="${esc(model.industry)}风险模型结构"><defs><linearGradient id="graph-output" x2="1" y2="1"><stop stop-color="#1E3264"/><stop offset="1" stop-color="#314C85"/></linearGradient><marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 1L9 5L0 9" fill="none" stroke="#788BB0" stroke-width="1.5"/></marker></defs>
    <text class="graph-heading" x="24" y="28">情景调节</text><text class="graph-heading" x="260" y="28">${esc(model.industry)}风险</text><text class="graph-heading" x="510" y="28">综合研判</text>
    ${visibleEdges.map(e=>{const a=positions[e.source],b=positions[e.target];const same=a.x===b.x;const path=same?`M${a.x+a.width} ${a.y+20} C${a.x+a.width+35} ${a.y+20},${b.x+b.width+35} ${b.y+20},${b.x+b.width} ${b.y+20}`:`M${a.x+a.width} ${a.y+20} C${a.x+a.width+45} ${a.y+20},${b.x-45} ${b.y+20},${b.x} ${b.y+20}`;return `<path class="graph-edge" data-edge-source="${esc(e.source)}" data-edge-target="${esc(e.target)}" d="${path}" marker-end="url(#graph-arrow)"/>`}).join('')}
    ${nodes.map(n=>{const p=positions[n.name],isOutput=n.type==='aux';return `<g class="graph-node graph-node-${n.type}" data-graph-node="${esc(n.name)}" tabindex="0" role="group" aria-label="${esc(labels[n.name])}"><rect x="${p.x}" y="${p.y}" width="${p.width}" height="40" rx="10" fill="${isOutput?'var(--brand)':'var(--surface)'}" stroke="${n.type==='stock'?'var(--iflyv-brand-2)':'var(--line)'}"/><circle cx="${p.x+13}" cy="${p.y+20}" r="3" fill="${isOutput?'var(--iflyv-brand-2)':n.type==='stock'?'var(--iflyv-brand-5)':'var(--iflyv-brand-4)'}"/><text x="${p.x+p.width/2+5}" y="${p.y+25}" text-anchor="middle" fill="${isOutput?'var(--surface)':'var(--brand)'}">${esc(labels[n.name])}</text></g>`}).join('')}
  </svg>`;
}
function bindModelGraph(){
  const canvas=$('.model-canvas');if(!canvas)return;
  $$('[data-graph-node]',canvas).forEach(node=>{
    const highlight=()=>{canvas.classList.add('graph-focused');$$('.graph-edge',canvas).forEach(e=>e.classList.toggle('connected',e.dataset.edgeSource===node.dataset.graphNode||e.dataset.edgeTarget===node.dataset.graphNode))};
    const clear=()=>canvas.classList.remove('graph-focused');node.onpointerenter=highlight;node.onfocus=highlight;node.onpointerleave=clear;node.onblur=clear;
  });
}
function industryEvidence(result){
  const evidence=result.industry_evidence;if(!evidence)return '';
  return `<section class="industry-evidence"><div class="evidence-summary"><h3>行业风险依据</h3><span>${evidence.matched_samples} / ${evidence.samples} 起事故识别到风险线索</span></div>${displayTable(['风险类别','涉及事故','样本占比','综合权重','半年趋势'],evidence.channels.map(c=>[c.label,c.count+' 起',c.share.toFixed(1)+'%',(c.weight*100).toFixed(1)+'%',c.trend===null?'样本不足':(c.trend>0?'+':'')+c.trend.toFixed(2)+' /月']))}${evidence.trend_reason?`<p class="muted">${esc(evidence.trend_reason)}</p>`:''}<div class="feature-evidence-list">${evidence.channels.filter(c=>c.evidence.length).map(c=>`<details><summary>${esc(c.label)} · 查看报告依据</summary>${c.evidence.map(e=>`<p><strong>${esc(e.number||'事故报告')} · ${esc(e.field)}</strong><span>${esc(e.excerpt)}</span></p>`).join('')}</details>`).join('')}</div></section>`;
}

const CHART_COLORS=['#244777','#df9855','#40a6a5','#9aa8bf'];
let simulationResizeObserver=null;
function selectedChartMetric(result=state.simulation){return result?.output_metrics?.[state.chartMetric]?state.chartMetric:'risk_index'}
function chartSeries(result,comparison=null){
  const metric=selectedChartMetric(result);
  const compatible=comparison?.scenarios[0]?.points.some(p=>Number.isFinite(p[metric]));
  return [...result.scenarios,...(compatible?[{name:'历史基准',points:comparison.scenarios[0].points,history:true}]:[])].map(s=>({...s,points:s.points.filter(p=>Number.isFinite(p[metric])).map(p=>({...p,risk_index:p[metric]}))}));
}
function chartDomain(values,mode){
  const minimum=Math.min(...values),maximum=Math.max(...values);
  const span=maximum-minimum;
  const padding=span>0?span*.1:Math.max(Math.abs(maximum)*.025,.5);
  let low=mode==='zero'?Math.min(0,minimum-padding):minimum-padding;
  if(minimum>=0)low=Math.max(0,low);
  let high=mode==='zero'?Math.max(0,maximum+padding):maximum+padding;
  const target=(high-low)/5;
  const magnitude=10**Math.floor(Math.log10(target));
  const fraction=target/magnitude;
  const step=([1,2,2.5,5,10].find(value=>value>=fraction)||10)*magnitude;
  if(mode==='zero'){low=Math.floor(low/step)*step;high=Math.ceil(high/step)*step}
  const firstTick=Math.ceil(low/step)*step;
  const ticks=Array.from({length:Math.floor((high-firstTick)/step)+1},(_,i)=>firstTick+i*step);
  const precision=Math.max(0,Math.min(6,Math.ceil(-Math.log10(step))+(String(step/magnitude)==='2.5'?1:0)));
  return {low,high,step,ticks,precision};
}
function lineChart(){return '';}
function simulationOption(result,comparison){
  const metric=selectedChartMetric(result),series=chartSeries(result,comparison);
  return {animation:false,color:CHART_COLORS,textStyle:{fontFamily:'Microsoft YaHei, sans-serif'},
    tooltip:{trigger:'axis',confine:true,valueFormatter:v=>Number(v).toFixed(2)},
    legend:{top:4,icon:'roundRect',itemWidth:18,itemHeight:3,textStyle:{color:'#56657b',fontSize:12}},
    grid:{left:58,right:26,top:58,bottom:48,containLabel:false},
    xAxis:{type:'value',min:0,name:'月',max:Math.max(...series.flatMap(s=>s.points.map(p=>p.month))),axisLabel:{color:'#7b8797',formatter:v=>Number(v.toFixed(2))},axisLine:{lineStyle:{color:'#dce3eb'}},splitLine:{show:false}},
    yAxis:{type:'value',scale:state.chartMode!=='zero',min:state.chartMode==='zero'?0:null,name:result.output_metrics?.[metric]?.label||'风险指数',nameTextStyle:{color:'#7b8797'},axisLabel:{color:'#7b8797',formatter:v=>Number(v.toFixed(2))},splitLine:{lineStyle:{color:'#edf1f5',type:'dashed'}}},
    series:series.map((s,i)=>({name:s.name,type:'line',data:s.points.map(p=>[p.month,p.risk_index]),showSymbol:false,smooth:false,lineStyle:{width:2.4,type:s.history?'dashed':'solid'},emphasis:{focus:'series'},endLabel:{show:false}}))};
}
function comparisonOptions(){
  return `<option value="">历史结果比较</option>${state.simulationHistory.map(s=>`<option value="${s.id}" ${state.chartComparison?.id===s.id?'selected':''}>${time(s.created_at)}</option>`).join('')}`;
}
function chartLegend(){
  return chartSeries(state.simulation,state.chartComparison).map((s,i)=>`<span><i ${s.history?'class="dashed"':''} style="--series-color:${CHART_COLORS[i]};background:${CHART_COLORS[i]}"></i>${esc(s.name)}</span>`).join('');
}
function chartToolbar(){
  return `<div class="simulation-chart-toolbar">${state.simulation?.output_metrics?`<select data-chart-metric aria-label="曲线指标">${['risk_index','accident_intensity','hazard_pressure','cumulative_load'].map(k=>`<option value="${k}" ${selectedChartMetric()===k?'selected':''}>${esc(state.simulation.output_metrics[k]?.label||k)}</option>`).join('')}</select>`:''}<div class="chart-scale" role="group" aria-label="纵轴范围"><button type="button" data-chart-scale="auto" aria-pressed="${state.chartMode==='auto'}">自适应</button><button type="button" data-chart-scale="zero" aria-pressed="${state.chartMode==='zero'}">从零开始</button></div></div>`;
}
function simulationPanel(){
  return `<section class="panel simulation-results"><div class="panel-head">${panelTitle('风险演化曲线','chart')}<div class="actions"><select id="compare-simulation" data-compare-simulation aria-label="历史结果比较">${comparisonOptions()}</select>${btn('放大查看','expand-chart','','expand')}<a class="btn" href="/api/simulations/${state.simulation.id}/export" download>${icon('download')}导出结果</a></div></div>${sdUI.summaries(state.simulation)}${chartToolbar()}<div class="simulation-plot" id="simulation-chart">${lineChart(state.simulation,state.chartComparison)}</div>${sdUI.evidenceSummary(state.simulation)}</section>`;
}
const liveSimulationCharts=new Map();
function drawSimulationCharts(){
  for(const [host,chart] of liveSimulationCharts)if(!host.isConnected){chart.dispose();liveSimulationCharts.delete(host)}
  if(!state.simulation||!window.echarts)return;
  for(const host of $$('.simulation-plot')){
    if(!host.clientWidth||!host.clientHeight)continue;
    let chart=liveSimulationCharts.get(host);
    if(!chart){chart=window.echarts.init(host,null,{renderer:'svg'});liveSimulationCharts.set(host,chart)}
    chart.setOption(simulationOption(state.simulation,state.chartComparison),true);chart.resize();
  }
  $$('[data-chart-scale]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.chartScale===state.chartMode)));
}
function hideChartTooltip(host){
  $('.chart-tooltip',host)?.setAttribute('hidden','');
  $('.chart-cursor',host)?.setAttribute('visibility','hidden');
}
function showChartTooltip(host,event){
  const svg=$('svg',host),tooltip=$('.chart-tooltip',host);
  if(!svg||!tooltip)return;
  const bounds=svg.getBoundingClientRect(),px=event.clientX-bounds.left,py=event.clientY-bounds.top;
  const left=Number(svg.dataset.plotLeft),right=Number(svg.dataset.plotRight),top=Number(svg.dataset.plotTop),bottom=Number(svg.dataset.plotBottom),horizon=Number(svg.dataset.xMax);
  if(px<left||px>right||py<top||py>bottom){hideChartTooltip(host);return}
  const series=chartSeries(state.simulation,state.chartComparison);
  const target=(px-left)/(right-left)*horizon;
  const months=[...new Set(series.flatMap(s=>s.points.map(p=>p.month)))];
  const month=months.reduce((nearest,value)=>Math.abs(value-target)<Math.abs(nearest-target)?value:nearest,months[0]);
  const precision=Math.max(2,Number(svg.dataset.yPrecision));
  tooltip.innerHTML=`<strong>${Number(month.toFixed(2))}月</strong>${series.map((scenario,i)=>{
    const point=scenario.points.find(p=>Math.abs(p.month-month)<1e-8);
    return point?`<div><span><i style="background:${CHART_COLORS[i]}"></i>${esc(scenario.name)}</span><b>${point.risk_index.toFixed(precision)}</b></div>`:'';
  }).join('')}`;
  tooltip.hidden=false;
  const cursor=$('.chart-cursor',host),cursorX=left+month/horizon*(right-left);
  cursor.setAttribute('x1',cursorX);cursor.setAttribute('x2',cursorX);cursor.setAttribute('visibility','visible');
  const tooltipWidth=tooltip.offsetWidth,tooltipHeight=tooltip.offsetHeight;
  tooltip.style.left=Math.max(4,Math.min(host.clientWidth-tooltipWidth-4,px+16))+'px';
  tooltip.style.top=Math.max(4,Math.min(host.clientHeight-tooltipHeight-4,py+12))+'px';
}
function bindChartControls(){
  $$('[data-chart-metric]').forEach(select=>select.onchange=()=>{state.chartMetric=select.value;$$('[data-chart-metric]').forEach(other=>other.value=select.value);drawSimulationCharts()});
  $$('[data-chart-scale]').forEach(button=>button.onclick=()=>{state.chartMode=button.dataset.chartScale;drawSimulationCharts()});
  $$('[data-compare-simulation]').forEach(select=>select.onchange=()=>{
    state.chartComparison=state.simulationHistory.find(s=>s.id===select.value)||null;
    $$('[data-compare-simulation]').forEach(other=>other.value=select.value);
    drawSimulationCharts();
  });
}
function observeSimulationCharts(){
  simulationResizeObserver?.disconnect();
  closeApplicationModels();
  simulationResizeObserver=new ResizeObserver(()=>drawSimulationCharts());
  $$('.simulation-plot').forEach(host=>simulationResizeObserver.observe(host));
  drawSimulationCharts();bindChartControls();
}
function expandSimulationChart(){
  if(!state.simulation)return;
  modal('风险演化曲线',`${chartToolbar()}<div class="simulation-plot" id="expanded-simulation-chart"></div>`);
  $('.modal').classList.add('chart-modal');
  $('.modal-header [data-action="close-modal"]').insertAdjacentHTML('beforebegin',`<div class="expanded-chart-actions"><select data-compare-simulation aria-label="历史结果比较">${comparisonOptions()}</select><a class="btn" href="/api/simulations/${state.simulation.id}/export" download>${icon('download')}导出结果</a></div>`);
  prefixLinks($('.modal'));
  const host=$('#expanded-simulation-chart');
  observeSimulationCharts();
  modalOnClose=()=>{simulationResizeObserver?.unobserve(host);const chart=liveSimulationCharts.get(host);chart?.dispose();liveSimulationCharts.delete(host)};
}

async function loadModelValidation(){try{state.modelValidation=await post('/models/validate',state.model);return state.modelValidation}catch(e){state.modelValidation=null;toast(e.message);return null}}

function bindModels(){
  bindModelGraph();
  state.modelParameters=state.modelParameters||{};
  $$('[data-param]').forEach(input=>input.oninput=()=>{if(input.checkValidity()){state.modelParameters[state.model.id]=state.modelParameters[state.model.id]||{};state.modelParameters[state.model.id][input.dataset.param]=Number(input.value)}});
  $$('[data-model-industry]').forEach(e=>e.onclick=async()=>{$$('[data-model-industry],[data-action=run-simulation],[data-action=edit-sd-model]').forEach(b=>b.disabled=true);state.model=fixedModel(e.dataset.modelIndustry);state.filters.industry=e.dataset.modelIndustry;state.simulation=null;state.chartComparison=null;state.simulationHistory=[];await loadModelValidation();render()});
  for(const key of ['region','start','end'])$('#sim-'+key).onchange=e=>state.filters[key]=e.target.value;$('#sim-months').onchange=e=>state.months=Number(e.target.value);
  if(state.simulation){
    observeSimulationCharts();
    const simulationId=state.simulation.id;
    api('/simulations').then(list=>{
      if(state.view!=='models'||state.simulation?.id!==simulationId)return;
      state.simulationHistory=list.filter(s=>s.model_id===state.model.id&&s.id!==simulationId);
      if(!state.simulationHistory.some(s=>s.id===state.chartComparison?.id))state.chartComparison=null;
      $$('[data-compare-simulation]').forEach(select=>select.innerHTML=comparisonOptions());
      drawSimulationCharts();bindChartControls();
    }).catch(e=>toast(e.message));
  }
}

function paintJobProgress(entry){
  if(progressViews.get(entry.selector)!==entry)return;
  const host=$(entry.selector);if(!host)return;
  let card=$('.progress-card',host);
  if(card?.dataset.jobId!==entry.id){
    host.innerHTML=`<div class="progress-card" data-job-id="${esc(entry.id)}"><div class="progress-label"><span></span><strong></strong></div><div class="progress-bar" role="progressbar" aria-label="任务进度" aria-valuemin="0" aria-valuemax="100"><div></div></div><p class="notice" hidden></p></div>`;
    card=$('.progress-card',host);
  }
  $('.progress-label span',card).textContent=userMessage(entry.stage);
  const percent=Math.floor(entry.value);
  $('.progress-label strong',card).textContent=percent+'%';
  $('.progress-bar',card).setAttribute('aria-valuenow',String(percent));
  $('.progress-bar div',card).style.transform=`scaleX(${entry.value/100})`;
  const error=$('.notice',card);error.hidden=entry.status!=='failed';error.textContent=userMessage(entry.error||'');
}
function animateJobProgress(now){
  progressFrame=0;let moving=false;
  for(const entry of progressViews.values()){
    if(entry.value<entry.target){
      const t=Math.min(1,(now-entry.started)/entry.duration);
      entry.value=t===1?entry.target:entry.from+(entry.target-entry.from)*(1-(1-t)**3);
      moving||=t<1;
    }
    paintJobProgress(entry);
  }
  if(moving)progressFrame=requestAnimationFrame(animateJobProgress);
}
function updateJobProgress(entry,job){
  entry.status=job.status;entry.stage=job.stage;entry.error=job.error;
  const actual=Number(job.progress)||0;
  const target=job.status==='completed'?100:Math.min(99,Math.max(0,actual));
  if(target!==entry.target){
    entry.from=entry.value;entry.target=Math.max(entry.value,target);entry.started=performance.now();
    entry.duration=window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:850;
  }
  paintJobProgress(entry);
  if(entry.value<entry.target&&!progressFrame)progressFrame=requestAnimationFrame(animateJobProgress);
}
async function finishJobProgress(entry){
  if(document.hidden||!$(entry.selector)){entry.value=entry.target;return}
  await new Promise(resolve=>{
    const start=performance.now();
    function wait(){if(entry.value>=entry.target||performance.now()-start>=950)resolve();else requestAnimationFrame(wait)}
    requestAnimationFrame(wait);setTimeout(resolve,1000);
  });
  entry.value=entry.target;paintJobProgress(entry);
}
async function watchJob(job,selector,onComplete,onFail=()=>{}){
  const entry={id:job.id,selector,value:0,target:0,from:0,started:performance.now(),duration:850};
  progressViews.set(selector,entry);polling.add(job.id);updateJobProgress(entry,job);let retries=0;
  while(polling.has(job.id)){
    if(job.status==='completed'){
      polling.delete(job.id);await finishJobProgress(entry);
      if(progressViews.get(selector)===entry)progressViews.delete(selector);
      await onComplete(job.result);return;
    }
    if(job.status==='failed'){
      polling.delete(job.id);await finishJobProgress(entry);
      if(progressViews.get(selector)===entry)progressViews.delete(selector);
      onFail();toast(job.error);return;
    }
    await new Promise(r=>setTimeout(r,1500));
    try{job=await api('/jobs/'+job.id);retries=0;updateJobProgress(entry,job)}
    catch(e){if(++retries>=5){polling.delete(job.id);if(progressViews.get(selector)===entry)progressViews.delete(selector);onFail();toast('任务状态连接中断，请在任务记录中查看');return}}
  }
}
async function reportHistory(){state.reports=await api('/reports');modal('历史分析报告',state.reports.length?state.reports.map(r=>`<div class="history-row"><div style="min-width:0"><strong>${esc(r.title)}</strong><div class="file-meta">${time(r.created_at)} · ${r.body_hanzi}字 · ${r.count}条记录</div></div><div class="actions"><button class="btn sm" data-open-report="${r.id}">打开</button><a class="btn sm" href="/api/reports/${r.id}/evidence" download>计算证据</a><button class="btn sm danger" data-delete-report="${r.id}">删除</button></div></div>`).join(''):empty('暂无分析报告','','report'),'',true);
  $$('[data-open-report]',$('.modal')).forEach(e=>e.onclick=()=>{state.report=state.reports.find(r=>r.id===e.dataset.openReport);const p=state.report.parameters||{};for(const key of ['industry','region','start','end'])if(p[key]!==undefined)state.filters[key]=p[key];state.months=p.months||state.months;state.scenario=p.scenario||state.scenario;state.reportModel=p.model_id||state.reportModel;if(state.config.llm.models.some(m=>m.id===p.llm_model))state.llmModel=p.llm_model;state.parameters=p.parameters||{};state.coverageConfirmed=Boolean(p.coverage_confirmed);if(p.indicators)state.selected=new Set(p.indicators);closeModal();navigate('reports')});
  $$('[data-delete-report]',$('.modal')).forEach(e=>e.onclick=()=>confirmModal('删除这份报告及生成文件？',async()=>{await api('/reports/'+e.dataset.deleteReport,{method:'DELETE'});if(state.report?.id===e.dataset.deleteReport)state.report=null;await refresh();render();setTimeout(reportHistory,50)}));
}
function helpModal(){
  modal('使用说明',`<div class="help-intro">从事故数据到研判报告，按需完成以下步骤。</div><div class="help-steps">${[
    ['database','整理数据','在数据库管理中上传事故调查报告或结构化表，预览并确认导入。可按行业、地区和日期筛选，查看与修正记录。'],
    ['model','比较风险','在SD模型库选择行业，设置分析范围与情景参数，运行仿真。曲线支持放大、历史对比和结果下载。'],
    ['report','生成报告','选择分析范围、预测设置和报告指标，点击一键生成。完成后可在线阅读，下载HTML或PDF；查看记录可重新打开历史报告。']
  ].map(([i,h,t])=>`<article><span class="help-icon">${icon(i)}</span><div><h3>${h}</h3><p>${t}</p></div></article>`).join('')}</div><div class="help-footnote">预测需要相应行业的事故数据。样本或时间序列不足时，报告会说明缺项；情景仿真指数不等同于事故发生概率。</div>`);
}
async function settingsModal(){
  const stores={postgres:'PostgreSQL',dm8:'达梦 DM8',sqlite:'SQLite',s3:'S3 对象存储',minio:'MinIO',local:'本地文件'};
  modal('系统设置',`<div class="settings-list"><div><span>研判服务</span><strong>${state.config.llm.configured?'已启用':'待接入'}</strong></div><div><span>数据存储</span><strong>${esc(stores[state.config.db_backend]||state.config.db_backend)} + ${esc(stores[state.config.storage_backend]||state.config.storage_backend)}</strong></div><div><span>访问权限</span><strong>${esc({admin:'管理',editor:'编辑',viewer:'查看'}[state.config.role]||state.config.role)}</strong></div></div><div class="settings-actions">${btn('检测服务','test-llm')}${btn('任务记录','task-history')}${btn('运行日志','audit')}${btn('验收记录','acceptance')}</div><div id="settings-result"></div>`);
  $('[data-action="acceptance"]',$('.modal')).onclick=()=>acceptanceModal().catch(e=>toast(e.message));
  $('[data-action="test-llm"]',$('.modal')).onclick=async e=>{
    e.currentTarget.disabled=true;
    try{await post('/llm/test',{});if($('#settings-result'))$('#settings-result').innerHTML='<div class="info-note">智能体服务连接正常</div>'}
    catch(e){if($('#settings-result'))$('#settings-result').innerHTML=`<div class="notice">${esc(userMessage(e.message))}</div>`}
    finally{const b=$('[data-action="test-llm"]');if(b)b.disabled=false}
  };
  $('[data-action="task-history"]',$('.modal')).onclick=async()=>{
    const jobs=await api('/jobs');
    modal('任务记录',jobs.map(j=>`<div class="history-row"><div>${esc({report:'生成报告',pdf:'导出PDF',import:'导入数据',parse:'解析资料'}[j.kind]||j.kind)} · ${esc(userMessage(j.stage))}<div class="file-meta">${time(j.created_at)}${j.error?' · '+esc(userMessage(j.error)):''}</div></div>${badge({completed:'已完成',running:'进行中',failed:'失败',queued:'等待中'}[j.status]||j.status,j.status==='failed'?'orange':'')}</div>`).join('')||empty('暂无任务'),'',true)
  };
  $('[data-action="audit"]',$('.modal')).onclick=async()=>{const rows=await api('/audit');modal('运行日志',rows.map(r=>`<div class="history-row"><span>${esc(({create_record:'新增记录',edit_record:'编辑记录',delete_record:'删除记录',upload:'上传资料',delete_file_and_records:'删除资料及记录',create_model:'新建模型',import_model:'导入模型',save_model:'保存模型',delete_model:'删除模型',simulate:'运行仿真',generate_report:'生成报告',delete_report:'删除报告',expert_evaluation:'录入专家评价',import:'导入数据'})[r.ACTION]||'业务操作')} · ${esc(r.ACTOR==='local-admin'?'本地管理员':r.ACTOR)}</span><span class="muted">${time(r.CREATED_AT)}</span></div>`).join('')||empty('暂无操作日志'))};
}
async function acceptanceModal(){const r=await api('/acceptance');const expert=r.expert;modal('功能与验收记录',`<div class="acceptance-grid">${[['结构化数据',r.records.actual.toLocaleString()+' 条','要求超过20万条',r.records.met],['原始资料',bytes(r.storage.actual_bytes),'要求超过3TB',r.storage.met],['行业覆盖','6个行业',r.industries.status,false],['候选指标','6类 × 11项','共66项候选内容',r.indicators.met],['基础字段覆盖',r.coverage.actual_percent+'%',r.coverage.definition,r.coverage.met],['预测验证','待验证',r.prediction.status,false],['专家建议一致性',expert?expert.recommendations_match.percent+'%':'无专家样本',expert?'90%区间：'+expert.recommendations_match.ci90.join('—')+'%':'要求超过70%',false],['关键内容一致性',expert?expert.content_match.percent+'%':'无专家样本',expert?'90%区间：'+expert.content_match.ci90.join('—')+'%':'要求超过80%',false]].map(([title,value,note,met])=>`<div class="acceptance-item"><div class="panel-head" style="margin-bottom:12px"><h3>${title}</h3>${badge(met?'已验证':'待验收',met?'green':'orange')}</div><h2>${esc(value)}</h2><p>${esc(note)}</p></div>`).join('')}</div><div class="actions" style="margin-top:24px">${btn('录入专家评价','expert-upload','primary')}${btn('核验存储字节','storage-verify')}</div><div id="acceptance-result"></div>`,'',true);
  $('[data-action="expert-upload"]',$('.modal')).onclick=()=>{modal('导入专家评价',`<div class="field"><label>专家评价文件</label><input type="file" id="expert-file" accept=".json"></div><p class="muted">包含审核人、样本编号、建议一致性、关键内容一致性和审核证据。</p><div id="expert-result"></div>`);$('#expert-file').onchange=async e=>{try{let body;try{body=JSON.parse(await e.target.files[0].text())}catch{throw new Error('评价文件格式不正确，请选择有效的评价文件')}const result=await post('/acceptance/expert',body);$('#expert-result').innerHTML=`<div class="info-note">已录入 ${result.sample_count} 个专家样本</div>`}catch(e){toast(e.message)}}};
  $('[data-action="storage-verify"]',$('.modal')).onclick=async()=>{const result=await post('/storage/verify',{});$('#acceptance-result').innerHTML=`<div class="info-note">实测 ${bytes(result.verified_bytes)} · ${result.all_verified?'全部文件大小一致':'存在文件异常'}</div>`};
}
function loginModal(){
  if($('#login-credential'))return;
  modal('访问验证',`<form id="login-form"><p class="muted">请输入管理员设置的访问密码。</p>${field('访问密码','login-credential','','password','autocomplete="current-password" required')}</form>`,btn('登录','login','primary'));
  const submit=async()=>{const credential=$('#login-credential')?.value||'';if(!credential)return;try{await post('/auth/session',{password:credential,token:credential});closeModal();await init()}catch(e){toast(e.message)}};
  $('[data-action="login"]',$('.modal')).onclick=submit;$('#login-form').onsubmit=e=>{e.preventDefault();submit()};
}
async function chatModal(){
  modal('智能风险研判',`<div class="chat-panel"><div class="chat-flow" id="chat-flow">${state.chatMessages.length?state.chatMessages.map(m=>`<div class="message ${m.role==='user'?'user':''}">${esc(m.content)}</div>`).join(''):empty('从真实事故数据开始研判','可询问事故特征、风险因素或运行情景仿真','chat')}</div><div class="chat-composer"><textarea id="chat-input" placeholder="询问当前行业、地区和时间范围的风险" aria-label="研判问题"></textarea><button class="btn primary" id="chat-send">发送</button></div><div class="chat-tools"><span>${esc(state.filters.industry)} · ${esc(state.filters.region||'全国')}</span><button class="btn link sm" id="chat-history">历史对话</button><button class="btn link sm" id="chat-new">新对话</button></div></div>`,'',true);
  const flow=$('#chat-flow');flow.scrollTop=flow.scrollHeight;
  $('#chat-send').onclick=async()=>{const input=$('#chat-input');const value=input.value.trim();if(!value)return;input.value='';state.chatMessages.push({role:'user',content:value});flow.innerHTML+=`<div class="message user">${esc(value)}</div><div class="message" id="chat-pending">正在查询与计算…</div>`;flow.scrollTop=flow.scrollHeight;$('#chat-send').disabled=true;
    try{const result=await post('/chat',{content:value,sessionId:state.chatSession,filters:state.filters,llm_model:state.llmModel});state.chatSession=result.sessionId;state.chatMessages.push({role:'assistant',content:result.answer});const pending=$('#chat-pending');if(pending)pending.outerHTML=`<div class="message">${esc(result.answer)}</div><details class="chat-tools"><summary>计算与数据依据</summary>${evidenceSteps(result.trace)}</details>`}catch(e){const p=$('#chat-pending');if(p)p.textContent=e.message;toast(e.message)}finally{if($('#chat-send'))$('#chat-send').disabled=false;if(flow.isConnected)flow.scrollTop=flow.scrollHeight}};
  $('#chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#chat-send').click()}};
  $('#chat-new').onclick=()=>{state.chatSession='';state.chatMessages=[];chatModal()};
  $('#chat-history').onclick=async()=>{const list=await api('/history');modal('历史研判对话',list.length?list.sort((a,b)=>Number(b.pinned)-Number(a.pinned)).map(s=>`<div class="history-row"><div><strong>${s.pinned?'★ ':''}${esc(s.title)}</strong><div class="file-meta">${time(s.updated_at||s.created_at)}</div></div><div class="actions"><button class="btn sm" data-chat-open="${s.id}">打开</button><button class="btn sm" data-chat-pin="${s.id}">${s.pinned?'取消置顶':'置顶'}</button><button class="btn sm" data-chat-rename="${s.id}">重命名</button><button class="btn sm danger" data-chat-delete="${s.id}">删除</button></div></div>`).join(''):empty('暂无历史对话'));
    $$('[data-chat-open]',$('.modal')).forEach(e=>e.onclick=()=>{const s=list.find(x=>x.id===e.dataset.chatOpen);state.chatSession=s.id;state.chatMessages=s.messages;chatModal()});
    $$('[data-chat-pin]',$('.modal')).forEach(e=>e.onclick=async()=>{const s=list.find(x=>x.id===e.dataset.chatPin);await api('/history/'+s.id,{method:'PATCH',body:JSON.stringify({pinned:!s.pinned})});toast('置顶状态已更新');e.textContent=s.pinned?'置顶':'取消置顶';s.pinned=!s.pinned});
    $$('[data-chat-rename]',$('.modal')).forEach(e=>e.onclick=()=>{const s=list.find(x=>x.id===e.dataset.chatRename);modal('重命名对话',field('名称','chat-title',s.title),btn('保存','rename-save','primary'));$('[data-action="rename-save"]',$('.modal')).onclick=async()=>{await api('/history/'+s.id,{method:'PATCH',body:JSON.stringify({title:$('#chat-title').value})});closeModal();toast('名称已保存')}});
    $$('[data-chat-delete]',$('.modal')).forEach(e=>e.onclick=()=>confirmModal('删除这个对话？',async()=>{await api('/history/'+e.dataset.chatDelete,{method:'DELETE'});if(state.chatSession===e.dataset.chatDelete){state.chatSession='';state.chatMessages=[]}}));
  };
}
async function action(name,element){try{
  if(name==='expand-model-rules'){const m=state.model;modal('变量与计算规则',m.variables.map(v=>`<article class="full-model-rule"><h3>${esc(v.label)} <small>${esc(v.unit||'')}</small></h3>${v.type==='stock'?`<p><span>初始状态</span>${esc(readableExpression(v.initial,m))}</p>`:''}<p><span>${v.type==='stock'?'变化速度':'计算公式'}</span>${esc(readableExpression(v.type==='stock'?v.rate:v.formula,m))}</p></article>`).join(''),'',true);return}
  if(name==='edit-sd-model'){await sdUI.editModel();return}
  if(name==='factor-evidence'){await sdUI.showEvidence();return}
  if(name==='reset-model-params'){state.modelParameters=state.modelParameters||{};state.modelParameters[state.model.id]={};$$('[data-param]').forEach(i=>i.value=state.model.parameters[i.dataset.param].value);return}
  if(name==='settings')return settingsModal();if(name==='acceptance')return acceptanceModal();if(name==='chat')return chatModal();if(name==='report-history')return reportHistory();if(name==='upload')return uploadModal();if(name==='new-record')return recordModal({},false);
  if(name==='retry-report'){$('#report-form')?.requestSubmit();return}
  if(name==='help')return helpModal();if(name==='expand-chart')return expandSimulationChart();
  if(name==='select-application-model')return openApplicationModels(element);
  if(name==='download-html'){download('/api/reports/'+state.report.id+'/html?download=true');return}
  if(name==='download-pdf'){const job=await post('/reports/'+state.report.id+'/pdf',{});watchJob(job,'#report-job',r=>{download(r.url);toast('PDF已生成')});return}
  if(name==='data-dates'){modal('数据时间范围',`<div class="form-grid">${field('开始日期','data-start',state.dataFilters.start,'date')}${field('结束日期','data-end',state.dataFilters.end,'date')}</div>`,btn('清空','clear-dates')+btn('应用','apply-dates','primary'));$('[data-action="clear-dates"]',$('.modal')).onclick=()=>{$('#data-start').value='';$('#data-end').value=''};$('[data-action="apply-dates"]',$('.modal')).onclick=async()=>{const start=$('#data-start').value,end=$('#data-end').value;if(start&&end&&start>end){toast('开始日期不能晚于结束日期');return}state.dataFilters.start=start;state.dataFilters.end=end;state.page=0;closeModal();await loadData()};return}
  if(name==='data-filter'){state.dataFilterDraft=null;state.dataFilters.q=$('#data-q').value;state.dataFilters.industry=$('#data-industry').value;state.dataFilters.region=$('#data-region').value;state.page=0;await loadData();return}
  if(name==='export-data'){download('/api/data/'+state.dataset+'/export?'+new URLSearchParams(state.dataFilters));return}
  if(name==='columns'){const s=state.config.schemas.find(s=>s.id===state.dataset),current=state.columns?.[state.dataset]||defaultColumns();modal('显示字段',`<div class="record-form">${s.fields.map(f=>`<label class="check"><input type="checkbox" name="columns" value="${esc(f)}" ${current.includes(f)?'checked':''}>${esc(f)}</label>`).join('')}</div>`,btn('应用','apply-columns','primary'),true);$('[data-action="apply-columns"]',$('.modal')).onclick=()=>{const values=$$('input[name=columns]:checked',$('.modal')).map(e=>e.value);if(!values.length){toast('至少选择一个字段');return}state.columns=state.columns||{};state.columns[state.dataset]=values;closeModal();render()};return}
  if(name==='storage-verify'){const r=await post('/storage/verify',{});modal('对象存储核验',`<div class="info-note">实测存储量 ${bytes(r.verified_bytes)} · ${r.all_verified?'全部匹配':'存在异常'}</div>${displayTable(['资料名称','实际大小','核验结果'],r.objects.map(o=>[o.name,bytes(o.bytes||0),o.matches?'一致':'存在异常']))}`);return}
  if(name==='run-simulation'){const parameters={};for(const e of $$('[data-param]'))if(!e.disabled){if(!e.checkValidity()){e.reportValidity();return}parameters[e.dataset.param]=Number(e.value)}const filters={industry:state.model.industry,region:$('#sim-region').value,start:$('#sim-start').value,end:$('#sim-end').value,q:''};state.filters=filters;state.months=Number($('#sim-months').value);element.disabled=true;state.simulation=await post('/simulations',{model_id:state.model.id,filters,months:state.months,parameters,threshold:60});render();toast('仿真已完成');return}
}catch(e){toast(e.message);if(element)element.disabled=false}}
H5.addEventListener('change',()=>$('.agent-navigation')?.setAttribute('aria-orientation',H5.matches?'horizontal':'vertical'));
document.addEventListener('keydown',e=>{
  const tab=e.target.closest?.('[data-nav]');if(!tab||$('.modal'))return;
  const previous=H5.matches?'ArrowLeft':'ArrowUp',next=H5.matches?'ArrowRight':'ArrowDown';
  if(![previous,next,'Home','End'].includes(e.key))return;
  e.preventDefault();const items=$$('[data-nav]'),index=items.indexOf(tab);
  const target=items[e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key===next?1:items.length-1))%items.length].dataset.nav;
  navigate(target).then(()=>$(`[data-nav="${target}"]`)?.focus()).catch(err=>toast(err.message));
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();$$('.more-menu[open]').forEach(menu=>menu.open=false)}if(e.key==='Tab'&&$('.modal')){const focusable=$$('button,a,input,select,textarea,summary',$('.modal')).filter(x=>!x.disabled&&x.offsetParent!==null);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}});
document.addEventListener('click',event=>$$('.more-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false}));
document.addEventListener('touchstart',()=>{},{passive:true});
window.onpopstate=()=>{state.view=location.pathname.endsWith('/agent')?'reports':'gallery';render()};
async function init(){try{
  [state.config,state.overview,state.models,state.reports]=await Promise.all([api('/config'),api('/overview'),api('/models'),api('/reports')]);
  state.filters.start=state.filters.start||state.overview.dates.START_DATE||'2020-01-01';state.filters.end=state.filters.end||state.overview.dates.END_DATE||'2026-10-13';
  state.llmModel=state.llmModel||state.config.llm.model;
  if(!state.selected.size)state.selected=new Set(['企业数量','事故总数','月度分布','事故类型分布','人员因素频次','管理因素频次','因素关联强度','死亡人数','直接经济损失','当前综合风险指数','预测末期风险指数','重点风险治理任务数']);
  state.model=fixedModel(state.filters.industry)||state.models[0];render();window.agentStartup?.complete();if(state.view!=='gallery')await resumeReportJob();
}catch(e){window.agentStartup?.fail('应用连接失败：'+e.message);toast(e.message)}}
sdUI=createSdWorkbench({state,api,post,modal,closeModal,toast,esc,btn,icon,$,$$,modelLabels,readableExpression,expressionTokens,render,refresh,loadModelValidation});
init();
