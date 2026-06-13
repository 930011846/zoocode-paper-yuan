# -*- coding: utf-8 -*-
"""
论文内容分析器
提供论文语义分析和段落自动标注功能
支持 DeepSeek API 大模型分析和备用规则引擎两种模式
"""

import os
import re
import json
import logging
from docx import Document

logger = logging.getLogger(__name__)

# DeepSeek API 配置
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_KEY = "sk-0423ef5c80ae402e84c7f599450d00a2"

# 所有支持的语义标签
ALL_LABELS = [
    "论文大标题", "作者信息", "摘要标题", "摘要正文", "关键词",
    "一级标题", "二级标题", "三级标题",
    "正文段落", "图表标题",
    "参考文献标题", "参考文献条目",
    "致谢", "附录标题", "附录内容",
    "页眉", "页脚",
]

# 标签类型映射（用于结构地图）
LABEL_TYPE_MAP = {
    "论文大标题": "title",
    "作者信息": "authors",
    "摘要标题": "abstract_heading",
    "摘要正文": "abstract",
    "关键词": "keywords",
    "一级标题": "heading1",
    "二级标题": "heading2",
    "三级标题": "heading3",
    "正文段落": "body",
    "图表标题": "caption",
    "参考文献标题": "reference_heading",
    "参考文献条目": "reference",
    "致谢": "acknowledgment",
    "附录标题": "appendix_heading",
    "附录内容": "appendix",
    "页眉": "header",
    "页脚": "footer",
}


# ================================================================
#  主入口
# ================================================================

def analyze_paper(paper_path, template_style_rules=None):
    """
    分析论文文档，标注每个段落的语义类别，生成结构化的论文结构地图。

    参数:
        paper_path (str): 论文 .docx 文件路径
        template_style_rules (dict, optional): 模板格式规范表（来自 analyzer）

    返回:
        dict: 论文结构地图
            {
                "method": "llm" | "rule_based",
                "paper_title": "...",
                "confidence": 0.95,
                "paragraph_labels": [{"index": 0, "label": "...", "confidence": 0.9}, ...],
                "sections": [...],
                "figures": [...],
                "tables": [...],
                "reference_start": null,
                "reference_end": null,
            }
    """
    # 1. 提取论文段落信息
    paragraphs = _extract_paragraphs(paper_path)

    if not paragraphs:
        logger.warning("论文文档中没有找到任何段落")
        return {
            "method": "rule_based",
            "paper_title": "",
            "confidence": 0.0,
            "paragraph_labels": [],
            "sections": [],
            "figures": [],
            "tables": [],
            "reference_start": None,
            "reference_end": None,
        }

    logger.info("论文共提取到 %d 个段落", len(paragraphs))

    # 2. 尝试大模型分析
    labels = None
    method = "rule_based"

    print("=" * 60)
    print("[ContentAnalyzer] 开始检查 DeepSeek API Key...")
    if DEEPSEEK_API_KEY:
        key_preview = DEEPSEEK_API_KEY[:10] + "..." if len(DEEPSEEK_API_KEY) > 10 else "(空)"
        print(f"[ContentAnalyzer] DEEPSEEK_API_KEY 已设置，前缀: {key_preview}")
        print(f"[ContentAnalyzer] API Key 长度: {len(DEEPSEEK_API_KEY)}")
        try:
            logger.info("尝试调用 DeepSeek API 进行语义分析...")
            print("[ContentAnalyzer] 正在调用 _call_deepseek_api...")
            labels = _call_deepseek_api(paragraphs)
            if labels:
                method = "llm"
                print("[ContentAnalyzer] DeepSeek API 分析成功!")
                logger.info("DeepSeek API 分析成功")
            else:
                print("[ContentAnalyzer] _call_deepseek_api 返回 None，将使用规则引擎")
        except Exception as e:
            import traceback
            print(f"[ContentAnalyzer] DeepSeek API 调用抛出异常: {type(e).__name__}: {e}")
            traceback.print_exc()
            logger.warning("DeepSeek API 调用失败，切换到规则引擎: %s", str(e))
    else:
        print("[ContentAnalyzer] DEEPSEEK_API_KEY 环境变量未设置!")
        print("[ContentAnalyzer] 提示: 可运行 'set DEEPSEEK_API_KEY=sk-你的key' 启用大模型分析")
        logger.info("未设置 DEEPSEEK_API_KEY 环境变量，使用规则引擎")
    print("=" * 60)

    # 3. 如果大模型失败或未配置，使用规则引擎
    if not labels:
        logger.info("使用规则引擎进行段落标注")
        labels = _rule_based_analysis(paragraphs)

    # 4. 构建结构地图
    structure_map = _build_structure_map(paragraphs, labels, method)

    return structure_map


# ================================================================
#  段落提取
# ================================================================

def _serialize_font_size(size_emu):
    """将 EMU 字体大小转换为磅值"""
    if size_emu is None:
        return None
    try:
        return round(size_emu / 12700, 1)
    except (TypeError, AttributeError):
        return None


def _serialize_length_cm(length_emu):
    """将 EMU 长度转换为厘米"""
    if length_emu is None:
        return None
    try:
        return round(length_emu / 360000, 2)  # 1cm = 360000 EMU
    except (TypeError, AttributeError):
        return None


def _serialize_alignment_str(alignment):
    """将对齐方式枚举值转换为中文字符串"""
    if alignment is None:
        return None
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    mapping = {
        WD_ALIGN_PARAGRAPH.LEFT: '左对齐',
        WD_ALIGN_PARAGRAPH.CENTER: '居中',
        WD_ALIGN_PARAGRAPH.RIGHT: '右对齐',
        WD_ALIGN_PARAGRAPH.JUSTIFY: '两端对齐',
    }
    return mapping.get(alignment, str(alignment))


def _serialize_line_spacing(line_spacing):
    """序列化行距值"""
    if line_spacing is None:
        return None
    try:
        # 如果是 float（倍数），直接返回
        if isinstance(line_spacing, float):
            return {'type': 'multiple', 'value': round(line_spacing, 1)}
        # 如果是 Length 对象（固定值），转为磅
        emu_val = int(line_spacing)
        return {'type': 'fixed', 'value': round(emu_val / 12700, 1)}
    except (TypeError, AttributeError, ValueError):
        return None


def _extract_paragraphs(docx_path):
    """
    提取论文文档的段落信息，包含当前格式详情。

    返回:
        list[dict]: 段落信息列表，每项包含 current_format
    """
    doc = Document(docx_path)
    paragraphs = []

    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        run = para.runs[0] if para.runs else None
        pf = para.paragraph_format

        current_format = {
            'font_name': run.font.name if run else None,
            'font_size': _serialize_font_size(run.font.size if run else None),
            'bold': run.font.bold if run else False,
            'italic': run.font.italic if run else False,
            'alignment': _serialize_alignment_str(para.alignment),
            'first_line_indent': _serialize_length_cm(pf.first_line_indent),
            'line_spacing': _serialize_line_spacing(pf.line_spacing),
            'space_before': _serialize_length_cm(pf.space_before),
            'space_after': _serialize_length_cm(pf.space_after),
        }

        para_info = {
            "index": idx,
            "text": text,
            "text_length": len(text),
            "style_name": para.style.name if para.style else None,
            "current_format": current_format,
        }
        paragraphs.append(para_info)

    return paragraphs


# ================================================================
#  构建完整文本（给大模型用）
# ================================================================

def _build_full_text(paragraphs):
    """
    将段落列表拼接成带索引的完整文本，供大模型分析。

    格式：
        [0] 基于深度学习的图像识别方法研究
        [1] 张三 李四
        [2] 摘要
        [3] 本文提出了一种...
        ...
    """
    lines = []
    for p in paragraphs:
        text = p["text"] if p["text"] else "(空段落)"
        lines.append(f"[{p['index']}] {text}")
    return "\n".join(lines)


# ================================================================
#  DeepSeek API 调用（带详细调试日志）
# ================================================================

def _call_deepseek_api(paragraphs):
    """
    调用 DeepSeek API 对论文段落进行语义标注。

    参数:
        paragraphs (list[dict]): 段落信息列表

    返回:
        list[dict]: 标注结果列表，或 None（失败时）
    """
    import requests
    import traceback

    print("=" * 60)
    print("[DeepSeek Debug] 进入 _call_deepseek_api")
    print(f"[DeepSeek Debug] 段落数: {len(paragraphs)}")

    # ---- API Key 检查 ----
    if not DEEPSEEK_API_KEY:
        print("[DeepSeek Debug] 错误: DEEPSEEK_API_KEY 为空或未设置!")
        print("[DeepSeek Debug] 请通过环境变量设置: set DEEPSEEK_API_KEY=sk-xxx")
        logger.error("DEEPSEEK_API_KEY 未设置，无法调用 API")
        return None

    key_prefix = DEEPSEEK_API_KEY[:10] + "..." if len(DEEPSEEK_API_KEY) > 10 else DEEPSEEK_API_KEY
    print(f"[DeepSeek Debug] API Key (前10位): {key_prefix}")
    print(f"[DeepSeek Debug] API URL: {DEEPSEEK_API_URL}")
    print(f"[DeepSeek Debug] 模型: {DEEPSEEK_MODEL}")
    print("=" * 60)

    # ---- 构建文本 ----
    full_text = _build_full_text(paragraphs)
    print(f"[DeepSeek Debug] 构建的全文长度: {len(full_text)} 字符")
    print(f"[DeepSeek Debug] 全文预览 (前500字):")
    print(f"[DeepSeek Debug] {full_text[:500]}")
    print("=" * 60)

    # 构建系统提示词
    system_prompt = """你是一个专业的学术论文结构分析助手。你的任务是根据论文段落文本，判断每个段落的语义类别。

可选的语义类别（标签）包括：
- 论文大标题：论文的主标题
- 作者信息：作者姓名、单位等
- 摘要标题："摘要"二字
- 摘要正文：摘要的具体内容
- 关键词："关键词：..." 行
- 一级标题：如 "1 引言"、"2 方法"
- 二级标题：如 "1.1 研究背景"
- 三级标题：如 "1.1.1 具体方法"
- 正文段落：普通的正文内容
- 图表标题：如图1、表2等标题
- 参考文献标题："参考文献"标题行
- 参考文献条目：类似 "[1] Author..." 的条目
- 致谢："致谢"标题或内容
- 附录标题："附录A"等
- 附录内容：附录正文
- 页眉：页面顶部重复文字
- 页脚：页面底部重复文字

请严格按照以下JSON格式返回结果，不要包含其他内容：
[
  {"段落索引": 0, "标签": "论文大标题", "置信度": 0.95},
  {"段落索引": 1, "标签": "作者信息", "置信度": 0.90},
  ...
]

注意：
1. 置信度范围 0-1，不确定的段落可以标低置信度（如0.5）
2. 每个段落都必须有一个标签
3. 对于完全空段落，标签设为"正文段落"，置信度0.3"""

    user_prompt = f"""请分析以下论文的全部段落，为每个段落标注语义类别：

{full_text}

请返回JSON格式的标注结果。"""

    # 构建请求体
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,  # 低温度保证一致性
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"[DeepSeek Debug] 请求体大小: {len(json.dumps(payload, ensure_ascii=False))} 字符")
    print("[DeepSeek Debug] 正在发送 POST 请求...")
    logger.info("正在发送请求到 DeepSeek API (段落数: %d)...", len(paragraphs))

    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

        print(f"[DeepSeek Debug] 响应状态码: {response.status_code}")
        print(f"[DeepSeek Debug] 响应 Headers: {dict(response.headers)}")

        # 如果状态码不是 200，打印完整响应内容
        if response.status_code != 200:
            print(f"[DeepSeek Debug] 错误响应内容:")
            print(f"[DeepSeek Debug] {response.text[:2000]}")
            logger.error("DeepSeek API 返回错误状态码: %s, 内容: %s",
                         response.status_code, response.text[:500])
            return None

        # 尝试解析 JSON
        print("[DeepSeek Debug] 正在解析响应 JSON...")
        try:
            response_data = response.json()
            print("[DeepSeek Debug] JSON 解析成功")
        except json.JSONDecodeError as e:
            print(f"[DeepSeek Debug] JSON 解析失败: {e}")
            print(f"[DeepSeek Debug] 原始响应文本 (前2000字符):")
            print(f"[DeepSeek Debug] {response.text[:2000]}")
            logger.error("DeepSeek API 返回的不是有效 JSON: %s", response.text[:500])
            return None

        # 提取回复内容
        print("[DeepSeek Debug] 提取 choices[0].message.content...")
        try:
            content = response_data["choices"][0]["message"]["content"]
            print(f"[DeepSeek Debug] 回复内容长度: {len(content)} 字符")
            print(f"[DeepSeek Debug] 回复内容预览 (前500字):")
            print(f"[DeepSeek Debug] {content[:500]}")
        except (KeyError, IndexError) as e:
            print(f"[DeepSeek Debug] 响应结构异常: {e}")
            print(f"[DeepSeek Debug] 完整响应数据: {json.dumps(response_data, ensure_ascii=False, indent=2)[:2000]}")
            logger.error("DeepSeek API 响应结构不符合预期: %s", str(e))
            return None

        logger.info("DeepSeek API 响应接收完成")

        # 解析 JSON
        labels = _parse_api_response(content, len(paragraphs))

        if labels:
            print(f"[DeepSeek Debug] 解析成功! 共 {len(labels)} 个标注")
        else:
            print(f"[DeepSeek Debug] _parse_api_response 返回 None，解析失败")
            print(f"[DeepSeek Debug] 完整回复内容:")
            print(f"[DeepSeek Debug] {content}")

        return labels

    except requests.exceptions.Timeout:
        print("[DeepSeek Debug] 请求超时 (timeout=60s)")
        logger.error("DeepSeek API 请求超时")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[DeepSeek Debug] 请求异常: {type(e).__name__}: {e}")
        traceback.print_exc()
        logger.error("DeepSeek API 请求失败: %s", str(e))
        return None
    except Exception as e:
        print(f"[DeepSeek Debug] 未知异常: {type(e).__name__}: {e}")
        traceback.print_exc()
        logger.error("调用 DeepSeek API 时发生未知异常: %s", str(e))
        return None


def _parse_api_response(content, expected_count):
    """
    解析 API 返回的 JSON 内容，提取段落标注。

    参数:
        content (str): API 返回的文本内容
        expected_count (int): 期望的段落数

    返回:
        list[dict] or None
    """
    import traceback

    print("[DeepSeek Debug] 进入 _parse_api_response")
    print(f"[DeepSeek Debug] 预期段落数: {expected_count}")
    print(f"[DeepSeek Debug] 原始内容长度: {len(content)} 字符")

    # 尝试从 markdown 代码块中提取 JSON
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if json_match:
        extracted = json_match.group(1)
        print(f"[DeepSeek Debug] 从 markdown 代码块中提取到 JSON (长度: {len(extracted)})")
        content = extracted
    else:
        print("[DeepSeek Debug] 未发现 markdown 代码块，直接解析全文")

    # 尝试直接解析 JSON
    try:
        labels = json.loads(content.strip())
        print(f"[DeepSeek Debug] 直接 JSON 解析成功")
    except json.JSONDecodeError as e:
        print(f"[DeepSeek Debug] 直接解析失败: {e}")
        # 尝试找到 JSON 数组的起始和结束
        array_match = re.search(r"\[[\s\S]*\]", content)
        if array_match:
            print(f"[DeepSeek Debug] 通过正则找到 JSON 数组 (长度: {len(array_match.group())})")
            try:
                labels = json.loads(array_match.group())
                print(f"[DeepSeek Debug] 正则提取后 JSON 解析成功")
            except json.JSONDecodeError as e2:
                print(f"[DeepSeek Debug] 正则提取后仍解析失败: {e2}")
                print(f"[DeepSeek Debug] 提取的内容 (前1000字): {array_match.group()[:1000]}")
                logger.error("无法解析 API 返回的 JSON")
                return None
        else:
            print("[DeepSeek Debug] 正则未找到 JSON 数组")
            print(f"[DeepSeek Debug] 完整内容 (前2000字): {content[:2000]}")
            logger.error("API 返回中没有找到 JSON 数组")
            return None

    # 验证格式
    if not isinstance(labels, list):
        print(f"[DeepSeek Debug] 解析结果不是数组，而是 {type(labels).__name__}: {str(labels)[:500]}")
        logger.error("API 返回的不是数组")
        return None

    print(f"[DeepSeek Debug] 解析得到 {len(labels)} 个标注项")

    # 标准化字段名
    standardized = []
    for i, item in enumerate(labels):
        if not isinstance(item, dict):
            print(f"[DeepSeek Debug] 第 {i} 项不是 dict，跳过: {type(item).__name__}")
            continue
        std_item = {
            "index": item.get("段落索引", item.get("index", 0)),
            "label": item.get("标签", item.get("label", "正文段落")),
            "confidence": item.get("置信度", item.get("confidence", 0.5)),
        }
        standardized.append(std_item)

    print(f"[DeepSeek Debug] 标准化后: {len(standardized)} 个标注")

    # 验证标签是否都在合法范围内
    invalid_count = 0
    for item in standardized:
        if item["label"] not in ALL_LABELS:
            invalid_count += 1
            # 如果标签不在列表中，尝试部分匹配
            matched = False
            for valid_label in ALL_LABELS:
                if valid_label in item["label"] or item["label"] in valid_label:
                    item["label"] = valid_label
                    matched = True
                    break
            if not matched:
                print(f"[DeepSeek Debug] 无法匹配标签: '{item['label']}'，设为 '正文段落'")
                item["label"] = "正文段落"
                item["confidence"] = 0.3

    if invalid_count > 0:
        print(f"[DeepSeek Debug] 共 {invalid_count} 个标签不在合法列表中，已尝试自动修正")
    else:
        print(f"[DeepSeek Debug] 所有标签均在合法列表中")

    logger.info("API 返回解析完成，共 %d 个标注", len(standardized))
    return standardized


# ================================================================
#  备用规则引擎
# ================================================================

def _rule_based_analysis(paragraphs):
    """
    基于规则的段落标注引擎（大模型不可用时的备用方案）。

    参数:
        paragraphs (list[dict]): 段落信息列表

    返回:
        list[dict]: 标注结果列表
    """
    labels = []
    found_first = False
    found_abstract_heading = False
    found_keywords = False
    found_reference_heading = False
    found_acknowledgment = False

    for i, p in enumerate(paragraphs):
        text = p["text"]
        text_len = p["text_length"]
        cf = p.get("current_format", {})
        is_bold = cf.get("bold") is True
        font_size = cf.get("font_size") or 0

        label = None
        confidence = 0.6  # 规则引擎统一置信度

        # --- 规则判断（按优先级） ---

        # 空段落
        if not text:
            label = "正文段落"
            confidence = 0.3

        # 第一个非空段落 → 论文大标题
        elif not found_first and text_len > 0:
            label = "论文大标题"
            confidence = 0.8
            found_first = True

        # 页眉/页脚检测（短文本，通常在开头或结尾）
        elif text_len < 10 and not found_first:
            # 极小段落在标题之前视为页眉
            label = "页眉"
            confidence = 0.5

        # 致谢
        elif re.match(r'^致谢', text):
            label = "致谢"
            confidence = 0.9
            found_acknowledgment = True

        # 附录
        elif re.match(r'^附录\s*[A-Z一二三四五六]', text):
            label = "附录标题"
            confidence = 0.9

        # 参考文献标题
        elif text == "参考文献" or re.match(r'^参考文献\s*$', text):
            label = "参考文献标题"
            confidence = 0.95
            found_reference_heading = True

        # 参考文献条目（以 [数字] 开头）
        elif re.match(r'^\[\d+\]', text):
            label = "参考文献条目"
            confidence = 0.9

        # 摘要标题
        elif re.match(r'^摘要', text) and text_len < 80:
            label = "摘要标题"
            confidence = 0.9
            found_abstract_heading = True

        # 关键词
        elif re.match(r'^关键词', text):
            label = "关键词"
            confidence = 0.9
            found_keywords = True

        # 图表标题
        elif re.match(r'^(图|Fig|Figure|表|Table)\s*\d', text):
            label = "图表标题"
            confidence = 0.85

        # 标题检测：短文本 + 加粗
        elif is_bold and text_len < 60:
            # 判断标题级别
            if re.match(r'^\d+\s', text):  # "1 引言", "2 方法"
                label = "一级标题"
                confidence = 0.85
            elif re.match(r'^\d+\.\d+\s', text):  # "1.1 研究背景"
                # 检查是否有第三级
                if re.match(r'^\d+\.\d+\.\d+\s', text):
                    label = "三级标题"
                    confidence = 0.8
                else:
                    label = "二级标题"
                    confidence = 0.85
            elif font_size and font_size >= 14:
                label = "一级标题"
                confidence = 0.7
            elif font_size and font_size >= 12:
                label = "二级标题"
                confidence = 0.7
            else:
                label = "三级标题"
                confidence = 0.7
        else:
            # 摘要正文（在摘要标题之后、关键词之前）
            if found_abstract_heading and not found_keywords:
                label = "摘要正文"
                confidence = 0.7
            # 作者信息（在标题之后、摘要之前，短文本）
            elif found_first and not found_abstract_heading and text_len < 50:
                label = "作者信息"
                confidence = 0.6
            # 正文段落
            else:
                label = "正文段落"
                confidence = 0.6

        # 如果在参考文献之后且是 [数字] 格式，修正为参考文献条目
        if found_reference_heading and re.match(r'^\[\d+\]', text):
            label = "参考文献条目"
            confidence = 0.9

        labels.append({
            "index": i,
            "label": label,
            "confidence": confidence,
        })

    return labels


# ================================================================
#  构建结构地图
# ================================================================

def _build_structure_map(paragraphs, labels, method):
    """
    将段落和标注结果整理成结构化的论文结构地图。

    参数:
        paragraphs (list[dict]): 段落信息列表
        labels (list[dict]): 标注结果列表
        method (str): "llm" 或 "rule_based"

    返回:
        dict: 论文结构地图
    """
    # 1. 提取论文标题
    paper_title = ""
    for lbl in labels:
        if lbl["label"] == "论文大标题" and lbl["index"] < len(paragraphs):
            paper_title = paragraphs[lbl["index"]]["text"]
            break

    # 2. 构建 sections（按连续标签分组）
    sections = _build_sections(paragraphs, labels)

    # 3. 提取图表位置
    figures = []
    tables = []
    for lbl in labels:
        idx = lbl["index"]
        if idx >= len(paragraphs):
            continue
        text = paragraphs[idx]["text"]
        if lbl["label"] == "图表标题":
            if re.match(r'^(图|Fig|Figure)', text):
                figures.append({
                    "index": len(figures) + 1,
                    "title_paragraph": idx,
                    "caption": text,
                })
            elif re.match(r'^(表|Table)', text):
                tables.append({
                    "index": len(tables) + 1,
                    "title_paragraph": idx,
                    "caption": text,
                })

    # 4. 查找参考文献范围
    reference_start = None
    reference_end = None
    for lbl in labels:
        if lbl["label"] == "参考文献标题":
            reference_start = lbl["index"]
        if lbl["label"] == "参考文献条目":
            if reference_start is None:
                # 可能没有显式的参考文献标题，找第一个条目
                reference_start = lbl["index"]
            reference_end = lbl["index"] + 1  # 包括当前段落

    # 5. 计算平均置信度
    if labels:
        avg_confidence = sum(
            lbl.get("confidence", 0) for lbl in labels
        ) / len(labels)
    else:
        avg_confidence = 0.0

    # 6. 将 text 合并到 paragraph_labels 中
    enriched_labels = []
    for lbl in labels:
        enriched = dict(lbl)
        idx = lbl["index"]
        if idx < len(paragraphs):
            enriched["text"] = paragraphs[idx].get("text", "")
            enriched["current_format"] = paragraphs[idx].get("current_format", {})
        else:
            enriched["text"] = ""
            enriched["current_format"] = {}
        enriched_labels.append(enriched)

    result = {
        "method": method,
        "paper_title": paper_title,
        "confidence": round(avg_confidence, 2),
        "paragraph_labels": enriched_labels,
        "sections": sections,
        "figures": figures,
        "tables": tables,
        "reference_start": reference_start,
        "reference_end": reference_end,
    }

    logger.info(
        "结构地图构建完成 - 方法: %s, 标题: %s, 段落数: %d",
        method, paper_title[:30] if paper_title else "(空)", len(labels)
    )
    return result


def _build_sections(paragraphs, labels):
    """
    将连续相同标签的段落合并为章节。

    返回:
        list[dict]: 章节列表
    """
    if not labels:
        return []

    sections = []
    current_section = None

    for lbl in labels:
        idx = lbl["index"]
        if idx >= len(paragraphs):
            continue

        label = lbl["label"]
        text = paragraphs[idx]["text"]

        # 判断是否开始新章节
        is_heading = label in ("一级标题", "二级标题", "三级标题",
                               "摘要标题", "关键词", "参考文献标题",
                               "致谢", "附录标题")
        is_title = label == "论文大标题"
        is_abstract = label == "摘要正文"
        is_body = label == "正文段落"
        is_reference = label == "参考文献条目"

        if is_title or is_heading:
            # 新章节开始
            section_type = LABEL_TYPE_MAP.get(label, "body")
            current_section = {
                "label": label,
                "type": section_type,
                "paragraphs": [idx],
                "summary": text[:80] if text else label,
            }
            sections.append(current_section)

        elif is_abstract:
            # 合并到摘要章节
            _append_to_section(sections, "abstract", idx, label, text)

        elif is_reference:
            # 合并到参考文献章节
            _append_to_section(sections, "reference", idx, label, text)

        elif is_body:
            # 合并到最近的章节
            if current_section:
                current_section["paragraphs"].append(idx)
            else:
                # 如果前面没有章节，创建一个
                current_section = {
                    "label": "正文段落",
                    "type": "body",
                    "paragraphs": [idx],
                    "summary": text[:80] if text else "正文",
                }
                sections.append(current_section)

        else:
            # 其他类型（作者信息、图表标题等）
            section_type = LABEL_TYPE_MAP.get(label, "body")
            current_section = {
                "label": label,
                "type": section_type,
                "paragraphs": [idx],
                "summary": text[:80] if text else label,
            }
            sections.append(current_section)

    return sections


def _append_to_section(sections, section_type, para_idx, label, text):
    """将段落追加到指定类型的最后一个章节"""
    for sec in reversed(sections):
        if sec["type"] == section_type:
            sec["paragraphs"].append(para_idx)
            # 更新 summary 以包含更多内容
            if len(sec["summary"]) < 200 and text:
                sec["summary"] += " " + text[:100]
            return

    # 没找到匹配的章节，新建一个
    sections.append({
        "label": label,
        "type": section_type,
        "paragraphs": [para_idx],
        "summary": text[:80] if text else label,
    })
