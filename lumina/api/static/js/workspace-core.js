var _translateLang = 'zh';
var _translateJobId = '';
var _comparePairs = [];
var _compareSync = false;
var _compareFullscreen = false;
var _pendingPdfFile = null;
var _documentBatchJobId = null;
var _documentBatchPollTimer = null;
var _labBatchJobId = null;
var _labBatchPollTimer = null;
var _documentTask = 'translate';
var _documentInputMode = 'text';
var _labInputMode = 'url';
var _documentTasks = {
  translate: {
    label: '翻译',
    description: '适合短文、长文和文档文件的中英互译，文本与 txt/md 会直接返回结果，PDF 或目录批量会保留任务追踪。',
    button: '开始翻译',
    outputTitle: '翻译结果',
    textLabel: '输入原文',
    textPlaceholder: '粘贴需要翻译的正文...',
    textHint: '适合网页正文、笔记、文章片段等直接翻译。',
    urlLabel: '输入 PDF 链接',
    urlHint: '适合线上论文、白皮书和可公开访问的 PDF 文档。',
    fileLabel: '上传文件'
  },
  summarize: {
    label: '总结',
    description: '适合长文本和文档文件的快速提炼，txt/md 会直接总结，PDF 和目录批量会走文档解析链路。',
    button: '生成总结',
    outputTitle: '总结结果',
    textLabel: '粘贴长文本',
    textPlaceholder: '粘贴文章、会议纪要、论文正文或任意长文本...',
    textHint: '适合网页正文、笔记、聊天记录、会议纪要等非 PDF 内容。',
    urlLabel: '输入 PDF 链接',
    urlHint: '适合线上论文、研究报告和长篇 PDF 文档。',
    fileLabel: '上传文件'
  }
};
var _labTasks = {};

getImageTaskDefs().forEach(function(item) {
  var modes = Array.isArray(item.modes) ? item.modes.slice() : [];
  if (!modes.includes('directory')) modes.push('directory');
  _labTasks[item.key] = {
    label: item.label,
    shortLabel: item.short_label,
    description: item.description,
    modes: modes,
    fileAccept: item.file_accept,
    fileLabel: item.file_label,
    button: item.button,
    promptText: item.prompt_text
  };
});

var _labTask = Object.keys(_labTasks)[0] || 'image_ocr';

function normalizeUrl(url) {
  return url.replace(/arxiv\.org\/abs\/([0-9]+\.[0-9]+)/g, 'arxiv.org/pdf/$1');
}

function fileExtension(name) {
  var parts = String(name || '').toLowerCase().split('.');
  return parts.length > 1 ? parts.pop() : '';
}

function isPdfFile(file) {
  return !!file && (fileExtension(file.name) === 'pdf' || (file.type || '') === 'application/pdf');
}

function isTextDocumentFile(file) {
  var ext = fileExtension(file && file.name);
  return !!file && (['txt', 'md', 'markdown'].includes(ext) || (file.type || '').startsWith('text/'));
}

function isSupportedDocumentFile(file) {
  return isPdfFile(file) || isTextDocumentFile(file);
}

async function readDocumentTextFile(file) {
  var text = await file.text();
  return (text || '').trim();
}

function readImageAsDataUrl(file) {
  return new Promise(function(resolve, reject) {
    var reader = new FileReader();
    reader.onload = function() { resolve(String(reader.result || '')); };
    reader.onerror = function() { reject(new Error('图片读取失败')); };
    reader.readAsDataURL(file);
  });
}

function sleep(ms) {
  return new Promise(function(r) { setTimeout(r, ms); });
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderPlainTextResult(targetId, text, meta) {
  var el = document.getElementById(targetId);
  if (!el) return;
  var metaHtml = meta ? '<div class="text-[11px] font-bold uppercase tracking-widest text-zinc-400 mb-4">' + escapeHtml(meta) + '</div>' : '';
  el.innerHTML = '<div class="w-full bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800 rounded-2xl p-5">' + metaHtml + '<div class="whitespace-pre-wrap text-sm leading-7 text-zinc-700 dark:text-zinc-200">' + escapeHtml(text) + '</div></div>';
}

function clearBatchPoll(kind) {
  if (kind === 'document' && _documentBatchPollTimer) {
    clearTimeout(_documentBatchPollTimer);
    _documentBatchPollTimer = null;
  }
  if (kind === 'image' && _labBatchPollTimer) {
    clearTimeout(_labBatchPollTimer);
    _labBatchPollTimer = null;
  }
}

function formatBatchTask(task, targetLanguage) {
  if (task === 'translate') return targetLanguage === 'en' ? '批量翻译 · 中 -> 英' : '批量翻译 · 英 -> 中';
  if (task === 'summarize') return '批量总结';
  if (task === 'image_ocr') return '批量 OCR';
  if (task === 'image_caption') return '批量 Caption';
  return task;
}

function renderBatchJob(targetId, job) {
  var el = document.getElementById(targetId);
  if (!el || !job) return;
  var percent = job.total ? Math.min(100, Math.round((job.completed / job.total) * 100)) : 0;
  var tone = job.status === 'error' ? 'from-red-500 to-rose-500' : (job.status === 'done' ? 'from-emerald-500 to-teal-500' : 'from-indigo-500 to-violet-500');
  var current = job.current_item ? '<div class="text-xs text-zinc-500 dark:text-zinc-400 mt-2">当前文件：' + escapeHtml(job.current_item) + '</div>' : '';
  var error = job.error ? '<div class="mt-4 text-sm font-bold text-red-600 dark:text-red-400">' + escapeHtml(job.error) + '</div>' : '';
  var items = (job.items || []).map(function(item) {
    var badgeCls = item.status === 'done'
      ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300'
      : item.status === 'error'
        ? 'bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300'
        : item.status === 'running'
          ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300'
          : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300';
    var outputs = (item.output_paths || []).map(function(path) {
      return '<div class="text-xs text-zinc-500 dark:text-zinc-400 break-all">' + escapeHtml(path) + '</div>';
    }).join('');
    var preview = item.preview ? '<div class="mt-3 text-sm leading-6 text-zinc-700 dark:text-zinc-200">' + escapeHtml(item.preview) + '</div>' : '';
    var itemError = item.error ? '<div class="mt-3 text-sm font-bold text-red-600 dark:text-red-400">' + escapeHtml(item.error) + '</div>' : '';
    return '<div class="rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/40 p-4">' +
      '<div class="flex items-start justify-between gap-3">' +
        '<div class="min-w-0">' +
          '<div class="text-sm font-bold text-zinc-900 dark:text-zinc-100 break-all">' + escapeHtml(item.rel_path) + '</div>' +
          '<div class="text-xs text-zinc-400 mt-1 break-all">' + escapeHtml(item.path) + '</div>' +
        '</div>' +
        '<span class="shrink-0 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ' + badgeCls + '">' + escapeHtml(item.status) + '</span>' +
      '</div>' +
      preview + itemError +
      (outputs ? '<div class="mt-3 pt-3 border-t border-zinc-200/70 dark:border-zinc-700/70 space-y-1">' + outputs + '</div>' : '') +
    '</div>';
  }).join('');

  el.innerHTML = '<div class="w-full bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800 rounded-2xl p-5">' +
    '<div class="flex items-start justify-between gap-4">' +
      '<div>' +
        '<div class="text-[11px] font-bold uppercase tracking-widest text-zinc-400">' + escapeHtml(formatBatchTask(job.task, job.target_language)) + '</div>' +
        '<div class="text-xl font-black text-zinc-900 dark:text-zinc-100 mt-2">' + job.completed + ' / ' + job.total + '</div>' +
        '<div class="text-sm text-zinc-500 dark:text-zinc-400 mt-2">成功 ' + job.succeeded + '，失败 ' + job.failed + '，状态 ' + escapeHtml(job.status) + '</div>' +
        current +
      '</div>' +
      '<div class="text-right">' +
        '<div class="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Output</div>' +
        '<div class="text-xs text-zinc-500 dark:text-zinc-400 mt-2 break-all max-w-[220px]">' + escapeHtml(job.output_dir) + '</div>' +
      '</div>' +
    '</div>' +
    '<div class="mt-5 h-3 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden"><div class="h-full rounded-full bg-gradient-to-r ' + tone + '" style="width:' + percent + '%"></div></div>' +
    error +
    '<div class="mt-6 space-y-3 max-h-[520px] overflow-y-auto pr-1">' + items + '</div>' +
  '</div>';
}

async function pollBatchJob(kind, targetId, jobId) {
  try {
    var res = await fetch('/v1/batch/' + encodeURIComponent(jobId));
    if (!res.ok) throw new Error((await res.json().catch(function() { return {}; })).detail || res.statusText);
    var job = await res.json();
    renderBatchJob(targetId, job);
    if (job.status === 'queued' || job.status === 'running') {
      clearBatchPoll(kind);
      var timer = setTimeout(function() { pollBatchJob(kind, targetId, jobId); }, 2000);
      if (kind === 'document') _documentBatchPollTimer = timer;
      else _labBatchPollTimer = timer;
    }
  } catch (e) {
    var el = document.getElementById(targetId);
    if (el) {
      el.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">批处理状态获取失败：' + escapeHtml(e.message) + '</span></div>';
    }
  }
}

function showFilename(input, targetId) {
  var el = document.getElementById(targetId);
  if (el) el.textContent = input.files[0] ? input.files[0].name : '';
}

function handleDropZone(event, fileInputId, filenameId) {
  var f = event.dataTransfer.files[0];
  var input = document.getElementById(fileInputId);
  if (!f || !input) return;
  var allowDocumentFiles = fileInputId === 'document-file';
  if ((allowDocumentFiles && !isSupportedDocumentFile(f)) || (!allowDocumentFiles && !isPdfFile(f))) return;
  var dt = new DataTransfer();
  dt.items.add(f);
  input.files = dt.files;
  showFilename(input, filenameId);
}

function handleLabDrop(event, target) {
  event.preventDefault();
  target.classList.remove('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-900/20');
  var file = event.dataTransfer.files[0];
  var input = document.getElementById('lab-file-input');
  if (!file || !input) return;
  if (!(file.type || '').startsWith('image/')) return;
  var dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
  showFilename(input, 'lab-filename');
}

function setDigestSeg(seg) {
  var btns = document.querySelectorAll('#digest-seg-ctrl button');
  btns.forEach(function(b) {
    b.classList.remove('bg-white', 'dark:bg-zinc-700', 'shadow-sm', 'text-zinc-900', 'dark:text-zinc-100');
    b.classList.add('text-zinc-500');
  });
  var active = document.getElementById('seg-' + seg);
  if (active) {
    active.classList.remove('text-zinc-500');
    active.classList.add('bg-white', 'dark:bg-zinc-700', 'shadow-sm', 'text-zinc-900', 'dark:text-zinc-100');
    var url = active.getAttribute('hx-get');
    if (url) {
      document.getElementById('digest-content').setAttribute('hx-get', url);
    }
  }
}

function setTranslateLang(lang) {
  _translateLang = lang;
  document.getElementById('lang-zh').classList.toggle('selected', lang === 'zh');
  document.getElementById('lang-en').classList.toggle('selected', lang === 'en');
}

function setDocumentTask(task, btn) {
  if (!_documentTasks[task]) return;
  _documentTask = task;
  document.querySelectorAll('#document-task-group .document-task-btn').forEach(function(el) {
    el.classList.remove('bg-indigo-500', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
    el.classList.add('bg-zinc-100', 'dark:bg-zinc-800/50', 'text-zinc-500');
  });
  if (btn) {
    btn.classList.remove('bg-zinc-100', 'dark:bg-zinc-800/50', 'text-zinc-500');
    btn.classList.add('bg-indigo-500', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
  }
  var spec = _documentTasks[task];
  var description = document.getElementById('document-task-description');
  var outputTitle = document.getElementById('document-output-title');
  var textLabel = document.getElementById('document-text-label');
  var textInput = document.getElementById('document-text');
  var textHint = document.getElementById('document-text-hint');
  var urlLabel = document.getElementById('document-url-label');
  var urlHint = document.getElementById('document-url-hint');
  var fileLabel = document.getElementById('document-file-label');
  var runBtn = document.getElementById('document-run-btn');
  var translateOptions = document.getElementById('document-translate-options');
  if (description) description.textContent = spec.description;
  if (outputTitle) outputTitle.textContent = spec.outputTitle;
  if (textLabel) textLabel.textContent = spec.textLabel;
  if (textInput) textInput.placeholder = spec.textPlaceholder;
  if (textHint) textHint.textContent = spec.textHint;
  if (urlLabel) urlLabel.textContent = spec.urlLabel;
  if (urlHint) urlHint.textContent = spec.urlHint;
  if (fileLabel) fileLabel.textContent = spec.fileLabel;
  if (runBtn) runBtn.textContent = spec.button;
  if (translateOptions) translateOptions.classList.toggle('hidden', task !== 'translate');
}

function setDocumentInputMode(mode) {
  _documentInputMode = mode;
  ['text', 'url', 'file', 'directory'].forEach(function(key) {
    var btn = document.getElementById('document-mode-' + key);
    var block = document.getElementById('document-input-' + key);
    var active = key === mode;
    if (btn) {
      btn.classList.toggle('bg-white', active);
      btn.classList.toggle('dark:bg-zinc-700', active);
      btn.classList.toggle('shadow-sm', active);
      btn.classList.toggle('text-zinc-900', active);
      btn.classList.toggle('dark:text-zinc-100', active);
      btn.classList.toggle('text-zinc-500', !active);
    }
    if (block) block.classList.toggle('hidden', !active);
  });
}

function setLabTask(task, btn) {
  if (!_labTasks[task] || !getEnabledLabTasks().includes(task)) return;
  _labTask = task;
  document.querySelectorAll('#lab-task-group .lab-task-btn').forEach(function(el) {
    el.classList.remove('bg-indigo-500', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
    el.classList.add('bg-zinc-100', 'dark:bg-zinc-800/50', 'text-zinc-500');
  });
  if (btn) {
    btn.classList.remove('bg-zinc-100', 'dark:bg-zinc-800/50', 'text-zinc-500');
    btn.classList.add('bg-indigo-500', 'text-white', 'shadow-lg', 'shadow-indigo-500/20');
  }
  var spec = _labTasks[task];
  var desc = document.getElementById('lab-task-description');
  if (desc) desc.textContent = spec.description;
  var runBtn = document.getElementById('lab-run-btn');
  if (runBtn) runBtn.textContent = spec.button;
  var fileInput = document.getElementById('lab-file-input');
  if (fileInput) fileInput.accept = spec.fileAccept || '';
  var fileLabel = document.getElementById('lab-file-label');
  if (fileLabel) fileLabel.textContent = spec.fileLabel || '点击选择或拖入文件';
  var nextMode = spec.modes.includes(_labInputMode) ? _labInputMode : spec.modes[0];
  setLabInputMode(nextMode);
}

function applyLabTaskAvailability() {
  var enabled = getEnabledLabTasks();
  document.querySelectorAll('#lab-task-group .lab-task-btn').forEach(function(btn) {
    var task = btn.dataset.task;
    btn.classList.toggle('hidden', !enabled.includes(task));
  });
  if (!enabled.includes(_labTask)) {
    var firstTask = enabled[0] || 'image_ocr';
    setLabTask(firstTask, document.querySelector('#lab-task-group [data-task="' + firstTask + '"]'));
  }
}

function setLabInputMode(mode) {
  var spec = _labTasks[_labTask] || _labTasks.image_ocr;
  if (!spec.modes.includes(mode)) mode = spec.modes[0];
  _labInputMode = mode;
  ['text', 'url', 'file', 'directory'].forEach(function(key) {
    var btn = document.getElementById('lab-mode-' + key);
    var block = document.getElementById('lab-input-' + key);
    var enabled = spec.modes.includes(key);
    var active = enabled && key === mode;
    if (btn) {
      btn.disabled = !enabled;
      btn.classList.toggle('opacity-40', !enabled);
      btn.classList.toggle('cursor-not-allowed', !enabled);
      btn.classList.toggle('bg-white', active);
      btn.classList.toggle('dark:bg-zinc-700', active);
      btn.classList.toggle('shadow-sm', active);
      btn.classList.toggle('text-zinc-900', active);
      btn.classList.toggle('dark:text-zinc-100', active);
      btn.classList.toggle('text-zinc-500', !active);
    }
    if (block) block.classList.toggle('hidden', !active);
  });
}

async function runLabTask() {
  var spec = _labTasks[_labTask] || _labTasks.image_ocr;
  var result = document.getElementById('lab-result');
  var btn = document.getElementById('lab-run-btn');
  if (!result || !btn) return;
  if (_labInputMode === 'directory') {
    var inputDir = (document.getElementById('lab-directory-input').value || '').trim();
    var outputDir = (document.getElementById('lab-output-dir').value || '').trim();
    if (!inputDir) {
      result.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">请先输入图片目录路径</span></div>';
      return;
    }
    btn.disabled = true;
    btn.textContent = '提交中…';
    result.innerHTML = '<div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-12 w-full flex flex-col items-center justify-center border border-zinc-100 dark:border-zinc-800"><svg class="w-8 h-8 animate-spin text-indigo-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><div class="text-sm font-bold text-zinc-500">正在提交批处理任务…</div></div>';
    try {
      clearBatchPoll('image');
      var batchRes = await fetch('/v1/batch/image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_dir: inputDir,
          output_dir: outputDir || null,
          task: _labTask
        })
      });
      if (!batchRes.ok) throw new Error(((await batchRes.json().catch(function() { return {}; })).detail) || batchRes.statusText);
      var batchData = await batchRes.json();
      _labBatchJobId = batchData.job_id;
      renderBatchJob('lab-result', batchData);
      pollBatchJob('image', 'lab-result', batchData.job_id);
      return;
    } catch (e) {
      result.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">错误：' + escapeHtml(e.message) + '</span></div>';
      return;
    } finally {
      btn.disabled = false;
      btn.textContent = spec.button;
    }
  }

  btn.disabled = true;
  btn.textContent = '处理中…';
  result.innerHTML = '<div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-12 w-full flex flex-col items-center justify-center border border-zinc-100 dark:border-zinc-800"><svg class="w-8 h-8 animate-spin text-indigo-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><div class="text-sm font-bold text-zinc-500">处理中，请稍候…</div></div>';

  try {
    if (_labTask === 'image_ocr' || _labTask === 'image_caption') {
      var prompts = getImagePrompts();
      var systemPrompt = prompts[_labTask] || '';
      var imageRef;
      if (_labInputMode === 'file') {
        var mediaFile = document.getElementById('lab-file-input');
        if (!mediaFile.files[0]) throw new Error('请先选择图片文件');
        imageRef = await readImageAsDataUrl(mediaFile.files[0]);
      } else {
        var imageUrl = (document.getElementById('lab-url-input').value || '').trim();
        if (!imageUrl) throw new Error('请先输入图片链接');
        imageRef = imageUrl;
      }
      var mediaRes = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'lumina',
          messages: [
            { role: 'system', content: systemPrompt },
            {
              role: 'user',
              content: [
                { type: 'text', text: spec.promptText || '请描述这张图片。' },
                { type: 'image_url', image_url: { url: imageRef } }
              ]
            }
          ]
        })
      });
      if (!mediaRes.ok) throw new Error(((await mediaRes.json().catch(function() { return {}; })).detail) || mediaRes.statusText);
      var mediaData = await mediaRes.json();
      var mediaText = (((mediaData || {}).choices || [])[0] || {}).message;
      renderPlainTextResult('lab-result', (mediaText && mediaText.content) || '', spec.label + ' · Chat');
      return;
    }

    throw new Error('暂不支持的图片任务');
  } catch (e) {
    result.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">错误：' + escapeHtml(e.message) + '</span></div>';
  } finally {
    btn.disabled = false;
    btn.textContent = spec.button;
  }
}

async function startDocumentTask() {
  var fileInput = document.getElementById('document-file');
  var urlInput = document.getElementById('document-url');
  var textInput = document.getElementById('document-text');
  var dirInput = document.getElementById('document-directory');
  var outputDirInput = document.getElementById('document-output-dir');
  var resultDiv = document.getElementById('document-result');
  var btn = document.getElementById('document-run-btn');
  var spec = _documentTasks[_documentTask];
  var selectedFile = fileInput && fileInput.files ? fileInput.files[0] : null;

  var text = textInput ? (textInput.value || '').trim() : '';
  var url = urlInput ? normalizeUrl((urlInput.value || '').trim()) : '';
  var inputDir = dirInput ? (dirInput.value || '').trim() : '';
  var outputDir = outputDirInput ? (outputDirInput.value || '').trim() : '';

  if ((_documentInputMode === 'text' && !text) || (_documentInputMode === 'url' && !url) || (_documentInputMode === 'file' && !selectedFile) || (_documentInputMode === 'directory' && !inputDir)) {
    var hint = _documentInputMode === 'text'
      ? '请先粘贴文本'
      : (_documentInputMode === 'url'
        ? '请先输入 PDF 链接'
        : (_documentInputMode === 'file' ? '请先上传文件' : '请先输入目录路径'));
    resultDiv.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">' + hint + '</span></div>';
    return;
  }

  if (_documentInputMode === 'directory') {
    btn.disabled = true;
    btn.textContent = '提交中…';
    resultDiv.innerHTML = '<div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-12 w-full flex flex-col items-center justify-center border border-zinc-100 dark:border-zinc-800"><svg class="w-8 h-8 animate-spin text-indigo-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><div class="text-sm font-bold text-zinc-500">正在提交批处理任务…</div></div>';
    try {
      clearBatchPoll('document');
      var batchRes = await fetch('/v1/batch/document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_dir: inputDir,
          output_dir: outputDir || null,
          task: _documentTask,
          target_language: _translateLang
        })
      });
      if (!batchRes.ok) {
        var batchErr = await batchRes.json().catch(function() { return { detail: batchRes.statusText }; });
        throw new Error(batchErr.detail || batchRes.statusText);
      }
      var batchData = await batchRes.json();
      _documentBatchJobId = batchData.job_id;
      renderBatchJob('document-result', batchData);
      pollBatchJob('document', 'document-result', batchData.job_id);
      return;
    } catch (e) {
      resultDiv.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">错误：' + escapeHtml(e.message) + '</span></div>';
      return;
    } finally {
      btn.disabled = false;
      btn.textContent = spec.button;
    }
  }

  btn.disabled = true;
  btn.textContent = _documentTask === 'translate' ? (_documentInputMode === 'text' ? '翻译中…' : '处理中…') : '总结中…';
  resultDiv.innerHTML = '<div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-12 w-full flex flex-col items-center justify-center border border-zinc-100 dark:border-zinc-800"><svg class="w-8 h-8 animate-spin text-indigo-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><div class="text-sm font-bold text-zinc-500">' + (_documentTask === 'translate' ? '处理中，请稍候…' : '生成中，请稍候…') + '</div></div>';

  try {
    var res;
    if (_documentTask === 'translate') {
      if (_documentInputMode === 'text') {
        res = await fetch('/v1/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text, target_language: _translateLang })
        });
        if (!res.ok) {
          var translateTextErr = await res.json().catch(function() { return { detail: res.statusText }; });
          throw new Error(translateTextErr.detail || res.statusText);
        }
        var translateTextData = await res.json();
        renderPlainTextResult('document-result', translateTextData.text || '', _translateLang === 'zh' ? '文本翻译 · 英 -> 中' : '文本翻译 · 中 -> 英');
        return;
      }

      if (_documentInputMode === 'file') {
        if (isTextDocumentFile(selectedFile)) {
          var translateFileText = await readDocumentTextFile(selectedFile);
          if (!translateFileText) throw new Error('文件内容为空');
          res = await fetch('/v1/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: translateFileText, target_language: _translateLang })
          });
          if (!res.ok) {
            var translateFileErr = await res.json().catch(function() { return { detail: res.statusText }; });
            throw new Error(translateFileErr.detail || res.statusText);
          }
          var translateFileData = await res.json();
          renderPlainTextResult('document-result', translateFileData.text || '', (selectedFile.name || '文本文件') + ' · 文件翻译');
          return;
        }
        if (!isPdfFile(selectedFile)) throw new Error('文件模式目前支持 PDF / TXT / MD');
        var translateFd = new FormData();
        translateFd.append('file', selectedFile);
        translateFd.append('lang_out', _translateLang);
        res = await fetch('/v1/pdf/upload', { method: 'POST', body: translateFd });
      } else {
        res = await fetch('/v1/pdf/url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: url, action: 'translate', lang_out: _translateLang })
        });
      }
      if (!res.ok) {
        var translateErr = await res.json().catch(function() { return { detail: res.statusText }; });
        throw new Error(translateErr.detail || res.statusText);
      }
      var translateData = await res.json();
      _translateJobId = translateData.job_id;
      _comparePairs = [];
      resultDiv.innerHTML = '<div hx-get="/fragments/pdf/status/' + translateData.job_id + '" hx-trigger="every 2s" hx-swap="outerHTML" class="w-full"><div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-6 w-full border border-zinc-100 dark:border-zinc-800"><div class="text-sm font-bold text-zinc-500 mb-4 flex justify-between items-center"><span>正在翻译，可能需要几分钟…</span><span>30%</span></div><div class="w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-2.5 overflow-hidden"><div class="bg-indigo-600 h-2.5 rounded-full transition-all duration-500 ease-out" style="width: 30%"></div></div></div></div>';
      if (window.htmx) htmx.process(resultDiv);
      return;
    }

    if (_documentInputMode === 'text') {
      res = await fetch('/v1/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
      if (!res.ok) {
        var summarizeTextErr = await res.json().catch(function() { return { detail: res.statusText }; });
        throw new Error(summarizeTextErr.detail || res.statusText);
      }
      var summarizeTextData = await res.json();
      renderPlainTextResult('document-result', summarizeTextData.text || '', '文本摘要');
      return;
    }

    var endpoint;
    var body;
    var headers = {};
    if (_documentInputMode === 'file') {
      if (isTextDocumentFile(selectedFile)) {
        var summarizeFileText = await readDocumentTextFile(selectedFile);
        if (!summarizeFileText) throw new Error('文件内容为空');
        res = await fetch('/v1/summarize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: summarizeFileText })
        });
        if (!res.ok) {
          var summarizeFileErr = await res.json().catch(function() { return { detail: res.statusText }; });
          throw new Error(summarizeFileErr.detail || res.statusText);
        }
        var summarizeFileData = await res.json();
        renderPlainTextResult('document-result', summarizeFileData.text || '', (selectedFile.name || '文本文件') + ' · 文件总结');
        return;
      }
      if (!isPdfFile(selectedFile)) throw new Error('文件模式目前支持 PDF / TXT / MD');
      var summarizeFd = new FormData();
      summarizeFd.append('file', selectedFile);
      endpoint = '/v1/pdf/summarize_sync';
      body = summarizeFd;
    } else {
      endpoint = '/v1/pdf/url_summarize_sync';
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify({ url: url });
    }
    res = await fetch(endpoint, { method: 'POST', headers: headers, body: body });
    if (!res.ok) {
      var summarizeErr = await res.json().catch(function() { return { detail: res.statusText }; });
      throw new Error(summarizeErr.detail || res.statusText);
    }
    resultDiv.innerHTML = await res.text();
  } catch (e) {
    resultDiv.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 w-full text-red-600 dark:text-red-400 font-bold flex items-start gap-2"><svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="text-sm">错误：' + escapeHtml(e.message) + '</span></div>';
  } finally {
    btn.disabled = false;
    btn.textContent = spec.button;
  }
}
