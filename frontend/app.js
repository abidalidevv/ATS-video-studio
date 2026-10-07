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
  voiceoverUrl:     null,
  voiceoverDuration: 0,
  avatarPath:       null,
  avatarUrl:        null,
  brollFolder:      '',
  brollPreviewUrl:  null,
  folderClipCount:  0,
  position:         'right',
  avatarFlip:       false,
  avatarSize:       920,
  avatarOpacity:    1.0,
  strokeColor:      'white',
  strokeWidth:      10,
  blurRadius:       0,
  darkTint:         0.25,
  captionPreset:    'capcut_yellow',
  captionPosition:  'center',
  captionSize:      'large',
  brollAudio:       'muted',
  visualizerEnabled:  false,
  visualizerStyle:    'glass_pill_cyan',
  visualizerPosition: 'top_center',
  visualizerTitle:    'Stoic Wisdom',
  visualizerSubtitle: 'Audio Story Series',
  currentJobId:     null,
  pollInterval:     null,
  gpuEncoder:       'detecting...',
  settings:         {},
  currentWizardStep: 1,
  bgmPath:          null,
  bgmUrl:           null,
  bgmDuration:      0,
  bgmVolume:        0.07,
  // B-Roll Pacing Mode & Dynamic Slicing
  brollPacingMode:  'full',      // 'full' | 'fast_cuts'
  brollMinSec:     5.0,
  brollMaxSec:     9.0,
  // Custom Green-Screen Visualizer Video State
  visMode:          'template',  // 'template' | 'video'
  visVideoPath:     null,
  visVideoUrl:      null,
  visVideoFilename: null,
  chromaKeyColor:   '#00FF00',
  chromaSimilarity: 0.25,
  chromaBlend:      0.08,
  chromaPreviewMode: 'keyed',    // 'keyed' | 'raw'
  // Studio Canvas Drag & Drop State (1920x1080 canvas coordinates)
  customLayout: {
    avatar: { x: null, y: null },
    caption: { x: null, y: null, w: null, h: null },
    visualizer: { x: null, y: null, scale: 1.0 },
    gridVisible: false
  },
  previewPlayback: {
    isPlaying: false,
    audioObj: null,
    bgmAudioObj: null,
    currentTime: 0,
    animFrame: null,
    synthOsc: null
  }
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
  updateVisPreview();
  updateEstimate();
  initStudioStage();
  syncStageFromState();

  const nicheSelect = document.getElementById('niche-select');
  if (nicheSelect) {
    nicheSelect.addEventListener('change', () => {
      onNicheChange(nicheSelect.value);
    });
  }

  // Initialize Step 1 of Multi-Step Wizard
  goToWizardStep(1);

  // Run System Health & Storage Pre-Flight Guard Check on Startup
  checkSystemHealthOnStartup();
});

// ═══════════════════════════════════════════════════════════════════════════
// Multi-Step Wizard Form Navigation
// ═══════════════════════════════════════════════════════════════════════════
function goToWizardStep(stepNum) {
  const step = Math.max(1, Math.min(5, parseInt(stepNum, 10)));
  STATE.currentWizardStep = step;

  // Update tabs
  for (let i = 1; i <= 5; i++) {
    const tab = document.getElementById(`tab-step-${i}`);
    if (tab) {
      tab.classList.toggle('active', i === step);
      tab.classList.toggle('completed', i < step);
    }
    const card = document.getElementById(`wizard-step-${i}`);
    if (card) {
      card.classList.toggle('active', i === step);
    }
  }

  // Update counters
  document.querySelectorAll('.current-step-num').forEach(el => el.textContent = step.toString());

  // If entering step 5 (Studio Canvas & Render), sync everything
  if (step === 5) {
    syncStageFromState();
    renderStagePlayerCard();
  }

  // Smoothly scroll to top of wizard stepper
  const stepper = document.getElementById('wizard-stepper');
  if (stepper) {
    const y = stepper.getBoundingClientRect().top + window.pageYOffset - 16;
    window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
  }
}

function nextWizardStep() {
  if (STATE.currentWizardStep < 5) {
    goToWizardStep(STATE.currentWizardStep + 1);
  }
}

function prevWizardStep() {
  if (STATE.currentWizardStep > 1) {
    goToWizardStep(STATE.currentWizardStep - 1);
  }
}

function onNicheChange(nicheVal) {
  const nicheCaptions = {
    'Stoicism & Philosophy': 'In the depths of adversity you find your truest inner strength.',
    'Dark Psychology': 'The mind conceals ancient secrets that conscious thought cannot always perceive.',
    'Motivation': 'Discipline is the unbreakable bridge between ambition and legendary achievement today.',
    'Narrative Storytelling': 'The midnight knock revealed a dark mystery hidden for ten years.',
    'True Crime': 'Behind every locked door lies an untold truth waiting to emerge.',
    'Business': 'Speed and relentless execution define the greatest moguls of our modern world.',
    'Sci-Fi': 'Beyond the event horizon time becomes an endless sea of stars.',
    'Horror': 'The cold footsteps stopped right outside the locked door in pitch darkness.',
    'Wealth': 'True wealth is measured by the hours of freedom you own completely.'
  };

  const text = nicheCaptions[nicheVal] || nicheCaptions['Motivation'];
  const captionEl = document.getElementById('stage-caption-content');
  if (captionEl) {
    const words = text.split(' ');
    captionEl.innerHTML = words.map((w, i) => `<span class="demo-word${i === 0 ? ' active' : ''}" data-w="${i}">${w}</span>`).join(' ');
  }

  // Update visualizer title if user hasn't typed custom title
  renderStagePlayerCard();
}


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
  const pitchEl = document.getElementById('pitch-slider');
  if (pitchEl) onPitchSliderChange(pitchEl);
  const speedEl = document.getElementById('speed-slider');
  if (speedEl) onSpeedSliderChange(speedEl);
  const blurEl = document.getElementById('blur-slider');
  if (blurEl) updateBlurSlider(blurEl);
}

// ─ Quick Pitch & Speed Handlers ─────────────────────────────────────────────
function setPitch(val) {
  const slider = document.getElementById('pitch-slider');
  if (!slider) return;
  slider.value = val;
  onPitchSliderChange(slider);
}

function onPitchSliderChange(slider) {
  const v = parseFloat(slider.value);
  const display = document.getElementById('pitch-display');
  const label = v === 0 ? '0 st (Natural)' : v > 0 ? `+${v} st (High)` : `${v} st (Deep)`;
  if (display) display.textContent = label;

  document.getElementById('pitch-pill-deep')?.classList.toggle('active', v === -2);
  document.getElementById('pitch-pill-natural')?.classList.toggle('active', v === 0);
  document.getElementById('pitch-pill-high')?.classList.toggle('active', v === 2);

  const min = parseFloat(slider.min), max = parseFloat(slider.max);
  slider.style.setProperty('--pct', `${((v - min) / (max - min)) * 100}%`);
}

function setSpeed(val) {
  const slider = document.getElementById('speed-slider');
  if (!slider) return;
  slider.value = val;
  onSpeedSliderChange(slider);
}

function onSpeedSliderChange(slider) {
  const v = parseFloat(slider.value);
  const display = document.getElementById('speed-display');
  const label = Math.abs(v - 1.0) < 0.01 ? '1.00x (Normal)' : v < 1.0 ? `${v.toFixed(2)}x (Slow)` : `${v.toFixed(2)}x (Fast)`;
  if (display) display.textContent = label;

  document.getElementById('speed-pill-slow')?.classList.toggle('active', Math.abs(v - 0.9) < 0.02);
  document.getElementById('speed-pill-normal')?.classList.toggle('active', Math.abs(v - 1.0) < 0.02);
  document.getElementById('speed-pill-fast')?.classList.toggle('active', Math.abs(v - 1.15) < 0.02);

  const min = parseFloat(slider.min), max = parseFloat(slider.max);
  slider.style.setProperty('--pct', `${((v - min) / (max - min)) * 100}%`);
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

function handleBgmDrop(e) {
  e.preventDefault();
  document.getElementById('bgm-dropzone')?.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleBgmFile(file);
}

function handleAvatarDrop(e) {
  e.preventDefault();
  document.getElementById('avatar-dropzone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleAvatarFile(file);
}

function handleVisVideoDrop(e) {
  e.preventDefault();
  document.getElementById('vis-video-dropzone')?.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleVisVideoUpload(file);
}

async function handleBgmFile(file) {
  if (!file) return;
  const allowed = ['.mp3', '.wav', '.m4a', '.aac', '.ogg'];
  const ext     = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast('❌ Unsupported audio format. Use: ' + allowed.join(', '), 'error');
    return;
  }

  // Instant local preview so UI never waits
  const localBlobUrl = URL.createObjectURL(file);
  STATE.bgmUrl = localBlobUrl;

  const bgmDropzone    = document.getElementById('bgm-dropzone');
  const bgmPrompt      = document.getElementById('bgm-prompt');
  const bgmLoadedInner = document.getElementById('bgm-loaded-inner');
  const fnEl           = document.getElementById('bgm-filename');
  const durEl          = document.getElementById('bgm-duration');

  if (fnEl)  fnEl.textContent  = file.name;
  if (durEl) durEl.textContent = `Uploading... · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
  if (bgmPrompt) bgmPrompt.style.display = 'none';
  if (bgmLoadedInner) bgmLoadedInner.style.display = 'flex';
  if (bgmDropzone) bgmDropzone.classList.add('has-file');

  showToast('📤 Uploading background music track...', 'info');
  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch(`${API}/api/upload-bgm`, { method: 'POST', body: form });
    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Upload failed');

    STATE.bgmPath     = data.path;
    STATE.bgmUrl      = data.url || localBlobUrl;
    STATE.bgmDuration = data.duration || 0;

    if (durEl) durEl.textContent = `Looping Ambience: ${formatDuration(data.duration)} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    showToast(`✅ Background music loaded (${formatDuration(data.duration)})`, 'success');
  } catch (e) {
    showToast(`❌ BGM upload failed: ${e.message}`, 'error');
  }
}

function removeBgm() {
  STATE.bgmPath = null;
  STATE.bgmUrl = null;
  STATE.bgmDuration = 0;
  if (STATE.previewPlayback.bgmAudioObj) {
    STATE.previewPlayback.bgmAudioObj.pause();
    STATE.previewPlayback.bgmAudioObj = null;
  }
  const bgmDropzone    = document.getElementById('bgm-dropzone');
  const bgmPrompt      = document.getElementById('bgm-prompt');
  const bgmLoadedInner = document.getElementById('bgm-loaded-inner');
  if (bgmPrompt) bgmPrompt.style.display = 'flex';
  if (bgmLoadedInner) bgmLoadedInner.style.display = 'none';
  if (bgmDropzone) bgmDropzone.classList.remove('has-file');

  const input = document.getElementById('bgm-file-input');
  if (input) input.value = '';
  showToast('Background music removed', 'info');
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

  // Instant local preview so UI never feels frozen
  const localBlobUrl = URL.createObjectURL(file);
  STATE.voiceoverUrl = localBlobUrl;

  const dropzone    = document.getElementById('voiceover-dropzone');
  const promptEl    = document.getElementById('voiceover-prompt');
  const loadedInner = document.getElementById('voiceover-loaded-inner');
  const fnEl        = document.getElementById('voiceover-filename');
  const durEl       = document.getElementById('voiceover-duration');

  if (fnEl)  fnEl.textContent = file.name;
  if (durEl) durEl.textContent = `Probing... · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
  if (promptEl) promptEl.style.display = 'none';
  if (loadedInner) loadedInner.style.display = 'flex';
  if (dropzone) dropzone.classList.add('has-file');

  const audioProbe = new Audio();
  audioProbe.src = localBlobUrl;
  audioProbe.onloadedmetadata = () => {
    if (audioProbe.duration && !STATE.voiceoverDuration) {
      STATE.voiceoverDuration = audioProbe.duration;
      if (durEl) durEl.textContent = `Duration: ${formatDuration(audioProbe.duration)} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
      updateEstimate();
      syncStageFromState();
    }
  };

  // Auto-suggest output filename immediately
  const outEl = document.getElementById('output-filename');
  if (outEl && !outEl.value) {
    const base = file.name.replace(/\.[^/.]+$/, '').replace(/\s+/g, '_');
    outEl.value = `${base}_avatar.mp4`;
  }

  showToast('📤 Uploading voiceover...', 'info');
  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch(`${API}/api/upload-audio`, { method: 'POST', body: form });
    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Upload failed');

    STATE.voiceoverPath     = data.path;
    STATE.voiceoverUrl      = data.url || localBlobUrl;
    STATE.voiceoverDuration = data.duration || STATE.voiceoverDuration || 0;

    if (durEl) durEl.textContent = `Duration: ${formatDuration(data.duration)} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    updateEstimate();
    syncStageFromState();
    showToast(`✅ Audio ready: ${formatDuration(data.duration)}`, 'success');

    // Trigger smart background pre-transcription immediately
    startBackgroundPreTranscription(data.path, STATE.niche);
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

  // Show local preview immediately with zero-copy blob URL
  const localBlobUrl = URL.createObjectURL(file);
  const img = document.getElementById('avatar-preview-img');
  const ph  = document.getElementById('avatar-placeholder');
  if (img) { img.src = localBlobUrl; img.style.display = 'block'; }
  if (ph)  { ph.style.display = 'none'; }
  STATE.avatarUrl = localBlobUrl;

  const avatarDropzone    = document.getElementById('avatar-dropzone');
  const avatarPrompt      = document.getElementById('avatar-prompt');
  const avatarLoadedInner = document.getElementById('avatar-loaded-inner');
  const fnEl              = document.getElementById('avatar-filename');
  const infoEl            = document.getElementById('avatar-info');

  if (fnEl)   fnEl.textContent   = file.name;
  if (infoEl) infoEl.textContent = `Uploading... · ${(file.size / 1024).toFixed(0)} KB`;
  if (avatarPrompt) avatarPrompt.style.display = 'none';
  if (avatarLoadedInner) avatarLoadedInner.style.display = 'flex';
  if (avatarDropzone) avatarDropzone.classList.add('has-file');

  syncStageFromState();

  showToast('📤 Uploading avatar...', 'info');
  const form = new FormData();
  form.append('file', file);

  try {
    const res  = await fetch(`${API}/api/upload-avatar`, { method: 'POST', body: form });
    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Upload failed');

    STATE.avatarPath = data.path;
    STATE.avatarUrl  = data.url || localBlobUrl;

    if (infoEl) infoEl.textContent = `${(data.size_bytes / 1024).toFixed(0)} KB · Stroke: ${STATE.strokeColor}`;
    syncStageFromState();
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
  if (btn) { btn.textContent = '⏳ Scanning...'; btn.disabled = true; }

  try {
    const statsRes  = await fetch(`${API}/api/scan-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folder })
    });
    const stats = await statsRes.json();
    if (!stats.success) throw new Error(stats.error || 'Scan failed');

    applyFolderStats(stats, folder);
    showToast(`✅ Found ${stats.clip_count} clips in folder!`, 'success');
  } catch (e) {
    showToast('❌ Scan failed: ' + e.message, 'error');
  } finally {
    if (btn) { btn.textContent = '🔍 Scan'; btn.disabled = false; }
  }
}

async function browseFolder() {
  const btn = document.getElementById('btn-browse');
  if (btn) { btn.textContent = '⏳ Choosing...'; btn.disabled = true; }
  try {
    const res = await fetch(`${API}/api/browse-folder`, { method: 'POST' });
    const data = await res.json();
    if (data.success && data.folder_path) {
      document.getElementById('broll-folder-input').value = data.folder_path;
      STATE.brollFolder = data.folder_path;
      if (data.stats && data.stats.success) {
        applyFolderStats(data.stats, data.folder_path);
      } else {
        await scanFolder();
      }
      showToast('📂 Folder selected!', 'success');
    }
  } catch (e) {
    showToast('❌ Browse failed: ' + e.message, 'error');
  } finally {
    if (btn) { btn.textContent = '📂 Browse'; btn.disabled = false; }
  }
}

function applyFolderStats(stats, folder) {
  STATE.folderClipCount = stats.clip_count;
  const statsPanel = document.getElementById('folder-stats');
  if (statsPanel) statsPanel.style.display = 'flex';

  const countEl = document.getElementById('stat-clip-count');
  const sizeEl  = document.getElementById('stat-size');
  if (countEl) countEl.textContent = stats.clip_count;
  if (sizeEl)  sizeEl.textContent  = `${stats.total_size_mb?.toFixed(0) || '?'} MB`;

  updateEstimate();
  syncStageFromState();

  // Asynchronously request clip estimation and frame extraction without blocking UI
  Promise.all([
    fetch(`${API}/api/preview-clips`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_path:    folder,
        audio_duration: STATE.voiceoverDuration || 120,
        stock_speed:    parseFloat(document.getElementById('stock-speed-slider')?.value || '0.75'),
        pacing_mode:    STATE.brollPacingMode || 'full',
        min_clip_sec:   STATE.brollMinSec || 5.0,
        max_clip_sec:   STATE.brollMaxSec || 9.0,
      })
    }).then(r => r.json()).then(preview => {
      const neededEl = document.getElementById('stat-clips-needed');
      const wrapEl   = document.getElementById('stat-wrap-status');
      if (neededEl) neededEl.textContent = preview.clips_needed || '?';
      if (wrapEl)   wrapEl.textContent   = preview.will_wrap_pool ? '⚠️ Wrap' : '✅';
      updateEstimate();
    }).catch(() => {}),

    fetch(`${API}/api/sample-broll-frame`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folder })
    }).then(r => r.json()).then(frameData => {
      if (frameData.success && frameData.url) {
        STATE.brollPreviewUrl = frameData.url;
        syncStageFromState();
      }
    }).catch(() => {})
  ]);
}

function resetFolderStats() {
  document.getElementById('folder-stats').style.display = 'none';
  STATE.folderClipCount = 0;
}

// ── B-Roll Pacing Mode & Fair-Use Slicing Functions ─────────────────────────
function setBrollPacing(mode) {
  STATE.brollPacingMode = mode;
  const btnFull = document.getElementById('btn-pacing-full');
  const btnFast = document.getElementById('btn-pacing-fast');
  const panel   = document.getElementById('pacing-sliders-panel');
  const badge   = document.getElementById('pacing-badge');

  if (btnFull) btnFull.classList.toggle('active', mode === 'full');
  if (btnFast) btnFast.classList.toggle('active', mode === 'fast_cuts');
  if (panel)   panel.style.display = (mode === 'fast_cuts' ? 'flex' : 'none');
  if (badge) {
    badge.textContent = mode === 'fast_cuts' ? '⚡ 5s–9s Fast Cuts Active' : '🛡️ YouTube Fair Use Safe';
  }

  refreshClipPreview();
  updateEstimate();
  showToast(mode === 'fast_cuts' ? '⚡ Dynamic Fast Cuts Active (5s–9s slices)' : '🎞️ Stock Footage Pacing: As-Is (Full clips)', 'info');
}

function onPacingMinChange(val) {
  let minVal = parseFloat(val);
  const maxSlider = document.getElementById('pacing-max-slider');
  if (maxSlider && minVal >= parseFloat(maxSlider.value)) {
    minVal = Math.max(3, parseFloat(maxSlider.value) - 1);
    document.getElementById('pacing-min-slider').value = minVal;
  }
  STATE.brollMinSec = minVal;
  const disp = document.getElementById('pacing-min-val');
  if (disp) disp.textContent = `${minVal.toFixed(1)}s`;
  refreshClipPreview();
  updateEstimate();
}

function onPacingMaxChange(val) {
  let maxVal = parseFloat(val);
  const minSlider = document.getElementById('pacing-min-slider');
  if (minSlider && maxVal <= parseFloat(minSlider.value)) {
    maxVal = parseFloat(minSlider.value) + 1;
    document.getElementById('pacing-max-slider').value = maxVal;
  }
  STATE.brollMaxSec = maxVal;
  const disp = document.getElementById('pacing-max-val');
  if (disp) disp.textContent = `${maxVal.toFixed(1)}s`;
  refreshClipPreview();
  updateEstimate();
}

function refreshClipPreview() {
  const folder = document.getElementById('broll-folder-input')?.value.trim();
  if (!folder) return;

  fetch(`${API}/api/preview-clips`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      folder_path:    folder,
      audio_duration: STATE.voiceoverDuration || 120,
      stock_speed:    parseFloat(document.getElementById('stock-speed-slider')?.value || '0.75'),
      pacing_mode:    STATE.brollPacingMode || 'full',
      min_clip_sec:   STATE.brollMinSec || 5.0,
      max_clip_sec:   STATE.brollMaxSec || 9.0
    })
  }).then(r => r.json()).then(preview => {
    if (preview.success) {
      const neededEl = document.getElementById('stat-clips-needed');
      const wrapEl   = document.getElementById('stat-wrap-status');
      if (neededEl) neededEl.textContent = preview.clips_needed || '?';
      if (wrapEl)   wrapEl.textContent   = preview.will_wrap_pool ? '⚠️ Wrap' : '✅';
      updateEstimate();
    }
  }).catch(() => {});
}


// ═══════════════════════════════════════════════════════════════════════════
// Position & Stroke Toggles
// ═══════════════════════════════════════════════════════════════════════════
function setPosition(pos) {
  STATE.position = pos;
  STATE.customLayout.avatar.x = null;
  STATE.customLayout.avatar.y = null;
  ['left', 'center', 'right'].forEach(p => {
    const btn = document.getElementById(`pos-${p}`);
    if (btn) {
      btn.classList.toggle('active', p === pos);
      btn.setAttribute('aria-pressed', p === pos ? 'true' : 'false');
    }
  });
  updateCaptionPositionDesc();
  syncStageFromState();
}

function toggleAvatarFlip() {
  STATE.avatarFlip = !STATE.avatarFlip;
  const btn = document.getElementById('btn-avatar-flip');
  const img = document.getElementById('avatar-preview-img');
  if (btn) {
    btn.classList.toggle('active', STATE.avatarFlip);
    btn.textContent = STATE.avatarFlip ? '🔄 Mirror ON (Flipped)' : '🔄 Mirror OFF (Normal)';
  }
  if (img) {
    img.style.transform = STATE.avatarFlip ? 'scaleX(-1)' : 'none';
  }
  syncStageFromState();
  showToast(STATE.avatarFlip ? '🔄 Avatar horizontally mirrored' : '🔄 Avatar orientation reset', 'info');
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
  syncStageFromState();
}

function selectPreset(card) {
  document.querySelectorAll('.preset-card, .preset-card-visual').forEach(c => {
    c.classList.remove('active');
    c.setAttribute('aria-pressed', 'false');
  });
  card.classList.add('active');
  card.setAttribute('aria-pressed', 'true');
  STATE.captionPreset = card.dataset.preset;
  syncStageFromState();
}

function updateAvatarSize(slider) {
  const val = parseInt(slider.value, 10);
  STATE.avatarSize = val;
  const label = val >= 920 ? `${val}px (Full / Large)` : val >= 750 ? `${val}px (Medium)` : `${val}px (Small)`;
  const display = document.getElementById('avatar-size-display');
  if (display) display.textContent = label;
  
  // Scale the avatar preview image slightly to reflect size change
  const img = document.getElementById('avatar-preview-img');
  if (img) {
    img.style.maxHeight = `${Math.min(100, Math.round((val / 920) * 100))}%`;
  }
  syncStageFromState();
}

function updateAvatarOpacity(slider) {
  const val = parseInt(slider.value, 10);
  STATE.avatarOpacity = val / 100;
  const display = document.getElementById('avatar-opacity-display');
  if (display) {
    display.textContent = val === 100 ? '100% Solid (Default OFF)' : `${val}%`;
  }
  syncStageFromState();
}

function updateBlurSlider(slider) {
  const val = parseInt(slider.value, 10);
  STATE.blurRadius = val;
  const display = document.getElementById('blur-display');
  const btn = document.getElementById('btn-blur-toggle');
  if (display) {
    display.textContent = val === 0 ? '0px (OFF)' : `${val}px`;
  }
  if (btn) {
    btn.textContent = val === 0 ? '🚫 Blur OFF' : '🌫️ Blur ON';
    btn.classList.toggle('active', val > 0);
  }
  syncStageFromState();
}

function toggleBlur() {
  const slider = document.getElementById('blur-slider');
  if (!slider) return;
  const current = parseInt(slider.value, 10);
  const next = current === 0 ? 12 : 0;
  slider.value = next;
  updateBlurSlider(slider);
  showToast(next === 0 ? '🚫 Background blur turned OFF (100% Crisp)' : '🌫️ Background blur set to 12px', 'info');
}

function setBrollAudio(mode) {
  STATE.brollAudio = mode;
  ['muted', 'ambient'].forEach(m => {
    const btn = document.getElementById(`audio-${m}`);
    if (btn) {
      btn.classList.toggle('active', m === mode);
      btn.setAttribute('aria-pressed', m === mode ? 'true' : 'false');
    }
  });
  showToast(mode === 'muted' ? '🔇 Stock footage sound 100% MUTED' : '🔈 Stock footage sound set to 3% low ambient', 'info');
}

function setCaptionPosition(pos) {
  STATE.captionPosition = pos;
  STATE.customLayout.caption.x = null;
  STATE.customLayout.caption.y = null;
  ['center', 'bottom'].forEach(p => {
    const btn = document.getElementById(`cap-pos-${p}`);
    if (btn) {
      btn.classList.toggle('active', p === pos);
      btn.setAttribute('aria-pressed', p === pos ? 'true' : 'false');
    }
  });
  updateCaptionPositionDesc();
  syncStageFromState();
}

function setCaptionSize(size) {
  STATE.captionSize = size;
  ['medium', 'large', 'huge'].forEach(s => {
    const btn = document.getElementById(`cap-size-${s}`);
    if (btn) {
      btn.classList.toggle('active', s === size);
      btn.setAttribute('aria-pressed', s === size ? 'true' : 'false');
    }
  });
  updateCaptionPositionDesc();
  syncStageFromState();
}

function updateCaptionPositionDesc() {
  const el = document.getElementById('caption-pos-desc');
  if (!el) return;
  const sizeLabels = { medium: '52px', large: '68px (Large)', huge: '82px (Huge)' };
  const sLabel = sizeLabels[STATE.captionSize] || '68px';

  if (STATE.captionPosition === 'center') {
    el.innerHTML = `<strong>🎯 DEAD CENTER</strong> (horizontally &amp; vertically) · <span style="color:var(--accent-secondary);font-weight:600;">${sLabel} Viral Font</span> · Prominent across entire video`;
  } else {
    const map = {
      left:   `Avatar in LEFT 25% ➔ Captions bottom of RIGHT 75% (${sLabel})`,
      right:  `Avatar in RIGHT 25% ➔ Captions bottom of LEFT 75% (${sLabel})`,
      center: `Avatar centered ➔ Captions at BOTTOM CENTER (${sLabel})`,
    };
    el.innerHTML = map[STATE.position] || `Captions at BOTTOM CENTER (${sLabel})`;
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Visualizer Overlay Functions
// ═══════════════════════════════════════════════════════════════════════════
function onVisToggleCheckbox(checked) {
  STATE.visualizerEnabled = checked;
  const label = document.getElementById('vis-toggle-label');
  const body  = document.getElementById('vis-controls-body');
  const banner = document.getElementById('vis-disabled-banner');
  const checkbox = document.getElementById('vis-toggle-checkbox');

  if (checkbox && checkbox.checked !== checked) {
    checkbox.checked = checked;
  }
  if (label) {
    label.textContent = checked ? '✨ Visualizer ON' : '🚫 Visualizer OFF';
  }
  if (body) {
    body.style.display = checked ? 'block' : 'none';
  }
  if (banner) {
    banner.classList.toggle('visible', !checked);
  }

  syncStageFromState();
  showToast(checked ? '✨ Audio Player Visualizer ON' : '🚫 Visualizer OFF (Clean video & faster encoding)', 'info');
}

function toggleVisualizer() {
  const cb = document.getElementById('vis-toggle-checkbox');
  const nextVal = cb ? !cb.checked : !STATE.visualizerEnabled;
  onVisToggleCheckbox(nextVal);
}

function setVisualizerPosition(pos) {
  STATE.visualizerPosition = pos;
  STATE.customLayout.visualizer.x = null;
  STATE.customLayout.visualizer.y = null;
  ['top_center', 'top_left', 'top_right', 'bottom_center', 'none'].forEach(p => {
    const btn = document.getElementById(`vis-pos-${p}`);
    if (btn) {
      btn.classList.toggle('active', p === pos);
      btn.setAttribute('aria-pressed', p === pos ? 'true' : 'false');
    }
  });
  updateVisPreview();
  syncStageFromState();
  const names = {
    top_center: 'Top-Center (Default)',
    top_left: 'Top-Left',
    top_right: 'Top-Right',
    bottom_center: 'Bottom-Center',
    none: 'Disabled (None)'
  };
  showToast(`📍 Visualizer placed at ${names[pos] || pos}`, 'info');
}

function selectVisPreset(card) {
  document.querySelectorAll('.vis-preset-card').forEach(c => {
    c.classList.remove('active');
    c.setAttribute('aria-pressed', 'false');
  });
  card.classList.add('active');
  card.setAttribute('aria-pressed', 'true');
  STATE.visualizerStyle = card.dataset.style;

  // Update card mockup class
  const mockup = document.getElementById('vis-card-mockup');
  if (mockup) {
    mockup.className = `vis-mockup-card style-${STATE.visualizerStyle}`;
  }

  updateVisPreview();
  syncStageFromState();
  const name = card.querySelector('.preset-name')?.textContent || STATE.visualizerStyle;
  showToast(`🎨 Selected style: ${name}`, 'success');
}

function updateVisPreview() {
  const title = document.getElementById('vis-title-input')?.value.trim() || 'Stoic Wisdom';
  const sub   = document.getElementById('vis-subtitle-input')?.value.trim() || 'Audio Story Series';
  
  const titleEl = document.getElementById('vis-preview-title');
  const subEl   = document.getElementById('vis-preview-sub');
  if (titleEl) titleEl.textContent = title;
  if (subEl)   subEl.textContent   = sub;

  const posNames = {
    top_center: 'Top-Center',
    top_left: 'Top-Left',
    top_right: 'Top-Right',
    bottom_center: 'Bottom-Center',
    none: 'Off'
  };
  const badge = document.getElementById('vis-preview-badge');
  if (badge) {
    const pName = posNames[STATE.visualizerPosition] || 'Top-Center';
    badge.textContent = `📍 ${pName} · Style: ${STATE.visualizerStyle}`;
  }
  syncStageFromState();
}

// ═══════════════════════════════════════════════════════════════════════════
// Custom Green-Screen Visualizer Video & Chroma Key System
// ═══════════════════════════════════════════════════════════════════════════

function setVisMode(mode) {
  STATE.visMode = mode;
  const btnTemplate = document.getElementById('btn-vis-mode-template');
  const btnVideo    = document.getElementById('btn-vis-mode-video');
  const secTemplate = document.getElementById('vis-template-section');
  const secVideo    = document.getElementById('vis-video-section');

  if (btnTemplate) {
    btnTemplate.classList.toggle('active', mode === 'template');
    btnTemplate.setAttribute('aria-pressed', mode === 'template');
  }
  if (btnVideo) {
    btnVideo.classList.toggle('active', mode === 'video');
    btnVideo.setAttribute('aria-pressed', mode === 'video');
  }
  if (secTemplate) secTemplate.style.display = mode === 'template' ? 'block' : 'none';
  if (secVideo)    secVideo.style.display    = mode === 'video' ? 'block' : 'none';

  if (mode === 'video' && STATE.visVideoUrl) {
    setTimeout(initSamplerCanvas, 100);
  } else {
    stopSamplerLoop();
  }

  syncStageFromState();
  showToast(mode === 'video' ? '🟢 Switched to Custom Green-Screen Video Mode' : '🎨 Switched to Built-in Templates', 'info');
}

let _samplerAnim = null;
let _samplerViewMode = 'keyed'; // 'keyed' | 'original'

function rgbToHex(r, g, b) {
  return '#' + [r, g, b].map(x => {
    const hex = Math.max(0, Math.min(255, Math.round(x))).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  }).join('').toUpperCase();
}

function stopSamplerLoop() {
  if (_samplerAnim) {
    cancelAnimationFrame(_samplerAnim);
    _samplerAnim = null;
  }
}

function toggleSamplerViewMode() {
  _samplerViewMode = (_samplerViewMode === 'keyed' ? 'original' : 'keyed');
  const btn = document.getElementById('btn-sampler-view-toggle');
  if (btn) {
    btn.textContent = (_samplerViewMode === 'keyed' ? '✨ Preview: Transparent Keyed' : '🎬 View: Original Video Frame');
    btn.style.borderColor = (_samplerViewMode === 'keyed' ? 'rgba(6,182,212,0.4)' : 'rgba(234,179,8,0.4)');
    btn.style.color = (_samplerViewMode === 'keyed' ? '#38bdf8' : '#facc15');
  }
}

function autoDetectChromaColor() {
  const video = document.getElementById('vis-sampler-video-source');
  if (!video || !video.videoWidth) {
    // If video element not ready yet, sample from stage canvas source
    const stageVid = document.getElementById('stage-keyed-video-source');
    if (stageVid && stageVid.videoWidth) {
      sampleFromVideoElement(stageVid);
      return;
    }
    setChromaKeyColor('#00FF00');
    return;
  }
  sampleFromVideoElement(video);
}

function sampleFromVideoElement(video) {
  const vw = video.videoWidth || 480;
  const vh = video.videoHeight || 270;
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = vw;
  tempCanvas.height = vh;
  const tempCtx = tempCanvas.getContext('2d');
  tempCtx.drawImage(video, 0, 0, vw, vh);

  // Sample top-left corner pixel (at 10, 10)
  const p = tempCtx.getImageData(Math.min(10, vw - 1), Math.min(10, vh - 1), 1, 1).data;
  const hex = rgbToHex(p[0], p[1], p[2]);
  setChromaKeyColor(hex);
  showToast(`⚡ Auto-detected background: ${hex} (Removed!)`, 'success');
}

function startSamplerLoop() {
  stopSamplerLoop();
  const canvas = document.getElementById('vis-sampler-canvas');
  const video  = document.getElementById('vis-sampler-video-source');
  if (!canvas || !video) return;

  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  function renderSamplerFrame() {
    if (!canvas || !video || !STATE.visVideoUrl || STATE.visMode !== 'video') {
      stopSamplerLoop();
      return;
    }

    if (video.readyState >= 2) {
      const vw = video.videoWidth || 480;
      const vh = video.videoHeight || 270;
      if (canvas.width !== vw || canvas.height !== vh) {
        canvas.width  = vw;
        canvas.height = vh;
      }

      ctx.drawImage(video, 0, 0, vw, vh);

      if (_samplerViewMode === 'keyed') {
        const imgData = ctx.getImageData(0, 0, vw, vh);
        const data = imgData.data;
        const [kr, kg, kb] = hexToRgb(STATE.chromaKeyColor || '#00FF00');
        const tol = (STATE.chromaSimilarity || 0.25) * 255;
        const blend = Math.max(1, (STATE.chromaBlend || 0.08) * 255);
        const isBlack = (kr === 0 && kg === 0 && kb === 0);

        for (let i = 0; i < data.length; i += 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];

          let dist;
          if (isBlack) {
            dist = Math.max(r, g, b);
          } else {
            const dr = r - kr;
            const dg = g - kg;
            const db = b - kb;
            dist = Math.sqrt(dr * dr + dg * dg + db * db);
          }

          if (dist < tol) {
            const alphaRatio = Math.max(0, Math.min(1, (dist - (tol - blend)) / blend));
            data[i + 3] = Math.round(255 * alphaRatio);
          }
        }
        ctx.putImageData(imgData, 0, 0);
      }
    }
    _samplerAnim = requestAnimationFrame(renderSamplerFrame);
  }

  _samplerAnim = requestAnimationFrame(renderSamplerFrame);
}

function initSamplerCanvas() {
  const canvas = document.getElementById('vis-sampler-canvas');
  const video  = document.getElementById('vis-sampler-video-source');
  if (!canvas || !video || !STATE.visVideoUrl) return;

  video.src = STATE.visVideoUrl;
  video.currentTime = 0.05;
  video.play().catch(() => {});

  video.onloadeddata = () => {
    setTimeout(() => {
      autoDetectChromaColor();
    }, 100);
    startSamplerLoop();
  };

  // Shared 1x1 sample canvas for ultra-fast zero-lag pixel extraction
  const sampleCanvas = document.createElement('canvas');
  sampleCanvas.width = 1;
  sampleCanvas.height = 1;
  const sampleCtx = sampleCanvas.getContext('2d', { willReadFrequently: true });

  // Click on canvas to sample exact background pixel color!
  canvas.onclick = (e) => {
    if (!video.videoWidth) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = video.videoWidth / rect.width;
    const scaleY = video.videoHeight / rect.height;
    const px = Math.floor((e.clientX - rect.left) * scaleX);
    const py = Math.floor((e.clientY - rect.top) * scaleY);

    sampleCtx.drawImage(video, px, py, 1, 1, 0, 0, 1, 1);
    const p = sampleCtx.getImageData(0, 0, 1, 1).data;

    const hex = rgbToHex(p[0], p[1], p[2]);
    setChromaKeyColor(hex);
    showToast(`🎯 Sampled ${hex} from frame — Background removed!`, 'success');
  };

  // Hover over canvas to show eyedropper swatch in real time
  let _lastHoverTime = 0;
  canvas.onmousemove = (e) => {
    const now = performance.now();
    if (now - _lastHoverTime < 30 || !video.videoWidth) return; // Throttle to 30ms for smooth UI
    _lastHoverTime = now;

    const rect = canvas.getBoundingClientRect();
    const scaleX = video.videoWidth / rect.width;
    const scaleY = video.videoHeight / rect.height;
    const px = Math.floor((e.clientX - rect.left) * scaleX);
    const py = Math.floor((e.clientY - rect.top) * scaleY);

    sampleCtx.drawImage(video, px, py, 1, 1, 0, 0, 1, 1);
    const p = sampleCtx.getImageData(0, 0, 1, 1).data;
    const hex = rgbToHex(p[0], p[1], p[2]);

    const swatch = document.getElementById('vis-hover-swatch');
    const text   = document.getElementById('vis-hover-text');
    if (swatch) swatch.style.background = hex;
    if (text)   text.textContent = `Click to Key: ${hex}`;
  };
}

async function handleVisVideoUpload(file) {
  if (!file) return;
  const allowed = ['.mp4', '.webm', '.mov', '.m4v'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast('❌ Unsupported video format. Please upload MP4, WebM, or MOV.', 'error');
    return;
  }

  // Instant local preview so UI never waits
  const localBlobUrl = URL.createObjectURL(file);
  STATE.visVideoUrl = localBlobUrl;
  STATE.visVideoFilename = file.name;

  const promptEl = document.getElementById('vis-video-prompt');
  const loadedEl = document.getElementById('vis-video-loaded');
  const nameEl   = document.getElementById('vis-video-name');
  const metaEl   = document.getElementById('vis-video-meta');

  if (promptEl) promptEl.style.display = 'none';
  if (loadedEl) loadedEl.style.display = 'flex';
  if (nameEl)   nameEl.textContent = file.name;
  if (metaEl)   metaEl.textContent = `Probing... · ${(file.size / 1024 / 1024).toFixed(1)} MB`;

  setVisMode('video');
  initSamplerCanvas();
  syncStageFromState();
  showToast('📤 Uploading green-screen visualizer video...', 'info');

  const form = new FormData();
  form.append('file', file);

  try {
    const res = await fetch(`${API}/api/upload-vis-video`, { method: 'POST', body: form });
    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Upload failed');

    STATE.visVideoPath = data.path;
    STATE.visVideoUrl  = data.url || localBlobUrl;
    if (metaEl) {
      metaEl.textContent = `${data.duration}s · ${data.width}×${data.height} · ${(data.size_bytes / 1024 / 1024).toFixed(1)} MB`;
    }
    initSamplerCanvas();
    syncStageFromState();
    showToast(`✅ Green-screen visualizer ready (${data.duration}s)`, 'success');
  } catch (e) {
    showToast('❌ Video upload failed: ' + e.message, 'error');
  }
}

function removeVisVideo() {
  STATE.visVideoPath = null;
  STATE.visVideoUrl  = null;
  STATE.visVideoFilename = null;
  const promptEl = document.getElementById('vis-video-prompt');
  const loadedEl = document.getElementById('vis-video-loaded');
  const fileInput = document.getElementById('vis-video-file-input');
  if (promptEl) promptEl.style.display = 'block';
  if (loadedEl) loadedEl.style.display = 'none';
  if (fileInput) fileInput.value = '';
  stopSamplerLoop();
  stopStageVideoKeying();
  syncStageFromState();
  showToast('Custom visualizer video removed', 'info');
}

function setChromaKeyColor(hex) {
  STATE.chromaKeyColor = hex.toUpperCase();
  const valEl = document.getElementById('chroma-color-val');
  const picker = document.getElementById('chroma-color-picker');
  if (valEl)  valEl.textContent = STATE.chromaKeyColor;
  if (picker) picker.value = hex;

  const btnGreen = document.getElementById('btn-chroma-green');
  const btnBlack = document.getElementById('btn-chroma-black');
  const btnBlue  = document.getElementById('btn-chroma-blue');
  if (btnGreen) btnGreen.classList.toggle('active', STATE.chromaKeyColor === '#00FF00');
  if (btnBlack) btnBlack.classList.toggle('active', STATE.chromaKeyColor === '#000000');
  if (btnBlue)  btnBlue.classList.toggle('active', STATE.chromaKeyColor === '#0000FF');

  syncStageFromState();
}

async function pickChromaColorFromScreen() {
  if (window.EyeDropper) {
    try {
      const eyeDropper = new EyeDropper();
      const result = await eyeDropper.open();
      if (result && result.sRGBHex) {
        setChromaKeyColor(result.sRGBHex);
        showToast(`🎯 Chroma key color sampled: ${result.sRGBHex}`, 'success');
      }
    } catch (e) {
      // User cancelled or aborted
    }
  } else {
    document.getElementById('chroma-color-picker')?.click();
  }
}

function onChromaSimChange(val) {
  STATE.chromaSimilarity = parseFloat(val) / 100;
  const el = document.getElementById('chroma-sim-val');
  if (el) el.textContent = `${val}%`;
}

function onChromaBlendChange(val) {
  STATE.chromaBlend = parseFloat(val) / 100;
  const el = document.getElementById('chroma-blend-val');
  if (el) el.textContent = `${val}%`;
}

function toggleChromaPreview(checked) {
  STATE.chromaPreviewMode = checked ? 'keyed' : 'raw';
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
  let avgRaw      = 45;
  if (STATE.brollPacingMode === 'fast_cuts') {
    avgRaw = (STATE.brollMinSec + STATE.brollMaxSec) / 2.0;
  }
  const avgEff    = avgRaw / speed;
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
  STATE.lastLogIndex = 0;
  appendLog('🚀 Render job submitted...\n');

  const payload = {
    voiceover_path:   STATE.voiceoverPath,
    broll_folder:     folder,
    broll_pacing_mode: STATE.brollPacingMode || 'full',
    broll_min_sec:     STATE.brollMinSec || 5.0,
    broll_max_sec:     STATE.brollMaxSec || 9.0,
    avatar_path:      STATE.avatarPath,
    avatar_position:  STATE.position,
    avatar_size:      STATE.avatarSize || 920,
    avatar_opacity:   STATE.avatarOpacity !== undefined ? STATE.avatarOpacity : 1.0,
    avatar_custom_x:  STATE.customLayout?.avatar?.x,
    avatar_custom_y:  STATE.customLayout?.avatar?.y,
    caption_box:      STATE.customLayout?.caption?.w ? {
      x: STATE.customLayout.caption.x,
      y: STATE.customLayout.caption.y,
      w: STATE.customLayout.caption.w,
      h: STATE.customLayout.caption.h
    } : null,
    flip_horizontal:  STATE.avatarFlip,
    stroke_color:     STATE.strokeColor,
    stroke_width:     parseInt(document.getElementById('stroke-width-slider')?.value || '10'),
    blur_radius:      parseInt(document.getElementById('blur-slider')?.value || '0'),
    dark_tint:        parseFloat(document.getElementById('tint-slider')?.value || '25') / 100,
    stock_speed:      parseFloat(document.getElementById('stock-speed-slider')?.value || '0.75'),
    pitch_semitones:  parseFloat(document.getElementById('pitch-slider')?.value || '0'),
    voice_speed:      parseFloat(document.getElementById('speed-slider')?.value || '1.0'),
    caption_preset:   STATE.captionPreset,
    caption_position: STATE.customLayout?.caption?.w ? 'custom' : (STATE.captionPosition || 'center'),
    caption_size:     STATE.captionSize || 'large',
    broll_audio:      STATE.brollAudio || 'muted',
    bg_audio_path:    STATE.bgmPath || null,
    bg_music_volume:  parseFloat(document.getElementById('bgm-vol-slider')?.value || '7') / 100,
    visualizer_enabled:  STATE.visualizerEnabled !== false,
    visualizer_style:    STATE.visualizerStyle || 'glass_pill_cyan',
    visualizer_position: STATE.customLayout?.visualizer?.x !== null ? 'custom' : (STATE.visualizerPosition || 'top_center'),
    visualizer_custom_x: STATE.customLayout?.visualizer?.x,
    visualizer_custom_y: STATE.customLayout?.visualizer?.y,
    visualizer_scale:    STATE.customLayout?.visualizer?.scale || 1.0,
    visualizer_title:    document.getElementById('vis-title-input')?.value.trim() || '',
    visualizer_subtitle: document.getElementById('vis-subtitle-input')?.value.trim() || '',
    visualizer_mode:     (STATE.visMode === 'video' || Boolean(STATE.visVideoPath)) ? 'video' : (STATE.visMode || 'template'),
    custom_vis_video_path: (STATE.visMode === 'video' || Boolean(STATE.visVideoPath)) ? STATE.visVideoPath : null,
    chroma_key_color:    STATE.chromaKeyColor || '#00FF00',
    chroma_similarity:   STATE.chromaSimilarity || 0.25,
    chroma_blend:        STATE.chromaBlend || 0.08,
    visualizer_width:    STATE.customLayout?.visualizer?.w || null,
    visualizer_height:   STATE.customLayout?.visualizer?.h || null,
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

  // Stream new server diagnostic logs cleanly into the terminal without duplicates
  if (Array.isArray(data.logs) && data.logs.length > (STATE.lastLogIndex || 0)) {
    const newLogs = data.logs.slice(STATE.lastLogIndex || 0);
    newLogs.forEach(l => appendLog(`[${new Date().toLocaleTimeString()}] ${l}\n`));
    STATE.lastLogIndex = data.logs.length;
  } else if (!data.logs) {
    appendLog(`[${new Date().toLocaleTimeString()}] ${message}\n`);
  }

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

function openDocsModal() {
  const modal = document.getElementById('docs-modal');
  if (modal) {
    modal.classList.add('visible');
    const frame = document.getElementById('docs-frame');
    if (frame && (!frame.src || frame.src === 'about:blank')) {
      frame.src = '/static/docs.html';
    }
  }
}

function closeDocsModal(event) {
  if (!event || event.target === document.getElementById('docs-modal')) {
    const modal = document.getElementById('docs-modal');
    if (modal) modal.classList.remove('visible');
  }
}

function reloadDocsIframe() {
  const frame = document.getElementById('docs-frame');
  if (frame) {
    frame.src = '/static/docs.html?t=' + Date.now();
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// System Health & Storage Guard Modal
// ═══════════════════════════════════════════════════════════════════════════
let _healthGuardAcknowledged = false;

async function checkSystemHealthOnStartup(forceModal = false) {
  try {
    const res = await fetch(`${API}/api/system/health`);
    if (!res.ok) return;
    const data = await res.json();

    // 1. Groq Status
    const groqBadge = document.getElementById('health-groq-badge');
    const groqMsg = document.getElementById('health-groq-msg');
    const groqSubtitle = document.getElementById('health-groq-subtitle');
    const groqInputWrap = document.getElementById('health-groq-input-wrap');
    const linkedPanel = document.getElementById('health-groq-linked-panel');
    const linkedKeyVal = document.getElementById('health-groq-linked-key-val');
    const pingLatency = document.getElementById('health-groq-ping-latency');

    if (data.groq && data.groq.configured) {
      if (linkedPanel) linkedPanel.style.display = 'flex';
      if (linkedKeyVal) linkedKeyVal.textContent = data.groq.masked_key || 'gsk_...';

      if (data.groq.valid) {
        if (groqBadge) {
          groqBadge.textContent = `🟢 Active (${data.groq.latency_ms || 110}ms)`;
          groqBadge.style.background = 'rgba(16, 185, 129, 0.15)';
          groqBadge.style.color = '#34d399';
          groqBadge.style.border = '1px solid rgba(16, 185, 129, 0.35)';
        }
        if (pingLatency) {
          pingLatency.textContent = `(🟢 ${data.groq.latency_ms || 110}ms · Active)`;
          pingLatency.style.color = '#34d399';
        }
        if (groqSubtitle) groqSubtitle.textContent = `Linked Key: ${data.groq.masked_key}`;
        if (groqMsg) groqMsg.innerHTML = `<span style="color:#34d399;">●</span> Groq AI Whisper is verified &amp; ready for parallel chunking.`;
        if (groqInputWrap) groqInputWrap.style.display = 'none';
      } else {
        if (groqBadge) {
          groqBadge.textContent = '⚠️ Check Connection';
          groqBadge.style.background = 'rgba(245, 158, 11, 0.15)';
          groqBadge.style.color = '#fbbf24';
          groqBadge.style.border = '1px solid rgba(245, 158, 11, 0.35)';
        }
        if (pingLatency) {
          pingLatency.textContent = `(⚠️ Ping Unconfirmed)`;
          pingLatency.style.color = '#fbbf24';
        }
        if (groqSubtitle) groqSubtitle.textContent = `Action Optional`;
        if (groqMsg) groqMsg.innerHTML = `<span style="color:#fbbf24;">●</span> ${data.groq.message}. Click <b>Ping Test</b> to verify or change key.`;
        // Keep input hidden if key is present, let user ping test first
        if (groqInputWrap) groqInputWrap.style.display = 'none';
      }
    } else {
      // No key configured at all
      if (linkedPanel) linkedPanel.style.display = 'none';
      if (groqBadge) {
        groqBadge.textContent = '⚠️ Key Required';
        groqBadge.style.background = 'rgba(239, 68, 68, 0.15)';
        groqBadge.style.color = '#f87171';
        groqBadge.style.border = '1px solid rgba(239, 68, 68, 0.35)';
      }
      if (groqSubtitle) groqSubtitle.textContent = 'Action Required';
      if (groqMsg) groqMsg.innerHTML = `<span style="color:#f87171;">●</span> No Groq API Key linked. Please enter a valid key to enable transcription.`;
      if (groqInputWrap) groqInputWrap.style.display = 'block';
    }

    // 2. Storage / Cache Status
    const cacheBadge = document.getElementById('health-cache-badge');
    const cacheMsg = document.getElementById('health-cache-msg');
    const cleanBtn = document.getElementById('btn-clean-health-cache');

    if (data.cache && data.cache.size_bytes > 0) {
      if (cacheBadge) {
        cacheBadge.textContent = `⚠️ ${data.cache.size_formatted}`;
        cacheBadge.style.background = 'rgba(245, 158, 11, 0.15)';
        cacheBadge.style.color = '#fbbf24';
        cacheBadge.style.border = '1px solid rgba(245, 158, 11, 0.35)';
      }
      if (cacheMsg) {
        cacheMsg.innerHTML = `<span style="color:#fbbf24;">●</span> Found <b>${data.cache.size_formatted}</b> in temporary cache (${data.cache.file_count} chunks/temp files). Clean this to keep the tool fast.`;
      }
      if (cleanBtn) {
        cleanBtn.style.display = 'inline-flex';
        cleanBtn.disabled = false;
        cleanBtn.textContent = '🧹 Clean Temp Cache Now';
      }
    } else {
      if (cacheBadge) {
        cacheBadge.textContent = '✅ Clean (0 B)';
        cacheBadge.style.background = 'rgba(16, 185, 129, 0.15)';
        cacheBadge.style.color = '#34d399';
        cacheBadge.style.border = '1px solid rgba(16, 185, 129, 0.35)';
      }
      if (cacheMsg) {
        cacheMsg.innerHTML = `<span style="color:#34d399;">●</span> Storage is clean and optimal. No temporary junk or stale cache found.`;
      }
      if (cleanBtn) {
        cleanBtn.textContent = '✅ Cache is Clean';
        cleanBtn.disabled = true;
      }
    }

    // 3. Diagnostics
    const gpuEl = document.getElementById('health-gpu-text');
    const ffmpegEl = document.getElementById('health-ffmpeg-text');
    if (gpuEl && data.gpu) {
      gpuEl.textContent = `⚡ GPU Acceleration: ${data.gpu.toUpperCase()}`;
    }
    if (ffmpegEl) {
      ffmpegEl.textContent = `🎬 FFmpeg Engine: ${data.ffmpeg ? 'Ready (Bundled)' : 'Missing'}`;
    }

    // Open modal on launch if user hasn't acknowledged yet or if forced
    if (forceModal || !_healthGuardAcknowledged) {
      openHealthGuardModal(false);
    }

  } catch (err) {
    console.warn('[HealthGuard] Startup health check error:', err);
  }
}

async function runGroqPingTest() {
  const btn = document.getElementById('btn-ping-groq');
  const badge = document.getElementById('health-groq-badge');
  const msg = document.getElementById('health-groq-msg');
  const latEl = document.getElementById('health-groq-ping-latency');
  const inputWrap = document.getElementById('health-groq-input-wrap');

  const origText = btn ? btn.innerHTML : '⚡ Ping Test';
  if (btn) { btn.disabled = true; btn.innerHTML = '⏳ Pinging...'; }
  if (latEl) latEl.textContent = '(Testing...)';

  try {
    const res = await fetch(`${API}/api/system/ping-groq`, { method: 'POST' });
    const data = await res.json();
    if (data.has_valid) {
      const lat = data.best_latency_ms || 110;
      if (badge) {
        badge.textContent = `🟢 Active (${lat}ms)`;
        badge.style.background = 'rgba(16, 185, 129, 0.15)';
        badge.style.color = '#34d399';
        badge.style.border = '1px solid rgba(16, 185, 129, 0.35)';
      }
      if (latEl) {
        latEl.textContent = `(🟢 ${lat}ms · Verified)`;
        latEl.style.color = '#34d399';
      }
      if (msg) msg.innerHTML = `<span style="color:#34d399;">●</span> Ping test passed (${lat}ms latency). All Whisper Large v3 features are ready.`;
      if (inputWrap) inputWrap.style.display = 'none';
      showToast(`⚡ Groq Ping Test Passed: ${lat}ms latency!`, 'success');
    } else {
      if (badge) {
        badge.textContent = '🔴 Ping Failed';
        badge.style.background = 'rgba(239, 68, 68, 0.15)';
        badge.style.color = '#f87171';
        badge.style.border = '1px solid rgba(239, 68, 68, 0.35)';
      }
      if (latEl) {
        latEl.textContent = `(🔴 Failed)`;
        latEl.style.color = '#f87171';
      }
      if (msg) msg.innerHTML = `<span style="color:#f87171;">●</span> Ping test failed: ${data.message || 'Authentication error'}. Please update key below.`;
      if (inputWrap) inputWrap.style.display = 'block';
      showToast(`❌ Groq Ping Test Failed: ${data.message || 'Key invalid'}`, 'error');
    }
  } catch (e) {
    showToast(`Ping error: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
  }
}

function toggleHealthGroqInput() {
  const wrap = document.getElementById('health-groq-input-wrap');
  if (!wrap) return;
  const isHidden = (wrap.style.display === 'none' || !wrap.style.display);
  wrap.style.display = isHidden ? 'block' : 'none';
  if (isHidden) {
    document.getElementById('health-groq-key-input')?.focus();
  }
}

function openHealthGuardModal(refresh = false) {
  const modal = document.getElementById('health-guard-modal');
  if (modal) {
    modal.classList.add('visible');
    if (refresh) checkSystemHealthOnStartup(true);
  }
}

function closeHealthGuardModal(event) {
  const modal = document.getElementById('health-guard-modal');
  if (!modal) return;
  if (!event || event.target === modal || (event.currentTarget && (event.currentTarget.id === 'btn-health-continue' || event.currentTarget.getAttribute('aria-label') === 'Close'))) {
    modal.classList.remove('visible');
    _healthGuardAcknowledged = true;
  }
}

async function submitHealthGroqKey() {
  const input = document.getElementById('health-groq-key-input');
  const btn = document.getElementById('btn-save-health-groq');
  const feedback = document.getElementById('health-groq-save-feedback');
  if (!input) return;
  const key = input.value.trim();
  if (!key) {
    showToast('Please paste a valid Groq API key', 'warning');
    return;
  }

  const origText = btn ? btn.textContent : 'Save';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Verifying...'; }

  try {
    const res = await fetch(`${API}/api/system/update-groq-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groq_api_key: key })
    });
    const data = await res.json();
    if (data.success && data.valid) {
      showToast('✅ Groq API key verified and connected!', 'success');
      if (feedback) {
        feedback.innerHTML = `<span style="color:#34d399; font-weight:600;">${data.message}</span>`;
      }
      input.value = '';
      await checkSystemHealthOnStartup(true);
    } else {
      showToast(`⚠️ ${data.message || 'Key verification failed'}`, 'error');
      if (feedback) {
        feedback.innerHTML = `<span style="color:#f87171;">${data.message}</span>`;
      }
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = origText; }
  }
}

// ── Smart Background Pre-Transcription ─────────────────────────────────────────
let _preTranscribeTimer = null;
async function startBackgroundPreTranscription(audioPath, niche) {
  if (!audioPath) return;
  try {
    console.log('[PreTranscribe] Kicking off background pre-transcription for:', audioPath);
    const res = await fetch(`${API}/api/pre-transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio_path: audioPath, niche: niche || 'Stoicism & Philosophy' })
    });
    const data = await res.json();
    if (data.success) {
      const durEl = document.getElementById('voiceover-duration');
      if (durEl && !document.getElementById('pre-transcribe-tag')) {
        const tag = document.createElement('span');
        tag.id = 'pre-transcribe-tag';
        tag.style.cssText = 'color:#38bdf8; font-size:0.75rem; margin-left:8px; font-weight:600; display:inline-flex; align-items:center; gap:4px;';
        tag.innerHTML = `⚡ <span id="pre-transcribe-text">Pre-transcribing in background...</span>`;
        durEl.appendChild(tag);
      }

      // Poll status until completed
      if (_preTranscribeTimer) clearInterval(_preTranscribeTimer);
      _preTranscribeTimer = setInterval(async () => {
        try {
          const sRes = await fetch(`${API}/api/pre-transcribe-status?audio_path=${encodeURIComponent(audioPath)}`);
          const sData = await sRes.json();
          if (sData.status === 'ready') {
            clearInterval(_preTranscribeTimer);
            _preTranscribeTimer = null;
            const textEl = document.getElementById('pre-transcribe-text');
            if (textEl) {
              textEl.innerHTML = `Transcribed (${sData.segments_count || 'all'} scenes ready)`;
              textEl.parentElement.style.color = '#34d399';
            }
            console.log('[PreTranscribe] ✅ Pre-transcription complete & cached!');
          } else if (sData.status === 'failed') {
            clearInterval(_preTranscribeTimer);
            _preTranscribeTimer = null;
            const textEl = document.getElementById('pre-transcribe-text');
            if (textEl) {
              textEl.innerHTML = `Groq will transcribe on render`;
              textEl.parentElement.style.color = '#fbbf24';
            }
          }
        } catch (pollErr) {
          clearInterval(_preTranscribeTimer);
        }
      }, 3500);
    }
  } catch (err) {
    console.warn('[PreTranscribe] Pre-transcription notice:', err);
  }
}

async function cleanHealthCache() {
  const btn = document.getElementById('btn-clean-health-cache');
  const origText = btn ? btn.textContent : 'Clean';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Cleaning...'; }

  try {
    const res = await fetch(`${API}/api/system/clean-cache`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`🧹 Cleaned! Freed ${data.freed_formatted}`, 'success');
      await checkSystemHealthOnStartup(true);
    } else {
      showToast('Cache cleaning completed', 'info');
    }
  } catch (e) {
    showToast(`Clean error: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = origText; }
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


// ═══════════════════════════════════════════════════════════════════════════
// STEP 6: LIVE INTERACTIVE STUDIO CANVAS & 20s PREVIEW ENGINE
// ═══════════════════════════════════════════════════════════════════════════

let _stageDrag = null;

/**
 * Initializes the Interactive Studio Canvas, drag-and-drop handles,
 * and mouse/touch pointer interactions.
 */
function initStudioStage() {
  const canvas = document.getElementById('stage-canvas');
  if (!canvas) return;

  // Pointer down on draggable elements or resize handles
  canvas.addEventListener('pointerdown', onStagePointerDown);
  window.addEventListener('pointermove', onStagePointerMove);
  window.addEventListener('pointerup', onStagePointerUp);

  // Keyboard shortcut: Esc to exit fullscreen
  window.addEventListener('keydown', e => {
    if (e.key === 'Escape' && STATE.customLayout.fullscreen) {
      toggleStageFullscreen();
    }
  });

  // Listen for dark tint slider directly if present
  const tintSlider = document.getElementById('tint-slider');
  if (tintSlider) {
    tintSlider.addEventListener('input', () => {
      STATE.darkTint = parseFloat(tintSlider.value) / 100;
      syncStageFromState();
    });
  }
}

/**
 * Synchronizes the visual state of the 16:9 Studio Canvas
 * with all parameters from Steps 1, 2, 3, 4, and 5.
 */
function syncStageFromState() {
  const canvas = document.getElementById('stage-canvas');
  if (!canvas) return;

  // 1. Background Scene (Image/Video + Blur + Dark Tint)
  const bgImg = document.getElementById('stage-bg-img');
  const bgTint = document.getElementById('stage-bg-tint');
  if (bgImg) {
    if (STATE.brollPreviewUrl) {
      bgImg.src = STATE.brollPreviewUrl;
    } else if (!bgImg.src || bgImg.src.includes('data:image/svg')) {
      // Default high-end cinematic dark aesthetic gradient
      bgImg.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1920' height='1080'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%' stop-color='%23050914'/><stop offset='50%' stop-color='%230f172a'/><stop offset='100%' stop-color='%23020617'/></linearGradient><radialGradient id='r' cx='60%' cy='35%' r='70%'><stop offset='0%' stop-color='%2300d2ff' stop-opacity='0.25'/><stop offset='100%' stop-color='%23000' stop-opacity='0'/></radialGradient></defs><rect width='100%' height='100%' fill='url(%23g)'/><rect width='100%' height='100%' fill='url(%23r)'/></svg>";
    }
    // Live CSS filter for background blur
    const blurPx = STATE.blurRadius > 0 ? (STATE.blurRadius * 0.45).toFixed(1) : 0;
    bgImg.style.filter = `blur(${blurPx}px)`;
  }
  if (bgTint) {
    bgTint.style.opacity = (STATE.darkTint !== undefined ? STATE.darkTint : 0.25).toString();
  }

  // 2. Author Avatar Layer
  const avatarBox = document.getElementById('stage-avatar-box');
  const avatarImg = document.getElementById('stage-avatar-img');
  if (avatarBox && avatarImg) {
    if (STATE.avatarUrl) {
      avatarImg.src = STATE.avatarUrl;
    } else {
      // Placeholder author silhouette
      avatarImg.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2364748b' width='100%' height='100%'><path d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/></svg>";
    }

    // Mirror flip
    avatarImg.style.transform = STATE.avatarFlip ? 'scaleX(-1)' : 'none';

    // Stroke glow
    const strokeWidth = parseInt(document.getElementById('stroke-width-slider')?.value || '10', 10);
    const glowRadius = Math.max(2, Math.round(strokeWidth * 0.6));
    const strokeGlows = {
      white: `drop-shadow(0 0 ${glowRadius}px rgba(255, 255, 255, 0.95)) drop-shadow(0 0 ${glowRadius * 2}px rgba(255, 255, 255, 0.5))`,
      gold:  `drop-shadow(0 0 ${glowRadius}px rgba(255, 215, 0, 0.95)) drop-shadow(0 0 ${glowRadius * 2}px rgba(255, 200, 0, 0.5))`,
      cyan:  `drop-shadow(0 0 ${glowRadius}px rgba(0, 210, 255, 0.95)) drop-shadow(0 0 ${glowRadius * 2}px rgba(0, 210, 255, 0.5))`,
      none:  'none'
    };
    avatarImg.style.filter = strokeGlows[STATE.strokeColor] || strokeGlows.white;

    // Opacity
    avatarImg.style.opacity = (STATE.avatarOpacity !== undefined ? STATE.avatarOpacity : 1.0).toString();

    // Height calculation relative to 1080p canvas
    const targetH = STATE.avatarSize || 920;
    const heightPct = (targetH / 1080) * 100;
    avatarBox.style.height = `${heightPct}%`;
    avatarBox.style.width = `${heightPct * 0.75}%`;

    // Coordinates: custom drag or preset position
    if (STATE.customLayout.avatar.x !== null && STATE.customLayout.avatar.y !== null) {
      avatarBox.style.left = `${(STATE.customLayout.avatar.x / 1920) * 100}%`;
      avatarBox.style.top = `${(STATE.customLayout.avatar.y / 1080) * 100}%`;
      avatarBox.style.bottom = 'auto';
      avatarBox.style.right = 'auto';
    } else {
      avatarBox.style.bottom = '0%';
      avatarBox.style.top = 'auto';
      if (STATE.position === 'left') {
        avatarBox.style.left = '0%';
        avatarBox.style.right = 'auto';
      } else if (STATE.position === 'center') {
        avatarBox.style.left = '50%';
        avatarBox.style.right = 'auto';
        avatarBox.style.transform = 'translateX(-50%)';
      } else {
        avatarBox.style.right = '0%';
        avatarBox.style.left = 'auto';
        avatarBox.style.transform = 'none';
      }
    }
  }

  // 3. Captions Layer
  const captionBox = document.getElementById('stage-caption-box');
  const captionContent = document.getElementById('stage-caption-content');
  if (captionBox && captionContent) {
    // Style preset colors (18 styles)
    const presetPalette = {
      capcut_yellow:    { base: '#ffffff', active: '#ffff00', glow: '#ffcc00' },
      hormozi_green:    { base: '#ffffff', active: '#00ff66', glow: '#00dd44' },
      neon_cyber:       { base: '#00ffff', active: '#ff00ff', glow: '#bf55ec' },
      dark_stoic:       { base: '#cbd5e1', active: '#ffffff', glow: '#94a3b8' },
      ali_abdaal:       { base: '#ffffff', active: '#38bdf8', glow: '#0284c7' },
      iman_gadzhi:      { base: '#ffffff', active: '#ffd700', glow: '#f59e0b' },
      tiktok_violet:    { base: '#ffffff', active: '#d946ef', glow: '#a855f7' },
      red_fire:         { base: '#ffffff', active: '#ff3344', glow: '#ef4444' },
      podcast_pill:     { base: '#ffffff', active: '#00e5ff', glow: '#00b4d8' },
      clean_minimal:    { base: '#ffffff', active: '#ffffff', glow: '#94a3b8' },
      mrbeast_punch:    { base: '#ffffff', active: '#fbbf24', glow: '#d97706' },
      streamer_lime:    { base: '#ffffff', active: '#a3e635', glow: '#84cc16' },
      retro_vintage:    { base: '#ffa03c', active: '#ffff00', glow: '#f59e0b' },
      midnight_blue:    { base: '#ffffff', active: '#38bdf8', glow: '#2563eb' },
      true_crime:       { base: '#e0e0e0', active: '#ef4444', glow: '#dc2626' },
      wealth_cash:      { base: '#ffffff', active: '#10df70', glow: '#059669' },
      cosmic_violet:    { base: '#ffffff', active: '#c084fc', glow: '#9333ea' },
      cinematic_bronze: { base: '#e8f0f8', active: '#f59e0b', glow: '#d97706' }
    };
    const pal = presetPalette[STATE.captionPreset] || presetPalette.capcut_yellow;
    captionContent.style.color = pal.base;

    // Apply accurate typography family matching the chosen viral preset
    const presetFonts = {
      capcut_yellow:    "'Montserrat', sans-serif",
      hormozi_green:    "Impact, 'Arial Black', sans-serif",
      neon_cyber:       "'Montserrat', sans-serif",
      dark_stoic:       "'Oswald', 'Arial Black', sans-serif",
      ali_abdaal:       "'Poppins', sans-serif",
      iman_gadzhi:      "'Cinzel', serif",
      tiktok_violet:    "'Archivo Black', sans-serif",
      red_fire:         "Impact, 'Arial Black', sans-serif",
      podcast_pill:     "'Outfit', 'Montserrat', sans-serif",
      clean_minimal:    "'Inter', sans-serif",
      mrbeast_punch:    "'Bangers', cursive, Impact",
      streamer_lime:    "'Luckiest Guy', cursive, Impact",
      retro_vintage:    "'Arial Black', Impact, sans-serif",
      midnight_blue:    "'Montserrat', sans-serif",
      true_crime:       "'Courier New', monospace",
      wealth_cash:      "Impact, 'Arial Black', sans-serif",
      cosmic_violet:    "'Montserrat', sans-serif",
      cinematic_bronze: "'Cinzel', serif"
    };
    captionContent.style.fontFamily = presetFonts[STATE.captionPreset] || "Impact, sans-serif";

    // Apply active word glow styles to active words
    captionContent.querySelectorAll('.demo-word.active').forEach(w => {
      w.style.color = pal.active;
      w.style.textShadow = `0 0 16px ${pal.glow}, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000`;
    });

    // Font size mapping (scaled relative to 16:9 canvas width)
    const fontSizes = { medium: '2.0vw', large: '2.6vw', huge: '3.3vw' };
    captionContent.style.fontSize = fontSizes[STATE.captionSize] || '2.6vw';

    // Position and Dimensions
    if (STATE.customLayout.caption.w !== null) {
      captionBox.style.left   = `${(STATE.customLayout.caption.x / 1920) * 100}%`;
      captionBox.style.top    = `${(STATE.customLayout.caption.y / 1080) * 100}%`;
      captionBox.style.width  = `${(STATE.customLayout.caption.w / 1920) * 100}%`;
      captionBox.style.height = `${(STATE.customLayout.caption.h / 1080) * 100}%`;
      captionBox.style.transform = 'none';
    } else {
      if (STATE.captionPosition === 'center') {
        captionBox.style.top    = '41%';
        captionBox.style.left   = '16%';
        captionBox.style.width  = '68%';
        captionBox.style.height = '18%';
        captionBox.style.transform = 'none';
      } else {
        captionBox.style.top    = '73%';
        captionBox.style.left   = '16%';
        captionBox.style.width  = '68%';
        captionBox.style.height = '18%';
        captionBox.style.transform = 'none';
      }
    }
  }

  // 4. Audio Visualizer / Player Widget Layer
  const playerBox = document.getElementById('stage-player-box');
  if (playerBox) {
    const isVisVisible = STATE.visualizerEnabled !== false && STATE.visualizerPosition !== 'none';
    playerBox.style.display = isVisVisible ? 'block' : 'none';

    renderStagePlayerCard();

    // Scale
    const scale = STATE.customLayout.visualizer.scale || 1.0;
    playerBox.style.transform = `scale(${scale})`;
    playerBox.style.transformOrigin = 'top center';

    // Position
    if (STATE.customLayout.visualizer.x !== null && STATE.customLayout.visualizer.y !== null) {
      playerBox.style.left = `${(STATE.customLayout.visualizer.x / 1920) * 100}%`;
      playerBox.style.top  = `${(STATE.customLayout.visualizer.y / 1080) * 100}%`;
      playerBox.style.right = 'auto';
      playerBox.style.bottom = 'auto';
    } else {
      playerBox.style.bottom = 'auto';
      playerBox.style.right = 'auto';
      if (STATE.visualizerPosition === 'top_left') {
        playerBox.style.top  = '3.5%';
        playerBox.style.left = '3.5%';
      } else if (STATE.visualizerPosition === 'top_right') {
        playerBox.style.top   = '3.5%';
        playerBox.style.left  = 'auto';
        playerBox.style.right = '3.5%';
      } else if (STATE.visualizerPosition === 'bottom_center') {
        playerBox.style.top    = 'auto';
        playerBox.style.bottom = '3.5%';
        playerBox.style.left   = '29%';
      } else {
        // default: top_center
        playerBox.style.top  = '3.5%';
        playerBox.style.left = '29%';
      }
    }
  }
}

let _stageVideoKeyAnim = null;

function stopStageVideoKeying() {
  if (_stageVideoKeyAnim) {
    cancelAnimationFrame(_stageVideoKeyAnim);
    _stageVideoKeyAnim = null;
  }
}

function hexToRgb(hex) {
  const clean = (hex || '#00FF00').replace('#', '');
  if (clean.length === 3) {
    return [
      parseInt(clean[0] + clean[0], 16),
      parseInt(clean[1] + clean[1], 16),
      parseInt(clean[2] + clean[2], 16)
    ];
  }
  return [
    parseInt(clean.substring(0, 2), 16) || 0,
    parseInt(clean.substring(2, 4), 16) || 0,
    parseInt(clean.substring(4, 6), 16) || 0
  ];
}

function startStageVideoKeying() {
  stopStageVideoKeying();
  const canvas = document.getElementById('stage-keyed-video-canvas');
  const video  = document.getElementById('stage-keyed-video-source');
  if (!canvas || !video) return;

  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  video.play().catch(() => {});

  function renderKeyedFrame() {
    if (!canvas || !video) return;
    if (STATE.visMode !== 'video' || !STATE.visVideoUrl) {
      stopStageVideoKeying();
      return;
    }

    if (video.readyState >= 2) {
      const vw = video.videoWidth || 360;
      const vh = video.videoHeight || 200;
      if (canvas.width !== vw || canvas.height !== vh) {
        canvas.width  = vw;
        canvas.height = vh;
      }

      ctx.drawImage(video, 0, 0, vw, vh);

      if (STATE.chromaPreviewMode !== 'raw') {
        const imgData = ctx.getImageData(0, 0, vw, vh);
        const data = imgData.data;
        const [kr, kg, kb] = hexToRgb(STATE.chromaKeyColor || '#00FF00');
        const tol = (STATE.chromaSimilarity || 0.25) * 255;
        const blend = Math.max(1, (STATE.chromaBlend || 0.08) * 255);
        const isBlack = (kr === 0 && kg === 0 && kb === 0);

        for (let i = 0; i < data.length; i += 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];

          let dist;
          if (isBlack) {
            dist = Math.max(r, g, b);
          } else {
            const dr = r - kr;
            const dg = g - kg;
            const db = b - kb;
            dist = Math.sqrt(dr * dr + dg * dg + db * db);
          }

          if (dist < tol) {
            const alphaRatio = Math.max(0, Math.min(1, (dist - (tol - blend)) / blend));
            data[i + 3] = Math.round(255 * alphaRatio);
          }
        }
        ctx.putImageData(imgData, 0, 0);
      }
    }
    _stageVideoKeyAnim = requestAnimationFrame(renderKeyedFrame);
  }

  _stageVideoKeyAnim = requestAnimationFrame(renderKeyedFrame);
}

/**
 * Renders the active visualizer card mockup OR live keyed custom video inside Studio Stage.
 */
function renderStagePlayerCard() {
  const container = document.getElementById('stage-player-card');
  if (!container) return;

  if (STATE.visMode === 'video') {
    if (!STATE.visVideoUrl) {
      stopStageVideoKeying();
      container.innerHTML = `
        <div style="padding:16px 20px;border:2px dashed #22c55e;border-radius:12px;background:rgba(34,197,94,0.12);color:#86efac;text-align:center;font-weight:600;display:flex;flex-direction:column;align-items:center;gap:6px;min-width:260px;">
          <span style="font-size:1.6rem;">🟢</span>
          <span>Custom Green-Screen Video</span>
          <span style="font-size:0.75rem;color:rgba(255,255,255,0.7);font-weight:400;">Upload an MP4/WebM video in Step 4 to preview keying here</span>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div id="stage-keyed-video-wrap" style="position:relative;width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:12px;">
        <canvas id="stage-keyed-video-canvas" style="display:block;max-width:100%;max-height:100%;object-fit:contain;"></canvas>
        <video id="stage-keyed-video-source" src="${STATE.visVideoUrl}" loop muted playsinline autoplay style="display:none;"></video>
      </div>
    `;
    startStageVideoKeying();
    return;
  } else {
    stopStageVideoKeying();
  }

  const nicheVal = document.getElementById('niche-select')?.value || '';
  const defaultNicheTitle = nicheVal ? `${nicheVal.split('&')[0].trim()} Story` : 'Stoic Wisdom';
  const title = document.getElementById('vis-title-input')?.value.trim() || STATE.visualizerTitle || defaultNicheTitle;
  const sub   = document.getElementById('vis-subtitle-input')?.value.trim() || STATE.visualizerSubtitle || 'Audio Story Series';
  const style = STATE.visualizerStyle || 'glass_pill_cyan';

  container.innerHTML = `
    <div class="vis-mockup-card style-${style}">
      <div class="vis-mockup-left">
        <div class="vis-mockup-playbtn">▶</div>
      </div>
      <div class="vis-mockup-center">
        <div class="vis-mockup-meta">
          <span class="vis-mockup-title">${title}</span>
          <span class="vis-mockup-sub">${sub}</span>
        </div>
        <div class="vis-mockup-waves stage-waves-anim">
          <div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div>
          <div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div>
          <div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div>
          <div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div>
          <div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div>
        </div>
        <div class="vis-mockup-prog-wrap">
          <div class="vis-mockup-prog-fill" id="stage-card-prog" style="width:0%;"></div>
        </div>
        <div class="vis-mockup-timecodes">
          <span id="stage-card-cur">00:00</span>
          <span>00:20</span>
        </div>
      </div>
    </div>
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// Drag-and-Drop & Resizing Pointer System
// ═══════════════════════════════════════════════════════════════════════════

function onStagePointerDown(e) {
  const canvas = document.getElementById('stage-canvas');
  if (!canvas) return;

  const handle = e.target.closest('.stage-resize-handle');
  const element = e.target.closest('.stage-element');

  if (!handle && !element) {
    // Clicked empty background: clear element selection outline
    document.querySelectorAll('.stage-element').forEach(el => el.classList.remove('selected'));
    const statsEl = document.getElementById('stage-elem-label');
    if (statsEl) statsEl.textContent = '🎯 Click an element on canvas to inspect';
    return;
  }

  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const targetEl = handle ? handle.closest('.stage-element') : element;

  // Set active selection
  document.querySelectorAll('.stage-element').forEach(el => el.classList.remove('selected'));
  targetEl.classList.add('selected');

  const elRect = targetEl.getBoundingClientRect();
  const targetId = targetEl.id;

  // Calculate current X, Y, W, H normalized to 1920x1080 canvas
  const normX = ((elRect.left - rect.left) / rect.width) * 1920;
  const normY = ((elRect.top - rect.top) / rect.height) * 1080;
  const normW = (elRect.width / rect.width) * 1920;
  const normH = (elRect.height / rect.height) * 1080;

  _stageDrag = {
    type: handle ? 'resize' : 'move',
    targetId: targetId,
    targetType: targetId.includes('avatar') ? 'avatar' : targetId.includes('caption') ? 'caption' : 'player',
    handleDir: handle ? (handle.dataset.dir || 'br') : null,
    startX: normX,
    startY: normY,
    startW: normW,
    startH: normH,
    startClientX: e.clientX,
    startClientY: e.clientY,
    canvasRect: rect,
    startScale: STATE.customLayout.visualizer.scale || 1.0,
    startAvatarH: STATE.avatarSize || 920
  };

  targetEl.classList.add('dragging');
  updateStageInspectStats(_stageDrag);
}

function onStagePointerMove(e) {
  if (!_stageDrag) return;
  e.preventDefault();

  const d = _stageDrag;
  const rect = d.canvasRect;
  const deltaNormX = ((e.clientX - d.startClientX) / rect.width) * 1920;
  const deltaNormY = ((e.clientY - d.startClientY) / rect.height) * 1080;

  const targetEl = document.getElementById(d.targetId);
  if (!targetEl) return;

  if (d.type === 'move') {
    // 2D Free Drag
    let newX = Math.round(d.startX + deltaNormX);
    let newY = Math.round(d.startY + deltaNormY);

    // Boundary constraints
    newX = Math.max(0, Math.min(1920 - d.startW, newX));
    newY = Math.max(0, Math.min(1080 - d.startH, newY));

    targetEl.style.left = `${(newX / 1920) * 100}%`;
    targetEl.style.top  = `${(newY / 1080) * 100}%`;
    targetEl.style.right = 'auto';
    targetEl.style.bottom = 'auto';
    if (d.targetType === 'player') {
      const scale = STATE.customLayout.visualizer.scale || 1.0;
      targetEl.style.transform = `scale(${scale})`;
      targetEl.style.transformOrigin = 'top left';
    } else {
      targetEl.style.transform = 'none';
    }

    // Update state in real time
    if (d.targetType === 'avatar') {
      STATE.customLayout.avatar.x = newX;
      STATE.customLayout.avatar.y = newY;

      // Two-way sync: update Step 2 position radio buttons
      if (newX < 450) {
        highlightStep2Position('left');
      } else if (newX > 1150) {
        highlightStep2Position('right');
      } else {
        highlightStep2Position('center');
      }
    } else if (d.targetType === 'caption') {
      STATE.customLayout.caption.x = newX;
      STATE.customLayout.caption.y = newY;
      STATE.customLayout.caption.w = d.startW;
      STATE.customLayout.caption.h = d.startH;
      const descEl = document.getElementById('caption-pos-desc');
      if (descEl) descEl.innerHTML = `<strong>✨ CUSTOM CANVAS PLACEMENT</strong>: X=${newX}px, Y=${newY}px`;
    } else if (d.targetType === 'player') {
      STATE.customLayout.visualizer.x = newX;
      STATE.customLayout.visualizer.y = newY;
      const stageCanvas = document.getElementById('stage-canvas');
      if (stageCanvas) {
        STATE.customLayout.visualizer.w = Math.round((targetEl.offsetWidth / stageCanvas.offsetWidth) * 1920);
        STATE.customLayout.visualizer.h = Math.round((targetEl.offsetHeight / stageCanvas.offsetHeight) * 1080);
      }
    }

    updateStageInspectStats({ ...d, curX: newX, curY: newY, curW: d.startW, curH: d.startH });
  } else if (d.type === 'resize') {
    // Handle Resizing
    if (d.targetType === 'avatar') {
      // Resize avatar height
      const newH = Math.max(450, Math.min(1080, Math.round(d.startAvatarH + deltaNormY)));
      STATE.avatarSize = newH;
      targetEl.style.height = `${(newH / 1080) * 100}%`;
      targetEl.style.width  = `${(newH / 1080) * 100 * 0.75}%`;

      // Update Step 2 slider live
      const slider = document.getElementById('avatar-size-slider');
      const display = document.getElementById('avatar-size-display');
      if (slider) slider.value = newH;
      if (display) display.textContent = `${newH}px (Canvas Resized)`;

      updateStageInspectStats({ ...d, curX: d.startX, curY: d.startY, curW: targetEl.offsetWidth, curH: newH });
    } else if (d.targetType === 'caption') {
      // Resize captions bounding area
      let newW = d.startW;
      let newH = d.startH;
      let newX = d.startX;

      if (d.handleDir === 'r' || d.handleDir === 'br') {
        newW = Math.max(350, Math.min(1850, Math.round(d.startW + deltaNormX)));
      }
      if (d.handleDir === 'l') {
        const delta = Math.round(deltaNormX);
        newW = Math.max(350, Math.min(1850, d.startW - delta));
        newX = Math.round(d.startX + delta);
      }
      if (d.handleDir === 'b' || d.handleDir === 'br') {
        newH = Math.max(90, Math.min(600, Math.round(d.startH + deltaNormY)));
      }

      STATE.customLayout.caption.w = newW;
      STATE.customLayout.caption.h = newH;
      STATE.customLayout.caption.x = newX;
      STATE.customLayout.caption.y = d.startY;

      targetEl.style.width  = `${(newW / 1920) * 100}%`;
      targetEl.style.height = `${(newH / 1080) * 100}%`;
      targetEl.style.left   = `${(newX / 1920) * 100}%`;

      updateStageInspectStats({ ...d, curX: newX, curY: d.startY, curW: newW, curH: newH });
    } else if (d.targetType === 'player') {
      // Resize visualizer scale in 2D
      const scaleDelta = (deltaNormX + deltaNormY) / 800;
      const newScale = Math.max(0.4, Math.min(2.5, +(d.startScale + scaleDelta).toFixed(2)));
      STATE.customLayout.visualizer.scale = newScale;
      targetEl.style.transform = `scale(${newScale})`;
      targetEl.style.transformOrigin = 'top left';

      const stageCanvas = document.getElementById('stage-canvas');
      if (stageCanvas) {
        STATE.customLayout.visualizer.w = Math.round((targetEl.offsetWidth * newScale / stageCanvas.offsetWidth) * 1920);
        STATE.customLayout.visualizer.h = Math.round((targetEl.offsetHeight * newScale / stageCanvas.offsetHeight) * 1080);
      }

      updateStageInspectStats({ ...d, curX: d.startX, curY: d.startY, curW: Math.round(d.startW * newScale), curH: Math.round(d.startH * newScale) });
    }
  }
}

function onStagePointerUp(e) {
  if (!_stageDrag) return;
  const targetEl = document.getElementById(_stageDrag.targetId);
  if (targetEl) targetEl.classList.remove('dragging');
  _stageDrag = null;
}

function highlightStep2Position(pos) {
  STATE.position = pos;
  ['left', 'center', 'right'].forEach(p => {
    const btn = document.getElementById(`pos-${p}`);
    if (btn) {
      btn.classList.toggle('active', p === pos);
      btn.setAttribute('aria-pressed', p === pos ? 'true' : 'false');
    }
  });
}

function updateStageInspectStats(d) {
  const statsEl = document.getElementById('stage-elem-label');
  if (!statsEl) return;
  const x = Math.round(d.curX || d.startX);
  const y = Math.round(d.curY || d.startY);
  const w = Math.round(d.curW || d.startW);
  const h = Math.round(d.curH || d.startH);
  statsEl.innerHTML = `📍 <strong>${d.targetType.toUpperCase()}</strong>: X=<code>${x}px</code>, Y=<code>${y}px</code>, Area=<code>${w}×${h}px</code>`;
}

// ═══════════════════════════════════════════════════════════════════════════
// 20-Second Studio Preview Audio Player & Kinetic Caption Sync
// ═══════════════════════════════════════════════════════════════════════════

function toggle20sPreview() {
  if (STATE.previewPlayback.isPlaying) {
    pause20sPreview();
  } else {
    play20sPreview();
  }
}

function play20sPreview() {
  STATE.previewPlayback.isPlaying = true;
  const btn = document.getElementById('btn-play-preview');
  const icon = document.getElementById('preview-play-icon');
  const text = document.getElementById('preview-play-text');
  if (btn) btn.classList.add('is-playing');
  if (icon) icon.textContent = '❚❚';
  if (text) text.textContent = 'PAUSE 20s PREVIEW';

  const scrubber = document.getElementById('stage-scrubber');
  let startTime = performance.now() - (parseFloat(scrubber?.value || '0') * 1000);

  // Play audio track
  if (STATE.voiceoverUrl) {
    if (!STATE.previewPlayback.audioObj) {
      STATE.previewPlayback.audioObj = new Audio(STATE.voiceoverUrl);
    }
    const audio = STATE.previewPlayback.audioObj;
    audio.currentTime = parseFloat(scrubber?.value || '0');
    audio.play().catch(() => {});
  } else {
    // Generate soft synthesized preview hum/speech pulse with Web Audio API
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        gain.gain.setValueAtTime(0.05, ctx.currentTime);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        STATE.previewPlayback.synthOsc = { osc, ctx };
      }
    } catch (_) {}
  }

  // Play background music alongside voiceover at chosen volume
  if (STATE.bgmUrl) {
    if (!STATE.previewPlayback.bgmAudioObj) {
      STATE.previewPlayback.bgmAudioObj = new Audio(STATE.bgmUrl);
      STATE.previewPlayback.bgmAudioObj.loop = true;
    }
    const bgmAudio = STATE.previewPlayback.bgmAudioObj;
    const vol = parseFloat(document.getElementById('bgm-vol-slider')?.value || '7') / 100;
    bgmAudio.volume = Math.max(0.005, Math.min(0.5, vol));
    bgmAudio.currentTime = (parseFloat(scrubber?.value || '0')) % (STATE.bgmDuration || 60);
    bgmAudio.play().catch(() => {});
  }

  function loop(now) {
    if (!STATE.previewPlayback.isPlaying) return;
    const elapsed = (now - startTime) / 1000;

    if (elapsed >= 20.0) {
      // Finished 20 seconds
      pause20sPreview();
      onStageScrub(0);
      return;
    }

    onStageScrub(elapsed, false);
    STATE.previewPlayback.animFrame = requestAnimationFrame(loop);
  }

  STATE.previewPlayback.animFrame = requestAnimationFrame(loop);
}

function pause20sPreview() {
  STATE.previewPlayback.isPlaying = false;
  const btn = document.getElementById('btn-play-preview');
  const icon = document.getElementById('preview-play-icon');
  const text = document.getElementById('preview-play-text');
  if (btn) btn.classList.remove('is-playing');
  if (icon) icon.textContent = '▶';
  if (text) text.textContent = 'PLAY 20s PREVIEW';

  if (STATE.previewPlayback.animFrame) {
    cancelAnimationFrame(STATE.previewPlayback.animFrame);
    STATE.previewPlayback.animFrame = null;
  }
  if (STATE.previewPlayback.audioObj) {
    STATE.previewPlayback.audioObj.pause();
  }
  if (STATE.previewPlayback.bgmAudioObj) {
    STATE.previewPlayback.bgmAudioObj.pause();
  }
  if (STATE.previewPlayback.synthOsc) {
    try {
      STATE.previewPlayback.synthOsc.osc.stop();
      STATE.previewPlayback.synthOsc.ctx.close();
    } catch (_) {}
    STATE.previewPlayback.synthOsc = null;
  }
}

function onStageScrub(valSec, syncAudio = true) {
  const sec = parseFloat(valSec);
  const scrubber = document.getElementById('stage-scrubber');
  const curTimeEl = document.getElementById('stage-cur-time');
  const cardProg = document.getElementById('stage-card-prog');
  const cardCur = document.getElementById('stage-card-cur');

  if (scrubber) scrubber.value = sec;
  const curStr = `0:${Math.floor(sec).toString().padStart(2, '0')}`;
  if (curTimeEl) curTimeEl.textContent = curStr;
  if (cardCur) cardCur.textContent = curStr;
  if (cardProg) cardProg.style.width = `${(sec / 20) * 100}%`;

  if (syncAudio && STATE.previewPlayback.audioObj) {
    STATE.previewPlayback.audioObj.currentTime = sec;
  }
  if (syncAudio && STATE.previewPlayback.bgmAudioObj) {
    STATE.previewPlayback.bgmAudioObj.currentTime = sec % (STATE.bgmDuration || 60);
  }

  // Kinetic Caption Word Highlight Sync: 10 words over 20 seconds
  const wordDur = 20.0 / 10; // 2.0s per word
  const activeWordIdx = Math.min(9, Math.floor(sec / wordDur));
  const words = document.querySelectorAll('#stage-caption-content .demo-word');
  words.forEach((w, idx) => {
    w.classList.toggle('active', idx === activeWordIdx);
  });

  // Dynamic visualizer bars dance
  const bars = document.querySelectorAll('.stage-waves-anim .vis-bar');
  bars.forEach((b, i) => {
    const h = 20 + Math.sin(sec * 8 + i) * 60;
    b.style.height = `${Math.max(10, Math.min(100, Math.round(h)))}%`;
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// Fullscreen, Grid, and Reset Actions
// ═══════════════════════════════════════════════════════════════════════════

function toggleStageFullscreen() {
  const container = document.getElementById('stage-viewport-container');
  const btn = document.getElementById('btn-fullscreen-stage');
  if (!container) return;

  STATE.customLayout.fullscreen = !STATE.customLayout.fullscreen;
  container.classList.toggle('stage-fullscreen-mode', STATE.customLayout.fullscreen);

  if (btn) {
    btn.textContent = STATE.customLayout.fullscreen ? '✖ Exit Fullscreen' : '⛶ Fullscreen';
  }
  showToast(STATE.customLayout.fullscreen ? '⛶ Studio Canvas Fullscreen (Press Esc to exit)' : 'Studio Canvas restored to window', 'info');
}

function toggleStageGrid() {
  const grid = document.getElementById('stage-grid');
  const btn = document.getElementById('btn-toggle-grid');
  if (!grid) return;

  const isVisible = grid.style.display !== 'none';
  grid.style.display = isVisible ? 'none' : 'flex';
  if (btn) btn.classList.toggle('active', !isVisible);
  showToast(!isVisible ? '📐 90% YouTube safe grid shown' : '📐 Safe grid hidden', 'info');
}

function resetStageElements() {
  STATE.customLayout.avatar = { x: null, y: null };
  STATE.customLayout.caption = { x: null, y: null, w: null, h: null };
  STATE.customLayout.visualizer = { x: null, y: null, scale: 1.0 };
  syncStageFromState();
  showToast('🔄 Studio Canvas layout reset to default preset alignment!', 'success');
}

