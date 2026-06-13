# -*- coding: utf-8 -*-
"""
可配置的模板规则库和论文类型预判系统
"""

import re
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# 学校名称 ↔ 内部键名 映射
SCHOOL_NAME_TO_KEY = {
    '国标默认': 'default',
    '北京大学': 'pku',
    '清华大学': 'thu',
    '遵义医科大学': 'zunyi',
}
SCHOOL_KEY_TO_NAME = {v: k for k, v in SCHOOL_NAME_TO_KEY.items()}


def resolve_school(school_input):
    """将学校名称或键名统一解析为内部键名"""
    if not school_input:
        return 'default'
    # 如果已经是键名
    if school_input in SCHOOL_RULES:
        return school_input
    # 如果是中文名称
    if school_input in SCHOOL_NAME_TO_KEY:
        return SCHOOL_NAME_TO_KEY[school_input]
    # 尝试模糊匹配
    for name, key in SCHOOL_NAME_TO_KEY.items():
        if school_input in name or name in school_input:
            return key
    return 'default'

# ================================================================
#  1. 内置规则数据库
#  ⚠️ 核心原则：所有规则基于可查证的官方规范。
#  未确认的字段设为 None，自动继承国标默认值。
# ================================================================

# ---------- a) 国标默认 (来源: GB/T 7713.1-2006 学位论文编写规则) ----------
GB_BASIC = {
    'school': '国标默认',
    'source': 'GB/T 7713.1-2006 学位论文编写规则',
    'paper_title': {
        'chinese_font': {'name': '黑体', 'size': '二号', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '二号', 'bold': True},
        'paragraph': {'alignment': '居中', 'space_before': '1行', 'space_after': '1行'},
    },
    'author_info': {
        'chinese_font': {'name': '楷体', 'size': '四号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '四号', 'bold': False},
        'paragraph': {'alignment': '居中'},
    },
    'abstract_heading': {
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '两端对齐'},
    },
    'abstract_body': {
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': False},
        'paragraph': {'alignment': '两端对齐', 'first_line_indent': '2字符'},
    },
    'keywords': {
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '两端对齐'},
    },
    'heading1': {
        'chinese_font': {'name': '黑体', 'size': '小三', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小三', 'bold': True},
        'paragraph': {'alignment': '居中', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    'heading2': {
        'chinese_font': {'name': '黑体', 'size': '四号', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '四号', 'bold': True},
        'paragraph': {'alignment': '左对齐', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    'heading3': {
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '左对齐', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    'body': {
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': False},
        'paragraph': {'alignment': '两端对齐', 'first_line_indent': '2字符', 'line_spacing': '1.5倍'},
    },
    'caption': {
        'chinese_font': {'name': '黑体', 'size': '五号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '五号', 'bold': False},
        'paragraph': {'alignment': '居中', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    'reference_heading': {
        'chinese_font': {'name': '黑体', 'size': '小三', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小三', 'bold': True},
        'paragraph': {'alignment': '居中'},
    },
    'reference_entry': {
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '五号', 'bold': False},
        'paragraph': {'alignment': '两端对齐', 'hanging_indent': '2字符'},
    },
    'header': {
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '五号', 'bold': False},
        'paragraph': {'alignment': '居中'},
    },
    'footer': {
        'chinese_font': {'name': 'Times New Roman', 'size': '小五', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小五', 'bold': False},
        'paragraph': {'alignment': '居中'},
    },
    'page_margins': {
        'top': '2.54cm', 'bottom': '2.54cm',
        'left': '3.17cm', 'right': '3.17cm',
    },
    'default_chinese_font': {'name': '宋体', 'size': '小四'},
    'default_western_font': {'name': 'Times New Roman', 'size': '小四'},
    'line_spacing': '1.5倍',
}

# ---------- b) 北京大学本科论文规范 ----------
# 来源: 北京大学教务部公开文件《本科毕业论文（设计）学术规范》
# 未确认字段设为 None
PKU_RULES = {
    'school': '北京大学',
    'source': '北京大学教务部《本科毕业论文（设计）学术规范》',
    'paper_title': {
        'chinese_font': {'name': '黑体', 'size': '二号', 'bold': True},
        'western_font': None,  # 继承国标
        'paragraph': {'alignment': '居中'},
    },
    'heading1': {
        'chinese_font': {'name': '黑体', 'size': '三号', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': '居中'},
    },
    'heading2': {
        'chinese_font': {'name': '黑体', 'size': '四号', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': '左对齐'},
    },
    'body': {
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': None,
        'paragraph': {'alignment': '两端对齐', 'first_line_indent': '2字符', 'line_spacing': '1.5倍'},
    },
    'reference_entry': {
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': None,
        'paragraph': {'alignment': '两端对齐'},
    },
    'page_margins': None,  # 继承国标
}

# ---------- c) 清华大学本科论文规范 ----------
# 来源: 清华大学教务处《本科生毕业论文（设计）管理办法》
# 未确认字段设为 None
THU_RULES = {
    'school': '清华大学',
    'source': '清华大学教务处《本科生毕业论文（设计）管理办法》',
    'paper_title': {
        'chinese_font': {'name': '黑体', 'size': '二号', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': '居中'},
    },
    'heading1': {
        'chinese_font': {'name': '黑体', 'size': '三号', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': '居中'},
    },
    'heading2': {
        'chinese_font': {'name': '黑体', 'size': '四号', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': '左对齐'},
    },
    'body': {
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': None,
        'paragraph': {'alignment': '两端对齐', 'first_line_indent': '2字符', 'line_spacing': '1.5倍'},
    },
    'page_margins': None,
}

# ---------- d) 遵义医科大学本科论文规范 ----------
# 严格按照用户提供的已确认字段填入，未提及字段设为 None
ZUNYI_RULES = {
    'school': '遵义医科大学',
    'source': '遵义医科大学官方论文格式要求',
    'paper_title': {
        'chinese_font': {'name': '黑体', 'size': '小二', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': '居中', 'space_before': '1行', 'space_after': None},
    },
    'heading1': {
        'chinese_font': {'name': '黑体', 'size': '四号', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': None},
    },
    'heading2': {
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': None,
        'paragraph': {'alignment': None},
    },
    'heading3': {
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': None,
        'paragraph': {'alignment': None},
    },
    'body': {
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': None,
        'paragraph': {
            'alignment': None,
            'first_line_indent': None,
            'line_spacing': '固定值20磅',
        },
    },
    'abstract_body': {
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': None,
        'paragraph': {'line_spacing': '固定值20磅'},
    },
    'author_info': None,        # 继承国标
    'abstract_heading': None,   # 继承国标
    'keywords': None,           # 继承国标
    'caption': None,            # 继承国标
    'reference_heading': None,  # 继承国标
    'reference_entry': None,    # 继承国标
    'header': None,             # 继承国标
    'footer': None,             # 继承国标
    'page_margins': None,       # 继承国标
}

# 所有学校规则注册表
SCHOOL_RULES = {
    'default': ('国标默认', GB_BASIC),
    'pku': ('北京大学', PKU_RULES),
    'thu': ('清华大学', THU_RULES),
    'zunyi': ('遵义医科大学', ZUNYI_RULES),
}

# ================================================================
#  2. 规则继承与覆盖
# ================================================================

def _merge_rules(base, override):
    """
    递归合并规则字典。
    override 中 None 的字段继承 base 的值。
    override 中非 None 的字段覆盖 base 的值。
    """
    if base is None:
        return override
    if override is None:
        return base
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override if override is not None else base

    result = {}
    all_keys = set(list(base.keys()) + list(override.keys()))
    for key in all_keys:
        base_val = base.get(key)
        override_val = override.get(key)
        if override_val is None:
            result[key] = deepcopy(base_val) if base_val is not None else None
        elif isinstance(override_val, dict) and isinstance(base_val, dict):
            result[key] = _merge_rules(base_val, override_val)
        else:
            result[key] = deepcopy(override_val)
    return result


def get_rules(school='default', paper_type=None, custom_overrides=None):
    """
    获取最终规则。
    
    加载优先级（高 → 低）：
    1. custom_overrides（用户手动设置）
    2. school 定制规则
    3. paper_type 差异化规则（未来扩展）
    4. 国标基础规则

    任何字段为 None 时自动向上一级继承。
    """
    # 1. 从国标开始
    rules = deepcopy(GB_BASIC)

    # 2. 合并学校规则
    school_info = SCHOOL_RULES.get(school)
    if school_info and school_info[1]:
        school_data = school_info[1]
        for key, val in school_data.items():
            if key == 'school' or key == 'source':
                continue
            if val is not None:
                rules[key] = _merge_rules(rules.get(key), deepcopy(val))

    # 3. 合并论文类型差异化（预留）
    if paper_type == 'research':
        rules['paper_type'] = 'research'
        rules['figure_numbering'] = '章节编号'  # 图1-1
    elif paper_type == 'review':
        rules['paper_type'] = 'review'
        rules['figure_numbering'] = '全文连续'  # 图1

    # 4. 合并用户自定义覆盖
    if custom_overrides:
        for key, val in custom_overrides.items():
            if val is not None:
                rules[key] = _merge_rules(rules.get(key), deepcopy(val))

    rules['school'] = school_info[0] if school_info else '国标默认'
    return rules


def add_school_rules(school_name, rules_dict):
    """动态添加学校规则"""
    key = school_name.lower().replace(' ', '_')
    SCHOOL_RULES[key] = (school_name, rules_dict)
    logger.info("已添加学校规则: %s (key=%s)", school_name, key)


def get_school_list():
    """获取可用学校列表"""
    return [(key, info[0]) for key, info in SCHOOL_RULES.items()]


# ================================================================
#  3. 论文类型差异化规则
# ================================================================

RESEARCH_CHECK = {
    'figure_numbering': '章节编号',
    'abstract_elements': ['目的', '方法', '结果', '结论'],
    'required_sections': ['方法', '结果'],
    'reference_count': (20, 50),
    'appendix_check': True,
}

REVIEW_CHECK = {
    'figure_numbering': '全文连续',
    'abstract_elements': ['背景', '现状', '展望'],
    'reference_count': (50, 150),
    'recent_5_year_ratio': 0.6,
    'foreign_ratio': None,
    'appendix_check': False,
}

# ================================================================
#  4. 论文类型预判函数
# ================================================================

# 高权重词（权重值越高影响越大）
RESEARCH_KEYWORDS = {
    '实验方法': 0.9,
    '受试者': 0.8,
    '仪器设备': 0.8,
    '数据采集': 0.8,
    '实验结果': 0.8,
    '样本': 0.6,
    '材料与方法': 0.9,
    '受试对象': 0.8,
    '实验组': 0.7,
    '对照组': 0.7,
    '统计分析': 0.7,
    '纳入标准': 0.7,
    '排除标准': 0.7,
    '伦理批准': 0.8,
    '临床试验': 0.8,
    '实验室': 0.6,
    '数据集': 0.6,
    '算法': 0.5,
    '模型': 0.4,
    '准确率': 0.6,
    '召回率': 0.6,
    'F1': 0.5,
    '消融实验': 0.7,
    '基线': 0.5,
}

REVIEW_KEYWORDS = {
    '研究进展': 0.9,
    '文献梳理': 0.8,
    '国内外现状': 0.8,
    '研究展望': 0.8,
    '检索策略': 0.8,
    '纳入排除': 0.8,
    '综述': 0.9,
    '述评': 0.8,
    '研究动态': 0.8,
    '发展趋势': 0.7,
    '文献检索': 0.7,
    '数据库': 0.5,
    '系统评价': 0.9,
    'Meta分析': 0.9,
    '荟萃分析': 0.9,
    '循证': 0.7,
    '概述': 0.5,
    '总结': 0.3,
}

# 低权重词（不干扰判断，只有当其他证据不足时使用）
NEUTRAL_KEYWORDS = {
    '方法': 0.2,
    '结果': 0.2,
    '讨论': 0.2,
    '分析': 0.2,
    '研究': 0.1,
    '文献': 0.1,
}


def predict_paper_type(paragraphs):
    """
    根据论文段落文本预判论文类型。
    
    参数:
        paragraphs (list): 段落文本列表，或 str 全文
        
    返回:
        dict: {"type": "research"|"review"|"general", "confidence": 0.0~1.0, "details": {...}}
    """
    # 如果传入的是字符串（全文），按换行分段
    if isinstance(paragraphs, str):
        para_texts = [p.strip() for p in paragraphs.split('\n') if p.strip()]
    elif isinstance(paragraphs, list):
        para_texts = [p.get('text', p) if isinstance(p, dict) else str(p) for p in paragraphs]
    else:
        para_texts = []

    full_text = ' '.join(para_texts).lower()
    research_score = 0.0
    review_score = 0.0

    detail_hits = {'research': [], 'review': [], 'neutral': []}

    # 扫描高权重词
    for word, weight in RESEARCH_KEYWORDS.items():
        if word.lower() in full_text:
            research_score += weight
            detail_hits['research'].append((word, weight))

    for word, weight in REVIEW_KEYWORDS.items():
        if word.lower() in full_text:
            review_score += weight
            detail_hits['review'].append((word, weight))

    # 扫描章节标题
    for text in para_texts:
        t = text.strip()
        if re.search(r'^[一二三四五六七八九十]+、\s*(材料与方法|实验方法|实验材料)', t):
            research_score += 1.0
            detail_hits['research'].append(('章节: ' + t[:20], 1.0))
        if re.search(r'^[一二三四五六七八九十]+、\s*(文献综述|研究进展|国内外研究现状)', t):
            review_score += 0.8
            detail_hits['review'].append(('章节: ' + t[:20], 0.8))
        if '材料与方法' in t:
            research_score += 0.5
        if '文献综述' in t or '国内外研究现状' in t:
            review_score += 0.5

    # 判断
    if research_score > review_score and research_score > 1.0:
        paper_type = 'research'
        confidence = min(research_score / (research_score + review_score + 0.1), 1.0)
    elif review_score > research_score and review_score > 1.0:
        paper_type = 'review'
        confidence = min(review_score / (review_score + research_score + 0.1), 1.0)
    else:
        paper_type = 'general'
        confidence = 0.5

    result = {
        'type': paper_type,
        'confidence': round(confidence, 2),
        'scores': {
            'research': round(research_score, 2),
            'review': round(review_score, 2),
        },
        'details': detail_hits,
    }

    logger.info(
        "论文类型预判: %s (置信度: %.2f, 研究分: %.2f, 综述分: %.2f)",
        paper_type, confidence, research_score, review_score
    )
    return result
