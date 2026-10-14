"""Industry-specific, auditable report clues for the feedback SD models.

These dictionaries identify reported clues, not causal findings or incidence rates.
The v2 dictionaries remain in industry_risk.py for historical reproducibility.
"""
import re
from collections import Counter
from itertools import combinations

RULE_VERSION = 'industry-factors/3.0'

def factor(key, label, terms, measure, weight, elasticity=.2, control=.3, scopes=None, protective=False):
    return dict(key=key, label=label, terms=terms.split('|'), measure=measure,
                weight=weight, elasticity=elasticity, control=control,
                scopes=scopes or ['all'], protective=protective)

FACTORS = {
    '煤矿': [
        factor('gas', '瓦斯及通风风险', '瓦斯|煤与瓦斯突出|煤尘爆炸|通风异常|通风不足|局部通风机停运|停风', '核查通风系统、瓦斯抽采与监测联锁，异常时落实停产撤人和复查。', .30,.35,.6),
        factor('roof', '顶板支护风险', '顶板|冒顶|片帮|支护|冲击地压', '复核采掘扰动、支护设计和现场支护质量，及时处置顶板异常。', .25,.45,.4),
        factor('water', '水害风险', '透水|突水|水害|探放水|老空水|防治水', '复核水文地质资料、探放水与排水能力，落实水害预警。', .25,.15,.5),
        factor('mining', '违规采掘风险', '违规采掘|违法开采|超层越界|超能力生产|违章爆破|无证开采|违规开采|掘进', '核查采掘边界、作业规程、生产组织及安全检查闭环。', .20,.6,.35)],
    '金属非金属矿山': [
        factor('stope', '采空区与顶板风险', '采空区|顶板|冒顶|片帮|支护|地压', '核查采空区处置、地压监测与巷道支护。', .25,.4,.4,['underground']),
        factor('slope', '边坡稳定风险', '边坡|滑坡|排土场|坍塌|坝体|溃坝', '核查边坡或坝体稳定、位移监测及排水条件。', .25,.3,.35,['openpit','tailings']),
        factor('drainage', '排水及水害风险', '透水|突水|水害|排水|洪水|尾矿库|浸润线', '检查排水系统、水位监测与防汛应急能力。', .20,.15,.5,['underground','openpit','tailings']),
        factor('blast', '爆破作业风险', '爆破|盲炮|炸药|飞石', '核查爆破设计、警戒、盲炮处理和爆破器材管理。', .15,.4,.4,['underground','openpit']),
        factor('transport', '运输提升风险', '提升|罐笼|矿车|运输|跑车|车辆伤害|坠罐', '核查提升保护、运输线路、车辆维护与人车分流。', .15,.5,.4,['underground','openpit'])],
    '石油天然气开采': [
        factor('well', '井控风险', '井喷|井控|溢流|防喷器|压井', '检查井控屏障、防喷器和异常溢流处置能力。', .30,.4,.6),
        factor('pipeline', '设备及管线泄漏风险', '泄漏|泄露|腐蚀|密封失效|管线破裂|穿孔', '开展腐蚀检测、密封和管线完整性检查，闭环检维修。', .20,.25,.5),
        factor('h2s', '硫化氢暴露风险', '硫化氢|含硫气体|酸性气体', '核查硫化氢检测、呼吸防护、撤离路线及应急演练。', .20,.2,.7),
        factor('pressure', '高压作业风险', '高压|超压|压裂|试压|带压', '核查压力监测、泄压保护和高压作业隔离。', .15,.5,.4),
        factor('maintenance', '检维修及动火风险', '检维修|检修|动火|焊接|切割|清罐', '落实隔离置换、气体检测、动火许可与作业监护。', .15,.3,.5)],
    '化工': [
        factor('process', '危险工艺控制风险', '反应釜|失控反应|超温|超压|联锁|工艺控制|聚合|硝化|氯化', '复核工艺控制、报警联锁和异常停车处置。', .30,.5,.6),
        factor('seal', '腐蚀与密封失效风险', '腐蚀|密封失效|穿孔|法兰泄漏|设备泄漏|管道泄漏|管线泄漏|垫片', '开展设备完整性、腐蚀监测和泄漏点闭环检修。', .25,.25,.5),
        factor('storage', '危险物质储存风险', '储罐|储存|仓储|危化品仓库|混存|超量储存|罐区', '核查介质相容性、储量、围堰与储存条件。', .25,.4,.3),
        factor('work', '特殊作业风险', '动火|受限空间|有限空间|检维修|检修|盲板|吊装|临时用电', '落实特殊作业许可、能量隔离、检测和监护。', .20,.3,.6),
        factor('detection', '泄漏检测与处置能力', '未设置报警|未安装报警|报警失效|检测失效|未检测|未进行气体检测|未及时处置|应急处置不当', '测试泄漏检测报警、自动切断与应急响应有效性。', 0,0,0,protective=True)],
    '烟花爆竹': [
        factor('staffing', '超员作业风险', '超员|超定员|人员超限|超核定人数', '按工房定员组织生产，核查人员进出和隔离要求。', .20,.5,.4),
        factor('charge', '超药量作业风险', '超药量|超量装药|药量超限|超量生产|超定量', '执行工房限药量与工序限量，核查现场药物周转。', .25,.6,.5),
        factor('mix', '混装药作业风险', '混药|装药|配药|混装|药剂混合|压药|筑药', '核查配混装药工艺、设备隔离与操作约束。', .20,.4,.5),
        factor('ignition', '静电及火源控制风险', '静电|明火|火源|火花|摩擦|撞击|吸烟', '核查防静电接地、工具与火源控制。', .20,.25,.7),
        factor('inventory', '危险品库存管理风险', '库房|仓库|库存|堆放|混存|储存|殉爆', '控制库存及堆放，检查安全距离和分库存放。', .15,.3,.3)],
    '工贸': [
        factor('height', '高处作业风险', '高处|坠落|高坠|安全带|临边|屋顶|脚手架', '核查高处作业方案、防坠设施和安全带挂设。', .25,.3,.5),
        factor('machine', '机械设备防护风险', '机械伤害|机械防护|防护罩|卷入|夹伤|挤压|设备意外启动|违规操作机器', '完善防护联锁、停机上锁和检修能量隔离。', .25,.45,.55),
        factor('space', '有限空间作业风险', '有限空间|受限空间|清池|清罐|中毒窒息|污水池|缺氧', '落实有限空间辨识、通风检测、监护与应急救援。', .20,.2,.7),
        factor('work', '危险作业管理风险', '动火|起重|吊装|临时用电|违规作业|违章作业|无证作业', '核查危险作业许可、承包协调、岗位资格与监护。', .15,.4,.5),
        factor('special', '特殊生产工艺风险', '粉尘爆炸|粉尘涉爆|可燃粉尘|涉氨|氨泄漏|液氨|氨制冷|熔融|钢水|铁水|铝液|金属熔体', '按实际工艺核查粉尘防爆、涉氨检测隔离或熔融金属防水防泄漏。', .15,.4,.6)]}

FIELDS = ['直接原因','间接原因','事故类型','事故名称','作业场所','作业环节','作业活动',
          '人员原因','设施设备原因','工艺技术原因','环境原因','管理原因']
CONTEXTS = {'underground':['地下矿','井下','巷道','采空区','井筒'],
            'openpit':['露天','边坡','排土场'], 'tailings':['尾矿库','尾矿坝','尾矿堆积坝'],
            'dust':['粉尘爆炸','粉尘涉爆','可燃粉尘'],
            'ammonia':['涉氨','液氨','氨泄漏','氨制冷'],
            'molten':['熔融','钢水','铁水','铝液','金属熔体']}

def present(text, term):
    for match in re.finditer(re.escape(term), text):
        prefix=re.split(r'[，。；、：!?！？]',text[max(0,match.start()-18):match.start()])[-1]
        if re.search(r'(未发生|没有发生|未涉及|未发现|不存在|未出现|排除|不涉及|不适用|无)(?:[^，。；]{0,5})$',prefix):
            continue
        return match
    return None

def extract(row):
    industry=row.get('_industry') or row.get('行业')
    texts={f:str(row.get(f) or '') for f in FIELDS}
    contexts={k for k,terms in CONTEXTS.items() if any(present(t,term) for t in texts.values() for term in terms)}
    hits={}
    for f in FACTORS.get(industry,[]):
        # Known mine subtypes exclude unrelated factors. Unknown scope stays explicit.
        mine=contexts & {'underground','openpit','tailings'}
        if industry=='金属非金属矿山' and mine and not mine.intersection(f['scopes']): continue
        evidence=[]
        for field,text in texts.items():
            for term in f['terms']:
                match=present(text,term)
                if match:
                    evidence.append({'record_id':row.get('_id',''),'number':row.get('编号',''),
                        'field':field,'term':term,'excerpt':text[max(0,match.start()-50):match.end()+90],
                        'reason':f'“{term}”命中{f["label"]}规则','rule_version':RULE_VERSION})
                    break
            if len(evidence)==3: break
        if evidence: hits[f['key']]=evidence
    return {'hits':hits,'contexts':sorted(contexts)}

def merge(a,b):
    for key,evidence in b['hits'].items():
        a['hits'].setdefault(key,[])
        a['hits'][key].extend(e for e in evidence if e not in a['hits'][key])
    a['contexts']=sorted(set(a['contexts'])|set(b['contexts']))

def summarize(rows):
    rows=list(rows); result={}
    for industry,factors in FACTORS.items():
        selected=[r for r in rows if r.get('_industry')==industry]
        if not selected: continue
        counts=Counter(); pairs=Counter(); contexts=Counter(); evidence={f['key']:[] for f in factors}
        matched=0
        for row in selected:
            features=row.get('_sd_features') or extract(row)
            row['_sd_features']=features
            keys=features['hits']; matched+=bool(keys); counts.update(keys.keys());contexts.update(features['contexts'])
            pairs.update(combinations(sorted(keys),2))
            for key,items in keys.items():
                # UI uses a short sample; full per-record matches have a dedicated endpoint.
                if len(evidence[key])<12: evidence[key].extend(items[:12-len(evidence[key])])
        n=len(selected)
        slices={}
        # Subtype and process slices prevent a selected scope from borrowing unrelated clues.
        selectors=({'mine_'+k:{k} for k in ['underground','openpit','tailings']} if industry=='金属非金属矿山' else
                   {'process_'+str(mask):{name for bit,name in [(1,'dust'),(2,'ammonia'),(4,'molten')] if mask&bit} for mask in range(1,8)} if industry=='工贸' else {})
        for name,allowed in selectors.items():
            subset=[r for r in selected if set(r.get('_sd_features',{}).get('contexts',[]))&allowed]
            values=Counter(k for row in subset for k in row['_sd_features']['hits'])
            slices[name]={'samples':len(subset),'matched_samples':sum(bool(r['_sd_features']['hits']) for r in subset),'counts':dict(values)}
        result[industry]={'samples':n,'matched_samples':matched,'contexts':dict(contexts),
            'context_slices':slices,
            'rule_version':RULE_VERSION,'channels':[{
                **{k:f[k] for k in ['key','label','measure','protective','scopes']},
                'count':counts[f['key']],'share':round(counts[f['key']]/n*100,4),
                'evidence':evidence[f['key']]} for f in factors],
            'cooccurrence':[{'source':a,'target':b,'count':n_pair,'support':round(n_pair/n*100,2)} for (a,b),n_pair in pairs.most_common()],
            'note':'比例以已收录去重事故为分母；未命中不表示现场无此风险，共现不证明因果。'}
    return result
