# -*- coding: utf-8 -*-
"""
合规性自检报告模块
检查论文结构完整性、格式合规性
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def check_compliance(paragraphs, rules=None, paper_type='research'):
    """
    对论文段落进行合规性检查。

    参数:
        paragraphs: 段落列表，每项含 {index, text, label, ...}
        rules: 格式规则字典
        paper_type: "research" | "review"

    返回:
        {"passed": [...], "warnings": [...], "errors": [...]}
    """
    results = {'passed': [], 'warnings': [], 'errors': []}

    if not paragraphs:
        results['errors'].append({
            'id': 'check_000', 'name': '段落数据检查',
            'type': 'error',
            'message': '未检测到任何段落数据',
            'detail': '请确认论文文档包含内容',
        })
        return results

    labels = [p.get('label', '') for p in paragraphs]
    texts = [p.get('text', '') for p in paragraphs]

    # ========== 通用检查 ==========

    # 1. 论文标题
    _add_check(results, 'check_001', '论文标题',
               '论文大标题' in labels,
               '未检测到论文大标题', '文档开头应包含论文主标题',
               error_weight=1.0)

    # 2. 摘要
    has_abstract = any('摘要' in lbl for lbl in labels)
    _add_check(results, 'check_002', '摘要',
               has_abstract,
               '未检测到摘要', '论文应包含摘要部分',
               error_weight=0.9)

    # 3. 关键词
    kw_indices = [i for i, lbl in enumerate(labels) if '关键词' in lbl]
    if kw_indices:
        kw_text = texts[kw_indices[0]]
        kw_count = len([w for w in re.split(r'[;；，,\s]', kw_text) if w.strip() and len(w.strip()) > 1])
        kw_ok = 3 <= kw_count <= 8
        _add_check(results, 'check_003', '关键词数量和范围',
                   kw_ok,
                   f'关键词数量为 {kw_count}（建议3-8个）',
                   f'当前提取到 {kw_count} 个关键词，建议控制在3-8个',
                   kw_ok, 0.7)
    else:
        _add_check(results, 'check_003', '关键词',
                   False, '未检测到关键词',
                   '论文应包含关键词，建议3-8个', error_weight=0.9)

    # 4. 参考文献
    has_ref_heading = '参考文献标题' in labels
    ref_count = len([l for l in labels if l == '参考文献条目'])
    _add_check(results, 'check_004', '参考文献',
               has_ref_heading and ref_count > 0,
               f'参考文献问题: 标题={has_ref_heading}, 条目数={ref_count}',
               '论文应包含参考文献章节和至少一条参考文献',
               error_weight=0.8)

    # 5. 图表标题
    caption_count = len([l for l in labels if l == '图表标题'])
    _add_check(results, 'check_005', '图表标题',
               True,  # 无图表也是允许的
               f'检测到 {caption_count} 个图表标题',
               '请确保每个图表标题对应一个实际图表', warning=True)

    # 6. 页码（预留）
    results['warnings'].append({
        'id': 'check_006', 'name': '页码连续性',
        'type': 'warning',
        'message': '页码检查暂未实现',
        'detail': '此功能将在后续版本中提供',
    })

    # ========== 研究性论文检查 ==========

    if paper_type == 'research':
        # 7. 方法章节
        has_method = False
        method_idx = None
        for i, (lbl, txt) in enumerate(zip(labels, texts)):
            if lbl == '一级标题' and any(kw in txt for kw in ['方法', '材料', '实验', 'Method']):
                has_method = True
                method_idx = i
                break
        _add_check(results, 'check_007', '方法/材料章节',
                   has_method,
                   '未检测到方法/材料章节',
                   '研究性论文应包含"材料与方法"章节，描述实验设计、样本、仪器等',
                   error_weight=0.9, position=method_idx)

        # 8. 结果章节
        has_result = False
        result_idx = None
        for i, (lbl, txt) in enumerate(zip(labels, texts)):
            if lbl == '一级标题' and '结果' in txt:
                has_result = True
                result_idx = i
                break
        _add_check(results, 'check_008', '结果章节',
                   has_result,
                   '未检测到结果章节',
                   '研究性论文应包含"结果"章节，展示实验数据和发现',
                   error_weight=0.8, position=result_idx)

        # 9. 讨论/结论
        has_discussion = False
        disc_idx = None
        for i, (lbl, txt) in enumerate(zip(labels, texts)):
            if lbl == '一级标题' and any(kw in txt for kw in ['讨论', '结论', 'Discussion', 'Conclusion']):
                has_discussion = True
                disc_idx = i
                break
        _add_check(results, 'check_009', '讨论/结论章节',
                   has_discussion,
                   '未检测到讨论或结论章节',
                   '建议包含"讨论"或"结论"章节，分析和总结研究发现',
                   error_weight=0.7, position=disc_idx)

        # 10. 公式编号（简化）
        formula_count = 0
        for txt in texts:
            formula_count += len(re.findall(r'\((\d+)\)', txt))
        _add_check(results, 'check_010', '公式编号',
                   True,
                   f'检测到约 {formula_count} 个公式引用',
                   '建议使用连续编号如 (1)(2)(3)', warning=True)

        # 11. 符号说明
        has_symbols = False
        for lbl, txt in zip(labels, texts):
            if '符号' in txt or '缩写' in txt or 'notation' in txt.lower():
                has_symbols = True
                break
        _add_check(results, 'check_011', '符号/缩写说明',
                   has_symbols,
                   '未检测到符号说明或缩写表',
                   '建议在文末添加符号说明或缩写对照表',
                   warning=True)

    # ========== 综述性论文检查 ==========

    elif paper_type == 'review':
        # 12. 文献数量
        min_refs = (rules or {}).get('min_references', 50) if rules else 50
        ref_ok = ref_count >= min_refs if ref_count > 0 else False
        _add_check(results, 'check_012', '参考文献数量',
                   ref_ok,
                   f'参考文献 {ref_count} 篇（建议≥{min_refs}篇）',
                   f'当前 {ref_count} 篇，建议至少 {min_refs} 篇',
                   error_weight=0.8)

        # 13. 近5年文献占比
        current_year = datetime.now().year
        recent_count = 0
        for txt in texts:
            years = re.findall(r'(19|20)\d{2}', txt)
            for y in years:
                if current_year - int(y) <= 5:
                    recent_count += 1
        total_ref_years = sum(1 for txt in texts if re.findall(r'(19|20)\d{2}', txt))
        recent_ratio = recent_count / total_ref_years if total_ref_years > 0 else 0
        ratio_ok = recent_ratio >= 0.6
        _add_check(results, 'check_013', '近5年文献占比',
                   ratio_ok,
                   f'近5年文献占比 {recent_ratio:.0%}（建议≥60%）',
                   f'当前 {recent_ratio:.0%}，建议至少 60%',
                   error_weight=0.7)

        # 14. 外文文献占比
        foreign_count = 0
        for txt in texts:
            # 简单检测：参考文献中包含英文名称或期刊名缩写
            if re.search(r'[A-Z][a-z]+ et al\.', txt) or re.search(r'[A-Z][a-z]+\. \d{4}', txt):
                foreign_count += 1
        foreign_ratio = foreign_count / ref_count if ref_count > 0 else 0
        _add_check(results, 'check_014', '外文文献占比',
                   True,
                   f'外文文献占比 {foreign_ratio:.0%}',
                   '建议包含一定比例的外文文献',
                   warning=True)

        # 15. 文献筛选流程 / PRISMA
        has_prisma = False
        for txt in texts:
            if any(kw in txt for kw in ['PRISMA', '检索策略', '纳入标准', '排除标准', '数据库检索']):
                has_prisma = True
                break
        _add_check(results, 'check_015', '文献筛选流程',
                   has_prisma,
                   '未检测到PRISMA流程图或检索策略说明',
                   '综述性论文建议包含文献筛选流程图和检索策略说明',
                   error_weight=0.8)

    return results


def _add_check(results, check_id, name, condition, fail_msg, detail,
               error_weight=0.5, position=None, warning=False):
    """添加一个检查项到结果中"""
    if condition:
        results['passed'].append({
            'id': check_id, 'name': name, 'type': 'passed',
            'message': fail_msg if not condition else f'✓ {name}检查通过',
            'detail': detail,
            'position': position,
        })
    elif warning:
        results['warnings'].append({
            'id': check_id, 'name': name, 'type': 'warning',
            'message': fail_msg,
            'detail': detail,
            'position': position,
        })
    else:
        results['errors'].append({
            'id': check_id, 'name': name, 'type': 'error',
            'message': fail_msg,
            'detail': detail,
            'position': position,
        })
