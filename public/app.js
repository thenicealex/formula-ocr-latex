const MAX_IMAGE_BYTES = 3 * 1024 * 1024;
const CREDENTIAL_KEYS = ['simpletex-app-id', 'simpletex-app-secret'];
const quotes = ['今天的努力，是明天的底气', '不负韶华，不负自己', '不积跬步，无以至千里；不积小流，无以成江海', '路漫漫其修远兮，吾将上下而求索', '万物皆有裂痕，那是光照进来的地方', '长风破浪会有时，直挂云帆济沧海', '翻过一座山，你就高过一座山', '每一个不曾起舞的日子，都是对生命的辜负', '不经一番寒彻骨，怎得梅花扑鼻香', '在繁忙的科研里，记得留一点时间给远方和诗意', '山重水复疑无路，柳暗花明又一村', '不怕慢，只怕站；不怕难，只怕懒', '心有山海，静而无边', '关关难过关关过，前路漫漫亦灿灿', '追光的人，终会光芒万丈'];

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);
const elements = {
  appId: $('#app-id'), appSecret: $('#app-secret'), credentials: $('#credentials'), copyLatex: $('#copy-latex'), copyPng: $('#copy-png'), downloadPng: $('#download-png'), emptyState: $('#empty-state'), error: $('#error-message'), formula: $('#formula'), imageInput: $('#image-input'), latex: $('#latex'), loading: $('#loading-message'), pasteTip: $('#paste-tip'), pasteZone: $('#paste-zone'), pngRender: $('#png-render'), preview: $('#preview'), result: $('#result'), resultBadge: $('#result-badge'), resultDetails: $('#result-details'), retry: $('#retry'), usageStandard: $('#usage-standard'), usageTotal: $('#usage-total'), usageTurbo: $('#usage-turbo'),
};
let imageData = null;
let imageType = null;
let model = 'standard';
let requestController = null;
let requestVersion = 0;
let pngBlob = null;
let usage = loadUsage();

function loadUsage() {
  try {
    const stored = JSON.parse(sessionStorage.getItem('simpletex-usage') || '');
    if (stored?.standard && stored?.turbo) return stored;
  } catch { /* Start a fresh local session. */ }
  return { standard: { count: 0, elapsed: 0 }, turbo: { count: 0, elapsed: 0 } };
}

function updateUsage() {
  const summary = (key, label) => `${label}：${usage[key].count} 次 · 平均 ${(usage[key].count ? usage[key].elapsed / usage[key].count : 0).toFixed(2)} s`;
  elements.usageTotal.textContent = usage.standard.count + usage.turbo.count;
  elements.usageStandard.textContent = summary('standard', '标准');
  elements.usageTurbo.textContent = summary('turbo', '轻量');
}

function recordUsage(requestModel, elapsed) {
  usage[requestModel].count += 1;
  usage[requestModel].elapsed += elapsed;
  sessionStorage.setItem('simpletex-usage', JSON.stringify(usage));
  updateUsage();
}

function setError(message) { elements.error.textContent = `识别失败：${message}`; elements.error.hidden = false; }
function clearError() { elements.error.hidden = true; elements.error.textContent = ''; }
function setLoading(loading) { elements.loading.hidden = !loading; }
function setPasteFeedback(text, state) { elements.pasteZone.classList.remove('focused', 'pasted'); if (state) elements.pasteZone.classList.add(state); elements.pasteTip.textContent = text; }
function hasCredentials() { return Boolean(elements.appId.value.trim() && elements.appSecret.value.trim()); }

function cancelRecognition() {
  requestController?.abort();
  requestController = null;
}

function clearPng() {
  pngBlob = null;
  if (elements.downloadPng.dataset.url) URL.revokeObjectURL(elements.downloadPng.dataset.url);
  elements.downloadPng.removeAttribute('href');
  delete elements.downloadPng.dataset.url;
}

function invalidateRecognition() {
  requestVersion += 1;
  cancelRecognition();
  clearPng();
  setLoading(false);
}

function setImage(file) {
  if (!file || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > MAX_IMAGE_BYTES) {
    setError('请选择不超过 3 MB 的 PNG、JPG 或 WEBP 图片。');
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    invalidateRecognition();
    imageData = reader.result.split(',')[1];
    imageType = file.type;
    elements.preview.src = reader.result;
    elements.preview.hidden = false;
    elements.result.hidden = true;
    elements.emptyState.hidden = false;
    clearError();
    setPasteFeedback('✅ 图片已接收，正在识别…', 'pasted');
    setTimeout(() => setPasteFeedback('可继续粘贴新截图', 'focused'), 1800);
    recognize();
  };
  reader.readAsDataURL(file);
}

async function recognize() {
  if (!imageData) return;
  if (!hasCredentials()) {
    elements.credentials.open = true;
    setError('请填写 SimpleTex APP ID 与 APP Secret 后重新识别。');
    return;
  }
  cancelRecognition();
  const version = ++requestVersion;
  const requestModel = model;
  const controller = new AbortController();
  requestController = controller;
  clearError();
  elements.result.hidden = true;
  elements.emptyState.hidden = true;
  setLoading(true);
  const startedAt = performance.now();
  try {
    sessionStorage.setItem(CREDENTIAL_KEYS[0], elements.appId.value.trim());
    sessionStorage.setItem(CREDENTIAL_KEYS[1], elements.appSecret.value.trim());
    const response = await fetch('/api/recognize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal, body: JSON.stringify({ appId: elements.appId.value.trim(), appSecret: elements.appSecret.value.trim(), model: requestModel, imageType, image: imageData }) });
    const text = await response.text();
    let payload;
    try { payload = JSON.parse(text); } catch { throw new Error(`识别服务返回了无效响应（HTTP ${response.status}）。`); }
    if (!response.ok) throw new Error(payload.error || '识别失败，请稍后重试。');
    if (version !== requestVersion || controller.signal.aborted) return;
    renderResult(payload, (performance.now() - startedAt) / 1000, requestModel, version);
  } catch (error) {
    if (error.name !== 'AbortError' && version === requestVersion) setError(error.message || '识别失败，请稍后重试。');
  } finally {
    if (version === requestVersion) { setLoading(false); requestController = null; }
  }
}

function renderResult(payload, elapsed, requestModel, version) {
  const latex = payload.latex;
  elements.latex.textContent = latex;
  elements.resultBadge.textContent = `✓ ${requestModel === 'standard' ? '标准模型' : '轻量模型'} · ${elapsed.toFixed(2)} s`;
  const details = [];
  if (typeof payload.confidence === 'number') details.push(`置信度：${(payload.confidence * 100).toFixed(1)}%`);
  if (payload.requestId) details.push(`请求 ID：${payload.requestId}`);
  elements.resultDetails.textContent = details.join(' · ');
  const previewLatex = latex.trim().replace(/^\$+|\$+$/g, '').trim();
  katex.render(previewLatex, elements.formula, { displayMode: true, throwOnError: false });
  katex.render(previewLatex, elements.pngRender, { displayMode: true, throwOnError: false });
  elements.result.hidden = false;
  recordUsage(requestModel, elapsed);
  preparePng(version);
}

function preparePng(version) {
  html2canvas(elements.pngRender, { backgroundColor: '#ffffff', scale: 5, useCORS: true, logging: false }).then((canvas) => canvas.toBlob((blob) => {
    if (!blob || version !== requestVersion) return;
    pngBlob = blob;
    if (elements.downloadPng.dataset.url) URL.revokeObjectURL(elements.downloadPng.dataset.url);
    const url = URL.createObjectURL(blob);
    elements.downloadPng.href = url;
    elements.downloadPng.dataset.url = url;
  }, 'image/png'));
}

function selectModel(button) {
  model = button.dataset.model;
  $$('[data-model]').forEach((item) => { const selected = item === button; item.classList.toggle('selected', selected); item.setAttribute('aria-pressed', String(selected)); });
  if (imageData) recognize();
}

$('#daily-quote').textContent = `✦ ${quotes[Math.floor(Math.random() * quotes.length)]} ✦`;
elements.appId.value = sessionStorage.getItem(CREDENTIAL_KEYS[0]) || '';
elements.appSecret.value = sessionStorage.getItem(CREDENTIAL_KEYS[1]) || '';
elements.credentials.open = !hasCredentials();
updateUsage();
elements.imageInput.addEventListener('change', () => setImage(elements.imageInput.files[0]));
elements.pasteZone.addEventListener('focus', () => setPasteFeedback('焦点已锁定，直接按 Ctrl+V 粘贴', 'focused'));
elements.pasteZone.addEventListener('blur', () => setPasteFeedback('点击此区域可锁定焦点，全局粘贴无需点击'));
elements.pasteZone.addEventListener('click', () => elements.pasteZone.focus());
elements.pasteZone.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') elements.pasteZone.focus(); });
document.addEventListener('paste', (event) => { const file = [...event.clipboardData.files].find((item) => item.type.startsWith('image/')); if (file) { event.preventDefault(); setImage(file); } });
$('#upload-zone').addEventListener('dragover', (event) => event.preventDefault());
$('#upload-zone').addEventListener('drop', (event) => { event.preventDefault(); setImage(event.dataTransfer.files[0]); });
$$('[data-model]').forEach((button) => button.addEventListener('click', () => selectModel(button)));
elements.retry.addEventListener('click', recognize);
$('#clear-credentials').addEventListener('click', () => { invalidateRecognition(); elements.appId.value = ''; elements.appSecret.value = ''; CREDENTIAL_KEYS.forEach((key) => sessionStorage.removeItem(key)); elements.credentials.open = true; });
elements.copyLatex.addEventListener('click', async () => { await navigator.clipboard.writeText(elements.latex.textContent); elements.copyLatex.textContent = '✓'; setTimeout(() => { elements.copyLatex.textContent = '⧉'; }, 1500); });
elements.copyPng.addEventListener('click', async () => { if (!pngBlob) return; try { await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob })]); elements.copyPng.textContent = '已复制'; } catch { elements.copyPng.textContent = '复制失败'; } setTimeout(() => { elements.copyPng.textContent = '复制为 PNG'; }, 2000); });
