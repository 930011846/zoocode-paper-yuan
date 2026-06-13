# -*- coding: utf-8 -*-
"""
论文格式自动排版 - Flask 后端主程序
提供文件上传、保存、分析、格式应用和下载功能
"""

import os
import json
import shutil
import logging
from flask import (
    Flask, request, jsonify, render_template, send_file
)
from werkzeug.utils import secure_filename

# 导入分析模块
try:
    from analyzer import analyze_template, get_target_format
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False
    get_target_format = None

# 导入论文内容分析器
try:
    from content_analyzer import analyze_paper
    CONTENT_ANALYZER_AVAILABLE = True
except ImportError:
    CONTENT_ANALYZER_AVAILABLE = False

# 导入格式应用函数
try:
    from utils import apply_format as utils_apply_format
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False

# 导入规则引擎
try:
    from rule_engine import get_rules, get_school_list, predict_paper_type, resolve_school, SCHOOL_KEY_TO_NAME
    RULE_ENGINE_AVAILABLE = True
except ImportError:
    RULE_ENGINE_AVAILABLE = False
    def resolve_school(s): return 'default'
    SCHOOL_KEY_TO_NAME = {}

# 导入合规检查
try:
    from checker import check_compliance
    CHECKER_AVAILABLE = True
except ImportError:
    CHECKER_AVAILABLE = False

# ---------- 配置 ----------
app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)
app.config['DEBUG'] = True
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
STRUCTURE_FILE = os.path.join(UPLOAD_DIR, 'paper_structure.json')
TEMPLATE_RULES_FILE = os.path.join(UPLOAD_DIR, 'template_rules.json')
FORMAT_DIFF_FILE = os.path.join(UPLOAD_DIR, 'format_diff.json')
FORMATTED_FILE = os.path.join(UPLOAD_DIR, 'formatted_paper.docx')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ---------- CORS ----------
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ---------- 辅助函数 ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'docx'


def clean_upload_dir():
    if not os.path.exists(UPLOAD_DIR):
        return
    for entry in os.listdir(UPLOAD_DIR):
        entry_path = os.path.join(UPLOAD_DIR, entry)
        try:
            if os.path.isfile(entry_path):
                os.remove(entry_path)
            elif os.path.isdir(entry_path):
                shutil.rmtree(entry_path)
        except Exception as e:
            logger.warning("删除文件失败: %s - %s", entry_path, e)


# ======================== 路由 ========================

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/review')
def review():
    """论文结构确认页"""
    return render_template('review.html')


@app.route('/upload', methods=['POST'])
def upload():
    """上传模板和论文文件"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    try:
        template_file = request.files.get('template')
        paper_file = request.files.get('paper')
        if not template_file or template_file.filename == '':
            return jsonify(success=False, message='请上传标准格式模板文件'), 400
        if not paper_file or paper_file.filename == '':
            return jsonify(success=False, message='请上传论文文件'), 400
        if not allowed_file(template_file.filename):
            return jsonify(success=False, message='模板文件必须是 .docx 格式'), 400
        if not allowed_file(paper_file.filename):
            return jsonify(success=False, message='论文文件必须是 .docx 格式'), 400

        template_filename = secure_filename(template_file.filename)
        paper_filename = secure_filename(paper_file.filename)
        template_path = os.path.join(UPLOAD_DIR, template_filename)
        paper_path = os.path.join(UPLOAD_DIR, paper_filename)
        template_file.save(template_path)
        paper_file.save(paper_path)

        logger.info("文件保存成功 - 模板: %s, 论文: %s", template_filename, paper_filename)
        return jsonify(
            success=True,
            template=template_path,
            paper=paper_path,
            message='文件上传成功，等待排版处理'
        )
    except Exception as e:
        logger.error("上传处理出错: %s", str(e), exc_info=True)
        return jsonify(success=False, message=f'上传失败：{str(e)}'), 500


@app.route('/cleanup', methods=['POST'])
def cleanup():
    """清理临时文件"""
    try:
        clean_upload_dir()
        return jsonify(success=True, message='临时文件已清理')
    except Exception as e:
        return jsonify(success=False, message=f'清理失败：{str(e)}'), 500


@app.route('/analyze-template', methods=['POST'])
def analyze_template_route():
    """分析模板格式"""
    if not ANALYZER_AVAILABLE:
        return jsonify(success=False, message='分析模块不可用'), 500
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    try:
        template_file = request.files.get('template')
        if not template_file or template_file.filename == '':
            return jsonify(success=False, message='请上传模板文件'), 400
        if not allowed_file(template_file.filename):
            return jsonify(success=False, message='模板文件必须是 .docx 格式'), 400
        template_filename = secure_filename(template_file.filename)
        template_path = os.path.join(UPLOAD_DIR, template_filename)
        template_file.save(template_path)
        result = analyze_template(template_path)
        clean_upload_dir()
        return jsonify(success=True, data=result)
    except Exception as e:
        logger.error("模板分析出错: %s", str(e), exc_info=True)
        clean_upload_dir()
        return jsonify(success=False, message=f'模板分析失败：{str(e)}'), 500


@app.route('/analyze-paper', methods=['POST'])
def analyze_paper_route():
    """
    论文分析路由：分析后保存 paper_structure 到 JSON 文件，
    供 /review 和 /get-paper-structure 使用。
    """
    if not CONTENT_ANALYZER_AVAILABLE:
        return jsonify(success=False, message='论文分析模块不可用'), 500
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    try:
        template_file = request.files.get('template')
        paper_file = request.files.get('paper')
        form_data = request.form.to_dict()
        use_national = form_data.get('use_national_standard') == 'true'
        school_raw = form_data.get('school', '')
        paper_type = form_data.get('paper_type', '')

        # 解析学校（支持中文名和键名）
        school_key = resolve_school(school_raw) if school_raw else 'default'
        is_builtin_school = (school_key not in ('default', 'custom'))

        if not paper_file or paper_file.filename == '':
            return jsonify(success=False, message='请上传论文文件'), 400
        if not allowed_file(paper_file.filename):
            return jsonify(success=False, message='论文文件必须是 .docx 格式'), 400

        paper_filename = secure_filename(paper_file.filename)
        paper_path = os.path.join(UPLOAD_DIR, paper_filename)
        paper_file.save(paper_path)

        # 如果是内置学校，不需要模板文件
        template_filename = ''
        template_path = ''
        if not is_builtin_school:
            if template_file and template_file.filename:
                if not allowed_file(template_file.filename):
                    return jsonify(success=False, message='模板文件必须是 .docx 格式'), 400
                template_filename = secure_filename(template_file.filename)
                template_path = os.path.join(UPLOAD_DIR, template_filename)
                template_file.save(template_path)
            elif not use_national:
                return jsonify(success=False, message='请上传模板文件、勾选国家标准或选择内置学校'), 400

        logger.info("分析论文: paper=%s, school=%s(%s), type=%s, template=%s",
                     paper_filename, school_key, school_raw, paper_type, template_filename)

        template_rules = None

        # 【规则引擎】内置学校 → 使用 rule_engine 获取规则
        if RULE_ENGINE_AVAILABLE and is_builtin_school:
            try:
                effective_paper_type = paper_type if paper_type else None
                engine_rules = get_rules(school=school_key, paper_type=effective_paper_type)
                converted = _convert_engine_rules(engine_rules)
                if converted:
                    template_rules = converted
                    school_name = SCHOOL_KEY_TO_NAME.get(school_key, school_key)
                    logger.info("规则引擎加载: %s, type=%s", school_name, effective_paper_type)
            except Exception as e:
                logger.warning("规则引擎加载失败: %s", e)
        elif use_national and RULE_ENGINE_AVAILABLE:
            # 国家标准 → rule_engine 国标
            try:
                engine_rules = get_rules(school='default')
                converted = _convert_engine_rules(engine_rules)
                if converted:
                    template_rules = converted
            except Exception as e:
                logger.warning("国标规则加载失败: %s", e)
        elif ANALYZER_AVAILABLE and template_path:
            # 自定义模板 → 解析模板
            try:
                template_rules = analyze_template(template_path)
            except Exception as e:
                logger.warning("模板格式分析失败（不影响论文分析）: %s", e)

        paper_structure = analyze_paper(paper_path, template_rules)
        logger.info("论文分析完成 - 方法: %s, 置信度: %s",
                    paper_structure.get("method", "unknown"),
                    paper_structure.get("confidence", 0))

        # 保存 paper_structure.json
        save_data = {
            'paper_structure': paper_structure,
            'files': {
                'template': template_filename,
                'paper': paper_filename,
            }
        }
        with open(STRUCTURE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        # 保存 template_rules.json（国标模式也保存）
        if template_rules:
            with open(TEMPLATE_RULES_FILE, 'w', encoding='utf-8') as f:
                json.dump(template_rules, f, ensure_ascii=False, indent=2)

        logger.info("数据已保存到 %s 和 %s", STRUCTURE_FILE, TEMPLATE_RULES_FILE)

        return jsonify(
            success=True,
            template_rules=template_rules,
            paper_structure=paper_structure,
            use_national_standard=use_national,
        )
    except Exception as e:
        logger.error("论文分析出错: %s", str(e), exc_info=True)
        clean_upload_dir()
        return jsonify(success=False, message=f'论文分析失败：{str(e)}'), 500


@app.route('/get-paper-structure', methods=['GET'])
def get_paper_structure():
    """
    获取论文结构数据，为每个段落计算 target_format。
    返回含格式对比的完整数据供 /review 渲染。
    """
    if not os.path.exists(STRUCTURE_FILE):
        return jsonify(success=False, message='未找到论文结构数据，请先进行分析'), 404
    try:
        with open(STRUCTURE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 读取模板规则
        template_rules = None
        if os.path.exists(TEMPLATE_RULES_FILE):
            try:
                with open(TEMPLATE_RULES_FILE, 'r', encoding='utf-8') as f:
                    template_rules = json.load(f)
            except Exception as e:
                logger.warning("读取 template_rules.json 失败: %s", e)

        paper_structure = data.get('paper_structure', {})
        para_labels = paper_structure.get('paragraph_labels', [])

        # 为每个段落计算 target_format 和 format_diffs
        enhanced_paras = []
        for pl in para_labels:
            para = dict(pl)
            label = para.get('label', '正文段落')
            cf = para.get('current_format', {})
            if get_target_format:
                para['target_format'] = get_target_format(label, template_rules)
            else:
                para['target_format'] = None
            tf = para.get('target_format', {})

            # 计算 format_diffs
            diffs = []
            tf_ch = tf.get('chinese_font', {}) if tf else {}
            tf_para = tf.get('paragraph', {}) if tf else {}

            if cf.get('font_name') and tf_ch.get('name') and cf['font_name'] != tf_ch['name']:
                diffs.append('font_name')
            if cf.get('font_size') and tf_ch.get('size'):
                diffs.append('font_size')
            if cf.get('bold') is not None and tf_ch.get('bold') is not None and cf['bold'] != tf_ch['bold']:
                diffs.append('bold')
            if cf.get('italic') is not None and tf_ch.get('bold') is not None and cf.get('italic') != tf_ch.get('bold'):
                diffs.append('italic')
            if cf.get('alignment') and tf_para.get('alignment') and cf['alignment'] != tf_para['alignment']:
                diffs.append('alignment')
            if tf_para.get('first_line_indent') or tf_para.get('space_before') or tf_para.get('space_after'):
                diffs.append('spacing')

            para['format_diffs'] = diffs
            enhanced_paras.append(para)

        logger.info(
            "/get-paper-structure 返回 %d 个段落（含 format_diffs）",
            len(enhanced_paras)
        )

        # 构建带 children 的 sections
        raw_sections = paper_structure.get('sections', [])
        sections_with_children = _build_section_tree(raw_sections)

        # 获取文件路径（供前端提交时使用）
        files_info = data.get('files', {})
        template_filename = files_info.get('template', '')
        paper_filename = files_info.get('paper', '')

        result = {
            'sections': sections_with_children,
            'paragraphs': enhanced_paras,
            'figures': paper_structure.get('figures', []),
            'tables': paper_structure.get('tables', []),
            'method': paper_structure.get('method', 'rule_based'),
            'confidence': paper_structure.get('confidence', 0),
            'paper_title': paper_structure.get('paper_title', ''),
            'reference_start': paper_structure.get('reference_start'),
            'reference_end': paper_structure.get('reference_end'),
            'files': {
                'template': template_filename,
                'paper': paper_filename,
            },
        }

        return jsonify(success=True, data=result)

    except Exception as e:
        logger.error("读取论文结构数据失败: %s", str(e), exc_info=True)
        return jsonify(success=False, message=f'读取数据失败：{str(e)}'), 500


def _build_section_tree(raw_sections):
    """
    将扁平的 sections 列表转换为层级树结构。
    相邻的 heading2 会被归为前一个 heading1 的 children。
    """
    tree = []
    current_parent = None

    for sec in raw_sections:
        sec_type = sec.get('type', '')
        node = dict(sec)
        node['children'] = []

        if sec_type == 'heading1':
            current_parent = node
            tree.append(node)
        elif sec_type == 'heading2' and current_parent is not None:
            current_parent['children'].append(node)
        elif sec_type == 'heading2' and current_parent is None:
            tree.append(node)
        else:
            tree.append(node)

    return tree


@app.route('/apply-format', methods=['POST'])
def apply_format_route():
    """
    应用格式路由：接收确认后的标签映射。
    1. 生成 format_diff.json（格式对比数据）
    2. 调用 utils.apply_format 生成 formatted_paper.docx
    """
    import traceback
    print("=" * 60)
    print("[apply-format] ====== 开始处理 ======")

    try:
        req_data = request.get_json(force=True)
        user_labels = req_data.get('labels', {})
        print(f"[apply-format] 1. 收到请求, labels 数: {len(user_labels)}, labels内容: {dict(list(user_labels.items())[:5])}")
        logger.info("收到格式应用请求，共 %d 个段落标签", len(user_labels))

        # 1. 读取论文结构数据
        print(f"[apply-format] 2. 读取 {STRUCTURE_FILE} ...")
        if not os.path.exists(STRUCTURE_FILE):
            print("[apply-format] 错误: paper_structure.json 不存在")
            return jsonify(success=False, message='未找到论文结构数据，请先分析论文'), 400
        with open(STRUCTURE_FILE, 'r', encoding='utf-8') as f:
            paper_data = json.load(f)
        print(f"[apply-format] 3. paper_structure.json 读取成功")

        # 2. 读取模板规则
        template_rules = None
        if os.path.exists(TEMPLATE_RULES_FILE):
            with open(TEMPLATE_RULES_FILE, 'r', encoding='utf-8') as f:
                template_rules = json.load(f)
            print(f"[apply-format] 4. template_rules.json 读取成功")
        else:
            print(f"[apply-format] 4. template_rules.json 不存在，跳过")

        # 3. 获取原始论文路径
        files_info = paper_data.get('files', {})
        paper_filename = files_info.get('paper', 'paper.docx')
        paper_path = os.path.join(UPLOAD_DIR, paper_filename)
        template_filename = files_info.get('template', 'template.docx')
        template_path = os.path.join(UPLOAD_DIR, template_filename)

        print(f"[apply-format] 5. paper_path={paper_path}, 存在={os.path.exists(paper_path)}")
        print(f"[apply-format]    template_path={template_path}, 存在={os.path.exists(template_path)}")

        paper_structure = paper_data.get('paper_structure', {})
        para_labels = paper_structure.get('paragraph_labels', [])
        paper_title = paper_structure.get('paper_title', '')
        print(f"[apply-format] 6. para_labels 数: {len(para_labels)}")

        # 4. 构建完整 labels 字典
        str_labels = {}
        for pl in para_labels:
            str_labels[str(pl['index'])] = pl.get('label', '正文段落')
        for k, v in user_labels.items():
            str_labels[str(k)] = v
        print(f"[apply-format] 7. 合并后标签数: {len(str_labels)} (用户修改 {len(user_labels)})")

        # 5. 调用 utils.apply_format 生成格式化文档
        format_ok = False
        if UTILS_AVAILABLE:
            print(f"[apply-format] 8. 检查 paper_path 是否存在: {os.path.exists(paper_path)}")
            if os.path.exists(paper_path):
                print(f"[apply-format] 9. 开始调用 utils.apply_format ...")
                print(f"[apply-format]    template_rules 类型: {type(template_rules).__name__}")
                try:
                    utils_apply_format(
                        template_path=template_path,
                        paper_path=paper_path,
                        output_path=FORMATTED_FILE,
                        labels=str_labels,
                        template_rules=template_rules,
                    )
                    format_ok = os.path.exists(FORMATTED_FILE)
                    print(f"[apply-format] 10. utils.apply_format 完成, 输出文件存在={format_ok}")
                    logger.info("格式化文档已生成: %s", FORMATTED_FILE)
                except Exception as e:
                    print(f"[apply-format] 错误: utils.apply_format 抛出异常: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    logger.error("格式应用失败: %s", str(e), exc_info=True)
                    # 不阻断流程
            else:
                print(f"[apply-format] 错误: paper_path 不存在: {paper_path}")
                logger.warning("论文文件不存在: %s", paper_path)
        else:
            print(f"[apply-format] UTILS_AVAILABLE={UTILS_AVAILABLE}，跳过格式应用")
            logger.warning("utils.apply_format 不可用")

        # 6. 生成 format_diff.json
        print(f"[apply-format] 11. 开始生成 format_diff.json ...")
        paragraphs = []
        modified_count = 0
        total_changes = 0

        for pl in para_labels:
            para = dict(pl)
            idx = str(para['index'])

            if idx in str_labels:
                para['label'] = str_labels[idx]

            label = para.get('label', '正文段落')
            cf = para.get('current_format', {})
            if get_target_format:
                para['target_format'] = get_target_format(label, template_rules)
            else:
                para['target_format'] = {}

            tf = para.get('target_format', {})
            tf_ch = tf.get('chinese_font', {}) if tf else {}
            tf_para = tf.get('paragraph', {}) if tf else {}

            diffs = []
            if cf.get('font_name') and tf_ch.get('name') and cf['font_name'] != tf_ch['name']:
                diffs.append('font_name')
            if cf.get('font_size') and tf_ch.get('size'):
                diffs.append('font_size')
            if cf.get('bold') is not None and tf_ch.get('bold') is not None and cf['bold'] != tf_ch['bold']:
                diffs.append('bold')
            if cf.get('alignment') and tf_para.get('alignment') and cf['alignment'] != tf_para['alignment']:
                diffs.append('alignment')
            if tf_para.get('first_line_indent') or tf_para.get('space_before') or tf_para.get('space_after'):
                diffs.append('spacing')

            para['format_diffs'] = diffs
            if diffs:
                modified_count += 1
                total_changes += len(diffs)

            paragraphs.append(para)

        print(f"[apply-format] 12. format_diff 计算完成: modified={modified_count}, changes={total_changes}")

        diff_data = {
            'paper_title': paper_title,
            'paragraphs': paragraphs,
            'summary': {
                'total_paragraphs': len(paragraphs),
                'modified_paragraphs': modified_count,
                'total_changes': total_changes,
            }
        }
        with open(FORMAT_DIFF_FILE, 'w', encoding='utf-8') as f:
            json.dump(diff_data, f, ensure_ascii=False, indent=2)
        print(f"[apply-format] 13. format_diff.json 已保存")

        print(f"[apply-format] ====== 成功返回 ======")
        print("=" * 60)
        return jsonify(
            success=True,
            message='格式应用完成',
            modified_count=modified_count,
            total_changes=total_changes,
            output_file=os.path.basename(FORMATTED_FILE) if os.path.exists(FORMATTED_FILE) else None,
            redirect='/preview',
        )
    except Exception as e:
        print(f"[apply-format] ====== 异常捕获 ======")
        print(f"[apply-format] 异常类型: {type(e).__name__}")
        print(f"[apply-format] 异常信息: {e}")
        traceback.print_exc()
        print("=" * 60)
        logger.error("格式应用出错: %s", str(e), exc_info=True)
        return jsonify(success=False, message=f'格式应用失败：{str(e)}'), 500


@app.route('/get-format-diff', methods=['GET'])
def get_format_diff():
    """获取格式对比数据和合规检查报告"""
    if not os.path.exists(FORMAT_DIFF_FILE):
        return jsonify(success=False, message='未找到格式对比数据'), 404
    try:
        with open(FORMAT_DIFF_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 同时读取合规报告
        report = None
        report_file = os.path.join(UPLOAD_DIR, 'compliance_report.json')
        if os.path.exists(report_file):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
            except Exception:
                pass

        result = {
            'paragraphs': data.get('paragraphs', []),
            'summary': data.get('summary', {}),
            'paper_title': data.get('paper_title', ''),
            'compliance_report': report,
        }
        return jsonify(success=True, data=result)
    except Exception as e:
        logger.error("读取格式对比数据失败: %s", str(e))
        return jsonify(success=False, message=f'读取失败：{str(e)}'), 500


@app.route('/download', methods=['GET'])
def download():
    """下载格式化后的论文"""
    if not os.path.exists(FORMATTED_FILE):
        return jsonify(success=False, message='未找到格式化后的论文，请先排版'), 404

    # 从文件信息中获取原论文名
    download_name = 'formatted_paper.docx'
    if os.path.exists(STRUCTURE_FILE):
        try:
            with open(STRUCTURE_FILE, 'r', encoding='utf-8') as f:
                sd = json.load(f)
            paper_fn = sd.get('files', {}).get('paper', 'paper.docx')
            name, ext = os.path.splitext(paper_fn)
            download_name = f'formatted_{name}{ext}'
        except Exception:
            pass

    return send_file(
        FORMATTED_FILE,
        as_attachment=True,
        download_name=download_name,
        mimetype='application/vnd.openxmlformats-officedocument.'
                 'wordprocessingml.document'
    )


@app.route('/preview', methods=['GET'])
def preview():
    """预览页：展示双栏格式对比"""
    diff_data = None
    has_formatted = os.path.exists(FORMATTED_FILE)
    if os.path.exists(FORMAT_DIFF_FILE):
        try:
            with open(FORMAT_DIFF_FILE, 'r', encoding='utf-8') as f:
                diff_data = json.load(f)
        except Exception as e:
            logger.warning("读取格式对比数据失败: %s", e)

    # 读取合规报告
    report = None
    report_file = os.path.join(UPLOAD_DIR, 'compliance_report.json')
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
        except Exception as e:
            logger.warning("读取合规报告失败: %s", e)

    return render_template('preview.html', diff_data=diff_data, has_formatted=has_formatted, report=report)


# ---------- OPTIONS ----------
@app.route('/upload', methods=['OPTIONS'])
@app.route('/cleanup', methods=['OPTIONS'])
@app.route('/analyze-template', methods=['OPTIONS'])
@app.route('/analyze-paper', methods=['OPTIONS'])
@app.route('/predict-paper-type', methods=['POST'])
def predict_paper_type_route():
    """预判论文类型"""
    if not RULE_ENGINE_AVAILABLE:
        return jsonify(success=False, message='规则引擎不可用'), 500
    try:
        paper_file = request.files.get('paper')
        if not paper_file or paper_file.filename == '':
            return jsonify(success=False, message='请上传论文文件'), 400

        from content_analyzer import extract_docx_text
        paper_path = os.path.join(UPLOAD_DIR, secure_filename(paper_file.filename))
        paper_file.save(paper_path)
        text = extract_docx_text(paper_path)
        os.remove(paper_path)

        paragraphs = [p for p in text.split('\n') if p.strip()]
        result = predict_paper_type(paragraphs)
        return jsonify(success=True, data=result)
    except Exception as e:
        logger.error("预判出错: %s", str(e), exc_info=True)
        return jsonify(success=False, message=f'预判失败：{str(e)}'), 500


@app.route('/get-rules', methods=['GET', 'POST'])
def get_rules_route():
    """获取指定学校+类型的规则（支持 GET 和 POST）"""
    if not RULE_ENGINE_AVAILABLE:
        return jsonify(success=False, message='规则引擎不可用'), 500
    try:
        if request.method == 'GET':
            school = request.args.get('school', 'default')
            paper_type = request.args.get('paper_type')
        else:
            req = request.get_json(force=True)
            school = req.get('school', 'default')
            paper_type = req.get('paper_type')
        rules = get_rules(school=school, paper_type=paper_type)
        return jsonify(success=True, data=rules)
    except Exception as e:
        logger.error("获取规则出错: %s", str(e))
        return jsonify(success=False, message=f'获取失败：{str(e)}'), 500


@app.route('/get-schools', methods=['GET'])
def get_schools_route():
    """获取可用学校列表"""
    if not RULE_ENGINE_AVAILABLE:
        return jsonify(success=False, message='规则引擎不可用'), 500
    try:
        schools = get_school_list()
        return jsonify(success=True, data=[{'key': k, 'name': n} for k, n in schools])
    except Exception as e:
        logger.error("获取学校列表出错: %s", str(e))
        return jsonify(success=False, message=f'获取失败：{str(e)}'), 500


def _convert_engine_rules(engine_rules):
    """将 rule_engine 的规则结构转换为 analyzer 兼容的 style_rules 格式"""
    if not engine_rules:
        return None
    # 映射 rule_engine 键名 -> style_rules 标签名
    key_map = {
        'paper_title': '论文大标题',
        'author_info': '作者信息',
        'abstract_heading': '摘要标题',
        'abstract_body': '摘要正文',
        'keywords': '关键词',
        'heading1': '一级标题',
        'heading2': '二级标题',
        'heading3': '三级标题',
        'body': '正文',
        'caption': '图表标题',
        'reference_heading': '参考文献标题',
        'reference_entry': '参考文献条目',
        'header': '页眉',
        'footer': '页脚',
    }
    style_rules = {}
    for eng_key, rule_label in key_map.items():
        rule_data = engine_rules.get(eng_key)
        if rule_data:
            ch_font = rule_data.get('chinese_font') or {}
            w_font = rule_data.get('western_font') or {}
            para = rule_data.get('paragraph') or {}
            style_rules[rule_label] = {
                'chinese_font': {'name': ch_font.get('name'), 'size': ch_font.get('size'), 'bold': ch_font.get('bold', False)},
                'western_font': {'name': w_font.get('name'), 'size': w_font.get('size'), 'bold': w_font.get('bold', False)},
                'paragraph': {
                    'alignment': para.get('alignment'),
                    'first_line_indent': para.get('first_line_indent'),
                    'line_spacing': para.get('line_spacing'),
                    'space_before': para.get('space_before'),
                    'space_after': para.get('space_after'),
                },
            }
    result = {
        'document_title': f'规则引擎 - {engine_rules.get("school", "未知")}',
        'style_rules': style_rules,
        'default_chinese_font': engine_rules.get('default_chinese_font'),
        'default_western_font': engine_rules.get('default_western_font'),
        'line_spacing': engine_rules.get('line_spacing'),
        'page_margins': engine_rules.get('page_margins'),
    }
    return result


@app.route('/check-compliance', methods=['POST'])
def check_compliance_route():
    """运行合规性检查"""
    if not CHECKER_AVAILABLE:
        return jsonify(success=False, message='合规检查模块不可用'), 500
    try:
        req = request.get_json(force=True)
        school = req.get('school', 'default')
        paper_type = req.get('paper_type', 'research')

        # 读取段落数据
        if not os.path.exists(STRUCTURE_FILE):
            return jsonify(success=False, message='未找到论文数据'), 404
        with open(STRUCTURE_FILE, 'r', encoding='utf-8') as f:
            paper_data = json.load(f)
        paras = paper_data.get('paper_structure', {}).get('paragraph_labels', [])

        # 读取规则
        rules = None
        if os.path.exists(TEMPLATE_RULES_FILE):
            with open(TEMPLATE_RULES_FILE, 'r', encoding='utf-8') as f:
                rules = json.load(f)

        report = check_compliance(paras, rules, paper_type)
        return jsonify(success=True, data=report)
    except Exception as e:
        logger.error("合规检查出错: %s", str(e), exc_info=True)
        return jsonify(success=False, message=f'检查失败：{str(e)}'), 500


@app.route('/apply-format', methods=['OPTIONS'])
@app.route('/preview', methods=['OPTIONS'])
@app.route('/get-format-diff', methods=['OPTIONS'])
@app.route('/download', methods=['OPTIONS'])
@app.route('/predict-paper-type', methods=['OPTIONS'])
@app.route('/get-rules', methods=['OPTIONS'])
@app.route('/get-schools', methods=['OPTIONS'])
@app.route('/check-compliance', methods=['OPTIONS'])
def handle_options():
    return jsonify(success=True), 200


# ---------- 启动 ----------
def get_local_ip():
    """自动获取本机局域网 IP 地址"""
    import socket
    try:
        # 创建一个 UDP socket 连接到外部地址（无需真实连接）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # 备选方案：遍历所有网络接口
            ip = socket.gethostbyname(socket.gethostname())
            if ip and ip != '127.0.0.1':
                return ip
        except Exception:
            pass
        # 最终备选
        return '127.0.0.1'


if __name__ == '__main__':
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Railway / Render 部署: 端口从环境变量 PORT 读取, debug 需设为 False
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    local_ip = get_local_ip()

    print()
    print('=' * 48)
    print(f'  📱 手机访问地址: http://{local_ip}:{port}')
    print(f'  💻 电脑访问地址: http://127.0.0.1:{port}')
    print('=' * 48)
    print()

    logger.info("启动 Flask 服务器: http://0.0.0.0:%d (debug=%s)", port, debug_mode)
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
