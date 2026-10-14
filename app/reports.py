from pathlib import Path
import html, re, json, subprocess, os, shutil
from bs4 import BeautifulSoup
from .config import ROOT, RUNTIME
from .db import db, uid, now, dumps
from .analytics import statistics, foundation, indicators, forecast_counts
from .sd import simulate, preferred_model
from .sd_feedback import PROFILE_VERSION as FEEDBACK_VERSION, LIMITATION
from .llm import report_prose, LLMError
from .jobs import update
from .report_charts import decorate_report
from datetime import datetime, timezone, timedelta

def readable(v):
    if v is None: return '数据不足'
    if isinstance(v,(dict,list)): return dumps(v)
    return str(v)

def business_text(value):
    """Keep the published report focused on safety findings rather than implementation details."""
    text=str(value or '')
    replacements=(
        ('全量采集口径','完整事故统计范围'),('同口径','同一统计标准'),('统计口径','统计说明'),('口径','统计标准'),
        ('已导入','已收录'),('导入数量','收录数量'),('导入文件标识','资料来源标识'),('新增事故、企业、气象和经济记录导入后','新增事故、企业、气象和经济资料后'),
        ('原字段体系','原始信息体系'),('字段为空','相关信息缺失'),('字段修订','信息修订'),('字段格式','信息格式'),('来源字段','信息来源'),('真实字段','原始资料信息'),('字段填写情况','资料完整情况'),('字段完整率','资料完整率'),
        ('系统保留','分析保留'),('系统同时统计','同时统计'),('系统按','按照'),('当前系统先','当前研判先'),('系统保持不可计算状态','暂不形成相关数值判断'),
        ('保存在计算证据文件中','列入相应分析结果'),('保留运行记录','保留更新记录'),('规则字典','专业分类标准'),
        ('运行时从参数和存量状态计算辅助变量，再计算存量变化率并完成积分','依据当前风险状态、治理能力和情景条件研判后续变化'),
        ('系统动力学数值积分','系统动力学情景推演'),('规则文本草稿','完整业务报告'),('LLM','智能研判服务'),('服务器','报告编制环节'),('机制假设','模型设定'),('1/月','月⁻¹'),('字段','信息项')
    )
    for old,new in replacements:text=text.replace(old,new)
    return text
def fallback_prose(stats,base,metrics,simulation,forecast):
    n=stats['count']; scope=stats['scope']; industry=scope.get('industry') or '六行业'; region=scope.get('region') or '全国'; start=scope.get('start') or '数据起始时间'; end=scope.get('end') or '数据截止时间'
    factors='、'.join(f'{k}因素标记涉及{v}起' for k,v in stats['factor_counts'].items()) or '没有可用原因标记'
    def m(k): return readable(metrics[k]['value'])+metrics[k].get('unit','')
    parts=[
    f'本报告面向{industry}，以{region}为查询范围，分析时段为{start}至{end}，围绕已导入的{n}起事故调查报告样本开展现状统计、风险因素识别、因素共现分析及情景仿真。研判对象和时间条件在查询阶段统一使用，报告各部分采用同一批筛选结果。报告用于梳理已有事故证据和提出后续核查方向。事故调查报告的导入数量受采集渠道、公开时间和资料完整性影响，尚不能直接代表区域全部生产安全事故；对总体发生率、企业暴露风险和未来事故数量的解释，应结合完整采集口径另行验证。',
    f'数据来源为用户提供的事故调查报告结构化表，系统保留事故报告、企业、气候环境和经济社会四个数据集的原字段体系。当前筛选后有效事故记录{n}条，有原因描述的记录{stats["cause_samples"]}条，日期可用于分组的记录{stats["dated_count"]}条。基础数据可查询记录数分别为企业{base["_counts"]["enterprises"]}条、气候环境{base["_counts"]["climate"]}条和经济社会{base["_counts"]["economy"]}条。缺失字段按未知处理，未明确的伤亡和经济损失不加入有效求和。每条记录保留导入文件标识、原报告编号和来源链接，方便人工复核和后续订正。',
    '分析方法包括按行业、地区和时间筛选的描述统计，依据原原因分类标记形成因素共现网络，以及使用明确公式的系统动力学数值积分。统计结果保留有效样本数与单位；关联网络输出共同出现频次、支持度、条件置信度和提升度。提升度衡量相对于边缘频率的共现强度，不能确认风险因素的因果方向。事故计数预测采用带时间趋势及季节项的惩罚泊松回归，只有在完整月度数据和全量采集口径得到确认后才启动，并通过训练时间早于测试时间的滚动回测检验预测误差。',
    f'企业基础条件部分查询与事故范围相匹配的企业记录，按企业标识和场所取最新有效记录，避免重复使用不同统计期的同一场所。企业数量为{m("企业数量")}，从业人员数量为{m("从业人员数量")}，重点企业数量为{m("重点企业数量")}。当企业台账缺失时，不以事故单位去重数量替代辖区企业总数，也不据此推算企业事故率。后续应补充统一社会信用代码、场所编号、生产状态、从业人数和重大危险源信息，并核对记录统计期与事故分析时段的一致性。对于同一企业多个生产场所，应保留场所层级，防止人员和投入被重复累计。',
    '经济社会数据用于解释行业生产经营活动背景，查询时需要关注统计期、行政层级、地区代码、数据截止日期和来源。当前字段标准中的规上工业增加值增速和固定资产投资增速属于变化率，不能当成工业增加值或固定资产投资额。不同地区、不同层级的经济总量也不能直接相加。若原始记录不足，相关定量指标应列为数据不足，保留补充数据清单。后续可在同口径、同层级、同统计期下，将生产强度变化作为预测模型的协变量，并用独立回测比较是否提升拟合和预测表现。',
    f'气候环境基础条件按有效观测记录核查。当前平均气温指标为{m("平均气温")}，高温指标为{m("高温天数")}，极端天气记录数为{m("极端天气次数")}。气象观测的空间站点与时间粒度需要同时明确；累计降水量须采用同站点非重叠时间窗，不能将滚动降水值相加。对缺少气候环境资料的范围，报告不推断气温、降雨或灾害强度，也不将缺测解释为正常天气。后续应优先取得来源明确的气象站或网格数据，关联到企业场所及事故日期，并区分观测、预测和预警记录。',
    '基础条件综合分析首先检验企业、经济社会与气候数据能否在地区和时间维度上对齐，再分析可能存在的生产暴露及外部环境变化。当前可使用的信息范围以指标表中有效样本数为准。对于缺少分母的事故发生率、缺少同口径对比期的增长率以及不同单位的产量累计，系统保持不可计算状态。补充数据后，应重新执行相同查询和统计，而不是沿用旧报告中的未知值。对新增数据来源、字段修订和统计范围变化，应保留运行记录，并检查其是否改变现状判断和后续模型参数。',
    f'事故总体情况基于{n}条筛选后的调查报告记录。系统按事故等级原字段分别统计一般、较大、重大和特别重大事故，事故总数为{m("事故总数")}，较大及以上事故占比为{m("较大及以上事故占比")}。该比例的分母为等级字段已知的事故，不将未明确等级的样本分配到一般事故。死亡事故的判定依据死亡人数大于零，死亡事故占比为{m("死亡事故占比")}。相关数值反映已导入样本的构成和后果特征，不能在采集不完整时据此判定整个地区总体事故形势优于或劣于其他地区。',
    '可比期分析需要两个时间窗具有一致的行业边界、行政层级、资料采集渠道和数据截止规则。目前未提供可以确认可比的对照资料，因此报告不输出未经验证的同比或环比变化率。后续建立可比期后，应分别列示本期和对比期的事故数量、死亡事故数量以及等级分布，并检查补报、延迟发布和事故发生日期归属。若某一时期只有公开调查报告而另一时期包含全部事故统计，两个序列不能直接用于趋势比较。对样本采集差异，应在结论中单独说明其对变化方向判断的影响。',
    f'事故发生特征从月份、季度、省份、地市、事故类型、作业场所、作业环节和作业活动分别分组。月度分布使用有效发生时间，不以报告发布日期代替事故发生日期；本次有效日期样本为{stats["dated_count"]}条。图表用于发现样本集中出现的类别和时段，完整分组结果保存在计算证据文件中。集中出现可能同时受企业暴露规模和资料采集范围影响，需进一步核对分母后再形成区域风险排序。对缺少行政区划或作业描述的记录，系统保留缺失计数，避免在筛选中静默消失。',
    f'事故后果统计中，已知死亡人数累计为{m("死亡人数")}，重伤人数为{m("重伤人数")}，轻伤人数为{m("轻伤人数")}，失踪人数为{m("失踪人数")}，直接经济损失为{m("直接经济损失")}。受伤总数与轻伤、重伤是不同层级的字段，不能在总伤亡中重复累计。经济损失按万元换算并排除无法确定单位或数值的记录。平均每起死亡人数为{m("平均每起死亡人数")}，其分母仅为死亡字段有效样本。对部分后果字段缺失的事故，应在补充调查资料后复算，并检查同一报告不同阶段人员伤亡口径是否发生调整。',
    '现状形势研判应将事故样本总量、严重后果构成、地区分布和作业环节特征结合起来审视。调查报告通常包含较详细原因证据，适合解释已经发生事故的失效环节，但存在样本选择和公开时滞。报告因此将当前统计发现作为监管核查的起点，建议关注记录中高后果事故对应的场所和作业类型，并补充现存隐患状态。当前未确认全量事故统计和企业暴露分母，报告不据此作出整个区域事故频率变化的确定判断。后续验证应结合全量台账与同口径对比期数据，保持事实统计和推断结论之间的边界。',
    f'风险因素识别依据事故结构化表中的人员、设施设备、工艺技术、环境和管理原因字段。当前原因标记统计为：{factors}。分类标记表示调查报告资料中出现对应因素，其频次不等于现场隐患发生概率。字段为空只表示未形成有效标记，不能确认该因素不存在。系统同时统计直接原因和间接原因描述的覆盖情况，保留报告源与事故编号以支持抽样复核。对原文表述复杂或同义词较多的原因，可在专家审核后的规则字典下进一步细化，但新增分类不得覆盖原有原因字段。',
    '原因标记的质量需要结合调查报告原文核查。人员因素应关注操作、培训、资格和现场行为；设备设施因素应关注设施完整性、失效和维护情况；工艺技术因素应关注技术控制及工艺约束；环境因素关注作业环境与外部条件；管理因素关注制度执行、承包管理和责任落实。上述类别用于组织审核和提出问题清单，不表明本次样本中每一个具体问题都已经证实。开展细项归并时，应记录规则版本、命中原文和人工审核结果，并检查跨行业语义差异，避免将通用词汇误判为明确事故原因。',
    f'因素关联网络以同一事故记录中的共同原因标记为边，共形成{len(stats["network"]["links"])}条因素共现关系。每条边的频次、支持度、置信度和提升度均由筛选样本实际计算，图中节点大小或连接度体现该分类在当前共现网络中的统计地位。共同出现只反映资料中的联合标记，不是具有时间方向的因果链。样本规模较小或某些分类标记较少时，提升度容易受单条记录影响，应结合边频次和原文证据一并评价，并用新增样本检查关系是否稳定。',
    '突出问题筛选以高频原因类别、强共现关系和人员伤亡后果为证据线索。当前系统先形成对应原因分类的治理候选任务，再由业务人员核对原文、现场现状和适用行业。对每一项候选问题，应明确涉及事故编号、对应原因字段和需要核查的现场环节。网络中连接度较高的分类并不自动成为所有企业的首要问题；企业监管任务还需要结合重大危险源、生产状态和未整改隐患资料。未提供这些现场资料时，报告保留核查建议，避免将历史调查结论直接扩展为当前全部企业的确定风险状态。',
    '事故发生机理分析需要区分已经认定的直接原因、促成失效的间接条件以及统计共现关系。当前结构化数据支持查询事故经过、直接原因、间接原因和整改建议，但不会自动确认新的机理链条。建议对高后果典型事故开展原文复核，按发生顺序记录危险状态、触发事件、保护措施失效和后果扩展过程。将机理映射到系统动力学变量之前，需要明确变量单位、状态含义、反馈方向和作用时滞。未经专家确认的边或速率参数应持续保留假设标识，并在模型版本说明中记录依据。',
    '风险演化仿真使用所选行业模型及其已保存版本。内置行业模型按事故类型、事故名称和直接原因提取对应行业风险线索，采用样本比例初始化指数、按频次计算权重，并结合管理风险推演。相邻两个半年的样本满足条件时估计线索比例变化；不足时不估计趋势。风险调整时间和治理速率保留为可编辑假设。场景包含保持当前参数的基准场景、上调生产压力的场景和下调安全投入强度的场景。用户可在运行前修改参数，并在结果证据中查看实际生效值。模型使用固定时间步长的四阶龙格库塔方法积分，不依赖大模型生成数值；模型缺少事故原因样本或公式校验失败时，仿真停止并显示原因。',
    '模型条件说明是解释仿真结果的必要部分。初始模型中的指数反映事故资料原因标记的相对构成，不是现场风险概率；响应时间及治理速率尚未获得连续企业台账和专家样本标定。不同场景比较仅说明这些明确假设下模型的变化方向和幅度。已有行业机理模型接入后，需要进一步核查状态变量定义、参数量纲、历史拟合和情景约束，再决定是否用于业务预测。模型每次保存形成新版本，运行结果引用具体版本和实际参数，历史报告保留计算快照，以支持复现和审查。',
    f'综合风险趋势由实际仿真曲线计算。当前初始综合风险指数为{m("当前综合风险指数")}，预测末期指数为{m("预测末期风险指数")}，预测期峰值为{m("预测期峰值风险")}，峰值出现时间为{m("峰值出现时间")}。这些值属于所选初始模型的情景计算，尚不能解释为未来事故数量或概率。基准场景与压力、投入变化场景采用相同模型结构，便于观察参数扰动对曲线的影响。对边界饱和、指数接近零或参数较敏感的运行，业务审核人员应查看各风险存量变化并开展参数敏感性核查。',
    '风险演化路径分析应沿模型中已经定义的存量、流量和辅助变量逐项追溯。系统保留公式及依赖图，运行时从参数和存量状态计算辅助变量，再计算存量变化率并完成积分。对于某一风险类别的上升，应先检查驱动参数、初值、反馈项和治理项的作用，而不直接把曲线变化解释为现实机理证据。各行业使用独立的风险线索字典及变量，管理反馈、综合权重和动态系数仍属待标定假设。后续需要补充适用场所、关键工艺及控制措施的真实关系。任何结构修改均应重新校验公式、代数循环、变量依赖和数值稳定性，并比较修改前后的结果。',
    '预测结果综合分析分别审视事故计数预测和系统动力学情景仿真。计数预测需要至少覆盖完整月度周期的真实序列及采集完整性确认；本次计数预测状态为'+('已运行，并保留滚动回测误差和区间覆盖率。' if forecast['status']=='available' else '数据不足，原因是'+forecast['reason']+'。')+'标称预测区间的置信水平不等于预测准确率，不能据此宣称验收要求已经达成。当前尚无约定统计口径、专家参考样本和独立验收集，报告只提供实际计算结果及其条件。后续应先固定预测目标、样本范围和评价方法，再开展独立验证。',
    '重点风险防控建议对应已经识别的原因类别形成可核查任务。对人员原因，应核对岗位资格、实际培训和作业行为；对设备设施原因，应核对设备状态、保护装置和检维修记录；对工艺技术原因，应复核关键控制条件和异常处置要求；对管理原因，应核查责任落实、承包协调和隐患闭环；对环境原因，应核查现场防护及预警联动。具体检查项目应由业务人员结合行业和原文证据确定。每项任务需要明确责任主体、整改期限、复核方式和证据文件，避免只以检查次数代替治理效果。',
    '重点领域防控以已知事故地区、作业场所、作业环节和事故类型分布为排查线索。对伤亡后果较重的典型作业，应核查相应企业当前是否仍有同类暴露和控制失效。差异化检查频次及资源配置需要结合企业生产状态、重大危险源和未整改隐患台账，当前缺少这些资料时不能自动下达现场处置结论。建议先建立企业与事故的关联标识，再补充现场检查结果，使历史教训可以转化为具体监管任务。对于不同地区资料采集深度不同的情况，应同时说明样本覆盖差异，防止把公开报告数量直接当成监管绩效排名。',
    '持续监测与动态研判应建立数据更新、质量复核、模型重算和报告审核的闭环。新增事故、企业、气象和经济记录导入后，先检查字段格式、重复摘要和日期范围，再按原查询条件复算。模型参数调整或结构变更后，保留新版本并比较基准和情景曲线。隐患整改率、培训完成率等治理指标需要同时提供完成数量及应完成数量；当前标准未完整提供这些分母，系统保持数据不足。补充业务台账后，还应检查完成口径与统计周期一致，使用独立审核证据评价治理效果。',
    '优先治理方向应从调查报告已记录的高后果事故和原因证据出发。当前可用样本支持原因分类频次、共现网络与实际情景计算，适合形成核查清单及模型接入准备。对每项重点问题，应回看原报告、确认适用行业及当前企业暴露状态，并避免把统计相关关系当成事故机理定论。模型初值来自资料标记比例，动态参数仍为假设，现阶段应将计算结果用于比较和讨论，待机理模型、完整基础台账与独立验证资料齐备后，再形成可用于业务决策的预测结论。',
    '资源安排需要将人员、设备、工艺、环境和管理核查任务落实到对应企业和作业场所。由于本次基础台账、企业规模分母和专家审核样本尚不完整，报告不自动给出预算额度、检查频次或治理绩效达标结论。建议业务部门先补齐企业标识及当前风险资料，再按后果严重性、隐患状态和现场可控性排列任务。每项安排保留任务来源、责任部门、实施记录和复核证据，使后续专家审核能够清楚区分历史事故发现、当前现场问题和模型假设。',
    '跟踪评价应以真实数据量、字段可统计覆盖率、时间外回测误差和专家审核一致性分别记录。当前资料仅构成样本运行基础，数据条目规模、原始文件存储量和专家一致性须通过实际台账及样本核验。报告正文长度由系统检查，但正文达到字数要求不代表预测效果或业务验收已经通过。后续应在约定目标及口径下开展独立验证，保存预测值、实际值、专家标注和计算方法，给出置信区间及有效样本数。对于新增证据导致的结论变化，应按版本更新并保留可追溯说明。'
    ]
    return {f'paragraph_{i+1:03d}':p for i,p in enumerate(parts)}

def bar_svg(items):
    items=items[:16]; width=800; height=max(260,42+len(items)*25); maximum=max([x['value'] for x in items]+[1]); body=[]
    for i,item in enumerate(items):
        y=28+i*25; w=item['value']/maximum*490
        body.append(f'<text x="4" y="{y+16}" font-size="18">{html.escape(str(item["name"])[:12])}</text><rect x="230" y="{y}" width="{w:.2f}" height="17" fill="#1E3264"/><text x="{240+w:.2f}" y="{y+16}" font-size="18">{item["value"]}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'+''.join(body)+'</svg>'
def network_svg(network):
    import math
    nodes=network['nodes']; points={n['id']:(400+220*math.cos(i/max(len(nodes),1)*2*math.pi),170+100*math.sin(i/max(len(nodes),1)*2*math.pi)) for i,n in enumerate(nodes)}; body=[]
    for e in network['links']:
        x,y=points[e['source']]; a,b=points[e['target']]; body.append(f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#AAB5CF" stroke-width="{1+min(e["count"]/20,4)}"/>')
    for n in nodes:
        x,y=points[n['id']]; body.append(f'<circle cx="{x}" cy="{y}" r="38" fill="#ECF0F8" stroke="#1E3264"/><text x="{x}" y="{y+6}" font-size="18" text-anchor="middle">{html.escape(n["id"])}</text><text x="{x}" y="{y+56}" font-size="18" text-anchor="middle">{n["count"]}起</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 340">'+''.join(body)+'</svg>'
def line_svg(simulation):
    if not simulation: return '<p>数据不足，仿真未运行</p>'
    colors=['#1E3264','#FC7819','#23B283']; allp=[p for s in simulation['scenarios'] for p in s['points']]; maximum=max(1,max(p['risk_index'] for p in allp)*1.15); horizon=max(p['month'] for p in allp); body=[]
    for i,s in enumerate(simulation['scenarios']):
        pts=' '.join(f'{60+p["month"]/horizon*650:.2f},{210-p["risk_index"]/maximum*160:.2f}' for p in s['points']); body.append(f'<polyline points="{pts}" fill="none" stroke="{colors[i]}" stroke-width="2.5"/><text x="{70+i*230}" y="28" fill="{colors[i]}" font-size="18">{s["name"]}</text>')
    body.append('<line x1="60" x2="710" y1="210" y2="210" stroke="#555"/><text x="748" y="240" font-size="16">月</text>')
    for month in [0,horizon/2,horizon]:
        body.append(f'<text x="{60+month/horizon*650}" y="240" font-size="16" text-anchor="middle">{month:g}</text>')
    for i in range(5):
        y=210-i*40; body.append(f'<text x="5" y="{y+6}" font-size="18">{maximum*i/4:.1f}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 260">'+''.join(body)+'</svg>'

def render_html(params,stats,base,metrics,simulation,forecast,prose,report_id):
    soup=BeautifulSoup((ROOT/'reference/report-template.html').read_text(encoding='utf-8'),'html.parser')
    china_date=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    region=params.get('region') or '全国'
    industry=params.get('industry') or '六行业'
    heading=soup.select_one('.cover-section h1')
    heading.clear();heading.append(region+industry);heading.append(soup.new_tag('br'));heading.append('安全生产事故风险研判及预测分析报告')
    scope_line=soup.new_tag('p',attrs={'class':'cover-sub'})
    scope_line.string=f'分析期间：{params["start"]} 至 {params["end"]}'
    heading.insert_after(scope_line)
    for row,value in zip(soup.select('.cover-meta tr'),['风险研判与预测智能体',china_date]):
        row.select('td')[1].string=value
    soup.title.string=region+industry+'安全生产事故风险研判及预测分析报告'
    for e in soup.select('script,.config-panel'): e.decompose()
    for e in soup.select('[data-field]'):
        key=e['data-field']
        if key in prose: e.clear(); e.append(business_text(prose[key]))
        elif '【' in e.get_text(): e.clear(); e.append('数据不足')
    for anchor,key in [('section-1-2','paragraph_002'),('section-1-3','paragraph_003'),('section-6-3','paragraph_025')]:
        heading=soup.find(id=anchor)
        paragraph=heading.find_next_sibling('p') if heading else None
        if paragraph:
            paragraph['data-field']=key;paragraph.clear();paragraph.append(business_text(prose[key]))
    for e in soup.select('[data-page-for]'): e.string=''
    for i,value in enumerate([stats['count'],stats['known'].get('死亡事故',0),sum(x['value'] for x in stats['distributions']['level'] if x['name']=='一般'),sum(x['value'] for x in stats['distributions']['level'] if x['name']=='较大'),sum(x['value'] for x in stats['distributions']['level'] if '重大' in x['name'])],1):
        e=soup.select_one(f'[data-field="accident_summary_{i}_1"]')
        if e: e.string=str(value)
        for j in [2,3]:
            e=soup.select_one(f'[data-field="accident_summary_{i}_{j}"]')
            if e: e.string='无可比期'
    selected=params['indicators']; table=soup.new_tag('table'); caption=soup.new_tag('p'); caption.string='表：本次选定定量指标与有效样本'
    header=soup.new_tag('tr')
    for label in ['指标','计算结果','有效样本','统计说明']:
        th=soup.new_tag('th'); th.string=label; header.append(th)
    thead=soup.new_tag('thead');thead.append(header);table.append(thead)
    tbody=soup.new_tag('tbody');table.append(tbody)
    for label in selected:
        m=metrics[label]; tr=soup.new_tag('tr'); value=readable(m['value'])
        if isinstance(m['value'],list): value='；'.join((str(x.get('name') or x.get('id') or x.get('source',''))+':'+str(x.get('value',x.get('count','')))) for x in m['value']) or '无有效分组'
        for text in [label,value+m['unit'],str(m['sample_count']),business_text(m['method'] or m['reason'])]:
            td=soup.new_tag('td'); td.string=text; tr.append(td)
        tbody.append(tr)
    anchor=soup.select_one('#section-7'); anchor.insert_before(table); table.insert_before(caption)
    decorate_report(soup,stats,simulation,params.get("_report_title") or soup.title.string,params.get("_generated_at") or now())
    result=str(soup)
    china_date=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    replacements={'【行业待填】':params.get('industry') or '六行业','【地区待填】':params.get('region') or '全国','【起始时间待填】':params['start'],'【结束时间待填】':params['end'],'【编制日期待填】':china_date,'【编制时间待填】':china_date,'【编制单位待填】':'安全生产风险研判工作组','【报告编号待填】':report_id[:12]}
    for a,b in replacements.items(): result=result.replace(a,html.escape(str(b)))
    result=re.sub(r'【[^】]+】','数据不足',result)
    css='''@page{size:A4;margin:16mm 18mm 18mm 20mm;}@media print{.report{width:auto;margin:0;padding:0;border:none}.cover-section,.toc-section{height:263mm;min-height:263mm;max-height:263mm;padding-left:0;padding-right:0}.report-body{padding:0}h2,h3{break-after:avoid}p{orphans:3;widows:3}table{width:calc(100% - 2px);font-size:10pt;table-layout:fixed}.figure{width:calc(100% - 2px)}th,td{word-break:break-word}thead{display:table-header-group}}'''
    result=result.replace('</head>','<style>'+css+'</style></head>')
    return result

def add_quantitative_text(prose,params,stats,metrics,simulation,forecast):
    """Generate numeric prose deterministically; the LLM never chooses numeric facts."""
    prose=dict(prose)
    scope=f'{params.get("region") or "全国"}{params["industry"]}，{params["start"]}至{params["end"]}'
    source=f'统计范围为{scope}。本次纳入{stats["record_count"]}条报告记录，经同一事故归并后形成{stats["count"]}个事故样本，重复报告{stats["duplicate_reports"]}条。基础资料完整率为{stats["coverage"]}%，该比例反映已收录资料的完整程度。'
    if stats.get('undated_excluded'):
        source+=f'同地区同行业另有{stats["undated_excluded"]}条记录因发生日期缺失未纳入本次时段统计。'
    prose['paragraph_002']=source+prose['paragraph_002']
    groups={
        'paragraph_004':['企业数量','从业人员数量','重点企业数量','行业产量/产值','企业安全投入总额'],
        'paragraph_005':['工业增加值','固定资产投资'],
        'paragraph_006':['平均气温','降水量','高温天数','极端天气次数'],
        'paragraph_008':['事故总数','事故等级分布'],
        'paragraph_010':['月度分布','季度分布','省级分布','地市分布','事故类型分布','作业场所分布','作业环节分布','作业活动分布','事故月份集中度'],
        'paragraph_011':['死亡人数','重伤人数','轻伤人数','失踪人数','伤亡总人数','直接经济损失','平均每起死亡人数','平均每起受伤人数','平均每起直接经济损失','较大及以上事故占比','死亡事故占比'],
        'paragraph_013':['人员因素频次','设备设施因素频次','工艺技术因素频次','环境因素频次','管理因素频次','典型致因组合数量','风险因素样本覆盖率'],
        'paragraph_015':['因素关联强度','关键因素重要度','直接原因频次','间接原因频次'],
        'paragraph_020':['当前综合风险指数','预测末期风险指数','预测期峰值风险','预测期最低风险','峰值出现时间','综合风险变化率','高风险持续时间','主要上升风险类别','预测事故起数'],
        'paragraph_022':['生产压力场景变化率','安全投入场景变化率'],
        'paragraph_023':['重点风险治理任务数','重点区域覆盖数','建议证据覆盖率','隐患整改率','重大隐患闭环率','检查覆盖率','培训完成率','设备检维修完成率','特殊作业合规率','应急演练完成率','监测异常处置率']}
    chosen=set(params['indicators'])
    for key,names in groups.items():
        sentences=[]
        for name in names:
            if name not in chosen: continue
            m=metrics[name]
            if m['value'] is None:
                sentences.append(name+'暂不可计算：'+m['reason']+'。');continue
            if isinstance(m['value'],list):
                # Detailed distributions remain in the chosen-indicator table/evidence.
                continue
            sentences.append(f'{name}为{readable(m["value"])}{m["unit"]}，有效样本{m["sample_count"]}条。{m["method"]}。')
        prose[key]=''.join(sentences)+prose[key]
    if simulation:
        model_note=f'仿真模型为{simulation["model_name"]}，本次定量研判采用{params["scenario"]}。{simulation["method"]}。'
        for scenario in simulation['scenarios']:
            p=scenario['parameters']
            parts=[f'{label}={p[k]}' for k,label in [('production_pressure','生产压力'),('safety_effort','安全投入强度')] if k in p]
            if parts:model_note+=scenario['name']+'：'+'，'.join(parts)+'。'
        evidence=simulation.get('industry_evidence')
        if evidence:
            model_note+=f'行业风险线索在{evidence["matched_samples"]}起事故中识别到，分母为{evidence["samples"]}起去重事故。'
            model_note+='；'.join(f'{c["label"]}涉及{c["count"]}起、占样本{c["share"]:.2f}%' for c in evidence['channels'])+'。同一事故可涉及多个类别。'
            model_note+=evidence['trend_reason'] or '时间趋势采用相邻两个半年风险线索比例的月均变化，不能当作区域全量事故发生率。'
        prose['paragraph_018']=model_note+prose['paragraph_018']
    if forecast['status']!='available':prose['paragraph_022']='事故起数预测暂不可计算：'+forecast['reason']+prose['paragraph_022']
    if simulation and simulation.get('profile_version')==FEEDBACK_VERSION:
        prose=feedback_narrative(prose,simulation)
    return prose

def feedback_narrative(prose,simulation):
    """Authoritative computed SD paragraphs, shared by rule and LLM report modes."""
    evidence=simulation['sd_evidence']; channels=evidence['channels']
    active=[c for c in channels if c['enabled']]
    labels={c['key']:c['label'] for c in channels}
    findings='；'.join(f'{c["label"]}线索涉及{c["count"]}起，占收录样本{c["share"]:.2f}%' for c in active)
    pairs='；'.join(f'{labels.get(p["source"],p["source"])}与{labels.get(p["target"],p["target"])}共同出现{p["count"]}起' for p in evidence['cooccurrence'][:5]) or '尚无可统计的专业因素共现组合'
    sources='；'.join(f'{c["label"]}对应报告编号{c["evidence"][0]["number"]}，来源字段为{c["evidence"][0]["field"]}' for c in active if c['evidence'])
    prose['paragraph_013']=f'本行业共有{evidence["samples"]}起去重事故样本，其中{evidence["matched_samples"]}起识别到行业风险线索。{findings}。上述结果属于历史报告统计，同一事故可涉及多个因素，占比之和可以超过百分之百。这些比例不代表区域事故发生概率，也不表示当前企业现场风险水平；未命中规则不等于排除该类风险。'
    prose['paragraph_014']=f'识别采用可追溯规则，覆盖事故类型、作业场所、作业环节、作业活动、直接原因和间接原因等真实字段。{sources}。匹配保留原编号、命中词、字段和原文片段，供人工复核。整改建议不会作为已经发生的事故原因证据；局部否定语句尽量排除，但复杂叙述仍需业务人员审阅。'
    prose['paragraph_015']=f'专业因素关联统计结果为：{pairs}。共同出现表示同一事故中存在多类风险因素，需要在现场核查中关注因素叠加和相互影响，不直接作为因果顺序判断。治理优先级应综合事故后果、现实暴露和适用工艺确定，并由专业人员结合现场条件复核。'
    excluded='、'.join(c['label'] for c in channels if not c['enabled'])
    prose['paragraph_016']=('本次不适用因素为'+excluded+'，已从形成速度和强度计算中排除。' if excluded else '本次采用模型中启用的专业因素。')+'矿山按地下、露天或尾矿库类型控制因素适用范围，工贸特殊工艺按粉尘涉爆、涉氨制冷与高温熔融的实际线索或用户指定条件启用。化工泄漏检测与处置作为保护能力，增强该能力会降低相对事故强度；缺陷线索本身不能反推出当前企业检测能力。'
    prose['paragraph_018']='风险演化研判围绕隐患压力、治理水平、事故信息反馈、累计相对风险负荷和综合风险变化展开。生产压力及行业专业因素会推动隐患形成，安全投入和治理能力用于抑制隐患积累；事故信息形成反馈后，将影响后续治理响应。三类情景采用一致的初始条件，以便比较生产压力和安全投入变化对风险趋势的影响。'
    prose['paragraph_019']='生产压力升高会提高形成速度及危险作业相对暴露，安全投入减少会降低治理水平并削弱专业防控作用。隐患压力上升又会增加治理需求；事故强度经一阶时间滞后进入治理反馈，形成后续风险抑制。滞后时间、形成和治理系数、专业因素权重及弹性均为明确机制假设，未经过连续台账标定，不作为已经验证的因果效应或事故发生率。'
    summaries=[]
    for s in simulation['scenarios']:
        v=s['summary'];summaries.append(f'{s["name"]}：初期综合指数{v["initial"]:.2f}，末期{v["final"]:.2f}，较基准末期差异{v["difference_from_baseline"]:+.2f}分，峰值{v["peak"]:.2f}出现在第{v["peak_month"]:g}月；末期隐患压力{v["final_hazard_pressure"]:.4f}，相对事故强度{v["final_accident_intensity"]:.4f}/月')
    prose['paragraph_020']='；'.join(summaries)+'。峰值与时点来自本次实际离散计算点。风险指数采用固定换算：'+simulation['index_conversion']+'。坐标自适应只改变图形显示，不修改计算值。'
    prose['paragraph_021']='风险曲线反映不同情景下综合风险的相对变化，可用于比较治理投入和生产压力变化带来的趋势差异。该指数用于风险排序和情景比较，不等同于事故发生概率或预计事故起数。研判时应结合企业生产状态、隐患排查结果和现场检查证据综合判断。'
    prose['paragraph_022']='当前资料能够支持事故特征分析和风险情景比较，但连续生产暴露、隐患治理及完整事故序列仍不充分，因此本报告不直接给出未来事故起数或事故概率。风险趋势结论用于识别重点方向，并应结合后续新增资料和专家复核持续更新。'
    measures='；'.join(c['label']+'：'+c['measure'] for c in sorted(active,key=lambda c:c['count'],reverse=True))
    prose['paragraph_023']='防控建议按本行业实际启用因素形成：'+measures+'。建议依据事故线索和模型治理环节提出，执行前应核对企业当前生产条件，明确责任人、期限和复核证据。'
    prose['paragraph_026']='综合事故后果、专业风险因素及其共同出现特征，应优先治理高后果事故涉及的关键作业环节，重点核查隐患形成较快、治理响应偏慢以及多类风险因素叠加的场所。对历史事故中反复出现的管理、设备和作业行为问题，应逐项对照当前现场确认是否仍然存在，并据此确定治理次序。'
    prose['paragraph_027']='资源配置应向高风险作业、重点企业和关键时段倾斜，统筹安排专业检查力量、设备检维修、人员培训和应急准备。对风险上升较快或治理能力不足的对象，应明确责任主体、完成时限和复核要求；对风险保持平稳的对象，也应维持必要的日常巡查和动态监测。'
    prose['paragraph_028']='后续评价应持续跟踪隐患整改、重大隐患闭环、检查覆盖、培训完成、设备检维修、特殊作业合规、应急演练和监测异常处置等指标。结合新增事故资料、现场检查结果和专家意见定期更新风险研判，对风险方向发生明显变化的领域及时调整治理重点和资源安排。'
    return prose

def create_report(job_id,params,actor):
    filters={k:params.get(k,'') for k in ['industry','region','start','end']}; update(job_id,progress=10,stage='查询与统计')
    stats=statistics(filters)
    if not stats['count']: raise ValueError('所选范围没有事故数据，请调整行业、地区或时间范围')
    base=foundation(filters); update(job_id,progress=25,stage='风险因素与关联分析')
    simulation=None; sim_error=''
    model=db.get_doc('model',params['model_id']) if params.get('model_id') else preferred_model(params['industry'])
    if model and model['industry']!=params['industry']: raise ValueError('所选SD模型与行业不一致')
    if model:
        try: simulation=simulate(model,stats,params['months'],params.get('parameters'),params.get('threshold',60))
        except ValueError as e: sim_error=str(e)
    update(job_id,progress=40,stage='预测与情景仿真')
    forecast=({'status':'unavailable','reason':LIMITATION,'points':[],'validation':None} if model and model.get('profile_version')==FEEDBACK_VERSION else forecast_counts(stats,params['months'],params.get('coverage_confirmed',False)))
    metrics=indicators(stats,base,simulation,forecast,params['scenario'])
    prose=fallback_prose(stats,base,metrics,simulation,forecast); llm={'status':'completed','provider':'本地研判引擎','note':'报告正文已完整生成'}
    if params.get('use_llm',True):
        update(job_id,progress=55,stage='DeepSeek组织报告文字')
        try:
            prose,llm=report_prose(stats,metrics,simulation,forecast,model=params.get('llm_model',''))
            llm['grounding']='LLM仅生成定性正文；定量段落由服务器按指标名、实际结果、单位、有效样本和口径直接填入'
        except LLMError as e: llm={'status':'completed','provider':'本地研判引擎','refinement_status':'unavailable'}
    prose=add_quantitative_text(prose,params,stats,metrics,simulation,forecast)
    count=sum(len(re.findall(r'[\u4e00-\u9fff]',p)) for p in prose.values())
    if count<3000: raise ValueError('正文未达到3000汉字，请检查生成器')
    id=uid(); title=f'{params["region"] or "全国"}{params["industry"]}安全生产风险研判及预测分析报告'
    params=dict(params,_report_title=title,_generated_at=now())
    update(job_id,progress=85,stage='填充A4模板与计算证据')
    path=RUNTIME/'reports'/f'{id}.html'; result_html=render_html(params,stats,base,metrics,simulation,forecast,prose,id)
    rendered=BeautifulSoup(result_html,'html.parser')
    count=sum(len(re.findall(r'[\u4e00-\u9fff]',e.get_text())) for e in rendered.select('.report-body p[data-field]'))
    if count<3000:
        prose=add_quantitative_text(fallback_prose(stats,base,metrics,simulation,forecast),params,stats,metrics,simulation,forecast)
        llm={'status':'completed','provider':'本地研判引擎','refinement_status':'replaced'}
        result_html=render_html(params,stats,base,metrics,simulation,forecast,prose,id)
        count=sum(len(re.findall(r'[\u4e00-\u9fff]',e.get_text())) for e in BeautifulSoup(result_html,'html.parser').select('.report-body p[data-field]'))
    if count<3000: raise ValueError('模板正文长度校验失败')
    path.write_text(result_html,encoding='utf-8')
    evidence={'parameters':params,'statistics':stats,'foundation':base,'indicators':metrics,'simulation':simulation,'simulation_error':sim_error,'forecast':forecast,'llm':llm,'body_hanzi':count,'model_snapshot':model}
    (RUNTIME/'reports'/f'{id}.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    doc={'id':id,'title':title,'actor':actor,'created_at':params['_generated_at'],'status':'待业务审核','body_hanzi':count,'count':stats['count'],'llm':llm,'parameters':params,'simulation_error':sim_error,'forecast_status':forecast['status']}
    db.put_doc('report',id,doc); db.audit(actor,'generate_report',id,{'body_hanzi':count,'llm_status':llm['status']})
    return doc

def render_pdf(id):
    doc=db.get_doc('report',id)
    if not doc: raise ValueError('报告不存在')
    path=RUNTIME/'reports'/f'{id}.html'; pdf=path.with_suffix('.pdf')
    node=os.getenv('NODE_BINARY') or shutil.which('node')
    if not node: raise ValueError('PDF运行环境缺少Node.js，请按部署说明配置')
    completed=subprocess.run([node,str(ROOT/'scripts/pdf.cjs'),str(path),str(pdf)],capture_output=True,text=True,encoding='utf-8',timeout=90,env=os.environ.copy())
    if completed.returncode!=0: raise ValueError('PDF渲染失败：请检查Playwright和浏览器安装。'+completed.stderr[-300:])
    # Read rendered PDF headings to fill true page numbers (cover/TOC excluded).
    from pypdf import PdfReader
    pages=[re.sub(r'\s+','',p.extract_text() or '') for p in PdfReader(pdf).pages]
    soup=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser'); changed=False
    for e in soup.select('[data-page-for]'):
        target=soup.find(id=e['data-page-for'])
        if target:
            heading=re.sub(r'\s+','',target.get_text())
            page=next((i+1 for i,t in enumerate(pages) if i>=2 and heading in t),None)
            if page and e.get_text()!=str(page): e.string=str(page); changed=True
    if changed:
        path.write_text(str(soup),encoding='utf-8')
        result=subprocess.run([node,str(ROOT/'scripts/pdf.cjs'),str(path),str(pdf)],capture_output=True,text=True,encoding='utf-8',timeout=90,env=os.environ.copy())
        if result.returncode: raise ValueError('PDF目录排版失败')
    return pdf

