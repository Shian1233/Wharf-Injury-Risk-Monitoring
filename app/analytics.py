"""Deterministic statistics, association network and temporal out-of-sample forecasting."""
from collections import Counter
from itertools import combinations
from datetime import date
import calendar
import math, re, hashlib
import numpy as np
from .db import db
from .ingest import num, money, missing
from .config import INDICATORS
from .industry_risk import extract_features, summarize_features
from .sd_factors import extract as extract_sd_factors, summarize as summarize_sd_factors, merge as merge_sd_factors

CAUSE_FIELDS={'人员':'人员原因','设备设施':'设施设备原因','工艺技术':'工艺技术原因','环境':'环境原因','管理':'管理原因'}
def marked(v): return not missing(v) and str(v).strip() not in {'0','否','无','×','不涉及','不适用'}
def ratio(a,b): return round(a/b*100,2) if b else None
def distribution(c): return [{'name':k,'value':v} for k,v in c.most_common()]
def metric(value,n=0,unit='',method='',reason=''):
    return {'value':value,'sample_count':n,'unit':unit,'method':method,'status':'available' if value is not None else 'unavailable','reason':reason if value is None else ''}

def statistics(filters):
    counters={k:Counter() for k in ['month','quarter','province','city','type','level','place','stage','activity','direct','indirect','factor','pairs']}
    known=Counter(); totals=Counter(); n=0; cause_samples=0; combos=set(); dated=0; valid_all=0; ids=[]; undated=0
    # An incident may have an investigation report plus a handling-result notice.
    # Keep all database records; count the incident once and reconcile known fields.
    incidents={}; record_count=0; conflict_count=0; manifest=[]
    for source in db.iter_records('accidents',**filters):
        record_count+=1
        manifest.append(source['_id']+':'+str(source['_version'])+':'+source['_hash'])
        title=str(source.get('事故名称') or '')
        title=re.split(r'事故(?:调查报告|调查|处理|的调查)',title)[0]+'事故' if '事故' in title else title
        title=re.sub(r'[^\w\u4e00-\u9fff]','',title)
        key=(source.get('省份'),source['_industry'],source['_date'],title) if title and not missing(source.get('事故名称')) else ('record',source['_id'])
        if key not in incidents:
            row=dict(source)
            row['_risk_features']=extract_features(source)
            row['_sd_features']=extract_sd_factors(source)
            for f in ['直接原因','间接原因']: row[f]='有原因描述' if not missing(row.get(f)) else None
            # Avoid retaining large narrative fields while scanning 200k records.
            for f in ['事故经过','事故防范与整改','事故处置与救援']: row.pop(f,None)
            incidents[key]=row
        else:
            row=incidents[key]
            row['_risk_features'].update(extract_features(source))
            merge_sd_factors(row['_sd_features'],extract_sd_factors(source))
            for f in ['失踪人数','受伤人数','轻伤人数','重伤人数','死亡人数','直接经济损失']:
                if missing(row.get(f)) and not missing(source.get(f)): row[f]=source[f]
                elif not missing(row.get(f)) and not missing(source.get(f)) and str(row[f])!=str(source[f]):
                    row[f]='报告未明确'; conflict_count+=1
            for f in CAUSE_FIELDS.values():
                if marked(source.get(f)): row[f]=source[f]
            for f in ['直接原因','间接原因']:
                if not missing(source.get(f)): row[f]='有原因描述'
            for f in ['事故等级','事故类型','作业场所','作业环节','作业活动']:
                if missing(row.get(f)) and not missing(source.get(f)): row[f]=source[f]
    for row in incidents.values():
        n+=1
        if len(ids)<1000: ids.append({'id':row['_id'],'编号':row.get('编号'),'报告源':row.get('报告源')})
        if row['_date']:
            dated+=1; counters['month'][row['_date'][:7]]+=1
            counters['quarter'][row['_date'][:4]+' Q'+str((int(row['_date'][5:7])-1)//3+1)]+=1
        else: undated+=1
        for key,field in [('province','省份'),('city','地市'),('type','事故类型'),('level','事故等级'),('place','作业场所'),('stage','作业环节'),('activity','作业活动')]:
            if not missing(row.get(field)): counters[key][str(row[field])]+=1
            else: known[key+'_missing']+=1
        for field in ['死亡人数','受伤人数','重伤人数','轻伤人数','失踪人数','直接经济损失']:
            v=money(row.get(field)) if field=='直接经济损失' else num(row.get(field))
            if v is not None:
                known[field]+=1; totals[field]+=v
        if num(row.get('死亡人数')) is not None and num(row.get('死亡人数'))>0: known['死亡事故']+=1
        if not missing(row.get('直接原因')) or not missing(row.get('间接原因')):
            cause_samples+=1
        for key,field in [('direct','直接原因'),('indirect','间接原因')]:
            if not missing(row.get(field)): counters[key]['有'+field+'记录']+=1
        factors=[k for k,f in CAUSE_FIELDS.items() if marked(row.get(f))]
        for f in factors: counters['factor'][f]+=1
        for pair in combinations(sorted(factors),2): counters['pairs'][pair]+=1
        if factors: combos.add(tuple(sorted(factors)))
        if all(not missing(row.get(f)) for f in ['发生时间','省份','行业','事故类型','事故等级','死亡人数','直接原因']): valid_all+=1
    links=[]; degrees=Counter()
    for (a,b),support in counters['pairs'].most_common():
        pa=counters['factor'][a]; pb=counters['factor'][b]
        lift=support*n/(pa*pb) if pa and pb else 0
        links.append({'source':a,'target':b,'count':support,'support':ratio(support,n),'confidence':ratio(support,pa),'lift':round(lift,4)})
        degrees[a]+=support; degrees[b]+=support
    excluded=None
    if filters.get('start') or filters.get('end'):
        f={k:v for k,v in filters.items() if k not in ['start','end']}
        w,a=db.where('accidents',**f)
        excluded=db.query('SELECT COUNT(*) AS N FROM RISK_ACCIDENTS'+w+(' AND ' if w else ' WHERE ')+'''("_date"='' OR "_date" IS NULL)''',a)[0]['N']
    return {'count':n,'record_count':record_count,'duplicate_reports':record_count-n,'conflicting_fields':conflict_count,
        'source_manifest_sha256':hashlib.sha256('\n'.join(sorted(manifest)).encode()).hexdigest(),
        'deduplication_rule':'省份、行业、规范化事故名称、发生日期相同的报告归为同一事故；不同事故记录完整保留。数字冲突字段暂不统计，需复核。',
        'dated_count':dated,'undated':undated,'undated_excluded':excluded,'totals':dict(totals),'known':dict(known),
        'coverage':ratio(valid_all,n),'cause_samples':cause_samples,'factor_counts':dict(counters['factor']),
        'distributions':{k:distribution(v) for k,v in counters.items() if k!='pairs'},
        'monthly':dict(sorted(counters['month'].items())),'network':{'nodes':[{'id':k,'count':v,'importance':degrees[k]} for k,v in counters['factor'].items()],'links':links},
        'combinations':len(combos),'sources':ids,'source_count':n,'scope':filters,
        'industry_evidence':summarize_features(incidents.values(),filters),
        'sd_evidence':summarize_sd_factors(incidents.values()),
        'data_note':'统计对象为已导入事故调查报告样本；未确认采集完整性，不能解释为区域事故全量。'}

def foundation(filters):
    # Enterprise snapshots are selected by latest period per stable location key.
    latest={}; f={k:v for k,v in filters.items() if k!='q'}
    for r in db.iter_records('enterprises',**f):
        key=(r.get('统一社会信用代码') or r.get('企业名称') or r.get('记录编号'),r.get('场所编号') or '')
        if key not in latest or (r['_date'] or '')>(latest[key]['_date'] or ''): latest[key]=r
    enterprise=list(latest.values()); climate=list(db.iter_records('climate',**{k:v for k,v in f.items() if k!='industry'}))
    economics=list(db.iter_records('economy',**{k:v for k,v in f.items() if k!='industry'}))
    def sumfield(rows,field,unit=''):
        values=[num(r.get(field)) for r in rows]; values=[v for v in values if v is not None]
        return metric(round(sum(values),4) if values else None,len(values),unit,'有效字段求和','无有效'+field+'数据')
    temp=[num(r.get('平均温度（℃）')) for r in climate]; temp=[x for x in temp if x is not None]
    # Do not sum mixed units, repeated periods or overlapping administrative levels.
    return {'企业数量':metric(len({r.get('统一社会信用代码') or r.get('企业名称') for r in enterprise}) if enterprise else None,len(enterprise),'家','信用代码/企业名称去重，取最新场所记录','企业数据为空'),
        '从业人员数量':sumfield(enterprise,'从业人数','人'),
        '重点企业数量':metric(sum(marked(r.get('重大危险源')) for r in enterprise) if enterprise else None,len(enterprise),'家','重大危险源企业，按企业键去重','企业数据为空'),
        '平均气温':metric(round(sum(temp)/len(temp),2) if temp else None,len(temp),'℃','气象记录算术均值，非空间加权','无有效气温数据'),
        '降水量':metric(None,0,'mm',reason='需要指定同站点、非重叠统计时段后方可累计'),
        '高温天数':metric(len({(r['_date'],r.get('气象站/网格编号')) for r in climate if (num(r.get('最高温度（℃）')) or -999)>=35}) if climate else None,len(climate),'站日','最高温度≥35℃，同站同日去重','气候环境数据为空'),
        '极端天气次数':metric(sum(any(marked(r.get(k)) for k in ['极端降雨标志','雷电','台风影响','冰雹']) for r in climate) if climate else None,len(climate),'条','存在极端天气标记的观测记录','气候环境数据为空'),
        '企业安全投入总额':metric(None,0,'万元',reason='需统一安全投入单位并指定不重叠统计期'),
        '行业产量/产值':metric(None,0,reason='需要统一产量单位、统计期和企业口径'),
        '工业增加值':metric(None,len(economics),reason='当前标准提供第二产业增加值及规上工业增加值增速，不能直接替代工业增加值'),
        '固定资产投资':metric(None,len(economics),reason='标准提供固定资产投资增速，未提供投资额'),
        '_counts':{'enterprises':len(enterprise),'climate':len(climate),'economy':len(economics)}}

def high_risk_duration(points,threshold):
    """Integrate time above the threshold using actual sample intervals.

    A crossing is estimated linearly within its interval. This also accepts
    historical monthly samples without treating the sample count as months.
    """
    duration=0.
    for first,last in zip(points,points[1:]):
        dt=last['month']-first['month']
        if dt<=0: continue
        a,b=first['risk_index'],last['risk_index']
        if a>=threshold and b>=threshold: duration+=dt
        elif a<threshold and b<threshold: continue
        else:
            crossing=(threshold-a)/(b-a)
            duration+=dt*((1-crossing) if b>=threshold else crossing)
    return duration


def indicators(stats,base,simulation=None,forecast=None,selected_scenario='基准场景'):
    n=stats['count']; k=stats['known']; t=stats['totals']; d=stats['distributions']; result={x:metric(None,reason='当前字段或样本不能支持该指标') for g in INDICATORS for x in g['items']}
    result.update({x:v for x,v in base.items() if not x.startswith('_')})
    result['事故总数']=metric(n,n,'起','按省份、行业、事故名称和发生日期合并同事故报告')
    for name,key in [('月度分布','month'),('季度分布','quarter'),('省级分布','province'),('地市分布','city'),('事故类型分布','type'),('事故等级分布','level'),('作业场所分布','place'),('作业环节分布','stage'),('作业活动分布','activity')]:
        result[name]=metric(d[key],sum(x['value'] for x in d[key]),'起','按原字段分组统计')
    result['事故月份集中度']=metric(round(sum((v/max(stats['dated_count'],1))**2 for v in stats['monthly'].values()),4) if stats['dated_count'] else None,stats['dated_count'],'HHI','按年月频率平方和')
    for name,factor in [('人员因素频次','人员'),('设备设施因素频次','设备设施'),('工艺技术因素频次','工艺技术'),('环境因素频次','环境'),('管理因素频次','管理')]:
        result[name]=metric(stats['factor_counts'].get(factor,0),stats['cause_samples'],'起','原原因字段有效标记计数，空值不代表无该因素')
    for name,key in [('直接原因频次','direct'),('间接原因频次','indirect')]: result[name]=metric(d[key],stats['cause_samples'],'起','有对应原因描述的记录数，未作自由文本同义归并')
    result['因素关联强度']=metric(stats['network']['links'],stats['cause_samples'],'提升度','共同标记频率/边缘标记频率乘积；共现不表示因果')
    result['关键因素重要度']=metric(stats['network']['nodes'],stats['cause_samples'],'加权度','网络边共现频次之和')
    result['典型致因组合数量']=metric(stats['combinations'],stats['cause_samples'],'组','原因标记集合去重')
    result['风险因素样本覆盖率']=metric(ratio(stats['cause_samples'],n),n,'%','有直接或间接原因描述的样本/全部样本')
    for f in ['死亡人数','重伤人数','轻伤人数','失踪人数','直接经济损失']:
        result[f]=metric(t.get(f) if k.get(f) else None,k.get(f,0),'万元' if '损失' in f else '人','有效已知字段求和，缺失排除','无有效字段')
    result['伤亡总人数']=metric(t.get('死亡人数',0)+t.get('受伤人数',0) if k.get('死亡人数')==n and k.get('受伤人数')==n and n else None,n,'人','死亡人数+受伤人数，重/轻伤不重复加总','死亡或受伤人数存在缺失')
    for name,f in [('平均每起死亡人数','死亡人数'),('平均每起受伤人数','受伤人数'),('平均每起直接经济损失','直接经济损失')]:
        result[name]=metric(round(t[f]/k[f],3) if k.get(f) else None,k.get(f,0),'万元/起' if '损失' in f else '人/起','有效字段总和/该字段有效样本数')
    levels=d['level']; severe=sum(x['value'] for x in levels if any(v in x['name'] for v in ['较大','重大']))
    result['较大及以上事故占比']=metric(ratio(severe,sum(x['value'] for x in levels)),sum(x['value'] for x in levels),'%','较大、重大、特别重大事故/等级已知事故')
    result['死亡事故占比']=metric(ratio(k.get('死亡事故',0),k.get('死亡人数',0)),k.get('死亡人数',0),'%','死亡人数>0事故/死亡字段有效事故')
    if simulation:
        base_curve=next(s['points'] for s in simulation['scenarios'] if s['name']==selected_scenario); values=[r['risk_index'] for r in base_curve]; peak=max(values); final=values[-1]; initial=values[0]
        for name,value,unit in [('当前综合风险指数',initial,'指数'),('预测末期风险指数',final,'指数'),('预测期峰值风险',peak,'指数'),('预测期最低风险',min(values),'指数'),('峰值出现时间',base_curve[values.index(peak)]['month'],'月'),('综合风险变化率',ratio(final-initial,initial),'%'),('高风险持续时间',high_risk_duration(base_curve,simulation['threshold']),'月')]:
            result[name]=metric(round(value,4) if isinstance(value,float) else value,n,unit,'SD数值积分；阈值为用户假设，不代表事故概率')
        result['高风险持续时间']['method']='按实际采样间隔累计阈值以上时长，区间内交叉时刻作线性估计；阈值为用户假设'
        risk_variables=[k for k,v in simulation.get('output_metrics',{}).items() if v.get('role')=='factor'] or simulation['stock_names']
        rises={v:base_curve[-1].get(v,0)-base_curve[0].get(v,0) for v in risk_variables}
        rising=max(rises,key=rises.get) if max(rises.values(),default=0)>0 else None
        result['主要上升风险类别']=metric(simulation.get('output_metrics',{}).get(rising,{}).get('label') or simulation.get('stock_labels',{}).get(rising,rising) if rising else '无上升类别',n,method='SD专业因素期末与初值比较；累计负荷与滞后状态不作为风险类别')
        baseline_final=simulation['scenarios'][0]['points'][-1]['risk_index']
        for label,index in [('生产压力场景变化率',1),('安全投入场景变化率',2)]: result[label]=metric(ratio(simulation['scenarios'][index]['points'][-1]['risk_index']-baseline_final,baseline_final),n,'%','该情景期末相对基准情景期末变化')
    if forecast and forecast['status']=='available': result['预测事故起数']=metric(round(sum(p['mean'] for p in forecast['points']),3),forecast['sample_count'],'起','Poisson趋势回归；仅适用于已确认全量采集口径')
    result['重点风险治理任务数']=metric(len(stats['network']['nodes']),stats['cause_samples'],'项','每类已识别原因对应一项治理建议')
    result['重点区域覆盖数']=metric(len(d['province']),n,'省级区域','报告涉及的已知省级区域数')
    result['建议证据覆盖率']=metric(100 if stats['cause_samples'] else None,len(stats['network']['nodes']),'%','每条生成建议链接到对应原因字段证据；不表示专家一致性')
    # No completion-rate denominators exist in the supplied standard.
    for f in ['隐患整改率','重大隐患闭环率','检查覆盖率','培训完成率','设备检维修完成率','特殊作业合规率','应急演练完成率','监测异常处置率']:
        result[f]=metric(None,reason='原字段未同时提供已完成数量与应完成数量，不能推算完成率')
    return result

def month_sequence(start,end):
    a=date.fromisoformat(start[:7]+'-01'); b=date.fromisoformat(end[:7]+'-01'); out=[]
    while a<=b:
        out.append(a.strftime('%Y-%m'))
        a=date(a.year+(a.month==12),a.month%12+1,1)
    return out
def forecast_counts(stats,horizon,coverage_confirmed=False):
    if not coverage_confirmed: return {'status':'unavailable','reason':'未确认分析期事故采集完整性，不能将无记录月份视为零事故。','points':[],'validation':None}
    scope=stats['scope']; monthly=stats['monthly']
    if not scope.get('start') or not scope.get('end'): return {'status':'unavailable','reason':'预测必须指定完整分析起止时间','points':[],'validation':None}
    months=month_sequence(scope['start'],scope['end'])
    if len(months)<24 or stats['dated_count']<30: return {'status':'unavailable','reason':'计数预测至少需要24个完整月、30条有时间事故记录及全量采集确认','points':[],'validation':None}
    end_date=date.fromisoformat(scope['end'])
    if scope['start'][8:]!='01' or end_date.day!=calendar.monthrange(end_date.year,end_date.month)[1]:
        return {'status':'unavailable','reason':'计数预测需按完整自然月设置起止日期','points':[],'validation':None}
    y=np.array([monthly.get(m,0) for m in months],dtype=float); rng=np.random.default_rng(20261013)
    def design(indices,scale):
        a=np.asarray(indices); return np.column_stack([np.ones(len(a)),a/scale,np.sin(2*np.pi*a/12),np.cos(2*np.pi*a/12)])
    def fit(values):
        X=design(np.arange(len(values)),len(months)); beta=np.zeros(4); beta[0]=math.log(max(float(np.mean(values)),0.05)); penalty=np.diag([0,0.2,0.2,0.2])
        for _ in range(60):
            mu=np.exp(np.clip(X@beta,-10,8)); grad=X.T@(values-mu)-penalty@beta
            delta=np.linalg.solve(X.T@(mu[:,None]*X)+penalty+np.eye(4)*1e-8,grad)
            beta+=np.clip(delta,-1,1)
            if np.linalg.norm(delta)<1e-7: break
        covariance=np.linalg.pinv(X.T@(np.exp(np.clip(X@beta,-10,8))[:,None]*X)+penalty)
        return beta,covariance
    hold=min(12,max(6,len(y)//4)); actual=y[-hold:]; predictions=[]; covered=[]; accuracies=[]
    for pos in range(len(y)-hold,len(y)):
        beta,cov=fit(y[:pos]); x=design([pos],len(months)); lam=np.exp(np.clip(x@beta,-10,8))[0]
        draws=rng.poisson(np.exp(np.clip(rng.multivariate_normal(beta,cov,2000)@x[0],-10,8)))
        lo,hi=np.quantile(draws,[.05,.95]); predictions.append(float(lam)); covered.append(lo<=y[pos]<=hi)
        accuracies.append(max(0,1-abs(lam-y[pos])/max(1,y[pos])))
    beta,cov=fit(y); xs=design(np.arange(len(y),len(y)+horizon),len(months)); sample_beta=rng.multivariate_normal(beta,cov,4000)
    points=[]
    last=date.fromisoformat(months[-1]+'-01')
    for j,x in enumerate(xs):
        ym=(last.year*12+last.month-1+j+1); label=f'{ym//12:04d}-{ym%12+1:02d}'
        pred=np.exp(np.clip(sample_beta@x,-10,8)); draws=rng.poisson(pred); lo,hi=np.quantile(draws,[.05,.95]); ci=np.quantile(pred,[.05,.95])
        points.append({'month':label,'mean':round(float(np.exp(np.clip(x@beta,-10,8))),4),'lower90':float(lo),'upper90':float(hi),'mean_ci90':[round(float(v),4) for v in ci]})
    validation={'method':'逐月滚动单步回测，训练期始终早于测试期','holdout_months':hold,'mae':round(float(np.mean(np.abs(actual-np.array(predictions)))),4),
        'accuracy_definition':'逐月max(0,1-|预测-实际|/max(实际,1))的均值','accuracy':round(float(np.mean(accuracies))*100,2),'interval_level':90,
        'interval_coverage':ratio(sum(covered),len(covered)),'actual':actual.tolist(),'predicted':[round(v,4) for v in predictions],
        'accepted':False,'note':'预测区间标称90%不等同于预测准确率90%；验收准确性阈值及统计口径需双方约定。'}
    return {'status':'available','points':points,'validation':validation,'sample_count':stats['dated_count'],'months':len(months),'model':'带趋势和季节项的惩罚Poisson回归','coverage_confirmed':True}

def wilson(matches,total,z=1.6448536269514722):
    if not total: return None
    p=matches/total; den=1+z*z/total; center=(p+z*z/(2*total))/den; margin=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [round((center-margin)*100,2),round((center+margin)*100,2)]
