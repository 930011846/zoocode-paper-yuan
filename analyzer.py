# -*- coding: utf-8 -*-
"""
格式分析器
基于规则从模板文档中分析并生成格式规范表
"""

import logging
from utils import extract_template_data

logger = logging.getLogger(__name__)

# ===== 字体大小 -> 中文名称映射 =====
FONT_SIZE_MAP = [
    (42, '初号'),
    (36, '小初'),
    (26, '一号'),
    (24, '小一'),
    (22, '二号'),
    (18, '小二'),
    (16, '三号'),
    (15, '小三'),
    (14, '四号'),
    (12, '小四'),
    (10.5, '五号'),
    (9, '小五'),
]

# ===== 默认值 =====
DEFAULT_CHINESE_FONT = {'name': '宋体', 'size': '小四'}
DEFAULT_WESTERN_FONT = {'name': 'Times New Roman', 'size': '小四'}
DEFAULT_LINE_SPACING = '1.5倍'
DEFAULT_MARGINS = {
    'top': '2.54cm', 'bottom': '2.54cm',
    'left': '3.17cm', 'right': '3.17cm'
}

# ===== GB/T 7713.1-2006 国标默认格式规则 =====
# 当模板中缺少某个板块定义时，自动使用此规则填补
GB_STYLE_RULES = {
    '论文大标题': {
        'description': '论文主标题（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '二号', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '二号', 'bold': True},
        'paragraph': {'alignment': '居中', 'space_before': '1行', 'space_after': '1行'},
    },
    '作者信息': {
        'description': '作者姓名、单位（国标默认）',
        'chinese_font': {'name': '楷体', 'size': '四号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '四号', 'bold': False},
        'paragraph': {'alignment': '居中'},
    },
    '摘要标题': {
        'description': '"摘要"二字（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '两端对齐'},
    },
    '摘要正文': {
        'description': '摘要内容（国标默认）',
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': False},
        'paragraph': {'alignment': '两端对齐', 'first_line_indent': '首行缩进2字符'},
    },
    '关键词': {
        'description': '"关键词"行（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '两端对齐'},
    },
    '一级标题': {
        'description': '一级标题（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '小三', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小三', 'bold': True},
        'paragraph': {'alignment': '居中', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    '二级标题': {
        'description': '二级标题（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '四号', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '四号', 'bold': True},
        'paragraph': {'alignment': '左对齐', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    '三级标题': {
        'description': '三级标题（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '左对齐', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    '正文': {
        'description': '正文段落（国标默认）',
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': False},
        'paragraph': {'alignment': '两端对齐', 'first_line_indent': '首行缩进2字符', 'line_spacing': '1.5倍'},
    },
    '图表标题': {
        'description': '图、表标题（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '五号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '五号', 'bold': False},
        'paragraph': {'alignment': '居中', 'space_before': '0.5行', 'space_after': '0.5行'},
    },
    '参考文献标题': {
        'description': '参考文献标题（国标默认）',
        'chinese_font': {'name': '黑体', 'size': '小三', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小三', 'bold': True},
        'paragraph': {'alignment': '居中', 'space_before': '1行', 'space_after': '1行'},
    },
    '参考文献条目': {
        'description': '参考文献条目（国标默认）',
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '五号', 'bold': False},
        'paragraph': {'alignment': '两端对齐'},
    },
    '页眉': {
        'description': '页眉（国标默认）',
        'chinese_font': {'name': '宋体', 'size': '五号', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '五号', 'bold': False},
        'paragraph': {'alignment': '居中'},
    },
    '页脚': {
        'description': '页脚/页码（国标默认）',
        'chinese_font': {'name': 'Times New Roman', 'size': '小五', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小五', 'bold': False},
        'paragraph': {'alignment': '居中'},
    },
}


def _pt_to_chinese_size(pt_size):
    """将磅值转换为中文字号名称"""
    if pt_size is None:
        return None
    for size_pt, name in FONT_SIZE_MAP:
        if abs(pt_size - size_pt) < 1.0:
            return name
    # 模糊匹配
    closest = min(FONT_SIZE_MAP, key=lambda x: abs(x[0] - pt_size))
    return closest[1]


def _get_para_info(para):
    """便捷获取段落格式信息"""
    return {
        'text': para.get('text', ''),
        'text_length': para.get('text_length', 0),
        'style_name': para.get('style_name', ''),
        'font': para.get('font', {}),
        'para_fmt': para.get('paragraph_format', {}),
    }


def _build_font_info(font_data, is_chinese=True):
    """从字体数据构建标准字体信息字典"""
    font_info = {
        'name': font_data.get('name'),
        'size': _pt_to_chinese_size(font_data.get('size')),
        'bold': font_data.get('bold') or False,
    }
    if not font_info['name']:
        font_info['name'] = '宋体' if is_chinese else 'Times New Roman'
    if not font_info['size']:
        font_info['size'] = '小四'
    return font_info


def _build_para_format(para_fmt):
    """从段落格式数据构建标准段落格式字典"""
    result = {
        'alignment': para_fmt.get('alignment') or '两端对齐',
    }
    # 段前间距
    space_before = para_fmt.get('space_before')
    if space_before is not None:
        result['space_before'] = f'{space_before}磅'
    # 段后间距
    space_after = para_fmt.get('space_after')
    if space_after is not None:
        result['space_after'] = f'{space_after}磅'
    # 首行缩进
    indent = para_fmt.get('first_line_indent')
    if indent is not None:
        result['first_line_indent'] = f'首行缩进{indent}字符'
    return result


def _classify_paragraphs(paragraphs):
    """
    对段落进行分类，识别不同的文档元素类型。

    返回:
        dict: 分类后的段落索引
    """
    classified = {
        'title_para': None,        # 论文大标题
        'headings': [],             # 各级标题
        'body_paras': [],           # 正文段落
        'reference_title': None,    # 参考文献标题
        'figure_captions': [],      # 图标题
        'table_captions': [],       # 表标题
    }

    for i, para in enumerate(paragraphs):
        text = para.get('text', '').strip()
        if not text:
            continue

        info = _get_para_info(para)

        # 检测"参考文献"
        if '参考文献' in text and len(text) < 30:
            classified['reference_title'] = i
            continue

        # 检测图标题（以"图"或"Fig"开头）
        if text.startswith('图') or text.startswith('Fig') or text.startswith('Figure'):
            classified['figure_captions'].append(i)
            continue

        # 检测表标题（以"表"或"Table"开头）
        if text.startswith('表') or text.startswith('Table'):
            classified['table_captions'].append(i)
            continue

        # 第一段：论文大标题
        if classified['title_para'] is None:
            classified['title_para'] = i
            continue

        # 标题检测：字数少且加粗
        is_bold = info['font'].get('bold') is True
        text_len = info['text_length']
        font_size = info['font'].get('size') or 0

        if is_bold and text_len < 30 and font_size >= 12:
            classified['headings'].append(i)
        else:
            classified['body_paras'].append(i)

    return classified


def _extract_heading_hierarchy(paragraphs, heading_indices):
    """
    从标题段落中识别层级结构（一级、二级、三级标题）。

    根据字号从大到小排序，分配层级。
    返回: [(index, level), ...]
    """
    if not heading_indices:
        return []

    # 获取每个标题的字号
    heading_sizes = []
    for idx in heading_indices:
        para = paragraphs[idx]
        font = para.get('font', {})
        size = font.get('size') or 0
        heading_sizes.append((idx, size))

    # 按字号降序排序
    heading_sizes.sort(key=lambda x: -x[1])

    if len(heading_sizes) == 0:
        return []

    # 分配层级
    result = []
    # 最大字号为一级，次大为二级，其余为三级
    max_size = heading_sizes[0][1]

    for i, (idx, size) in enumerate(heading_sizes):
        if i == 0:
            level = 1
        elif i == 1 and size >= max_size * 0.8:
            level = 2
        else:
            level = 3
        result.append((idx, level))

    # 按原文顺序排序
    result.sort(key=lambda x: x[0])
    return result


def _build_style_rule(name, para_info, level=None):
    """构建单个样式规则条目"""
    font = para_info['font']
    para_fmt = para_info['para_fmt']

    # 中文字体
    chinese_font = _build_font_info(font, is_chinese=True)
    # 西文字体
    western_font = _build_font_info(font, is_chinese=False)

    # 段落格式
    paragraph = _build_para_format(para_fmt)

    rule = {
        'description': para_info['text'][:30] if para_info['text'] else '',
        'chinese_font': chinese_font,
        'western_font': western_font,
        'paragraph': paragraph,
    }

    if level:
        rule['level'] = level

    return rule


def analyze_template(template_path):
    """
    分析模板文档，生成格式规范表。

    使用规则（非大模型）识别文档结构，提取各元素的格式规范。

    参数:
        template_path (str): .docx 模板文件路径

    返回:
        dict: 格式规范表，包含 style_rules 和文档级默认设置
    """
    # 1. 提取模板原始数据
    raw_data = extract_template_data(template_path)
    paragraphs = raw_data.get('paragraphs', [])
    headers = raw_data.get('headers', [])
    footers = raw_data.get('footers', [])
    page_margins = raw_data.get('page_margins', {})

    logger.info("开始分析模板 - 共 %d 个段落", len(paragraphs))

    # 2. 对段落进行分类
    classified = _classify_paragraphs(paragraphs)

    # 3. 构建样式规则
    style_rules = {}

    # 3a. 论文大标题
    if classified['title_para'] is not None:
        idx = classified['title_para']
        info = _get_para_info(paragraphs[idx])
        style_rules['论文大标题'] = _build_style_rule(
            '论文大标题', info
        )
        style_rules['论文大标题']['description'] = '全文第一段，论文主标题'
    else:
        style_rules['论文大标题'] = {
            'description': '全文第一段（未检测到标题）',
            'chinese_font': {'name': '黑体', 'size': '二号', 'bold': True},
            'western_font': {'name': 'Times New Roman', 'size': '二号', 'bold': True},
            'paragraph': {'alignment': '居中', 'space_before': '0磅', 'space_after': '0磅'},
            'inferred': True,
        }

    # 3b. 各级标题
    heading_tree = _extract_heading_hierarchy(
        paragraphs, classified['headings']
    )

    heading_names = {
        1: '一级标题',
        2: '二级标题',
        3: '三级标题',
    }

    # 收集已使用的标题索引
    used_heading_indices = set()

    for idx, level in heading_tree:
        name = heading_names.get(level, f'{level}级标题')
        info = _get_para_info(paragraphs[idx])
        rule = _build_style_rule(name, info, level=level)

        # 特殊处理一级标题的默认描述
        if level == 1:
            rule['description'] = '一级标题（如"1 引言"）'
        elif level == 2:
            rule['description'] = '二级标题（如"1.1 研究背景"）'
        elif level == 3:
            rule['description'] = '三级标题（如"1.1.1 国内外现状"）'

        style_rules[name] = rule
        used_heading_indices.add(idx)

    # 补全缺少的标题层级
    for level in [1, 2, 3]:
        name = heading_names[level]
        if name not in style_rules:
            style_rules[name] = _generate_default_heading(level)
            style_rules[name]['inferred'] = True

    # 3c. 正文
    if classified['body_paras']:
        # 取第一个正文段落作为参考
        idx = classified['body_paras'][0]
        info = _get_para_info(paragraphs[idx])
        style_rules['正文'] = _build_style_rule('正文', info)
        style_rules['正文']['description'] = '正文段落'
        # 正文通常首行缩进2字符
        if not style_rules['正文']['paragraph'].get('first_line_indent'):
            style_rules['正文']['paragraph']['first_line_indent'] = '首行缩进2字符'
    else:
        style_rules['正文'] = {
            'description': '正文段落',
            'chinese_font': {'name': '宋体', 'size': '小四'},
            'western_font': {'name': 'Times New Roman', 'size': '小四'},
            'paragraph': {'alignment': '两端对齐', 'first_line_indent': '首行缩进2字符'},
            'inferred': True,
        }

    # 3d. 参考文献标题
    if classified['reference_title'] is not None:
        idx = classified['reference_title']
        info = _get_para_info(paragraphs[idx])
        style_rules['参考文献标题'] = _build_style_rule(
            '参考文献标题', info
        )
        style_rules['参考文献标题']['description'] = '参考文献章节标题'
    else:
        style_rules['参考文献标题'] = {
            'description': '参考文献章节标题',
            'chinese_font': {'name': '黑体', 'size': '三号', 'bold': True},
            'western_font': {'name': 'Times New Roman', 'size': '三号', 'bold': True},
            'paragraph': {'alignment': '居中'},
            'inferred': True,
        }

    # 3e. 参考文献条目
    style_rules['参考文献条目'] = {
        'description': '参考文献列表中的各条目',
        'chinese_font': {'name': '宋体', 'size': '五号'},
        'western_font': {'name': 'Times New Roman', 'size': '五号'},
        'paragraph': {'alignment': '两端对齐'},
        'inferred': True,
    }

    # 3f. 页眉
    if headers:
        style_rules['页眉'] = {
            'description': f'页眉内容：{"；".join(headers[:2])}',
            'chinese_font': {'name': '宋体', 'size': '五号'},
            'western_font': {'name': 'Times New Roman', 'size': '五号'},
            'paragraph': {'alignment': '居中'},
        }
    else:
        style_rules['页眉'] = {
            'description': '页眉（未检测到内容，使用默认）',
            'chinese_font': {'name': '宋体', 'size': '五号'},
            'western_font': {'name': 'Times New Roman', 'size': '五号'},
            'paragraph': {'alignment': '居中'},
            'inferred': True,
        }

    # 3g. 页脚
    if footers:
        style_rules['页脚'] = {
            'description': f'页脚内容：{"；".join(footers[:2])}',
            'chinese_font': {'name': '宋体', 'size': '五号'},
            'western_font': {'name': 'Times New Roman', 'size': '五号'},
            'paragraph': {'alignment': '居中'},
        }
    else:
        style_rules['页脚'] = {
            'description': '页脚（未检测到内容，使用默认）',
            'chinese_font': {'name': '宋体', 'size': '小五'},
            'western_font': {'name': 'Times New Roman', 'size': '小五'},
            'paragraph': {'alignment': '居中'},
            'inferred': True,
        }

    # 3h. 图表标题
    style_rules['图表标题'] = {
        'description': '图、表标题',
        'chinese_font': {'name': '黑体', 'size': '小四', 'bold': True},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
        'paragraph': {'alignment': '居中'},
        'inferred': True,
    }

    # 4. 计算默认字体和行距
    default_chinese = None
    default_western = None
    if classified['body_paras']:
        idx = classified['body_paras'][0]
        font = paragraphs[idx].get('font', {})
        default_chinese = _build_font_info(font, is_chinese=True)
        default_western = _build_font_info(font, is_chinese=False)
        # 估算行距
        ls = paragraphs[idx].get('paragraph_format', {}).get('line_spacing')
        if ls:
            if ls > 10:  # 固定值磅数
                default_ls = f'{_pt_to_chinese_size(ls) or ls}磅'
            else:  # 倍数
                default_ls = f'{ls}倍'
        else:
            default_ls = DEFAULT_LINE_SPACING
    else:
        default_chinese = DEFAULT_CHINESE_FONT
        default_western = DEFAULT_WESTERN_FONT
        default_ls = DEFAULT_LINE_SPACING

    # 5. 用国标 GB/T 7713.1-2006 填补缺失的样式规则
    for gb_key, gb_rule in GB_STYLE_RULES.items():
        if gb_key not in style_rules:
            style_rules[gb_key] = dict(gb_rule)
            style_rules[gb_key]['inferred'] = True
            logger.info("国标填补缺失规则: %s", gb_key)
        else:
            # 已有规则中缺少的字段用国标填补
            existing = style_rules[gb_key]
            for field in ['chinese_font', 'western_font', 'paragraph']:
                if field not in existing or not existing[field]:
                    existing[field] = dict(gb_rule.get(field, {}))
                elif field == 'paragraph':
                    # 段落格式中缺少的子字段也用国标填补
                    for subfield in ['alignment', 'first_line_indent', 'line_spacing', 'space_before', 'space_after']:
                        if subfield not in existing[field] or not existing[field][subfield]:
                            if subfield in gb_rule.get(field, {}):
                                existing[field][subfield] = gb_rule[field][subfield]

    # 6. 构建最终结果
    result = {
        'document_title': '模板分析结果',
        'style_rules': style_rules,
        'default_chinese_font': default_chinese or DEFAULT_CHINESE_FONT,
        'default_western_font': default_western or DEFAULT_WESTERN_FONT,
        'line_spacing': default_ls or DEFAULT_LINE_SPACING,
        'page_margins': {
            'top': DEFAULT_MARGINS['top'],
            'bottom': DEFAULT_MARGINS['bottom'],
            'left': DEFAULT_MARGINS['left'],
            'right': DEFAULT_MARGINS['right'],
        },
    }

    logger.info("模板分析完成 - 识别到 %d 个样式规则（含国标填补）", len(style_rules))
    return result


def _generate_default_heading(level):
    """为指定层级生成默认标题格式"""
    defaults = {
        1: {
            'description': '一级标题',
            'chinese_font': {'name': '黑体', 'size': '三号', 'bold': True},
            'western_font': {'name': 'Times New Roman', 'size': '三号', 'bold': True},
            'paragraph': {'alignment': '居中', 'space_before': '1行', 'space_after': '0.5行'},
        },
        2: {
            'description': '二级标题',
            'chinese_font': {'name': '黑体', 'size': '四号', 'bold': True},
            'western_font': {'name': 'Times New Roman', 'size': '四号', 'bold': True},
            'paragraph': {'alignment': '左对齐', 'space_before': '0.5行', 'space_after': '0.5行'},
        },
        3: {
            'description': '三级标题',
            'chinese_font': {'name': '楷体', 'size': '小四', 'bold': True},
            'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': True},
            'paragraph': {'alignment': '左对齐', 'space_before': '0.5行', 'space_after': '0行'},
        },
    }
    return defaults.get(level, defaults[3])


def get_target_format(label, template_rules):
    """
    根据段落语义标签，从模板规则中查找对应的目标格式。

    参数:
        label (str): 语义标签，如 "一级标题"、"正文" 等
        template_rules (dict): 模板格式规范表（analyze_template 的返回值）

    返回:
        dict: 目标格式字典，包含 chinese_font, western_font, paragraph 字段
              如果找不到对应规则，返回默认正文格式
    """
    # 默认正文格式
    default_format = {
        'chinese_font': {'name': '宋体', 'size': '小四', 'bold': False},
        'western_font': {'name': 'Times New Roman', 'size': '小四', 'bold': False},
        'paragraph': {
            'alignment': '两端对齐',
            'first_line_indent': '首行缩进2字符',
        },
    }

    if not template_rules or not isinstance(template_rules, dict):
        return default_format

    style_rules = template_rules.get('style_rules', {})
    if not style_rules:
        return default_format

    # 直接匹配标签名
    if label in style_rules:
        rule = style_rules[label]
        return _extract_target_format(rule, default_format)

    # 尝试部分匹配
    for rule_name, rule in style_rules.items():
        if label in rule_name or rule_name in label:
            return _extract_target_format(rule, default_format)

    return default_format


def _extract_target_format(rule, default_format):
    """从单个规则中提取目标格式，缺少的字段用默认值填充"""
    result = {
        'chinese_font': {
            'name': rule.get('chinese_font', {}).get('name')
                    or default_format['chinese_font']['name'],
            'size': rule.get('chinese_font', {}).get('size')
                    or default_format['chinese_font']['size'],
            'bold': rule.get('chinese_font', {}).get('bold', False),
        },
        'western_font': {
            'name': rule.get('western_font', {}).get('name')
                    or default_format['western_font']['name'],
            'size': rule.get('western_font', {}).get('size')
                    or default_format['western_font']['size'],
            'bold': rule.get('western_font', {}).get('bold', False),
        },
        'paragraph': {
            'alignment': rule.get('paragraph', {}).get('alignment')
                         or default_format['paragraph']['alignment'],
            'first_line_indent': rule.get('paragraph', {}).get('first_line_indent'),
            'space_before': rule.get('paragraph', {}).get('space_before'),
            'space_after': rule.get('paragraph', {}).get('space_after'),
        },
    }
    return result
