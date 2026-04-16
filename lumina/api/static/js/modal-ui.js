function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function openCompareModal() {
  var modal = document.getElementById('compare-modal');
  modal.classList.add('open');
  if (_comparePairs.length > 0) {
    renderComparePairs();
    return;
  }
  if (!_translateJobId) {
    document.getElementById('cmp-left-content').innerHTML = '<div class="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm font-bold">Job ID 丢失</div>';
    return;
  }
  document.getElementById('cmp-left-content').innerHTML = '<div class="flex items-center justify-center h-32 text-zinc-400 text-sm animate-pulse">加载中…</div>';
  document.getElementById('cmp-right-content').innerHTML = '';
  try {
    var res = await fetch('/v1/pdf/pairs/' + _translateJobId);
    if (!res.ok) throw new Error(res.statusText);
    var data = await res.json();
    _comparePairs = data.pairs || [];
    renderComparePairs();
  } catch (e) {
    document.getElementById('cmp-left-content').innerHTML = '<div class="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm font-bold">加载失败：' + escHtml(e.message) + '</div>';
  }
}

function renderComparePairs() {
  var leftHtml = '';
  var rightHtml = '';
  var blockCls = 'p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800 transition-colors hover:bg-white dark:hover:bg-zinc-800 hover:shadow-sm group/pair';
  var badgeCls = 'inline-flex items-center justify-center px-2 py-0.5 rounded-md bg-zinc-200/50 dark:bg-zinc-700/50 text-zinc-500 dark:text-zinc-400 text-[10px] font-bold mb-2 transition-colors group-hover/pair:bg-zinc-200 dark:group-hover/pair:bg-zinc-700';
  _comparePairs.forEach(function(pair) {
    leftHtml += '<div class="' + blockCls + '"><div class="' + badgeCls + '">P' + pair.page + '</div><div class="whitespace-pre-wrap">' + escHtml(pair.original) + '</div></div>';
    rightHtml += '<div class="' + blockCls + '"><div class="' + badgeCls + '">P' + pair.page + '</div><div class="whitespace-pre-wrap">' + escHtml(pair.translated) + '</div></div>';
  });
  document.getElementById('cmp-left-content').innerHTML = leftHtml;
  document.getElementById('cmp-right-content').innerHTML = rightHtml;
}

function closeCompareModal() {
  document.getElementById('compare-modal').classList.remove('open');
}

function toggleCompareFullscreen() {
  _compareFullscreen = !_compareFullscreen;
  var sheet = document.getElementById('compare-sheet');
  var btn = document.getElementById('compare-fullscreen-btn');
  sheet.classList.toggle('fullscreen', _compareFullscreen);
  btn.textContent = _compareFullscreen ? '⊠' : '⊡';
  btn.title = _compareFullscreen ? '退出全屏' : '全屏';
}

function syncScroll(side) {
  if (_compareSync) return;
  _compareSync = true;
  var L = document.getElementById('cmp-left');
  var R = document.getElementById('cmp-right');
  if (!L || !R) {
    _compareSync = false;
    return;
  }
  var src = side === 'left' ? L : R;
  var dst = side === 'left' ? R : L;
  dst.scrollTop = (src.scrollTop / Math.max(1, src.scrollHeight - src.clientHeight)) * (dst.scrollHeight - dst.clientHeight);
  requestAnimationFrame(function() { _compareSync = false; });
}

function showPdfRouteSheet(file) {
  _pendingPdfFile = file;
  var el = document.getElementById('pdf-route-filename');
  if (el) el.textContent = '📄 ' + file.name;
  document.getElementById('pdf-route-sheet').classList.add('open');
}

function closePdfRouteSheet() {
  document.getElementById('pdf-route-sheet').classList.remove('open');
  _pendingPdfFile = null;
}

function routePdf(target) {
  var file = _pendingPdfFile;
  closePdfRouteSheet();
  if (!file) return;
  var dt = new DataTransfer();
  dt.items.add(file);
  var inp = document.getElementById('document-file');
  if (inp) {
    inp.files = dt.files;
    showFilename(inp, 'document-filename');
  }
  setDocumentTask(target, document.querySelector('#document-task-group [data-task="' + target + '"]'));
  setDocumentInputMode('file');
  selectHomeTab('document');
}

document.addEventListener('dragover', function(e) { e.preventDefault(); });
document.addEventListener('drop', function(e) {
  e.preventDefault();
  var f = e.dataTransfer.files[0];
  if (!isSupportedDocumentFile(f)) return;
  if (document.getElementById('tab-digest').checked) {
    showPdfRouteSheet(f);
  } else if (document.getElementById('tab-document').checked) {
    var dt = new DataTransfer();
    dt.items.add(f);
    var inp = document.getElementById('document-file');
    if (inp) {
      inp.files = dt.files;
      showFilename(inp, 'document-filename');
    }
    setDocumentInputMode('file');
  }
});
