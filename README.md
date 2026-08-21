# LaTeX OCR

将公式图片识别为 LaTeX 的 Vercel 应用。每位使用者填写自己的 SimpleTex `APP ID` 与 `APP Secret`，并消耗自己的 SimpleTex 额度。

## 部署到 Vercel

1. 将仓库导入 [Vercel](https://vercel.com/new)。
2. 保持默认的 Framework Preset（Other）并部署；无需配置环境变量。
3. 打开部署后的页面，填写自己的 SimpleTex 凭据，上传或粘贴公式图片后开始识别。

Vercel 会将 `api/recognize.js` 部署为无状态函数。页面通过同源 HTTPS 请求将凭据和图片交给该函数，函数仅在内存中用凭据生成 SimpleTex 请求签名，随后立即丢弃；应用不会将凭据写入文件、数据库或日志。

凭据在浏览器的 `sessionStorage` 中保存，关闭标签页后会自动清除，也可以使用页面上的“清除凭据”按钮立即移除。图片大小上限为 3 MB；这是为使 JSON/Base64 请求不超过 Vercel Function 的 4.5 MB 请求体上限。

## 本地验证

安装依赖后可使用 Vercel CLI 运行：

```bash
npm install --global vercel
vercel dev
```

访问终端显示的本地地址即可测试。部署前请确保 SimpleTex 凭据有效。
