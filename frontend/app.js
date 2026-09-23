/**
 * Avatar Storyteller Engine — Frontend Application Logic
 * Handles all UI interactions, API calls, file uploads, and render pipeline.
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════════════
// App State
// ═══════════════════════════════════════════════════════════════════════════
const STATE = {
  voiceoverPath:    null,
  voiceoverDuration: 0,
  avatarPath:       null,
  brollFolder:      '',
  folderClipCount:  0,
  position:         'right',
  strokeColor:      'white',
  captionPreset:    'capcut_yellow',
  currentJobId:     null,
  pollInterval:     null,
  gpuEncoder:       'detecting...',
  settings:         {},
};

const API = '';  // Same origin


// ═══════════════════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initSliders();
  loadGpuInfo();
  loadSettings();
  updateCaptionPositionDesc();
  updateEstimate();
});


// ═══════════════════════════════════════════════════════════════════════════
// Slider Utilities
// ═══════════════════════════════════════════════════════════════════════════
function updateSlider(input, displayId, formatter) {
  const display = document.getElementById(displayId);
  if (display) display.textContent = formatter(input.value);
  // Update CSS fill gradient
  const min = parseFloat(input.min), max = parseFloat(input.max), val = parseFloat(input.value);
  const pct = ((val - min) / (max - min)) * 100;
  input.style.setProperty('--pct', `${pct}%`);
}

function initSliders() {
  document.querySelectorAll('input[type="range"]').forEach(slider => {
    const min = parseFloat(slider.min), max = parseFloat(slider.max), val = parseFloat(slider.value);
    const pct = ((val - min) / (max - min)) * 100;
    slider.style.setProperty('--pct', `${pct}%`);
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// GPU Info
// ═══════════════════════════════════════════════════════════════════════════
async function loadGpuInfo() {
  try {
    const res  = await fetch(`${API}/api/gpu-info`);
    const data = await res.json();
    STATE.gpuEncoder = data.encoder || 'libx264';

    const dot   = document.getElementById('gpu-dot');
    const label = document.getElementById('gpu-label-text');
    if (dot && label) {
      label.textContent = data.encoder || 'libx264';
      dot.className = 'gpu-indicator';
      if (data.encoder === 'h264_nvenc') { dot.classList.add('nvenc'); }
      else if (data.encoder === 'h264_qsv') { dot.classList.add('qsv'); }
      else { dot.classList.add('cpu'); }
    }

    const estEncoder = document.getElementById('est-encoder');
    if (estEncoder) estEncoder.textContent = data.encoder || 'CPU';
    updateEstimate();
  } catch (e) {
    console.warn('[GPU] Failed to load GPU info:', e);
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Settings
// ═══════════════════════════════════════════════════════════════════════════
async function loadSettings() {
  try {
    const res  = await fetch(`${API}/api/settings`);
    STATE.settings = await res.json();
    const keyEl  = document.getElementById('settings-groq-key');
    const encEl  = document.getElementById('settings-encoder');
    const dirEl  = document.getElementById('settings-output-dir');
    if (keyEl) keyEl.value = STATE.settings.groq_api_key || '';
    if (encEl) encEl.value = STATE.settings.hardware_encoder || 'auto';
    if (dirEl) dirEl.value = STATE.settings.output_dir || '';
  } catch (e) {
    console.warn('[Settings] Load failed:', e);
  }
}

async function saveSettings() {
  const groqKey   = document.getElementById('settings-groq-key')?.value.trim() || '';
  const encoder   = document.getElementById('settings-encoder')?.value || 'auto';
  const outputDir = document.getElementById('settings-output-dir')?.value.trim() || '';

  const payload = { groq_api_key: groqKey, hardware_encoder: encoder };
  if (outputDir) payload.output_dir = outputDir;

  try {
    const res = await fetch(`${API}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const msg = document.getElementById('settings-msg');
      if (msg) { msg.style.display = 'block'; setTimeout(() => msg.style.display = 'none', 3000); }
      loadGpuInfo();
    }
  } catch (e) {
    alert('Failed to save settings: ' + e.message);
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Drag & Drop Handlers
// ═══════════════════════════════════════════════════════════════════════════
function onDragOver(e, el) {
  e.preventDefault();
  el.classList.add('drag-over');
}

function onDragLeave(el) {
  el.classList.remove('drag-over');
}

function handleVoiceoverDrop(e) {
  e.preventDefault();
  document.getElementById('voiceover-dropzone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleVoiceoverFile(file);
}

function handleAvatarDrop(e) {
  e.preventDefault();
  document.getElementById('avatar-dropzone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleAvatarFile(file);
}


// ═══════════════════════════════════════════════════════════════════════════
// File Upload — Voiceover
// ═══════════════════════════════════════════════════════════════════════════
async function handleVoiceoverFile(file) {
  if (!file) return;
  const allowed = ['.mp3', '.wav', '.m4a', '.aac', '.ogg'];
  const ext     = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast('❌ Unsupported audio format. Use: ' + allowed.join(', '), 'error');
    return;
  }

  showToast('📤 Uploading voiceover...', 'info');
  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch(`${API}/api/upload-audio`, { method: 'POST', body: form });
    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Upload failed');

    STATE.voiceoverPath     = data.path;
    STATE.voiceoverDuration = data.duration || 0;

    const loaded   = document.getElementById('voiceover-loaded');
    const fnEl     = document.getElementById('voiceover-filename');
    const durEl    = document.getElementById('voiceover-duration');

    fnEl.textContent  = file.name;
    durEl.textContent = `Duration: ${formatDuration(data.duration)} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    loaded.style.display = 'flex';

    // Auto-suggest output filename
    const outEl = document.getElementById('output-filename');
    if (outEl && !outEl.value) {
      const base = file.name.replace(/\.[^/.]+$/, '').replace(/\s+/g, '_');
      outEl.value = `${base}_avatar.mp4`;
    }

    updateEstimate();
    showToast(`✅ Audio loaded: ${formatDuration(data.duration)}`, 'success');
  } catch (e) {
    showToast('❌ Upload failed: ' + e.message, 'error');
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// File Upload — Avatar
// ═══════════════════════════════════════════════════════════════════════════
async function handleAvatarFile(file) {
  if (!file) return;
  const allowed = ['.png', '.jpg', '.jpeg', '.webp'];
  const ext     = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast('❌ Unsupported image format. Use: ' + allowed.join(', '), 'error');
    return;
  }

  // Show local preview immediately
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('avatar-preview-img');
    const ph  = document.getElementById('avatar-placeholder');
    if (img) { img.src = e.target.result; img.style.display = 'block'; }
    if (ph)  { ph.style.display = 'none'; }
  };
  reader.readAsDataURL(file);

  showToast('📤 Uploading avatar...', 'info');
  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch(`${API}/api/upload-avatar`, { method: 'POST', body: form });
    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Upload failed');

    STATE.avatarPath = data.path;

    const loaded = document.getElementById('avatar-loaded');
    const fnEl   = document.getElementById('avatar-filename');
    const infoEl = document.getElementById('avatar-info');
    fnEl.textContent  = file.name;
    infoEl.textContent = `${(data.size_bytes / 1024).toFixed(0)} KB · Stroke: ${STATE.strokeColor}`;
    loaded.style.display = 'flex';

    showToast('✅ Avatar uploaded!', 'success');
  } catch (e) {
    showToast('❌ Avatar upload failed: ' + e.message, 'error');
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// B-Roll Folder Scan
// ═══════════════════════════════════════════════════════════════════════════
async function scanFolder() {
  const folder = document.getElementById('broll-folder-input').value.trim();
  if (!folder) { showToast('📂 Please enter a folder path first', 'warning'); return; }

  STATE.brollFolder = folder;
  const btn = document.getElementById('btn-scan');
  btn.textContent = '⏳ Scanning...';
  btn.disabled = true;

  try {
    // First get folder stats
    const statsRes  = await fetch(`${API}/api/scan-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folder })
    });
    const stats = await statsRes.json();

    if (!stats.success) throw new Error(stats.error || 'Scan failed');

    STATE.folderClipCount = stats.clip_count;

    // Get clip preview/estimate
    const previewRes = await fetch(`${API}/api/preview-clips`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_path:    folder,
        audio_duration: STATE.voiceoverDuration || 120,
        stock_speed:    parseFloat(document.getElementById('stock-speed-slider').value),
      })
    });
    const preview = await previewRes.json();

    // Show stats
    const statsPanel = document.getElementById('folder-stats');
    statsPanel.style.display = 'flex';

    document.getElementById('stat-clip-count').textContent = stats.clip_count;
    document.getElementById('stat-size').textContent       = `${stats.total_size_mb?.toFixed(0) || '?'} MB`;
    document.getElementById('stat-clips-needed').textContent = preview.clips_needed || '?';
    document.getElementById('stat-wrap-status').textContent  = preview.will_wrap_pool ? '⚠️ Wrap' : '✅';

    updateEstimate();
    showToast(`✅ Found ${stats.clip_count} clips in folder!`, 'success');
  } catch (e) {
    showToast('❌ Scan failed: ' + e.message, 'error');
  } finally {
    btn.textContent = '🔍 Scan';
    btn.disabled = false;
  }
}

function resetFolderStats() {
  document.getElementById('folder-stats').style.display = 'none';
  STATE.folderClipCount = 0;
}


// ═══════════════════════════════════════════════════════════════════════════
// Position & Stroke Toggles
// ═══════════════════════════════════════════════════════════════════════════
function setPosition(pos) {
  STATE.position = pos;
  ['left', 'center', 'right'].forEach(p => {
    const btn = document.getElementById(`pos-${p}`);
    if (btn) {
      btn.classList.toggle('active', p === pos);
      btn.setAttribute('aria-pressed', p === pos ? 'true' : 'false');
    }
  });
  updateCaptionPositionDesc();
}

function setStroke(color) {
  STATE.strokeColor = color;
  ['white', 'gold', 'cyan', 'none'].forEach(c => {
    const btn = document.getElementById(`stroke-${c}`);
    if (btn) {
      btn.classList.toggle('active', c === color);
      btn.setAttribute('aria-pressed', c === color ? 'true' : 'false');
    }
  });
  // Update avatar info
  const infoEl = document.getElementById('avatar-info');
  if (infoEl && STATE.avatarPath) {
    infoEl.textContent = infoEl.textContent.replace(/Stroke: \w+/, `Stroke: ${color}`);
  }
}

function selectPreset(card) {
  document.querySelectorAll('.preset-card').forEach(c => {
    c.classList.remove('active');
    c.setAttribute('aria-pressed', 'false');
  });
  card.classList.add('active');
  card.setAttribute('aria-pressed', 'true');
  STATE.captionPreset = card.dataset.preset;
}

function updateCaptionPositionDesc() {
  const el  = document.getElementById('caption-pos-desc');
  if (!el) return;
  const map = {
    left:   'Avatar LEFT → Captions placed in RIGHT half (MarginL=960)',
    right:  'Avatar RIGHT → Captions placed in LEFT half (MarginR=960)',
    center: 'Avatar CENTER → Captions at BOTTOM CENTER (MarginV=50)',
  };
  el.textContent = map[STATE.position] || '';
}


// ═══════════════════════════════════════════════════════════════════════════
// Render Estimate
// ═══════════════════════════════════════════════════════════════════════════
function updateEstimate() {
  const durEl     = document.getElementById('est-duration');
  const renderEl  = document.getElementById('est-render-time');
  const clipsEl   = document.getElementById('est-clips');
  const encEl     = document.getElementById('est-encoder');

  const dur = STATE.voiceoverDuration;
  if (durEl)  durEl.textContent  = dur > 0 ? formatDuration(dur) : '—';

  // Estimate render time
  const speedup   = { 'h264_nvenc': 120, 'h264_qsv': 60, 'h264_amf': 80, 'libx264': 15 };
  const sp        = speedup[STATE.gpuEncoder] || 20;
  const estSec    = dur > 0 ? Math.round(dur / sp) : 0;
  if (renderEl) renderEl.textContent = dur > 0 ? `~${formatDuration(estSec)}` : '—';
  if (encEl)    encEl.textContent    = STATE.gpuEncoder || '—';

  // Clips estimate
  const speed     = parseFloat(document.getElementById('stock-speed-slider')?.value || '0.75');
  const avgEff    = 45 / speed;
  const needed    = dur > 0 ? Math.ceil(dur / avgEff) : 0;
  if (clipsEl) clipsEl.textContent = needed > 0 ? `~${needed}` : '—';
}


// ═══════════════════════════════════════════════════════════════════════════
// Render Pipeline
// ═══════════════════════════════════════════════════════════════════════════
async function startRender() {
  // Validation
  if (!STATE.voiceoverPath) { showToast('❌ Please upload a voiceover audio file', 'error'); return; }
  if (!STATE.avatarPath)    { showToast('❌ Please upload an avatar/portrait image', 'error'); return; }
  const folder = document.getElementById('broll-folder-input').value.trim();
  if (!folder)              { showToast('❌ Please specify a B-Roll folder path', 'error'); return; }

  const btn = document.getElementById('btn-render');
  btn.disabled = true;
  btn.textContent = '⏳ Starting render pipeline...';

  // Hide previous success/error
  document.getElementById('success-banner').classList.remove('visible');
  const progressSec = document.getElementById('progress-section');
  progressSec.classList.add('visible');
  setProgress(2, 'Preparing render job...');
  appendLog('🚀 Render job submitted...\n');

  const payload = {
    voiceover_path:   STATE.voiceoverPath,
    broll_folder:     folder,
    avatar_path:      STATE.avatarPath,
    avatar_position:  STATE.position,
    stroke_color:     STATE.strokeColor,
    stroke_width:     parseInt(document.getElementById('stroke-width-slider')?.value || '10'),
    blur_radius:      parseInt(document.getElementById('blur-slider')?.value || '12'),
    dark_tint:        parseFloat(document.getElementById('tint-slider')?.value || '25') / 100,
    stock_speed:      parseFloat(document.getElementById('stock-speed-slider')?.value || '0.75'),
    pitch_semitones:  parseFloat(document.getElementById('pitch-slider')?.value || '0'),
    voice_speed:      parseFloat(document.getElementById('speed-slider')?.value || '1.0'),
    caption_preset:   STATE.captionPreset,
    niche:            document.getElementById('niche-select')?.value || 'Stoicism & Philosophy',
    output_filename:  document.getElementById('output-filename')?.value.trim() || '',
  };

  try {
    const res  = await fetch(`${API}/api/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!data.job_id) throw new Error('No job ID returned');

    STATE.currentJobId = data.job_id;
    appendLog(`📋 Job ID: ${data.job_id}\n`);
    startPolling(data.job_id);
  } catch (e) {
    showError('Failed to start render: ' + e.message);
  }
}

function startPolling(jobId) {
  if (STATE.pollInterval) clearInterval(STATE.pollInterval);
  STATE.pollInterval = setInterval(async () => {
    try {
      const res  = await fetch(`${API}/api/job/${jobId}`);
      const data = await res.json();
      handleJobUpdate(data);
      if (data.status === 'complete' || data.status === 'error') {
        clearInterval(STATE.pollInterval);
        STATE.pollInterval = null;
      }
    } catch (e) {
      console.warn('[Poll] Error:', e);
    }
  }, 800);
}

function handleJobUpdate(data) {
  const pct     = data.percent || 0;
  const message = data.message || 'Processing...';

  setProgress(pct, message);
  appendLog(`[${new Date().toLocaleTimeString()}] ${message}\n`);

  if (data.status === 'complete') {
    onRenderComplete(data);
  } else if (data.status === 'error') {
    showError(data.message || 'Unknown error');
  }
}

function setProgress(pct, msg) {
  const bar   = document.getElementById('progress-bar');
  const msgEl = document.getElementById('progress-message');
  const pctEl = document.getElementById('progress-pct');
  if (bar)   bar.style.width   = `${pct}%`;
  if (msgEl) msgEl.textContent = msg;
  if (pctEl) pctEl.textContent = `${pct}%`;
}

function appendLog(text) {
  const log = document.getElementById('log-output');
  if (!log) return;
  log.textContent += text;
  log.scrollTop = log.scrollHeight;
}

function onRenderComplete(data) {
  const btn = document.getElementById('btn-render');
  btn.disabled = false;
  btn.textContent = '🚀 RENDER 1-HOUR VIDEO (GPU TURBO)';

  const banner = document.getElementById('success-banner');
  banner.classList.add('visible');

  document.getElementById('success-title').textContent = '🎉 Video Rendered Successfully!';
  document.getElementById('success-meta').textContent  =
    `${data.output || 'Output saved'} · ${data.size_mb || '?'} MB · ${data.clips_used || '?'} clips used · ${formatDuration(data.duration || 0)} voiceover`;

  appendLog(`\n✅ COMPLETE! Output: ${data.output}\n`);
  showToast('🎉 Video render complete!', 'success');
}

function showError(msg) {
  const btn = document.getElementById('btn-render');
  btn.disabled = false;
  btn.textContent = '🚀 RENDER 1-HOUR VIDEO (GPU TURBO)';
  setProgress(0, '❌ ' + msg);
  appendLog(`\n❌ ERROR: ${msg}\n`);
  showToast('❌ ' + msg, 'error');
}


// ═══════════════════════════════════════════════════════════════════════════
// Output Actions
// ═══════════════════════════════════════════════════════════════════════════
async function openOutputFolder() {
  try {
    await fetch(`${API}/api/open-output-folder`, { method: 'POST' });
  } catch (e) {
    showToast('Could not open folder: ' + e.message, 'error');
  }
}

function resetForNewRender() {
  document.getElementById('success-banner').classList.remove('visible');
  document.getElementById('progress-section').classList.remove('visible');
  setProgress(0, 'Ready');
  document.getElementById('log-output').textContent = 'Ready to render...\n';
  const btn = document.getElementById('btn-render');
  btn.disabled = false;
  btn.textContent = '🚀 RENDER 1-HOUR VIDEO (GPU TURBO)';
}


// ═══════════════════════════════════════════════════════════════════════════
// Outputs Panel
// ═══════════════════════════════════════════════════════════════════════════
async function openOutputsPanel() {
  document.getElementById('outputs-panel').classList.add('visible');
  await loadOutputsList();
}

function closeOutputsPanel(event) {
  if (!event || event.target === document.getElementById('outputs-panel')) {
    document.getElementById('outputs-panel').classList.remove('visible');
  }
}

async function loadOutputsList() {
  const list = document.getElementById('outputs-list');
  list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:24px;">Loading...</div>';
  try {
    const res   = await fetch(`${API}/api/outputs`);
    const files = await res.json();
    if (!files.length) {
      list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:var(--sp-2xl);">No rendered videos yet. Start your first render!</div>';
      return;
    }
    list.innerHTML = files.map(f => `
      <div class="output-file-row">
        <span style="font-size:1.6rem;">🎬</span>
        <div style="flex:1;">
          <div class="output-filename">${f.name}</div>
          <div class="output-size">${f.size_mb} MB · ${new Date(f.created * 1000).toLocaleDateString()}</div>
        </div>
        <a href="/api/download/${encodeURIComponent(f.name)}" download="${f.name}" class="btn btn-ghost" style="font-size:0.75rem;">⬇ Download</a>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = `<div style="color:var(--accent-red);padding:16px;">Error: ${e.message}</div>`;
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Settings Panel
// ═══════════════════════════════════════════════════════════════════════════
function openSettingsPanel() {
  document.getElementById('settings-panel').classList.add('visible');
}

function closeSettingsPanel(event) {
  if (!event || event.target === document.getElementById('settings-panel')) {
    document.getElementById('settings-panel').classList.remove('visible');
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════════════════════════════════
let _toastContainer;

function showToast(message, type = 'info') {
  if (!_toastContainer) {
    _toastContainer = document.createElement('div');
    _toastContainer.style.cssText = `
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      display: flex; flex-direction: column; gap: 8px; pointer-events: none;
    `;
    document.body.appendChild(_toastContainer);
  }

  const colors = {
    success: '#10B981', error: '#EF4444', warning: '#F59E0B', info: '#06B6D4'
  };

  const toast = document.createElement('div');
  toast.style.cssText = `
    background: rgba(15, 15, 25, 0.95); backdrop-filter: blur(16px);
    border: 1px solid ${colors[type] || colors.info}44;
    border-left: 3px solid ${colors[type] || colors.info};
    padding: 12px 18px; border-radius: 10px;
    font-size: 0.82rem; font-family: 'Inter', sans-serif;
    color: #F8FAFC; max-width: 320px; pointer-events: auto;
    animation: slide-in 0.3s ease; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  `;
  toast.textContent = message;
  _toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}


// ═══════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════
function formatDuration(sec) {
  if (!sec || sec <= 0) return '0:00';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}
