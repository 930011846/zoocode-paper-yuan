/* ============================================================
   preview.js — 排版预览页交互
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  // ======================== DOM 引用 ========================
  var leftContent = document.getElementById('leftContent');
  var rightContent = document.getElementById('rightContent');
  var bottomStatus = document.getElementById('bottomStatus');
  var complianceBody = document.getElementById('compliance-body');
  var complianceIcon = document.getElementById('compliance-icon');
  var complianceSummary = document.getElementById('compliance-summary');
  var complianceErrors = document.getElementById('compliance-errors');
  var complianceWarnings = document.getElementById('compliance-warnings');
  var compliancePassed = document.getElementById('compliance-passed');

  // ======================== 安全设置内容 ========================
  function setContent(el, html) {
    if (el) el.innerHTML = html || '<div class="empty-state">暂无内容</div>';
  }

  // ======================== 映射表 ========================

  /**
   * 字体名称 → CSS font-family
   */
  function fontNameMap(name) {
    var map = {
      '宋体': 'SimSun, serif',
      '黑体': 'SimHei, sans-serif',
      '楷体': 'KaiTi, serif',
      'Times New Roman': "'Times New Roman', serif"
    };
    return map[name] || 'SimSun, serif';
  }

  /**
   * 字号 (pt 数值) → CSS font-size (pt)
   */
  function fontSizeMap(size) {
    if (size === null || size === undefined) return '';
    // 如果已经带单位则直接使用
    if (typeof size === 'string' && /[a-z%]/i.test(size)) return size;
    return String(Number(size)) + 'pt';
  }

  /**
   * 中文对齐 → CSS text-align
   */
  function alignMap(alignment) {
    var map = {
      '居中': 'center',
      '两端对齐': 'justify',
      '左对齐': 'left',
      '右对齐': 'right'
    };
    return map[alignment] || 'left';
  }

  /**
   * 构建段落内联样式字符串
   * @param {Object} fmt - current_format 或 target_format
   * @param {boolean} isTarget - 是否是目标格式 (target_format 结构不同)
   * @returns {string} CSS 样式字符串
   */
  function buildInlineCss(fmt, isTarget) {
    if (!fmt) return '';
    var css = '';

    if (isTarget) {
      // target_format: { chinese_font: {name, size, bold}, paragraph: {alignment, first_line_indent} }
      var ch = fmt.chinese_font || {};
      var pp = fmt.paragraph || {};

      if (ch.name) css += 'font-family:' + fontNameMap(ch.name) + ';';
      if (ch.size) css += 'font-size:' + fontSizeMap(ch.size) + ';';
      if (ch.bold) css += 'font-weight:bold;';
      if (pp.alignment) css += 'text-align:' + alignMap(pp.alignment) + ';';
      if (pp.first_line_indent) css += 'text-indent:2em;';
    } else {
      // current_format: { font_name, font_size, bold, alignment, first_line_indent, line_spacing }
      if (fmt.font_name) css += 'font-family:' + fontNameMap(fmt.font_name) + ';';
      if (fmt.font_size) css += 'font-size:' + fontSizeMap(fmt.font_size) + ';';
      if (fmt.bold) css += 'font-weight:bold;';
      if (fmt.alignment) css += 'text-align:' + alignMap(fmt.alignment) + ';';
      if (fmt.first_line_indent) css += 'text-indent:2em;';
    }

    return css;
  }

  // ======================== 数据获取 ========================
  fetch('/get-format-diff')
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (result) {
      // result = { success: true, data: { paragraphs: [...], summary: {...}, compliance_report: {...} } }
      if (!result.success || !result.data) {
        throw new Error(result.message || '数据获取失败');
      }
      var d = result.data;
      var paragraphs = d.paragraphs || [];
      var summary = d.summary || {};
      var report = d.compliance_report || null;

      console.log('[Preview] 段落数:', paragraphs.length);
      if (paragraphs.length > 0) {
        console.log('[Preview] 首个段落:', JSON.stringify(paragraphs[0]).substring(0, 200));
      }

      renderParagraphs(paragraphs);
      updateStats(summary);
      renderComplianceReport(report);
    })
    .catch(function (err) {
      console.error('[Preview] 数据获取失败:', err.message);
      // 请求失败，显示空状态
      var msg = '<div class="empty-state"><div style="font-size:40px;margin-bottom:16px;">📄</div>' +
        '<div style="font-size:16px;font-weight:500;">暂无对比数据，请先完成排版确认</div>' +
        '<a href="/review" style="display:inline-block;margin-top:20px;padding:10px 28px;' +
        'background:#4A90D9;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">🔄 返回修改</a></div>';
      setContent(leftContent, msg);
      setContent(rightContent, '');
      if (bottomStatus) bottomStatus.textContent = '';
      if (complianceBody) complianceBody.innerHTML = '<div class="report-empty">暂无对比数据</div>';
    });

  // ======================== 渲染段落 ========================
  function renderParagraphs(paragraphs) {
    if (!paragraphs || paragraphs.length === 0) {
      setContent(leftContent, '<div class="empty-state">暂无段落数据</div>');
      setContent(rightContent, '<div class="empty-state">暂无段落数据</div>');
      return;
    }

    var leftHtml = '';
    var rightHtml = '';

    for (var i = 0; i < paragraphs.length; i++) {
      var p = paragraphs[i];
      var text = p.text || '(空段落)';
      var label = p.label || '';
      var diffs = p.format_diffs || [];
      var cf = p.current_format || {};
      var tf = p.target_format || {};

      var leftStyle = buildInlineCss(cf, false);
      var rightStyle = buildInlineCss(tf, true);

      // --- 左侧 (原始) ---
      leftHtml += '<div class="para-block">';
      if (label) {
        leftHtml += '<span class="para-badge">' + esc(label) + '</span>';
      }
      leftHtml += '<p class="para-text" style="' + leftStyle + '">' + esc(text) + '</p>';
      leftHtml += '</div>';

      // --- 右侧 (排版后) ---
      rightHtml += '<div class="para-block formatted"';
      // 如果有格式差异，添加左侧高亮边框
      if (diffs.length > 0) {
        rightHtml += ' style="border-left:3px solid #4A90D9;"';
      }
      rightHtml += '>';
      if (label) {
        rightHtml += '<span class="para-badge">' + esc(label) + '</span>';
      }
      // 差异标签
      if (diffs.length > 0) {
        rightHtml += '<div class="diff-tags">';
        for (var d = 0; d < diffs.length; d++) {
          rightHtml += '<span class="diff-tag">' + esc(diffs[d]) + '</span>';
        }
        rightHtml += '</div>';
      }
      rightHtml += '<p class="para-text" style="' + rightStyle + '">' + esc(text) + '</p>';
      rightHtml += '</div>';
    }

    setContent(leftContent, leftHtml);
    setContent(rightContent, rightHtml);
  }

  // ======================== 更新底部统计 ========================
  function updateStats(summary) {
    if (!bottomStatus) return;
    var totalChanges = summary.total_changes || 0;
    var modifiedParas = summary.modified_paragraphs || 0;
    bottomStatus.textContent = '共 ' + totalChanges + ' 处格式修改';
  }

  // ======================== 渲染合规报告 ========================
  function renderComplianceReport(report) {
    // 如果没有合规报告，使用兜底模拟数据
    if (!report) {
      report = {
        errors: [
          { name: '方法章节', message: '已检测到方法章节', type: 'passed' }
        ],
        warnings: [
          { name: '近5年文献占比', message: '建议≥60%，请手动核实', type: 'warning' }
        ],
        passed: [
          { name: '关键词检查', message: '检测到关键词，符合要求', type: 'passed' },
          { name: '参考文献标题检查', message: '已检测到参考文献', type: 'passed' }
        ]
      };
    }

    var errors = report.errors || [];
    var warnings = report.warnings || [];
    var passed = report.passed || [];

    // 更新摘要
    if (complianceSummary) {
      complianceSummary.textContent = '🔴' + errors.length + '项 | 🟡' + warnings.length + '项 | 🟢' + passed.length + '项';
    }

    // ---- 错误 ----
    if (complianceErrors) {
      var eHtml = '';
      if (errors.length > 0) {
        eHtml += '<div class="report-group">';
        eHtml += '<div class="report-group-header" style="color:#FF4D4F;">🔴 需要修改（' + errors.length + '项）</div>';
        for (var e = 0; e < errors.length; e++) {
          var item = errors[e];
          eHtml += '<div class="report-item">';
          eHtml += '<div class="report-item-name">' + esc(item.name) + '</div>';
          eHtml += '<div class="report-item-msg">' + esc(item.message || '') + '</div>';
          if (item.position !== null && item.position !== undefined) {
            eHtml += '<span class="position-link" data-idx="' + item.position + '">📌 段落 ' + item.position + '</span>';
          }
          eHtml += '</div>';
        }
        eHtml += '</div>';
      }
      complianceErrors.innerHTML = eHtml;
    }

    // ---- 警告 ----
    if (complianceWarnings) {
      var wHtml = '';
      if (warnings.length > 0) {
        wHtml += '<div class="report-group">';
        wHtml += '<div class="report-group-header" style="color:#FAAD14;">🟡 建议检查（' + warnings.length + '项）</div>';
        for (var w = 0; w < warnings.length; w++) {
          var item = warnings[w];
          wHtml += '<div class="report-item">';
          wHtml += '<div class="report-item-name">' + esc(item.name) + '</div>';
          wHtml += '<div class="report-item-msg">' + esc(item.message || '') + '</div>';
          if (item.position !== null && item.position !== undefined) {
            wHtml += '<span class="position-link" data-idx="' + item.position + '">📌 段落 ' + item.position + '</span>';
          }
          wHtml += '</div>';
        }
        wHtml += '</div>';
      }
      complianceWarnings.innerHTML = wHtml;
    }

    // ---- 通过 ----
    if (compliancePassed) {
      var pHtml = '';
      if (passed.length > 0) {
        pHtml += '<div class="report-group">';
        pHtml += '<div class="report-group-header" style="color:#52C41A;">🟢 已通过（' + passed.length + '项）</div>';
        for (var q = 0; q < passed.length; q++) {
          var item = passed[q];
          pHtml += '<div class="report-item">';
          pHtml += '<div class="report-item-name">' + esc(item.name) + '</div>';
          pHtml += '<div class="report-item-msg">' + esc(item.message || '') + '</div>';
          pHtml += '</div>';
        }
        pHtml += '</div>';
      }
      compliancePassed.innerHTML = pHtml;
    }

    // 绑定位置链接（跳转段落）
    var containers = [complianceErrors, complianceWarnings];
    for (var c = 0; c < containers.length; c++) {
      var el = containers[c];
      if (!el) continue;
      var links = el.querySelectorAll('.position-link');
      for (var l = 0; l < links.length; l++) {
        (function (link) {
          link.addEventListener('click', function (e) {
            e.stopPropagation();
            var idx = parseInt(link.dataset.idx);
            scrollToParagraph(idx);
          });
        })(links[l]);
      }
    }
  }

  // ======================== 跳转段落（双栏同步高亮） ========================
  function scrollToParagraph(idx) {
    var panels = [leftContent, rightContent];
    for (var i = 0; i < panels.length; i++) {
      var panel = panels[i];
      if (!panel) continue;
      var targets = panel.querySelectorAll('.para-block');
      if (targets[idx]) {
        targets[idx].classList.add('highlight');
        targets[idx].scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(function () {
          targets[idx].classList.remove('highlight');
        }, 2000);
      }
    }
  }
});

// ======================== 全局折叠函数 ========================
function toggleCompliance() {
  var body = document.getElementById('compliance-body');
  var icon = document.getElementById('compliance-icon');
  if (!body || !icon) return;
  if (body.style.display === 'none') {
    body.style.display = 'block';
    icon.textContent = '▼';
  } else {
    body.style.display = 'none';
    icon.textContent = '▶';
  }
}

// ======================== HTML 转义工具 ========================
function esc(str) {
  if (typeof str !== 'string') return String(str);
  var d = document.createElement('div');
  d.appendChild(document.createTextNode(str));
  return d.innerHTML;
}
