/* ============================================================
   论文格式确认页面 (review.html)
   依赖后端 GET /get-paper-structure 接口
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    console.log('[Review] ====== 初始化开始 ======');

    // ======================== 标签颜色映射 ========================
    var LABEL_COLORS = {
        '论文大标题': '#4A90D9',
        '作者信息': '#8C8C8C',
        '摘要标题': '#52C41A',
        '摘要正文': '#52C41A',
        '关键词': '#52C41A',
        '一级标题': '#FAAD14',
        '二级标题': '#FA8C16',
        '三级标题': '#D46B08',
        '正文段落': '#D9D9D9',
        '图表标题': '#FF4D4F',
        '参考文献标题': '#722ED1',
        '参考文献条目': '#722ED1',
        '致谢': '#13C2C2',
        '附录标题': '#13C2C2',
        '附录内容': '#13C2C2',
    };

    var ALL_LABELS = Object.keys(LABEL_COLORS);

    // ======================== DOM 引用 ========================
    var sidebar = document.getElementById('sidebar');
    var previewPanel = document.getElementById('previewPanel');
    var btnReAnalyze = document.getElementById('btnReAnalyze');
    var btnConfirm = document.getElementById('btnConfirm');
    var bottomStatus = document.getElementById('bottomStatus');
    var paraCountEl = document.getElementById('paraCount');

    if (!sidebar) console.error('[Review] #sidebar 不存在');
    if (!previewPanel) console.error('[Review] #previewPanel 不存在');

    // ======================== 状态 ========================
    var sections = [];
    var paragraphs = [];
    var userLabels = {};

    // ======================== 获取数据 ========================
    console.log('[Review] 正在请求 GET /get-paper-structure ...');

    fetch('/get-paper-structure')
        .then(function (res) {
            console.log('[Review] 响应状态码:', res.status);
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
        })
        .then(function (result) {
            console.log('[Review] 数据接收到, success:', result.success);

            if (!result.success) {
                previewPanel.innerHTML = '<div style="padding:40px;color:#FF4D4F;text-align:center;">❌ ' +
                    escapeHtml(result.message || '服务器返回错误') + '</div>';
                return;
            }

            var data = result.data;
            if (!data) {
                previewPanel.innerHTML = '<div style="padding:40px;color:#999;text-align:center;">⚠️ 数据为空</div>';
                return;
            }

            sections = data.sections || [];
            paragraphs = data.paragraphs || [];
            window.__filePaths = data.files || {};

            console.log('[Review] 段落数: ' + paragraphs.length + ', 章节数: ' + sections.length);
            console.log('[Review] 文件路径:', window.__filePaths);

            if (paragraphs.length > 0) {
                console.log('[Review] 首个段落示例:', JSON.stringify(paragraphs[0]).substring(0, 300));
            }

            // 更新底部状态
            if (paraCountEl) paraCountEl.textContent = paragraphs.length;
            if (bottomStatus) bottomStatus.textContent = '共 ' + paragraphs.length + ' 个段落';

            // 渲染
            buildTOC(sections);
            renderDocument(paragraphs);

            console.log('[Review] ====== 渲染完成 ======');
        })
        .catch(function (err) {
            console.error('[Review] 请求失败:', err.message);
            previewPanel.innerHTML = '<div style="padding:40px;color:#FF4D4F;text-align:center;">❌ 加载失败: ' +
                escapeHtml(err.message) + '</div>';
        });

    // ======================== 绑定底部按钮 ========================
    if (btnReAnalyze) {
        btnReAnalyze.addEventListener('click', function () {
            console.log('[Review] 点击重新分析，跳转首页');
            window.location.href = '/';
        });
    }

    if (btnConfirm) {
        btnConfirm.addEventListener('click', doConfirm);
    }

    // （筛选功能已移除）

    // ================================================================
    //  buildTOC(sections) — 递归构建层级目录树
    //  每个节点: color dot + label + expand arrow (▶/▼) if has children
    //  使用 data-level 控制缩进
    // ================================================================
    function buildTOC(sections) {
        console.log('[Review] buildTOC 开始, sections 数量:', sections.length);

        if (!sidebar) return;

        if (!sections || sections.length === 0) {
            sidebar.innerHTML = '<div class="sidebar-title">📂 论文结构目录</div>' +
                '<div style="padding:20px;color:#999;text-align:center;">暂无章节数据</div>';
            return;
        }

        var html = '<div class="sidebar-title">📂 论文结构目录</div>';
        html += '<div class="tree-container">';

        for (var i = 0; i < sections.length; i++) {
            html += buildTreeItem(sections[i], 0);
        }

        html += '</div>';
        sidebar.innerHTML = html;

        console.log('[Review] buildTOC 完成');

        // 事件委托: 树节点点击
        sidebar.addEventListener('click', function (e) {
            var treeItem = e.target.closest('.tree-item');
            if (!treeItem) return;

            var arrow = e.target.closest('.tree-arrow');
            if (arrow) {
                // 展开/折叠
                var childrenContainer = treeItem.nextElementSibling;
                if (childrenContainer && childrenContainer.classList.contains('tree-children')) {
                    var isCollapsed = childrenContainer.classList.toggle('collapsed');
                    arrow.classList.toggle('collapsed');
                    console.log('[Review] 切换展开/折叠:', isCollapsed ? '折叠' : '展开');
                }
                return;
            }

            // 滚动到段落
            var paraIndex = treeItem.dataset.para;
            if (paraIndex !== undefined) {
                var idx = parseInt(paraIndex);
                console.log('[Review] 目录点击 -> 段落 #' + idx);
                scrollToParagraph(idx);
                // 高亮当前节点
                sidebar.querySelectorAll('.tree-item').forEach(function (el) {
                    el.classList.remove('active');
                });
                treeItem.classList.add('active');
            }
        });
    }

    // 递归构建单个树节点
    function buildTreeItem(sec, level) {
        var label = sec.label || '未知';
        var color = LABEL_COLORS[label] || '#999';
        var firstPara = (sec.paragraphs && sec.paragraphs.length > 0) ? sec.paragraphs[0] : -1;
        var paraCount = sec.paragraphs ? sec.paragraphs.length : 0;
        var hasChildren = sec.children && sec.children.length > 0;

        var html = '';

        // 节点行
        html += '<div class="tree-item" data-level="' + level + '" data-para="' + firstPara + '">';

        // 展开/折叠箭头 或 占位符
        if (hasChildren) {
            html += '<span class="tree-arrow">▶</span>';
        } else {
            html += '<span class="tree-arrow-placeholder"></span>';
        }

        // 颜色圆点
        html += '<span class="tree-dot" style="background:' + color + ';"></span>';

        // 标签文字
        html += '<span class="tree-label">' + escapeHtml(label) + '</span>';

        // 段落计数
        html += '<span class="tree-count">(' + paraCount + ')</span>';

        html += '</div>';

        // 子节点容器
        if (hasChildren) {
            html += '<div class="tree-children">';
            for (var i = 0; i < sec.children.length; i++) {
                html += buildTreeItem(sec.children[i], level + 1);
            }
            html += '</div>';
        }

        return html;
    }

    // ================================================================
    //  renderDocument(paragraphs)
    //  每个段落渲染为 .paragraph-block, 包含:
    //  - border-left 颜色
    //  - .para-badge 标签徽章
    //  - .paragraph-text <p> 文本
    //  - 基于 format_diffs 的格式差异标记
    // ================================================================
    function renderDocument(paragraphs) {
        console.log('[Review] renderDocument 开始, 段落数:', paragraphs.length);

        if (!previewPanel) return;

        if (!paragraphs || paragraphs.length === 0) {
            previewPanel.innerHTML = '<div style="padding:40px;color:#999;text-align:center;">⚠️ 暂无段落数据</div>';
            return;
        }

        var html = '';

        for (var i = 0; i < paragraphs.length; i++) {
            var para = paragraphs[i];
            var idx = para.index;
            var text = para.text || '';
            var label = userLabels[idx] || para.label || '正文段落';
            var color = LABEL_COLORS[label] || '#999';
            var diffs = para.format_diffs || [];

            // 调试前5个段落
            if (i < 5) {
                console.log('[Review]   段落#' + idx + ' label=' + label +
                    ' text="' + text.substring(0, 30) + '" diffs=' + JSON.stringify(diffs));
            }

            html += '<div class="paragraph-block" id="p-' + idx +
                    '" data-index="' + idx +
                    '" data-label="' + escapeAttr(label) +
                    '" style="border-left-color: ' + color + ';">';

            // 标签徽章
            html += '  <span class="para-badge" style="background:' + color + ';">' +
                    escapeHtml(label) + '</span>';

            // 段落编号
            html += '  <span class="para-index">#' + idx + '</span>';

            // 格式差异标记 (内联)
            if (diffs.length > 0) {
                html += '  <span class="diff-markers">' + formatDiffHtml(diffs) + '</span>';
            }

            // 段落文本 — 核心内容，使用 p.paragraph-text
            if (text) {
                html += '  <p class="paragraph-text">' + escapeHtml(text) + '</p>';
            } else {
                html += '  <p class="paragraph-text empty">(空段落)</p>';
            }

            // 格式差异摘要条
            if (diffs.length > 0) {
                html += '  <div class="diff-summary">' + formatDiffSummary(diffs, para) + '</div>';
            }

            html += '</div>';
        }

        previewPanel.innerHTML = html;

        var blocks = previewPanel.querySelectorAll('.paragraph-block');
        console.log('[Review] renderDocument 完成, 段落块数:', blocks.length);

        // 事件委托: 点击段落块弹出编辑浮窗
        previewPanel.addEventListener('click', function (e) {
            // 如果点击的是段落块本身或其内部 (但不包含编辑浮窗内部)
            var block = e.target.closest('.paragraph-block');
            if (block) {
                // 不要阻止事件处理浮窗内部
                if (e.target.closest('.para-popup') || e.target.closest('.tag-dropdown')) return;
                var idx = parseInt(block.dataset.index);
                console.log('[Review] 段落块点击 #' + idx);
                showEditPopup(block, idx);
            }
        });
    }

    // ================================================================
    //  formatDiffHtml(diffs) — 将 format_diffs 数组渲染为内联标记
    //  返回内联 span 字符串
    // ================================================================
    function formatDiffHtml(diffs) {
        if (!diffs || diffs.length === 0) return '';

        var parts = [];
        for (var i = 0; i < diffs.length; i++) {
            var d = diffs[i];
            var cls = 'diff-' + d.replace(/_/g, '-');
            var label = getDiffLabel(d);
            parts.push('<span class="' + cls + '" title="' + escapeAttr(label) + '">' +
                       escapeHtml(label) + '</span>');
        }
        return parts.join(' ');
    }

    // ================================================================
    //  formatDiffSummary(diffs, para) — 底部差异摘要条
    // ================================================================
    function formatDiffSummary(diffs, para) {
        if (!diffs || diffs.length === 0) return '';

        var parts = [];
        for (var i = 0; i < diffs.length; i++) {
            var d = diffs[i];
            var label = getDiffLabel(d);
            var cls = d.replace(/_/g, '-');
            var detail = getDiffDetail(d, para);
            parts.push('<span class="diff-tag ' + cls + '" title="' + escapeAttr(detail) + '">' +
                       escapeHtml(label) + '</span>');
        }
        return parts.join(' ');
    }

    // 获取差异的中文标签名
    function getDiffLabel(diff) {
        var map = {
            'font_name': '字体',
            'font_size': '字号',
            'bold': '加粗',
            'italic': '斜体',
            'bold-italic': '粗斜体',
            'alignment': '对齐',
            'first_line_indent': '首行缩进',
            'line_spacing': '行间距',
            'space_before': '段前距',
            'space_after': '段后距',
        };
        return map[diff] || diff;
    }

    // 获取差异详情
    function getDiffDetail(diff, para) {
        if (!para) return '';
        var cf = para.current_format || {};
        var tf = para.target_format || {};

        switch (diff) {
            case 'font_name':
                return (cf.font_name || '?') + ' → ' + ((tf.chinese_font && tf.chinese_font.name) || '?');
            case 'font_size':
                return (cf.font_size || '?') + ' → ' + ((tf.chinese_font && tf.chinese_font.size) || '?');
            case 'bold':
                return '加粗: ' + (cf.bold ? '是' : '否') + ' → ' +
                       ((tf.chinese_font && tf.chinese_font.bold) ? '是' : '否');
            case 'alignment':
                return (cf.alignment || '?') + ' → ' + ((tf.paragraph && tf.paragraph.alignment) || '?');
            case 'first_line_indent':
                return '缩进: ' + (cf.first_line_indent || '0') + ' → ' +
                       ((tf.paragraph && tf.paragraph.first_line_indent) || '0');
            case 'line_spacing':
                return '行距: ' + (cf.line_spacing || '?') + ' → ' +
                       ((tf.paragraph && tf.paragraph.line_spacing) || '?');
            default:
                return diff;
        }
    }

    // ================================================================
    //  scrollToParagraph(index) — 平滑滚动到指定段落，高亮2秒
    // ================================================================
    function scrollToParagraph(index) {
        console.log('[Review] scrollToParagraph #' + index);

        var el = document.getElementById('p-' + index);
        if (!el) {
            console.warn('[Review] 未找到段落元素 #p-' + index);
            return;
        }

        // 清除现有高亮
        previewPanel.querySelectorAll('.paragraph-block.highlight').forEach(function (p) {
            p.classList.remove('highlight');
        });

        // 添加高亮并滚动
        el.classList.add('highlight');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // 2 秒后移除高亮
        setTimeout(function () {
            el.classList.remove('highlight');
        }, 2000);
    }

    // ================================================================
    //  showEditPopup(paraDiv, index) — 弹出编辑浮窗
    //  包含 select 下拉列表，修改后更新 data-label, border, badge, userLabels
    // ================================================================
    function showEditPopup(paraDiv, index) {
        console.log('[Review] showEditPopup #' + index);

        // 关闭已有浮窗
        closePopup();

        var para = null;
        for (var i = 0; i < paragraphs.length; i++) {
            if (paragraphs[i].index === index) {
                para = paragraphs[i];
                break;
            }
        }
        if (!para) {
            console.warn('[Review] 未找到段落数据 #' + index);
            return;
        }

        var currentLabel = userLabels[index] || para.label || '正文段落';

        // 创建浮窗
        var popup = document.createElement('div');
        popup.className = 'para-popup';
        popup.id = 'paraPopup';

        var popupHtml = '';
        popupHtml += '<div class="popup-title">✏️ 段落 #' + index + ' 标签</div>';
        popupHtml += '<div class="popup-current">当前：<strong>' + escapeHtml(currentLabel) + '</strong></div>';
        popupHtml += '<select class="popup-select" id="popupSelect">';

        for (var j = 0; j < ALL_LABELS.length; j++) {
            var lbl = ALL_LABELS[j];
            var sel = (lbl === currentLabel) ? ' selected' : '';
            popupHtml += '<option value="' + escapeAttr(lbl) + '"' + sel + '>' +
                         escapeHtml(lbl) + '</option>';
        }

        popupHtml += '</select>';
        popupHtml += '<div class="popup-actions">';
        popupHtml += '  <button class="popup-btn popup-btn-cancel" id="popupCancel">取消</button>';
        popupHtml += '  <button class="popup-btn popup-btn-ok" id="popupOk">确认修改</button>';
        popupHtml += '</div>';

        popup.innerHTML = popupHtml;
        document.body.appendChild(popup);

        // 定位浮窗
        var rect = paraDiv.getBoundingClientRect();
        var top = rect.top + window.scrollY - 10;
        var left = rect.left + window.scrollX;

        // 确保不超出视窗
        if (top < 10) top = 10;
        if (left + 260 > window.innerWidth) left = window.innerWidth - 270;
        if (left < 10) left = 10;

        popup.style.top = top + 'px';
        popup.style.left = left + 'px';

        console.log('[Review] 浮窗位置: top=' + top + ' left=' + left);

        // 绑定确认按钮
        document.getElementById('popupOk').addEventListener('click', function () {
            var newLabel = document.getElementById('popupSelect').value;
            console.log('[Review] 段落 #' + index + ' 标签修改: ' + currentLabel + ' → ' + newLabel);

            // 更新状态
            userLabels[index] = newLabel;

            // 更新 DOM
            updateParagraphStyle(paraDiv, index, newLabel);

            closePopup();
        });

        // 绑定取消按钮
        document.getElementById('popupCancel').addEventListener('click', function () {
            closePopup();
        });

        // 点击外部关闭
        setTimeout(function () {
            document.addEventListener('click', popupOutsideHandler);
        }, 0);
    }

    // 点击浮窗外部时关闭
    function popupOutsideHandler(e) {
        var popup = document.getElementById('paraPopup');
        if (popup && !popup.contains(e.target) && !e.target.closest('.paragraph-block')) {
            closePopup();
        }
    }

    // 关闭浮窗
    function closePopup() {
        var popup = document.getElementById('paraPopup');
        if (popup) {
            popup.remove();
        }
        document.removeEventListener('click', popupOutsideHandler);
    }

    // 更新段落样式: data-label, border color, badge color, badge text
    function updateParagraphStyle(paraDiv, index, newLabel) {
        var color = LABEL_COLORS[newLabel] || '#999';

        // 更新 data-label
        paraDiv.dataset.label = newLabel;

        // 更新左边框颜色
        paraDiv.style.borderLeftColor = color;

        // 更新标签徽章
        var badge = paraDiv.querySelector('.para-badge');
        if (badge) {
            badge.textContent = newLabel;
            badge.style.background = color;
        }

        console.log('[Review] 段落 #' + index + ' 样式已更新为: ' + newLabel);
    }

    // ================================================================
    //  doConfirm() — 一键确认，提交修改过的标签
    // ================================================================
    function doConfirm() {
        console.log('[Review] ====== 开始提交确认 ======');
        if (!btnConfirm) return;

        btnConfirm.disabled = true;
        btnConfirm.textContent = '⏳ 提交中...';

        // 构建请求体
        var requestBody = {
            labels: userLabels,  // 只传用户修改过的标签
        };

        // 获取文件路径
        if (window.__filePaths) {
            requestBody.template = window.__filePaths.template || '';
            requestBody.paper = window.__filePaths.paper || '';
            console.log('[Review] 文件路径:', requestBody.template, requestBody.paper);
        } else {
            console.warn('[Review] 未找到文件路径信息');
            requestBody.template = '';
            requestBody.paper = '';
        }

        console.log('[Review] 提交标签数:', Object.keys(userLabels).length, '内容:', JSON.stringify(userLabels));
        console.log('[Review] 请求体:', JSON.stringify(requestBody));

        fetch('/apply-format', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        })
        .then(function (res) {
            console.log('[Review] 提交响应状态:', res.status);
            if (!res.ok) {
                return res.json().then(function (errData) {
                    throw new Error(errData.message || 'HTTP ' + res.status);
                });
            }
            return res.json();
        })
        .then(function (result) {
            console.log('[Review] 提交结果:', result);
            if (result.success) {
                showToast('✅ ' + (result.message || '提交成功'));
                setTimeout(function () {
                    window.location.href = result.redirect || '/preview';
                }, 1000);
            } else {
                showToast('❌ ' + (result.message || '提交失败'));
                btnConfirm.disabled = false;
                btnConfirm.textContent = '✅ 一键确认';
            }
        })
        .catch(function (err) {
            console.error('[Review] 提交出错:', err);
            showToast('❌ ' + err.message);
            if (btnConfirm) {
                btnConfirm.disabled = false;
                btnConfirm.textContent = '✅ 一键确认';
            }
        });
    }

    // ================================================================
    //  工具函数
    // ================================================================

    // escapeHtml — 转义 HTML 特殊字符
    function escapeHtml(str) {
        if (typeof str !== 'string') return String(str);
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(str));
        return d.innerHTML;
    }

    // escapeAttr — 转义 HTML 属性值
    // 使用 String.replace 全局替换，避免 HTML 实体在传输中被解析
    function escapeAttr(str) {
        if (typeof str !== 'string') return String(str);
        var s = str;
        s = s.replace(/&/g, '&' + 'amp;');
        s = s.replace(/"/g, '&' + 'quot;');
        s = s.replace(/'/g, '&' + '#x27;');
        s = s.replace(/</g, '&' + 'lt;');
        s = s.replace(/>/g, '&' + 'gt;');
        return s;
    }

    // showToast — 显示 Toast 提示
    function showToast(msg) {
        console.log('[Review] Toast:', msg);

        var toast = document.getElementById('toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast';
            toast.className = 'toast';
            document.body.appendChild(toast);
        }

        toast.textContent = msg;
        toast.classList.add('show');

        clearTimeout(toast._timer);
        toast._timer = setTimeout(function () {
            toast.classList.remove('show');
        }, 2500);
    }

    console.log('[Review] ====== 初始化完成 ======');
});
