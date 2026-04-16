(function() {
  var hash = location.hash.slice(1);
  var initialDocumentTask = (hash === 'translate' || hash === 'summarize') ? hash : 'translate';
  if (_allHomeTabs.includes(hash)) {
    selectHomeTab(hash, false);
  } else if (hash === 'translate' || hash === 'summarize') {
    selectHomeTab('document', false);
  }
  setDocumentTask(initialDocumentTask, document.querySelector('#document-task-group [data-task="' + initialDocumentTask + '"]'));
  setDocumentInputMode('text');
  var initialLabTask = Object.keys(_labTasks)[0] || 'image_ocr';
  setLabTask(initialLabTask, document.querySelector('#lab-task-group [data-task="' + initialLabTask + '"]'));
  applyLabTaskAvailability();
  applyHomeTabVisibility();
})();
