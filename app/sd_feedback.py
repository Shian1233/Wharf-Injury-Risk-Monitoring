"""Relative-risk stock/flow models; coefficients are explicit mechanism assumptions.

No accident-count calibration is claimed for an incomplete investigation-report sample.
"""
import ast
import copy
import math
from .sd_factors import FACTORS
from .db import uid, now

PROFILE_VERSION = 'industry-feedback/3.0'
LIMITATION = '当前结果为情景推演：隐患压力是模拟状态，事故强度为相对量；缺少完整事故口径、连续暴露量和经过验证的发生率，暂不预测事故起数。'

def param(label,value,low,high,unit='',dimension=0,**extra):
    return dict(label=label,value=value,min=low,max=high,unit=unit,dimension=dimension,
                source='机制假设，尚未经历史数据或专家标定',**extra)

def default_model(industry):
    factors=FACTORS[industry]
    p={
        'production_pressure':param('生产压力',1,.1,3,'倍',scenario=True),
        'safety_effort':param('安全投入强度',1,0,3,'倍',scenario=True),
        'response_time':param('治理响应滞后',3,.25,24,'月',1,scenario=True),
        'prevention_rate':param('基准隐患消除系数',.18,0,1,'1/月',-1,scenario=True),
        'formation_rate':param('基准隐患形成速度',.08,.001,1,'归一化状态/月',-1),
        'hazard_response':param('隐患治理响应系数',.4,0,2),
        'feedback_gain':param('事故信息反馈强度',.6,0,3),
        'intensity_scale':param('相对强度换算系数',.25,.01,2,'1/月',-1),
        'intensity_reference':param('风险指数半饱和强度',.25,.01,2,'相对强度/月',-1),
        'exposure_scale':param('相对作业暴露',1,.1,3,'倍'),
        'exposure_elasticity':param('作业暴露压力弹性',.3,0,1),
        'coupling':param('专业因素联合作用系数',.15,0,1),
    }
    if industry=='金属非金属矿山':
        p['mine_scope']=param('矿山类型',0,0,3,scenario=True,choices={0:'按报告识别',1:'地下矿山',2:'露天矿山',3:'尾矿库'})
    if industry=='工贸':
        for key,label in [('dust','粉尘涉爆'),('ammonia','涉氨制冷'),('molten','高温熔融')]:
            p['process_'+key]=param(label,-1,-1,1,scenario=True,choices={-1:'按报告识别',0:'不适用',1:'适用'})
    variables=[]
    for f in factors:
        key=f['key']; label=f['label']
        p[key+'_reference']=param(label+'参考值',.5,0,1,calibrate=f'feedback:{key}:reference')
        p[key+'_enabled']=param(label+'适用开关',1,0,1,calibrate=f'feedback:{key}:enabled')
        if not f['protective']:
            p[key+'_weight']=param(label+'形成权重',f['weight'],0,1)
            p[key+'_elasticity']=param(label+'压力弹性',f['elasticity'],0,1)
            p[key+'_control']=param(label+'治理敏感度',f['control'],0,1)
            formula=f'{key}_enabled*{key}_reference*max(0,1+{key}_elasticity*(production_pressure-1))/(1+{key}_control*max(0,governance_level-1))'
        else:
            # A capability is protective, never added as a positive hazard weight.
            formula=f'{key}_enabled*min(1,{key}_reference*safety_effort)'
        variables.append(dict(name=key+'_factor',label=label,type='aux',role='factor',unit='相对量',dimension=0,formula=formula,measure=f['measure']))
    weighted='+'.join(f'{f["key"]}_enabled*{f["key"]}_weight' for f in factors if not f['protective'])
    initial='+'.join(f'{f["key"]}_enabled*{f["key"]}_weight*{f["key"]}_reference' for f in factors if not f['protective'])
    load='+'.join(f'{f["key"]}_weight*{f["key"]}_factor' for f in factors if not f['protective'])
    interactions={'煤矿':'gas_factor*mining_factor','金属非金属矿山':'drainage_factor*(stope_factor+slope_factor)',
        '石油天然气开采':'pressure_factor*pipeline_factor','化工':'process_factor*seal_factor',
        '烟花爆竹':'staffing_factor*charge_factor','工贸':'work_factor*(height_factor+space_factor)'}
    variables=[
        dict(name='hazard_pressure',label='隐患压力',type='stock',role='core',unit='归一化状态',dimension=0,
             initial=f'0.25+0.75*({initial})/max(0.001,{weighted})',rate='hazard_formation-hazard_removal',min=0,max=1e6),
        dict(name='cumulative_load',label='累计相对风险负荷',type='stock',role='core',unit='相对负荷',dimension=0,
             initial='0',rate='accident_intensity',min=0,max=1e8),
        dict(name='feedback_signal',label='滞后事故信息',type='stock',role='delay',unit='相对强度/月',dimension=-1,
             initial='0',rate='(accident_intensity-feedback_signal)/response_time',min=0,max=1e6),
        *variables,
        dict(name='governance_level',label='安全治理水平',type='aux',unit='倍',dimension=0,
             formula='safety_effort*(1+hazard_response*hazard_pressure/(1+hazard_pressure)+feedback_gain*feedback_signal/(intensity_reference+feedback_signal))'),
        dict(name='factor_load',label='专业因素综合作用',type='aux',unit='相对量',dimension=0,
             formula=f'({load})/max(0.001,{weighted})+coupling*({interactions[industry]})'),
        dict(name='relative_exposure',label='危险作业相对暴露',type='aux',unit='倍',dimension=0,
             formula='exposure_scale*production_pressure**exposure_elasticity'),
        dict(name='hazard_formation',label='隐患形成速度',type='aux',role='flow',unit='归一化状态/月',dimension=-1,
             formula='formation_rate*production_pressure*(1+factor_load)'),
        dict(name='hazard_removal',label='隐患消除速度',type='aux',role='flow',unit='归一化状态/月',dimension=-1,
             formula='prevention_rate*governance_level*hazard_pressure'),
        dict(name='accident_intensity',label='相对事故强度',type='aux',role='flow',unit='相对强度/月',dimension=-1,
             formula='intensity_scale*relative_exposure*hazard_pressure*(1+factor_load)'+('*(1-0.7*detection_factor)' if industry=='化工' else '')),
        dict(name='risk_index',label='综合风险指数',type='aux',unit='分',dimension=0,
             formula='100*accident_intensity/(intensity_reference+accident_intensity)')]
    return dict(id=uid(),name=industry+'隐患治理与反馈模型',industry=industry,version=1,format='risk-sd/1.0',
        profile_version=PROFILE_VERSION,model_family=PROFILE_VERSION,status='情景推演',created_at=now(),
        description='事故报告提供行业因素参考，隐患形成与治理闭环推动状态变化，事故信息经时间滞后影响治理。',
        parameters=p,variables=variables,feature_labels={f['key']:f['label'] for f in factors},
        quantity_mode='relative',count_calibration=None,
        assumptions={'time_unit':'月','integration_step':.05,'coefficient_source':'明确机制假设；未冒充专家评审或回归结果',
            'index_conversion':'100 × 相对事故强度 ÷（固定半饱和强度 + 相对事故强度）',
            'initial_pressure':'0.25 + 0.75 × 适用行业因素参考值加权均值；不是实测隐患数量',
            'delay':'一阶信息平滑；初始新增事故信息为0，三个场景一致',
            'limitation':LIMITATION})

def prepare(model,stats,overrides):
    model=copy.deepcopy(model); provenance=[]; p=model['parameters']
    for key,val in (overrides or {}).items():
        if key not in p: raise ValueError('未知模型参数：'+key)
        if p[key].get('calibrate'): raise ValueError('自动参考值请在调整模型中切换为手动设置：'+key)
        p[key]['value']=val
    evidence=copy.deepcopy(stats.get('sd_evidence',{}).get(model['industry']) or {
        'samples':0,'matched_samples':0,'channels':[],'cooccurrence':[],'contexts':{}})
    channels={c['key']:c for c in evidence['channels']}; contexts=evidence['contexts']; scope=int(p.get('mine_scope',{}).get('value',0))
    enabled={}; scopes={1:'underground',2:'openpit',3:'tailings'}
    for f in FACTORS[model['industry']]:
        key=f['key']; c=channels.get(key,{}); active=True; applicability='行业适用'
        reference_count=c.get('count',0);reference_samples=evidence['samples'];assumed=not evidence['matched_samples']
        if model['industry']=='金属非金属矿山':
            known={scopes[scope]} if scope in scopes else set(contexts)&set(scopes.values())
            active=bool(set(f['scopes'])&known) if known else True
            applicability=('用户指定矿山类型' if scope else '报告识别矿山类型') if known else '矿山类型未明确，按混合场景假设；建议选择矿山类型'
            if scope in scopes:
                subset=evidence.get('context_slices',{}).get('mine_'+scopes[scope],{})
                reference_count=subset.get('counts',{}).get(key,0);reference_samples=subset.get('samples',0);assumed=not subset.get('matched_samples')
        if model['industry']=='工贸' and key=='special':
            processes=[proc for proc in ['dust','ammonia','molten'] if p['process_'+proc]['value']==1 or (p['process_'+proc]['value']==-1 and contexts.get(proc,0)>0)]
            active=bool(processes); applicability='启用：'+('、'.join({'dust':'粉尘涉爆','ammonia':'涉氨制冷','molten':'高温熔融'}[x] for x in processes) or '无；未识别到实际工艺')
            mask=sum({'dust':1,'ammonia':2,'molten':4}[x] for x in processes)
            subset=evidence.get('context_slices',{}).get('process_'+str(mask),{})
            reference_count=subset.get('counts',{}).get(key,0);reference_samples=subset.get('samples',0);assumed=not subset.get('matched_samples')
        enabled[key]=active
        # A report with no mention cannot establish a functioning protective system.
        ref=.5 if f['protective'] or assumed else reference_count/reference_samples
        method='能力参考值为0.5的机制假设；事故报告缺陷线索不等于当前检测能力' if f['protective'] else ('适用报告样本中该因素出现比例，仅用于状态初始化' if not assumed else '适用范围内样本或线索不足，采用0.5机制参考值')
        for suffix,value,note in [('reference',ref,method),('enabled',float(active),applicability)]:
            name=key+'_'+suffix
            if p.get(name,{}).get('calibrate') or (suffix=='enabled' and not active):
                p[name]['value']=value
                provenance.append({'parameter':name,'value':value,'numerator':reference_count,'denominator':reference_samples,
                    'method':note,'source':'机制假设' if f['protective'] or assumed else '事故报告规则统计',
                    'status':'assumption' if f['protective'] or assumed else 'reference'})
        if not c:
            c={'key':key,'label':f['label'],'count':0,'share':0,'evidence':[],'measure':f['measure'],'protective':f['protective'],'scopes':f['scopes']}
            evidence['channels'].append(c)
        c.update(enabled=bool(p[key+'_enabled']['value']),applicability=applicability,reference=p[key+'_reference']['value'],reference_samples=reference_samples,reference_count=reference_count)
    for key,v in p.items():
        if not v.get('calibrate'):
            provenance.append({'parameter':key,'value':v['value'],'method':v.get('source','用户设置'),'status':'assumption'})
    evidence['note']='因素占比反映已收录事故；动态系数与治理滞后尚未验证。'
    return model,provenance,evidence

def validate_structure(model,expressions):
    """Check time dimensions, required outputs and protective capability semantics."""
    p=model['parameters']; variables={v['name']:v for v in model['variables']}
    required={'hazard_pressure','cumulative_load','feedback_signal','hazard_formation','hazard_removal','accident_intensity','risk_index'}
    if required-set(variables): raise ValueError('请保留隐患、累计负荷、反馈、主要流量与综合指数')
    if any(variables[k]['type']!='stock' for k in ['hazard_pressure','cumulative_load','feedback_signal']): raise ValueError('隐患、累计负荷和反馈需保持存量类型')
    if model.get('quantity_mode')!='relative': raise ValueError('当前模型尚无通过验证的事故发生率，只允许相对量输出')
    for key,param_value in p.items():
        if 'choices' in param_value and str(param_value['value']).removesuffix('.0') not in {str(k) for k in param_value['choices']}:
            raise ValueError('适用范围选择无效：'+key)
        cal=param_value.get('calibrate','')
        valid={f'feedback:{f["key"]}:{suffix}' for f in FACTORS[model['industry']] for suffix in ['reference','enabled']}
        if cal and cal not in valid: raise ValueError('参数的事故特征与所属行业不匹配：'+key)
    dims={k:v.get('dimension',0) for k,v in {**p,**variables}.items()}; dims['time']=1
    def dim(node):
        if isinstance(node,ast.Constant): return None if node.value==0 else 0
        if isinstance(node,ast.Name): return dims[node.id]
        if isinstance(node,ast.UnaryOp): return dim(node.operand)
        if isinstance(node,ast.BinOp):
            a,b=dim(node.left),dim(node.right)
            if isinstance(node.op,(ast.Add,ast.Sub)):
                if a is not None and b is not None and a!=b: raise ValueError('公式相加或相减的时间量纲不一致')
                return a if a is not None else b
            if isinstance(node.op,ast.Mult): return (a or 0)+(b or 0)
            if isinstance(node.op,ast.Div): return (a or 0)-(b or 0)
            if isinstance(node.op,ast.Pow):
                if b not in (0,None): raise ValueError('幂指数必须无量纲')
                if a and not isinstance(node.right,ast.Constant): raise ValueError('带时间量纲的幂指数需为常数')
                return a*node.right.value if a else 0
        if isinstance(node,ast.Call):
            values=[dim(x) for x in node.args]; nonzero={x for x in values if x is not None}; name=node.func.id
            if name in ['min','max']:
                if len(nonzero)>1: raise ValueError('最小值或最大值的时间量纲不一致')
                return next(iter(nonzero),None)
            if name=='abs': return values[0]
            if name=='sqrt': return (values[0] or 0)/2
            if any(v not in (0,None) for v in values): raise ValueError('指数、对数和三角函数输入必须无量纲')
            return 0
        raise ValueError('公式量纲无法识别')
    for key,expression in expressions.items():
        expected=dims[key]-(1 if variables[key]['type']=='stock' else 0)
        actual=dim(expression.tree)
        if actual is not None and actual!=expected: raise ValueError(variables[key]['label']+'的变化率或公式时间量纲不一致')
    for v in variables.values():
        if v['type']=='stock':
            actual=dim(ast.parse(str(v['initial']),mode='eval').body)
            if actual is not None and actual!=v.get('dimension',0): raise ValueError(v['label']+'的初始值时间量纲不一致')
    if variables['risk_index']['formula']!='100*accident_intensity/(intensity_reference+accident_intensity)':
        raise ValueError('综合风险指数保留固定换算规则，请调整驱动因素和强度公式')

def summarize_result(result,model,evidence):
    baseline=result['scenarios'][0]['points'][-1]['risk_index']
    for scenario in result['scenarios']:
        points=scenario['points']; peak=max(points,key=lambda x:x['risk_index'])
        scenario['summary']={'initial':points[0]['risk_index'],'final':points[-1]['risk_index'],
            'difference_from_baseline':round(points[-1]['risk_index']-baseline,6),
            'peak':peak['risk_index'],'peak_month':peak['month'],
            'final_hazard_pressure':points[-1]['hazard_pressure'],
            'final_accident_intensity':points[-1]['accident_intensity'],
            'cumulative_relative_load':points[-1]['cumulative_load'],
            'expected_accidents':None,'prediction_interval':None}
    result.update(profile_version=PROFILE_VERSION,quantity_mode='relative',sd_evidence=evidence,
        industry_evidence=None,warning=LIMITATION,
        qualification={'count_prediction':False,'reason':LIMITATION,'sample_count':evidence['samples'],
            'out_of_sample_validation':None,'parameter_source':'机制假设与报告因素统计；尚未验证发生率'},
        output_metrics={v['name']:{'label':v['label'],'unit':v.get('unit',''),'role':v.get('role','')} for v in model['variables']},
        index_conversion=model['assumptions']['index_conversion'],model_snapshot=model)
    return result
