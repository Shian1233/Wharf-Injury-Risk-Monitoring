"""Auditable industry features from reports; never a probability of a future accident."""
from collections import Counter
from datetime import date
import re

# These dictionaries classify report clues, not legal findings or validated causal models.
# Only accident type, title and direct-cause statements are used, never prevention advice.
PROFILES = {
    '煤矿': [
        ('gas', '瓦斯与煤尘', '瓦斯|煤与瓦斯突出|煤尘爆炸'),
        ('roof', '顶板与地压', '冒顶|顶板|冲击地压|坍塌'),
        ('water', '水害', '透水|突水|涌水|淹井'),
        ('transport', '机电与运输', '机械伤害|触电|车辆伤害|运输|跑车|绞车|皮带|提升机')],
    '金属非金属矿山': [
        ('slope', '边坡与冒顶', '边坡|冒顶|坍塌|垮塌|滑坡'),
        ('stope', '采空区与地压', '采空区|地压|地表塌陷|岩爆'),
        ('blast', '爆破与运输', '爆破|火药爆炸|车辆伤害|机械伤害|运输|提升|触电'),
        ('water', '水害与尾矿', '透水|突水|涌水|尾矿|溃坝|淹溺')],
    '石油天然气开采': [
        ('well', '井控失稳', '井喷|溢流|井涌|井控|喷出'),
        ('leak', '泄漏与火爆', '泄漏|泄露|火灾|爆炸|燃烧'),
        ('toxic', '中毒与窒息', '中毒|窒息|硫化氢|缺氧'),
        ('operation', '井场作业', '机械伤害|高处坠落|起重伤害|车辆伤害|触电|钻具|修井|管柱')],
    '化工': [
        ('reaction', '反应与工艺失控', '反应失控|失控反应|超温|超压|分解爆炸|反应釜|聚合|热失控'),
        ('leak', '泄漏与火爆', '泄漏|泄露|火灾|爆炸|闪爆|燃烧'),
        ('toxic', '中毒与窒息', '中毒|窒息|硫化氢|缺氧|有毒气体'),
        ('operation', '特殊与检维修作业', '动火|检维修|检修|受限空间|高处坠落|车辆伤害|起重|触电')],
    '烟花爆竹': [
        ('mix', '药物混配', '混药|混配|配药|药物混合|搅拌|受潮|化学反应'),
        ('press', '装药与成型', '装药|压药|筑药|切引|插引|造粒|摩擦|静电'),
        ('storage', '储存与运输', '仓库|储存|储运|运输|搬运|装卸|堆放'),
        ('spread', '燃爆与殉爆', '爆炸|火灾|殉爆|燃烧|引燃')],
    '工贸': [
        ('mechanical', '机械与起重', '机械伤害|起重伤害|车辆伤害|卷入|挤压|吊装'),
        ('height', '高处与物体打击', '高处坠落|物体打击|坍塌|坠落|坠物'),
        ('electric', '电气与触电', '触电|漏电|电击|电弧'),
        ('space', '有限空间与窒息', '中毒|窒息|有限空间|缺氧|淹溺'),
        ('thermal', '粉尘与高温', '粉尘爆炸|火灾|爆炸|灼烫|高温|熔融|铁水|铝液')]
}
PROFILE_VERSION = 'industry-report/2.0'
RULES = {industry: [(key, label, re.compile(pattern)) for key, label, pattern in rows]
         for industry, rows in PROFILES.items()}


def extract_features(row):
    """Retain one bounded, explainable excerpt per channel per report."""
    rules = RULES.get(row.get('_industry') or row.get('行业'), [])
    matches = {}
    for key, label, pattern in rules:
        for field in ('事故类型', '事故名称', '直接原因'):
            text = str(row.get(field) or '')
            for match in pattern.finditer(text):
                # Conservative local negation: avoid '未发生爆炸', '排除瓦斯'.
                prefix = text[max(0, match.start()-10):match.start()]
                if re.search(r'(?:未发生|没有发生|未涉及|排除|不存在|无|未)(?:明显|发生|发现|出现|涉及)?[^，。；、]{0,3}$', prefix):
                    continue
                matches[key] = {'field': field, 'term': match.group(),
                    'excerpt': text[max(0,match.start()-24):match.end()+40],
                    'record_id': row.get('_id'), 'number': row.get('编号')}
                break
            if key in matches:
                break
    return matches


def summarize_features(rows, scope):
    """Denominators are distinct incidents within each industry, never report rows."""
    groups = {}
    for row in rows:
        industry = row.get('_industry')
        if industry not in PROFILES:
            continue
        group = groups.setdefault(industry, {'samples': 0, 'matched_samples': 0,
            'counts': Counter(), 'monthly': {}, 'evidence': {}})
        group['samples'] += 1
        found = row.get('_risk_features', {})
        group['matched_samples'] += bool(found)
        for key, evidence in found.items():
            group['counts'][key] += 1
            examples = group['evidence'].setdefault(key, [])
            if len(examples) < 3:
                examples.append(evidence)
        month = (row.get('_date') or '')[:7]
        if month:
            period = group['monthly'].setdefault(month, {'samples': 0, 'counts': Counter()})
            period['samples'] += 1
            period['counts'].update(found.keys())
    for industry, g in groups.items():
        anchor = scope.get('end') or max(g['monthly'], default='')
        end_index = int(anchor[:4])*12+int(anchor[5:7])-1 if anchor else None
        windows = [{'samples': 0, 'counts': Counter(), 'months': 0} for _ in range(2)]
        if end_index is not None:
            for month, values in g['monthly'].items():
                age = end_index-(int(month[:4])*12+int(month[5:7])-1)
                if 0 <= age < 12:
                    window = windows[0 if age < 6 else 1]
                    window['samples'] += values['samples']
                    window['counts'].update(values['counts'])
                    window['months'] += 1
        sufficient = all(w['samples'] >= 5 and w['months'] >= 3 for w in windows)
        g['trend_status'] = 'available' if sufficient else 'insufficient'
        g['trend_reason'] = '' if sufficient else '相邻两个半年均需至少5起事故、覆盖至少3个月；当前不足，未推算时间趋势。'
        g['trend_windows'] = [{'samples': w['samples'], 'months_with_reports': w['months']} for w in windows]
        g['trend_anchor'] = anchor[:7]
        smooth_total = sum(g['counts'].get(key, 0)+1 for key, _, _ in PROFILES[industry])
        g['channels'] = []
        for key, label, pattern in PROFILES[industry]:
            count = g['counts'].get(key, 0)
            trend = ((100*windows[0]['counts'][key]/windows[0]['samples'] -
                      100*windows[1]['counts'][key]/windows[1]['samples'])/6) if sufficient else None
            g['channels'].append({'key': key, 'label': label, 'count': count,
                'share': round(100*count/g['samples'], 6), 'weight': (count+1)/smooth_total,
                'weight_numerator': count+1, 'weight_denominator': smooth_total,
                'trend': trend, 'evidence': g['evidence'].get(key, [])})
        g['counts'] = dict(g['counts'])
        # All intermediate fields are small counts, not full report text.
        for period in g['monthly'].values():
            period['counts'] = dict(period['counts'])
    return groups


def calibration_value(kind, stats, industry):
    _, key, quantity = kind.split(':')
    profile = stats.get('industry_evidence', {}).get(industry)
    if not profile or not profile['matched_samples']:
        raise ValueError('所选范围缺少可识别的行业事故特征，请检查事故类型与原因记录')
    channel = next((c for c in profile['channels'] if c['key'] == key), None)
    if not channel:
        raise ValueError('该标定特征不属于当前行业')
    result = {'field': channel['label'], 'denominator': profile['samples'],
              'numerator': channel['count'], 'status': 'available'}
    if quantity == 'initial':
        result.update(value=channel['share'], method='去重事故中该行业风险线索的匹配比例；未匹配不等于排除风险')
    elif quantity == 'weight':
        result.update(value=channel['weight'], numerator=channel['weight_numerator'],
            denominator=channel['weight_denominator'], method='匹配频次加1平滑后归一化；同一起事故可涉及多个风险')
    elif quantity == 'trend':
        result.update(value=channel['trend'] if channel['trend'] is not None else 0,
            status=profile['trend_status'], method='相邻两个半年线索比例之差除以6（月）；不是区域事故发生率',
            reason=profile['trend_reason'])
    else:
        raise ValueError('不支持的行业特征标定方式')
    return result
