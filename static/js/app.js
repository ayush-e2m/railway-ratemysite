(function () {
  const qs = (s, r = document) => r.querySelector(s);
  const qsa = (s, r = document) => Array.from(r.querySelectorAll(s));

  const btnGo = qs('#go');
  const btnStop = qs('#stop');
  const btnDownload = qs('#download');
  const bar = qs('#progress');
  const barInner = qs('#progress .bar');
  const statusEl = qs('#status');
  const logEl = qs('#log');
  const thead = qs('#thead');
  const tbody = qs('#tbody');
  const downloadSection = qs('#download-section');

  let es = null;
  let total = 0;
  let completed = 0;
  let aborted = false;
  let currentSessionId = null;
  let analysisResults = [];

  function resetUI() {
    // Clear table columns
    qsa('#thead th:not(:first-child)').forEach(el => el.remove());
    qsa('#tbody tr').forEach(tr => qsa('td:not(:first-child)', tr).forEach(td => td.remove()));

    // Reset UI elements
    bar.classList.add('hidden');
    barInner.style.width = '0%';
    statusEl.textContent = '';
    statusEl.className = 'status';
    logEl.textContent = '';
    logEl.classList.add('hidden');
    downloadSection.classList.add('hidden');
    
    // Reset state
    completed = 0;
    total = 0;
    aborted = false;
    currentSessionId = null;
    analysisResults = [];
  }

  function appendColumnHeader(text) {
    const th = document.createElement('th');
    th.textContent = text || '—';
    th.title = text; // Tooltip for long domain names
    thead.appendChild(th);
  }

  function fillColumn(data) {
    qsa('#tbody tr').forEach(tr => {
      const key = tr.getAttribute('data-key');
      const td = document.createElement('td');
      let val = (data && data[key]) || '-';
      
      if (key === 'URL' && val && typeof val === 'string' && val !== '-') {
        const a = document.createElement('a');
        a.href = val;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = val;
        td.appendChild(a);
      } else {
        td.textContent = val;
        
        // Add score styling
        if (key.includes('Score') && val !== '-' && !isNaN(val)) {
          const score = parseInt(val);
          td.classList.add('score-cell');
          if (score >= 80) {
            td.classList.add('score-high');
          } else if (score >= 60) {
            td.classList.add('score-medium');
          } else {
            td.classList.add('score-low');
          }
        }
      }
      
      tr.appendChild(td);
    });
  }

  function setProgress(pct, text, type = '') {
    bar.classList.remove('hidden');
    barInner.style.width = Math.max(0, Math.min(100, pct)) + '%';
    statusEl.textContent = text || '';
    statusEl.className = `status ${type}`;
    
    // Add spinner for active states
    if (pct < 100 && !aborted) {
      if (!qs('.spinner', statusEl)) {
        const spinner = document.createElement('div');
        spinner.className = 'spinner';
        statusEl.prepend(spinner);
      }
    } else {
      const spinner = qs('.spinner', statusEl);
      if (spinner) spinner.remove();
    }
  }

  function addLog(line, type = '') {
    logEl.classList.remove('hidden');
    
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type ? `log-${type}` : ''}`;
    logEntry.textContent = line;
    
    logEl.appendChild(logEntry);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function formatLogLine(line) {
    const timestamp = new Date().toLocaleTimeString();
    return `[${timestamp}] ${line}`;
  }

  function showDownloadSection() {
    if (analysisResults.length > 0 && currentSessionId) {
      downloadSection.classList.remove('hidden');
      const resultCount = qs('#result-count');
      if (resultCount) {
        resultCount.textContent = analysisResults.length;
      }
    }
  }

  function stopStream() {
    if (es) { 
      es.close(); 
      es = null; 
    }
    btnGo.disabled = false;
    btnStop.disabled = true;
  }

  function downloadExcel() {
    if (!currentSessionId) {
      addLog('No session ID available for download', 'error');
      return;
    }

    btnDownload.disabled = true;
    btnDownload.innerHTML = '<div class="spinner"></div> Preparing...';

    // Create download link
    const downloadUrl = `/download/excel/${currentSessionId}`;
    
    // Use fetch to handle potential errors
    fetch(downloadUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.blob();
      })
      .then(blob => {
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `ratemysite_analysis_${new Date().toISOString().slice(0, 10)}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        addLog('Excel file downloaded successfully! ✅', 'success');
        setProgress(100, 'Download complete!', 'success');
      })
      .catch(error => {
        console.error('Download failed:', error);
        addLog(`Download failed: ${error.message}`, 'error');
        setProgress(100, 'Download failed', 'error');
      })
      .finally(() => {
        btnDownload.disabled = false;
        btnDownload.innerHTML = '📊 Download Excel';
      });
  }

  // Event Listeners
  btnGo.addEventListener('click', () => {
    resetUI();
    const urls = [qs('#u1').value, qs('#u2').value, qs('#u3').value, qs('#u4').value]
      .map(s => s.trim())
      .filter(Boolean);

    if (!urls.length) {
      statusEl.textContent = 'Please enter at least one URL.';
      statusEl.className = 'status warning';
      return;
    }

    btnGo.disabled = true;
    btnStop.disabled = false;
    setProgress(0, 'Starting analysis...');
    addLog(formatLogLine(`🚀 Starting analysis of ${urls.length} site(s)...`));

    const params = new URLSearchParams();
    urls.forEach(u => params.append('u', u));
    es = new EventSource('/stream?' + params.toString());

    es.addEventListener('init', (e) => {
      const payload = JSON.parse(e.data);
      total = payload.total || urls.length;
      currentSessionId = payload.session_id;
      addLog(formatLogLine(`Initialized analysis session: ${currentSessionId || 'unknown'}`));
      setProgress(1, 'Initializing...');
    });

    es.addEventListener('start_url', (e) => {
      const { index, url } = JSON.parse(e.data);
      addLog(formatLogLine(`--- [${index}/${total}] Starting: ${url} ---`));
      
      try {
        const urlObj = new URL(url);
        appendColumnHeader(urlObj.hostname.replace('www.', ''));
      } catch {
        appendColumnHeader(url);
      }
      
      const pct = ((index - 1) / total) * 100;
      setProgress(pct + 2, `Analyzing ${url}...`);
    });

    es.addEventListener('progress', (e) => {
      const { index, phase, p, of } = JSON.parse(e.data);
      const base = ((index - 1) / total) * 100;
      const within = (p / of) * (100 / total);
      setProgress(base + within, `[${index}/${total}] ${phase}`);
    });

    es.addEventListener('debug', (e) => {
      const { index, message } = JSON.parse(e.data);
      if (message) {
        addLog(formatLogLine(`  [${index}] ${message}`));
      }
    });

    es.addEventListener('result', (e) => {
      const { index, url, data, error } = JSON.parse(e.data);
      if (error) {
        addLog(formatLogLine(`❌ [${index}/${total}] ERROR: ${error}`), 'error');
        fillColumn({ "Company": "Error", "URL": url, "Overall Score": "-" });
      } else {
        addLog(formatLogLine(`✅ [${index}/${total}] SUCCESS: ${url}`), 'success');
        fillColumn(data);
        analysisResults.push(data);
      }
      completed += 1;
      const pct = (completed / total) * 100;
      setProgress(pct, `Completed ${completed} of ${total}`);
    });

    es.addEventListener('done', () => {
      const message = aborted ? 'Analysis stopped' : 'Analysis complete!';
      const type = aborted ? 'warning' : 'success';
      setProgress(100, message, type);
      addLog(formatLogLine(`🎉 ${message} Total results: ${analysisResults.length}`), type);
      stopStream();
      
      if (analysisResults.length > 0) {
        showDownloadSection();
      }
    });

    es.onerror = () => {
      if (!aborted) {
        addLog(formatLogLine('❌ Stream connection failed. Check server console.'), 'error');
        setProgress(100, 'Connection failed', 'error');
      }
      stopStream();
    };
  });

  btnStop.addEventListener('click', () => {
    aborted = true;
    addLog(formatLogLine('🛑 Stopping analysis...'), 'warning');
    stopStream();
    setProgress(100, 'Stopped', 'warning');
  });

  if (btnDownload) {
    btnDownload.addEventListener('click', downloadExcel);
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      switch(e.key) {
        case 'Enter':
          if (!btnGo.disabled) {
            e.preventDefault();
            btnGo.click();
          }
          break;
        case 's':
          if (!btnStop.disabled) {
            e.preventDefault();
            btnStop.click();
          }
          break;
        case 'd':
          if (btnDownload && !btnDownload.disabled && !downloadSection.classList.contains('hidden')) {
            e.preventDefault();
            btnDownload.click();
          }
          break;
      }
    }
    
    // ESC to stop
    if (e.key === 'Escape' && !btnStop.disabled) {
      btnStop.click();
    }
  });

  // Auto-focus first input on page load
  window.addEventListener('load', () => {
    const firstInput = qs('#u1');
    if (firstInput) {
      firstInput.focus();
    }
  });

  // URL validation and auto-correction
  qsa('input[type="url"]').forEach(input => {
    input.addEventListener('blur', (e) => {
      let value = e.target.value.trim();
      if (value && !value.startsWith('http://') && !value.startsWith('https://')) {
        e.target.value = 'https://' + value;
      }
    });
    
    // Enter key to start analysis
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !btnGo.disabled) {
        btnGo.click();
      }
    });
  });

  // Add tooltips for better UX
  function addTooltip(element, text) {
    element.title = text;
  }

  // Initialize tooltips
  if (btnGo) addTooltip(btnGo, 'Start analysis (Ctrl+Enter)');
  if (btnStop) addTooltip(btnStop, 'Stop analysis (Ctrl+S or Esc)');
  if (btnDownload) addTooltip(btnDownload, 'Download results as Excel file (Ctrl+D)');

  // Show keyboard shortcuts help
  console.log('🎹 Keyboard shortcuts:');
  console.log('  Ctrl+Enter: Start analysis');
  console.log('  Ctrl+S or Esc: Stop analysis');
  console.log('  Ctrl+D: Download Excel (when available)');
  
})();
