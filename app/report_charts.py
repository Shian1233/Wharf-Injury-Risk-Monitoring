"""One ECharts option source for interactive HTML and offline SVG/PDF output."""
import base64, html, json, os, shutil, subprocess
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from .config import ROOT

COLORS=['#4ca6b0','#e8b64b','#df8064','#aa5260','#6b8ec0','#89b8a0']
def base():
    return {'animation':False,'color':COLORS,'textStyle':{'fontFamily':'Microsoft YaHei, sans-serif','fontSize':14},'tooltip':{'trigger':'item','confine':True},'legend':{'top':10,'textStyle':{'color':'#596577'},'itemWidth':16,'itemHeight':9}}

def cartesian(items, horizontal=False):
    option=base(); categories=[x['name'] for x in items]
    value={'type':'value','minInterval':1,'splitLine':{'lineStyle':{'color':'#e4e9ee','type':'dashed'}}}
    category={'type':'category','data':categories,'axisTick':{'show':False},'axisLine':{'lineStyle':{'color':'#bcc6d2'}},'axisLabel':{'color':'#64748b','width':160,'overflow':'truncate','rotate':0 if horizontal else 25}}
    option.update(grid={'left':185 if horizontal else 65,'right':55,'top':45,'bottom':65},xAxis=value if horizontal else category,yAxis=category if horizontal else value,legend={'show':False},series=[{'name':'事故起数','type':'bar','barMaxWidth':27,'data':[x['value'] for x in items],'itemStyle':{'borderRadius':[0,4,4,0] if horizontal else [4,4,0,0]},'label':{'show':True,'position':'right' if horizontal else 'top','color':'#4ca6b0'}}])
    return option

def specifications(stats,simulation):
    all_types=stats['distributions']['type']
    types=all_types[:12]
    pie_types=all_types[:11]+[{'name':'其余类型','value':sum(x['value'] for x in all_types[11:])}] if len(all_types)>12 else all_types
    spec=[{'option':cartesian(types,True),'height':max(340,70+len(types)*28)}]
    option=base();network=stats['network']
    option.update(legend={'show':False},series=[{'type':'graph','layout':'circular','roam':False,'circular':{'rotateLabel':False},'left':170,'right':170,'top':70,'bottom':70,'symbolSize':65,'label':{'show':True,'color':'#244777','fontSize':15},'itemStyle':{'color':'#edf3fa','borderColor':'#9fb6d4','borderWidth':1.5},'edgeLabel':{'show':True,'formatter':'{c}','fontSize':11},'lineStyle':{'color':'#a4b8ce','curveness':0.13,'opacity':0.7},'data':[{'name':n['id'],'value':n['count']} for n in network['nodes']],'links':[{'source':e['source'],'target':e['target'],'value':e['count']} for e in network['links']]}])
    spec.append({'option':option,'height':400})
    option=base();option['color']=['#244777','#df9855','#40a6a5']
    option.update(tooltip={'trigger':'axis','confine':True},grid={'left':65,'right':50,'top':70,'bottom':55},xAxis={'type':'value','min':0,'name':'月','splitLine':{'show':False},'axisLine':{'lineStyle':{'color':'#bcc6d2'}}},yAxis={'type':'value','name':'风险指数','scale':True,'splitLine':{'lineStyle':{'color':'#e4e9ee','type':'dashed'}}},series=[{'name':s['name'],'type':'line','showSymbol':False,'lineStyle':{'width':3},'data':[[p['month'],p['risk_index']] for p in s['points']]} for s in (simulation or {}).get('scenarios',[])])
    if not simulation:option['title']={'text':'暂无可用仿真结果','left':'center','top':'middle'}
    spec.append({'option':option,'height':400})
    spec.append({'option':cartesian([{'name':k,'value':v} for k,v in stats['monthly'].items()]),'height':380})
    option=base();option.update(series=[{'name':'事故类型构成','type':'pie','radius':['35%','64%'],'center':['50%','57%'],'avoidLabelOverlap':True,'label':{'formatter':'{b}\n{d}%','fontSize':13},'itemStyle':{'borderColor':'#fff','borderWidth':3},'data':pie_types}],legend={'type':'scroll','top':8,'textStyle':{'color':'#596577'}})
    spec.append({'option':option,'height':400})
    return spec

def decorate_report(soup,stats,simulation,title,created_at):
    specs=specifications(stats,simulation)
    node=os.getenv('NODE_BINARY') or shutil.which('node')
    if not node:raise ValueError('ECharts报告渲染需要Node.js')
    rendered=subprocess.run([node,str(ROOT/'scripts/echarts-render.cjs')],input=json.dumps(specs,ensure_ascii=False),capture_output=True,text=True,encoding='utf-8',timeout=45)
    if rendered.returncode:raise ValueError('ECharts图表渲染失败：'+rendered.stderr[-300:])
    svgs=json.loads(rendered.stdout)
    for el in soup.select('[data-extra-chart],#report-echarts-library,#report-echarts-init,.report-watermark,#report-chart-style'):el.decompose()
    hosts=list(soup.select('[data-chart]'))
    if len(hosts)>=1:
        anchor=hosts[0].find_parent(class_='figure') or hosts[0]
        for i,caption in [(3,'事故月度分布'),(4,'事故类型占比')]:
            figure=soup.new_tag('figure',attrs={'class':'echarts-figure','data-extra-chart':str(i)})
            host=soup.new_tag('div',attrs={'data-echart':str(i)});figure.append(host)
            label=soup.new_tag('figcaption');label.string=caption;figure.append(label);anchor.insert_after(figure);anchor=figure;hosts.append(host)
    for i,el in enumerate(hosts):
        el.clear();el['data-echart']=str(i);el['style']=f'width:100%;height:auto;aspect-ratio:900/{specs[i]["height"]};border:0;'
        el.append(BeautifulSoup(svgs[i],'html.parser'))
    library=soup.new_tag('script',id='report-echarts-library');library.string=(ROOT/'frontend/vendor/echarts.min.js').read_text(encoding='utf-8');soup.body.append(library)
    initializer=soup.new_tag('script',id='report-echarts-init')
    safe=json.dumps(specs,ensure_ascii=False).replace('<','\\u003c')
    initializer.string='''(()=>{const specs='''+safe+''';const charts=[];document.querySelectorAll('[data-echart]').forEach(el=>{el.innerHTML='';const c=echarts.init(el,null,{renderer:'svg'});c.setOption(specs[Number(el.dataset.echart)].option);charts.push(c)});let observer=new ResizeObserver(()=>charts.forEach(c=>c.resize()));document.querySelectorAll('[data-echart]').forEach(el=>observer.observe(el));window.addEventListener('beforeprint',()=>charts.forEach(c=>c.resize()));window.__reportChartsReady=true;})();'''
    soup.body.append(initializer)
    timestamp=datetime.fromisoformat(created_at.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    watermark=f'<svg xmlns="http://www.w3.org/2000/svg" width="650" height="300"><g transform="translate(325 150) rotate(-24)" text-anchor="middle" fill="#6b7280" fill-opacity="0.09" font-family="Microsoft YaHei,sans-serif"><text y="0" font-size="17">{html.escape(title)}</text><text y="28" font-size="15">{timestamp}</text></g></svg>'
    url='data:image/svg+xml;base64,'+base64.b64encode(watermark.encode()).decode()
    layer=soup.new_tag('div',attrs={'class':'report-watermark','aria-hidden':'true'});soup.body.append(layer)
    style=soup.new_tag('style',id='report-chart-style');style.string='''[data-echart] svg{width:100%;height:100%}.figure,.echarts-figure{border:0!important;background:transparent;margin:20px 0;break-inside:avoid}figcaption{text-align:center;color:#64748b;font-size:11pt;margin-top:8px}.report-watermark{position:fixed;inset:0;z-index:99;pointer-events:none;background-image:url("'''+url+'''");background-repeat:repeat;print-color-adjust:exact;-webkit-print-color-adjust:exact}@media print{[data-echart]{break-inside:avoid}.report-watermark{display:block}}''';soup.head.append(style)
    return soup
