const imageInput = document.querySelector('#image-input');
const preview = document.querySelector('#preview');
const recognize = document.querySelector('#recognize');
const statusMessage = document.querySelector('#status');
const result = document.querySelector('#result');
const latexOutput = document.querySelector('#latex');
const formula = document.querySelector('#formula');
const appId = document.querySelector('#app-id');
const appSecret = document.querySelector('#app-secret');
let imageData;
let imageType;

appId.value = sessionStorage.getItem('simpletex-app-id') || '';
appSecret.value = sessionStorage.getItem('simpletex-app-secret') || '';

function setImage(file) {
  if (!file || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 3 * 1024 * 1024) {
    statusMessage.textContent = '请选择不超过 3 MB 的 PNG、JPG 或 WEBP 图片。';
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    imageData = reader.result.split(',')[1];
    imageType = file.type;
    preview.src = reader.result;
    preview.hidden = false;
    recognize.disabled = false;
    result.hidden = true;
    statusMessage.textContent = '图片已准备好，可以开始识别。';
  };
  reader.readAsDataURL(file);
}

imageInput.addEventListener('change', () => setImage(imageInput.files[0]));
document.querySelector('#drop-zone').addEventListener('dragover', (event) => event.preventDefault());
document.querySelector('#drop-zone').addEventListener('drop', (event) => { event.preventDefault(); setImage(event.dataTransfer.files[0]); });
document.addEventListener('paste', (event) => {
  const file = [...event.clipboardData.files].find((item) => item.type.startsWith('image/'));
  if (file) setImage(file);
});

document.querySelector('#clear-credentials').addEventListener('click', () => {
  appId.value = '';
  appSecret.value = '';
  sessionStorage.removeItem('simpletex-app-id');
  sessionStorage.removeItem('simpletex-app-secret');
});

recognize.addEventListener('click', async () => {
  if (!appId.value.trim() || !appSecret.value.trim()) {
    statusMessage.textContent = '请先填写 SimpleTex APP ID 与 APP Secret。';
    return;
  }
  sessionStorage.setItem('simpletex-app-id', appId.value.trim());
  sessionStorage.setItem('simpletex-app-secret', appSecret.value.trim());
  recognize.disabled = true;
  statusMessage.textContent = '识别中…';
  result.hidden = true;
  try {
    const response = await fetch('/api/recognize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ appId: appId.value.trim(), appSecret: appSecret.value.trim(), model: document.querySelector('#model').value, imageType, image: imageData }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || '识别失败，请稍后重试。');
    latexOutput.value = payload.latex;
    katex.render(payload.latex, formula, { displayMode: true, throwOnError: false });
    statusMessage.textContent = `识别完成${payload.confidence == null ? '' : ` · 置信度 ${(payload.confidence * 100).toFixed(1)}%`}`;
    result.hidden = false;
  } catch (error) {
    statusMessage.textContent = error.message;
  } finally {
    recognize.disabled = false;
  }
});

document.querySelector('#copy').addEventListener('click', async () => {
  await navigator.clipboard.writeText(latexOutput.value);
  statusMessage.textContent = 'LaTeX 已复制。';
});
