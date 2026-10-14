"""Safe scalar expression interpreter and fourth-order Runge-Kutta SD engine."""
import ast, math, re, operator, copy, json
from .config import INDUSTRIES, ROOT
from .db import db, uid, now
from .analytics import CAUSE_FIELDS
from .industry_risk import PROFILES, PROFILE_VERSION, calibration_value
from . import sd_feedback

FUNCTIONS={'min':min,'max':max,'abs':abs,'exp':math.exp,'log':math.log,'sqrt':math.sqrt,'sin':math.sin,'cos':math.cos}
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
class Formula:
    def __init__(self,text,names):
        if not isinstance(text,str) or len(text)>1000: raise ValueError('公式长度超限')
        try: self.tree=ast.parse(text,mode='eval').body
        except SyntaxError: raise ValueError('公式语法无效')
        self.dependencies=set()
        nodes=list(ast.walk(self.tree))
        if len(nodes)>200: raise ValueError('公式过于复杂')
        allowed=(ast.BinOp,ast.UnaryOp,ast.Constant,ast.Name,ast.Call,ast.Load,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.UAdd,ast.USub)
        for node in nodes:
            if not isinstance(node,allowed): raise ValueError('公式仅支持数值、变量和允许的数学函数')
            if isinstance(node,ast.Constant) and (type(node.value) not in [float,int] or not math.isfinite(node.value) or abs(node.value)>1e9): raise ValueError('常量无效')
            if isinstance(node,ast.Name):
                if node.id not in names and node.id not in FUNCTIONS: raise ValueError('未知变量：'+node.id)
                if node.id in names: self.dependencies.add(node.id)
            if isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.func.id not in FUNCTIONS or node.keywords or len(node.args)>10): raise ValueError('函数调用无效')
    def __call__(self,env):
        def visit(n):
            if isinstance(n,ast.Constant): return float(n.value)
            if isinstance(n,ast.Name): return env[n.id]
            if isinstance(n,ast.UnaryOp): return visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
            if isinstance(n,ast.BinOp):
                a,b=visit(n.left),visit(n.right)
                if isinstance(n.op,ast.Pow) and abs(b)>16: raise ValueError('幂指数超限')
                return OPS[type(n.op)](a,b)
            if isinstance(n,ast.Call): return FUNCTIONS[n.func.id](*[visit(a) for a in n.args])
            raise ValueError('公式节点无效')
        try: value=float(visit(self.tree))
        except (ArithmeticError,ValueError,TypeError,KeyError): raise ValueError('公式计算失败（除零、函数定义域或缺少参数）')
        if not math.isfinite(value) or abs(value)>1e10: raise ValueError('公式结果发散或溢出')
        return value

def compile_model(model):
    if model.get('industry') not in INDUSTRIES: raise ValueError('模型行业无效')
    variables=model.get('variables',[]); params=model.get('parameters',{})
    if not 1<=len(variables)<=100 or len(params)>100: raise ValueError('模型变量/参数数量无效')
    vnames=[v['name'] for v in variables]; names=vnames+list(params)+['time']
    if len(set(names))!=len(names) or any(not re.fullmatch(r'[A-Za-z_\u4e00-\u9fff][A-Za-z_0-9\u4e00-\u9fff]*',n) or n in FUNCTIONS or n.startswith('__') for n in names): raise ValueError('变量名称重复或非法')
    for name,p in params.items():
        val=p['value']
        if type(val) not in [int,float] or not math.isfinite(val) or not p.get('min',-1e6)<=val<=p.get('max',1e6): raise ValueError('参数越界：'+name)
        calibration=p.get('calibrate')
        if calibration and model.get('profile_version')!=sd_feedback.PROFILE_VERSION:
            supported=set(CAUSE_FIELDS.values()) | {f'industry:{key}:{kind}' for key,_,_ in PROFILES[model['industry']] for kind in ['initial','weight','trend']}
            if calibration not in supported: raise ValueError('参数的事故特征与所属行业不匹配：'+name)
    expressions={}; stocks=[]; auxiliary=[]
    for v in variables:
        if v.get('type')=='stock':
            stocks.append(v); expressions[v['name']]=Formula(v['rate'],set(names)); Formula(str(v['initial']),set(params))
        elif v.get('type')=='aux': auxiliary.append(v); expressions[v['name']]=Formula(v['formula'],set(names))
        else: raise ValueError('变量类型需为stock/aux')
    if not stocks: raise ValueError('SD模型至少包含一个存量')
    if 'risk_index' not in vnames: raise ValueError('模型需提供risk_index输出')
    order=[]; unresolved={v['name'] for v in auxiliary}
    while unresolved:
        ready=sorted(n for n in unresolved if not expressions[n].dependencies & unresolved)
        if not ready: raise ValueError('辅助变量存在代数循环：'+','.join(sorted(unresolved)))
        order.extend(ready); unresolved.difference_update(ready)
    if model.get('profile_version')==sd_feedback.PROFILE_VERSION:
        sd_feedback.validate_structure(model,expressions)
    return stocks,order,expressions

def validate(model):
    stocks,order,expr=compile_model(model); params={k:v['value'] for k,v in model['parameters'].items()}
    state={v['name']:Formula(str(v['initial']),set(params))(params) for v in stocks}
    env={**params,**state,'time':0}
    for name in order: env[name]=expr[name](env)
    for v in stocks: expr[v['name']](env)
    links=[]
    for target,f in expr.items():
        for source in sorted(f.dependencies): links.append({'source':source,'target':target})
    return {'valid':True,'stocks':len(stocks),'auxiliary':len(order),'edges':links,'initial_output':env['risk_index']}

def legacy_model(industry):
    params={'production_pressure':{'value':1.,'min':0.1,'max':3.,'label':'生产压力','unit':'倍','source':'情景假设'},
            'safety_effort':{'value':1.,'min':0.,'max':3.,'label':'安全投入强度','unit':'倍','source':'情景假设'},
            'response_time':{'value':6.,'min':1.,'max':36.,'label':'风险调整时间','unit':'月','source':'待专家标定假设'},
            'prevention_rate':{'value':.05,'min':0.,'max':1.,'label':'治理速率','unit':'1/月','source':'待专家标定假设'}}
    variables=[]
    for name,label in [('personnel','人员'),('equipment','设备设施'),('process','工艺技术'),('environment','环境'),('management','管理')]:
        params[name+'_initial']={'value':0.,'min':0.,'max':100.,'label':label+'初始指数','unit':'指数','source':'运行时事故原因标记比例标定','calibrate':CAUSE_FIELDS[label]}
        variables.append({'name':name+'_risk','label':label+'风险','type':'stock','unit':'指数','initial':name+'_initial','min':0,'max':100,
            'rate':f'({name}_initial*production_pressure-{name}_risk)/response_time-prevention_rate*safety_effort*{name}_risk'})
    variables.append({'name':'risk_index','label':'综合风险指数','type':'aux','unit':'指数','formula':'(personnel_risk+equipment_risk+process_risk+environment_risk+management_risk)/5'})
    return {'id':uid(),'name':industry+'风险演化初始模型','industry':industry,'version':1,'status':'待业务标定','description':'基于事故原因标记比例的五维风险存量模型，响应时间及治理速率为显式假设；指数不是事故概率。','format':'risk-sd/1.0','parameters':params,'variables':variables,'created_at':now()}

def default_model(industry):
    model=legacy_model(industry)
    params={k:v for k,v in model['parameters'].items() if not v.get('calibrate')}
    variables=[]
    for key,label,_ in PROFILES[industry]:
        for suffix,value,low,high,unit in [('initial',0.,0,100,'指数'),('weight',1/len(PROFILES[industry]),0,1,'权重'),('trend',0.,-100/6,100/6,'指数/月')]:
            params[f'{key}_{suffix}']={'value':value,'min':low,'max':high,'unit':unit,
                'label':label+{'initial':'初始指数','weight':'权重','trend':'趋势'}[suffix],
                'calibrate':f'industry:{key}:{suffix}','source':'运行时根据同业事故报告计算'}
        variables.append({'name':key+'_risk','label':label+'风险','type':'stock','unit':'指数',
            'initial':key+'_initial','min':0,'max':100,
            'rate':f'(max(0,min(100,{key}_initial*production_pressure*(1+0.15*(management_risk-management_initial)/100)+{key}_trend*response_time*(1-exp(-time/response_time))))-{key}_risk)/response_time-prevention_rate*safety_effort*{key}_risk'})
    params['management_initial']={'value':0.,'min':0.,'max':100.,'label':'管理初始指数','unit':'指数',
        'calibrate':CAUSE_FIELDS['管理'],'source':'运行时按管理原因标记比例计算'}
    variables.append({'name':'management_risk','label':'管理风险','type':'stock','unit':'指数','min':0,'max':100,
        'initial':'management_initial','rate':'(management_initial*production_pressure-management_risk)/response_time-prevention_rate*safety_effort*management_risk'})
    variables.append({'name':'risk_index','label':'综合风险指数','type':'aux','unit':'指数',
        'formula':'0.8*('+ '+'.join(key+'_weight*'+key+'_risk' for key,_,_ in PROFILES[industry])+')+0.2*management_risk'})
    model.update(name=industry+'事故风险演化模型',parameters=params,variables=variables,profile_version=PROFILE_VERSION,
        description='从同业事故类型、名称及直接原因提取风险线索，计算初始指数、权重与半年趋势，结合管理风险进行情景推演。动态系数仍需专家标定；指数不代表事故概率。',
        assumptions={'hazard_weight':.8,'management_weight':.2,'management_coupling':.15,'trend_window_months':6},
        feature_labels={key:label for key,label,_ in PROFILES[industry]})
    return model


def initialize_legacy_models():
    for industry in INDUSTRIES:
        existing=[m for m in db.list_docs('model') if m['industry']==industry]
        if any(m.get('profile_version')==PROFILE_VERSION for m in existing): continue
        legacy=legacy_model(industry)
        # Only migrate untouched built-ins; retain every prior version and custom model.
        original=next((m for m in existing if all(m.get(k)==legacy[k] for k in ['name','parameters','variables'])),None)
        m=default_model(industry)
        if original:
            m.update(id=original['id'],version=original['version']+1,created_at=original['created_at'],updated_at=now())
        with db.transaction() as c:
            if original: db.put_doc('model_version',original['id']+':'+str(original['version']),original,c)
            db.put_doc('model',m['id'],m,c); db.put_doc('model_version',m['id']+':'+str(m['version']),m,c)

def initialize_models():
    """Migrate built-ins once, archive exact snapshots and never rewrite custom models."""
    for industry in INDUSTRIES:
        existing=[m for m in db.list_docs('model') if m['industry']==industry]
        # model_family persists through a user-requested restore to a historical version.
        if any(m.get('model_family')==sd_feedback.PROFILE_VERSION or m.get('profile_version')==sd_feedback.PROFILE_VERSION for m in existing): continue
        templates=[legacy_model(industry),default_model(industry)]
        original=next((m for m in existing if any(all(m.get(k)==t[k] for k in ['name','parameters','variables']) for t in templates)),None)
        m=sd_feedback.default_model(industry)
        if original:
            m.update(id=original['id'],version=original['version']+1,created_at=original['created_at'],updated_at=now())
        elif existing:
            # Preserve custom originals and explicitly carry their scenario settings into the new model.
            m['migration_sources']=[x['id'] for x in existing]
            for key in ['production_pressure','safety_effort','response_time','prevention_rate']:
                old=existing[0]['parameters'].get(key)
                if old and m['parameters'][key]['min']<=old['value']<=m['parameters'][key]['max']:
                    m['parameters'][key]['value']=old['value'];m['parameters'][key]['source']='沿用已保存模型的用户参数，尚未经验证'
        validate(m)
        with db.transaction() as c:
            if original: db.put_doc('model_version',original['id']+':'+str(original['version']),original,c)
            db.put_doc('model',m['id'],m,c);db.put_doc('model_version',m['id']+':'+str(m['version']),m,c)

def preferred_model(industry):
    models=[m for m in db.list_docs('model') if m['industry']==industry]
    return next((m for m in models if m.get('model_family')==sd_feedback.PROFILE_VERSION),models[0] if models else None)

def simulate(model,stats,months=3,overrides=None,threshold=60):
    feedback=model.get('profile_version')==sd_feedback.PROFILE_VERSION
    industry_model=any(p.get('calibrate','').startswith('industry:') for p in model['parameters'].values())
    if not feedback and (not stats['count'] or (not industry_model and not stats['cause_samples'])): raise ValueError('范围内没有事故原因数据，无法标定SD模型')
    model=copy.deepcopy(model); provenance=[]
    if feedback:
        model,provenance,evidence=sd_feedback.prepare(model,stats,overrides)
    for key,p in ([] if feedback else model['parameters'].items()):
        if p.get('calibrate'):
            if p['calibrate'].startswith('industry:'):
                item=calibration_value(p['calibrate'],stats,model['industry'])
                p['value']=item['value']; provenance.append({'parameter':key,**item})
                continue
            field=p['calibrate']; factor=next((k for k,v in CAUSE_FIELDS.items() if v==field),None)
            if not factor: raise ValueError('标定字段未实现：'+field)
            p['value']=100*stats['factor_counts'].get(factor,0)/stats['count']
            provenance.append({'parameter':key,'field':field,'value':p['value'],'numerator':stats['factor_counts'].get(factor,0),'denominator':stats['count'],'method':'原调查报告原因标记比例；空标记不代表排除该原因'})
    for key,val in ([] if feedback else (overrides or {}).items()):
        if key not in model['parameters']: raise ValueError('未知模型参数：'+key)
        if model['parameters'][key].get('calibrate'): raise ValueError('事故数据计算参数不能手动覆盖：'+key)
        model['parameters'][key]['value']=val
        provenance.append({'parameter':key,'value':val,'method':'用户显式设置，覆盖标定值'})
    stocks,order,expr=compile_model(model); validate(model)
    if not 1<=months<=36: raise ValueError('仿真周期需在1至36个月')
    initial_params={k:v['value'] for k,v in model['parameters'].items()}
    common_initial=[Formula(str(v['initial']),set(initial_params))(initial_params) for v in stocks]
    scenarios=[]
    for label,p_mult,s_mult in [('基准场景',1.,1.),('生产压力增大',1.2,1.),('安全投入减少',1.,.8)]:
        params={k:v['value'] for k,v in model['parameters'].items()}
        if 'production_pressure' in params: params['production_pressure']*=p_mult
        if 'safety_effort' in params: params['safety_effort']*=s_mult
        names=[v['name'] for v in stocks]
        y=list(common_initial) if feedback else [Formula(str(v['initial']),set(params))(params) for v in stocks]
        def env_at(y,t):
            env={**params,**dict(zip(names,y)),'time':t}
            for n in order: env[n]=expr[n](env)
            if feedback:
                for n in ['hazard_pressure','cumulative_load','feedback_signal','hazard_formation','hazard_removal','accident_intensity']:
                    if env[n]<-1e-9: raise ValueError('模型出现负存量或负流量，请调整公式：'+n)
                if not 0<=env['risk_index']<=100: raise ValueError('综合风险指数超出固定范围')
            return env
        def rates(y,t):
            env=env_at(y,t); return [expr[n](env) for n in names]
        def point(y,t):
            env=env_at(y,t); return {'month':round(t,4),**{n:round(env[n],6) for n in names+order}}
        points=[point(y,0)]; h=.05
        for step in range(months*20):
            t=step*h; k1=rates(y,t); k2=rates([a+h*b/2 for a,b in zip(y,k1)],t+h/2); k3=rates([a+h*b/2 for a,b in zip(y,k2)],t+h/2); k4=rates([a+h*b for a,b in zip(y,k3)],t+h)
            y=[a+h*(b+2*c+2*d+e)/6 for a,b,c,d,e in zip(y,k1,k2,k3,k4)]
            y=[min(v.get('max',1e10),max(v.get('min',-1e10),a)) for v,a in zip(stocks,y)]
            points.append(point(y,(step+1)*h))
        scenarios.append({'name':label,'parameters':params,'points':points})
    result={'id':uid(),'model_id':model['id'],'model_version':model['version'],'model_name':model['name'],'model_status':model['status'],
        'method':'RK4，时间步长0.05月','sampling_interval_months':.05,'scenarios':scenarios,'calibration':provenance,'stock_names':[s['name'] for s in stocks],'stock_labels':{s['name']:s.get('label',s['name']) for s in stocks},'threshold':threshold,
        'industry_evidence':stats.get('industry_evidence',{}).get(model['industry']) if industry_model else None,
        'source_manifest_sha256':stats.get('source_manifest_sha256'),
        'warning':'初始模型未经专家机理校验，动态速率参数为假设；仿真用于情景比较，不作为已验收预测结果。','created_at':now(),'scope':stats['scope']}
    return sd_feedback.summarize_result(result,model,evidence) if feedback else result

def import_vensim(text,industry,name):
    """Support an explicit numeric/INTEG subset, refuse unsupported functions."""
    body=text.split('\\\\\\---')[0]; body=re.sub(r'^\{[^\n]+\}\s*','',body)
    entries={}
    for block in body.split('|'):
        equation=block.split('~')[0].strip()
        if '=' in equation:
            key,formula=equation.split('=',1); key=key.strip().replace(' ','_'); entries[key]=formula.strip().replace('^','**')
    if not entries: raise ValueError('Vensim文件未找到可解析公式')
    ignored={'INITIAL_TIME','FINAL_TIME','TIME_STEP','SAVEPER'}; params={}; variables=[]
    for key,value in entries.items():
        if key in ignored: continue
        value=value.replace('TIME','time')
        m=re.fullmatch(r'INTEG\s*\((.*),\s*([^,]+)\)',value,re.S|re.I)
        if m: variables.append({'name':key,'label':key,'type':'stock','initial':m[2].strip(),'rate':m[1].strip()})
        else:
            try: params[key]={'label':key,'value':float(value),'source':'导入模型','min':-1e6,'max':1e6}
            except ValueError: variables.append({'name':key,'label':key,'type':'aux','formula':value})
    model={'id':uid(),'name':name,'industry':industry,'version':1,'status':'导入待校验','format':'risk-sd/1.0','parameters':params,'variables':variables,'created_at':now()}
    validate(model)
    return model
