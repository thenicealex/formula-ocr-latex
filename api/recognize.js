const crypto = require('crypto');

const MAX_IMAGE_BYTES = 3 * 1024 * 1024;
const API_URLS = {
  standard: 'https://server.simpletex.cn/api/latex_ocr',
  turbo: 'https://server.simpletex.cn/api/latex_ocr_turbo',
};
const IMAGE_TYPES = {
  'image/png': { extension: 'png', type: 'image/png' },
  'image/jpeg': { extension: 'jpg', type: 'image/jpeg' },
  'image/webp': { extension: 'webp', type: 'image/webp' },
};

function signedHeaders(appId, appSecret) {
  const headers = {
    'app-id': appId,
    'random-str': crypto.randomBytes(12).toString('base64url'),
    timestamp: String(Math.floor(Date.now() / 1000)),
  };
  const signatureSource = Object.keys(headers).sort().map((key) => `${key}=${headers[key]}`).join('&');
  headers.sign = crypto.createHash('md5').update(`${signatureSource}&secret=${appSecret}`).digest('hex');
  return headers;
}

function sendJson(response, status, body) {
  response.setHeader('Cache-Control', 'no-store');
  response.status(status).json(body);
}

module.exports = async function handler(request, response) {
  if (request.method !== 'POST') return sendJson(response, 405, { error: 'Method not allowed.' });
  const { appId, appSecret, image, imageType, model = 'standard' } = request.body || {};
  if (typeof appId !== 'string' || typeof appSecret !== 'string' || !appId.trim() || !appSecret.trim()) return sendJson(response, 400, { error: '请填写 SimpleTex APP ID 与 APP Secret。' });
  if (!API_URLS[model] || !IMAGE_TYPES[imageType] || typeof image !== 'string') return sendJson(response, 400, { error: '请求格式无效。' });

  let imageBuffer;
  try { imageBuffer = Buffer.from(image, 'base64'); } catch { return sendJson(response, 400, { error: '图片数据无效。' }); }
  if (!imageBuffer.length || imageBuffer.length > MAX_IMAGE_BYTES) return sendJson(response, 400, { error: '图片不能超过 3 MB。' });

  const imageInfo = IMAGE_TYPES[imageType];
  const form = new FormData();
  form.append('file', new Blob([imageBuffer], { type: imageInfo.type }), `formula.${imageInfo.extension}`);
  try {
    const upstream = await fetch(API_URLS[model], { method: 'POST', headers: signedHeaders(appId.trim(), appSecret.trim()), body: form, signal: AbortSignal.timeout(25_000) });
    const payload = await upstream.json();
    if (!upstream.ok || !payload.status) return sendJson(response, upstream.status || 502, { error: simpletexError(upstream.status, payload) });
    const latex = payload.res?.latex;
    if (!latex) return sendJson(response, 502, { error: 'SimpleTex 未返回 LaTeX 结果。' });
    return sendJson(response, 200, { latex, confidence: payload.res.conf, requestId: payload.request_id });
  } catch (error) {
    const message = error.name === 'TimeoutError' ? '连接 SimpleTex 超时，请稍后重新识别。' : '无法连接 SimpleTex，请检查网络后重试。';
    return sendJson(response, 502, { error: message });
  }
};

function simpletexError(status, payload) {
  const messages = {
    req_unauthorized: '鉴权失败，请检查 APP ID 与 APP Secret。',
    resource_no_valid: '没有可用识别额度，请检查 SimpleTex 账户余额或资源包。',
    image_missing: '未收到图片，请重新上传或粘贴。',
    image_oversize: '图片过大，请压缩后重试。',
    exceed_max_qps: '请求过于频繁，请稍后重试。',
    exceed_max_ccy: '当前请求过多，请稍后重试。',
    sever_closed: 'SimpleTex 服务维护中，请稍后重试。',
  };
  return messages[payload.errType || payload.error_type] || `SimpleTex 识别失败（HTTP ${status}）。`;
}
