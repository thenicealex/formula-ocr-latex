import os
import time
import random
import streamlit as st
import streamlit.components.v1 as components

import json

from backend import (
    base64_to_image,
    image_bytes_to_image,
    run_simpletex,
    increment_usage,
    get_model_usage,
    get_usage,
)

# ──────────────────────────────────────────────────────────────
# 声明自定义粘贴组件
# ──────────────────────────────────────────────────────────────
_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "components", "paste_component")
paste_component = components.declare_component("paste_component", path=_COMPONENT_DIR)

# ──────────────────────────────────────────────────────────────
# 页面配置
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="图片转公式",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────
# 全局 CSS
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.6rem !important; }
    .app-header { text-align: center; margin-bottom: 1.4rem; }
    .app-header h1 {
        font-size: 1.8rem; font-weight: 700;
        color: inherit; margin-bottom: 0.2rem;
    }
    .app-header p { font-size: 0.9rem; color: inherit; opacity: 0.7; margin: 0; }
    .badge {
        display: inline-block;
        background: #dcfce7; color: #15803d;
        padding: 0.2rem 0.7rem; border-radius: 999px;
        font-size: 0.8rem; font-weight: 600;
        animation: fadeIn 0.35s ease;
    }
    .formula-card {
        background: #f8fafc; border: 1px solid #e2e8f0;
        border-radius: 10px; padding: 1rem 1.2rem;
        margin-bottom: 0.4rem;
    }
    .section-label {
        font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.08em; color: #94a3b8; margin: 1.2rem 0 0.3rem;
        display: flex; align-items: center; gap: 0.5rem;
    }
    .section-label::after {
        content: ''; flex: 1; height: 1px; background: #e2e8f0;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
    .preview-hint {
        font-size: 0.78rem; color: #94a3b8;
        margin-top: 0.3rem; line-height: 1.5;
    }
    /* LaTeX 复制按钮常驻显示（默认 hover 才显示） */
    [data-testid="stCode"] button {
        opacity: 1 !important;
    }
    /* 上传区与粘贴区使用同一套蓝色主题 */
    [data-testid="stFileUploader"] > label {
        color: #bfdbfe !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        min-height: 130px;
        background: #f8faff !important;
        border: 2px dashed #93c5fd !important;
        border-radius: 12px !important;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
        text-align: center;
        transition: border-color 0.2s, background 0.2s;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        background: #eff6ff !important;
        border-color: #3b82f6 !important;
    }
    [data-testid="stFileUploaderDropzone"] > span {
        order: 1;
    }
    [data-testid="stFileUploaderDropzone"]::after {
        content: "拖拽图片到此处，或点击浏览";
        order: 2;
        color: #64748b;
        font-size: 0.82rem;
    }
    [data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] {
        order: 3;
    }
    [data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] * {
        color: #64748b !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background: transparent !important;
        border: none !important;
        color: #2563eb !important;
        padding: 0 !important;
    }
    [data-testid="stFileUploaderDropzone"] button:hover {
        background: transparent !important;
    }
    [data-testid="stFileUploaderDropzone"] button [data-has-shortcut="false"] {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.2rem;
    }
    [data-testid="stFileUploaderDropzone"] button [data-testid="stIconMaterial"] {
        font-size: 1.6rem;
    }
    [data-testid="stFileUploaderDropzone"] button p {
        margin: 0 !important;
        font-size: 0;
    }
    [data-testid="stFileUploaderDropzone"] button p::after {
        content: "上传图片";
        font-size: 1rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# 初始化 Session State
# ──────────────────────────────────────────────────────────────
for _key, _default in [
    ("last_paste_hash", None),
    ("current_image", None),
    ("latex_result", None),
    ("elapsed", 0.0),
    ("recognize_error", None),
    ("active_model", None),
    ("recognition_metadata", {}),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ──────────────────────────────────────────────────────────────
# 页面标题
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="app-header">
        <h1>Latex OCR</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

shici = [
    '今天的努力，是明天的底气',
    '不负韶华，不负自己',
    '不积跬步，无以至千里；不积小流，无以成江海',
    '路漫漫其修远兮，吾将上下而求索',
    '万物皆有裂痕，那是光照进来的地方',
    '长风破浪会有时，直挂云帆济沧海',
    '翻过一座山，你就高过一座山',
    '每一个不曾起舞的日子，都是对生命的辜负',
    '不经一番寒彻骨，怎得梅花扑鼻香',
    '在繁忙的科研里，记得留一点时间给远方和诗意',
    '山重水复疑无路，柳暗花明又一村',
    '不怕慢，只怕站；不怕难，只怕懒',
    '心有山海，静而无边',
    '关关难过关关过，前路漫漫亦灿灿',
    '追光的人，终会光芒万丈',
]

# 每次打开页面随机选一条，session 期间保持不变
if "daily_quote" not in st.session_state:
    st.session_state.daily_quote = random.choice(shici)

st.markdown(
    f'<p style="text-align:center; color:#22c55e; font-size:0.88rem;'
    f' font-style:italic; margin-top:-0.6rem; margin-bottom:1.2rem;">'
    f'✦ {st.session_state.daily_quote} ✦</p>',
    unsafe_allow_html=True,
)

model_label = st.segmented_control(
    "识别模型",
    options=["标准模型", "轻量模型"],
    default="标准模型",
    help="标准模型效果更好；轻量模型速度更快。",
)
model_name = "standard" if model_label == "标准模型" else "turbo"
if st.session_state.active_model != model_name:
    st.session_state.active_model = model_name
    if st.session_state.current_image is not None:
        st.session_state.latex_result = None
        st.session_state.recognize_error = None
        st.session_state.recognition_metadata = {}
        st.rerun()

col_left, col_right = st.columns([1, 1], gap="large")

# ──────────────────────────────────────────────────────────────
# 左列：粘贴区 + 图片预览
# ──────────────────────────────────────────────────────────────
with col_left:
    # 自定义粘贴组件（返回 base64 data URL 或 None）
    raw_paste = paste_component(key="paste_zone", default=None)
    uploaded_file = st.file_uploader(
        "上传或拖拽公式图片",
        type=["png", "jpg", "jpeg", "webp"],
    )

    # 检测是否粘贴了新图片
    if raw_paste is not None:
        paste_hash = hash(raw_paste)
        if paste_hash != st.session_state.last_paste_hash:
            st.session_state.last_paste_hash = paste_hash
            st.session_state.current_image   = base64_to_image(raw_paste)
            st.session_state.latex_result    = None
            st.session_state.recognize_error = None
            st.session_state.recognition_metadata = {}
            st.rerun()

    if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        image_hash = hash(image_bytes)
        if image_hash != st.session_state.last_paste_hash:
            st.session_state.last_paste_hash = image_hash
            try:
                st.session_state.current_image = image_bytes_to_image(image_bytes)
            except Exception:
                st.error("无法读取该图片，请上传 PNG、JPG 或 WEBP 格式的文件。")
            else:
                st.session_state.latex_result = None
                st.session_state.recognize_error = None
                st.session_state.recognition_metadata = {}
                st.rerun()

    if st.session_state.current_image is not None:
        img = st.session_state.current_image
        st.image(img, caption=f"{img.width} × {img.height} px", width='stretch')

# ──────────────────────────────────────────────────────────────
# 自动识别（有新图且尚未识别时触发）
# ──────────────────────────────────────────────────────────────
if (
    st.session_state.current_image is not None
    and st.session_state.latex_result is None
    and st.session_state.recognize_error is None
):
    spinner_placeholder = st.empty()
    spinner_placeholder.markdown(
        """
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2.5rem 0;">
            <div style="position:relative;width:52px;height:52px;">
                <div style="position:absolute;inset:0;border:3.5px solid #e2e8f0;border-radius:50%;"></div>
                <div style="position:absolute;inset:0;border:3.5px solid transparent;border-top-color:#7c3aed;border-radius:50%;animation:spin .8s linear infinite;"></div>
            </div>
            <div style="margin-top:1rem;font-size:0.95rem;color:#7c3aed;font-weight:600;letter-spacing:0.04em;">
                识别中<span style="animation:blink 1.2s steps(3,end) infinite;">…</span>
            </div>
        </div>
        <style>
            @keyframes spin { to { transform: rotate(360deg); } }
            @keyframes blink { 33% { opacity:.2; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
    t0 = time.time()
    try:
        result = run_simpletex(
            st.session_state.current_image, st.session_state.active_model
        )
        st.session_state.latex_result = result.latex
        st.session_state.recognition_metadata = {
            "confidence": result.confidence,
            "request_id": result.request_id,
        }
        elapsed = time.time() - t0
        increment_usage(st.session_state.active_model, elapsed)
    except Exception as exc:
        st.session_state.recognize_error = str(exc)

    st.session_state.elapsed = time.time() - t0
    spinner_placeholder.empty()
    st.rerun()

# ──────────────────────────────────────────────────────────────
# 右列：识别结果（全部展开，无 Tab）
# ──────────────────────────────────────────────────────────────
with col_right:
    if st.session_state.recognize_error:
        st.error(f"识别失败：{st.session_state.recognize_error}")

    elif st.session_state.latex_result:
        latex = st.session_state.latex_result
        elapsed = st.session_state.elapsed
        metadata = st.session_state.recognition_metadata

        status_col, retry_col = st.columns([3, 1])
        with status_col:
            st.markdown(
                f'<span class="badge">✓ {model_label} · {elapsed:.2f} s</span>',
                unsafe_allow_html=True,
            )
        with retry_col:
            if st.button("重新识别", key="retry_recognition"):
                st.session_state.latex_result = None
                st.session_state.recognize_error = None
                st.session_state.recognition_metadata = {}
                st.rerun()

        details = []
        if metadata.get("confidence") is not None:
            details.append(f"置信度：{metadata['confidence']:.1%}")
        if metadata.get("request_id"):
            details.append(f"请求 ID：{metadata['request_id']}")
        if details:
            st.caption(" · ".join(details))

        # ── 1. 公式预览 ──────────────────────────────
        st.markdown('<div class="section-label">公式预览</div>', unsafe_allow_html=True)
        render_str = latex.strip().lstrip("$").rstrip("$").strip()
        # KaTeX 不支持所有 LaTeX 语法，复杂公式（如 \begin{array}）可能无法渲染
        try:
            st.markdown(
                f'''$$\n{render_str}\n$$''',
                unsafe_allow_html=True,
            )
        except Exception:
            st.info("当前公式结构较复杂，预览不可用，请直接使用下方 LaTeX 代码或 PNG 格式。")
        st.markdown(
            '<div class="preview-hint">预览仅供参考，渲染失败不影响 LaTeX 代码和 PNG 格式的正常使用。</div>',
            unsafe_allow_html=True,
        )

        # ── 2. LaTeX 代码 ────────────────────────────
        st.markdown('<div class="section-label">LaTeX 代码</div>', unsafe_allow_html=True)
        st.caption("点击右上角复制按钮一键复制")
        st.code(latex, language="latex")

        # ── 3. PNG 格式（渲染公式为图片）──────────
        st.markdown('<div class="section-label">PNG 格式</div>', unsafe_allow_html=True)
        safe_latex_json = json.dumps(latex)
        st.iframe(
            f"""
            <!DOCTYPE html>
            <html><head><meta charset="UTF-8">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
            <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
            <style>
                :root {{
                    color-scheme: light dark;
                    --png-background: #fff;
                    --png-foreground: #0f172a;
                    --png-hint: #94a3b8;
                }}
                :root[data-theme="dark"] {{
                    --png-background: #0e1117;
                    --png-foreground: #f8fafc;
                }}
                @media (prefers-color-scheme: dark) {{
                    :root:not([data-theme]) {{
                        --png-background: #0e1117;
                        --png-foreground: #f8fafc;
                    }}
                }}
                body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--png-background); color: var(--png-foreground); }}
                .controls {{ display: flex; gap: 0.6rem; margin-top: 0.5rem; flex-wrap: wrap; }}
                .btn {{
                    display: inline-flex; align-items: center; gap: 0.4rem;
                    background: #7c3aed; color: #fff;
                    border: none; border-radius: 8px;
                    padding: 0.55rem 1.2rem;
                    font-size: 0.88rem; font-weight: 600;
                    cursor: pointer;
                    transition: background 0.15s, transform 0.1s;
                }}
                .btn:hover  {{ background: #6d28d9; }}
                .btn:active {{ transform: scale(0.97); }}
                .btn.ok     {{ background: #16a34a; }}
                .btn.err    {{ background: #dc2626; }}
                .hint {{ font-size: 0.76rem; color: var(--png-hint); margin-top: 0.4rem; line-height: 1.5; }}
                #katex-render {{ display: inline-block; padding: 0.5rem; background: var(--png-background); color: var(--png-foreground); }}
                #katex-render .katex {{ color: var(--png-foreground); }}
            </style>
            <script>
                (function() {{
                    var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    try {{
                        var app = window.parent.document.querySelector('[data-testid="stApp"]');
                        var rgb = app && getComputedStyle(app).backgroundColor.match(/\\d+/g);
                        if (rgb) isDark = rgb.slice(0, 3).map(Number).reduce(function(a, b) {{ return a + b; }}, 0) < 382;
                    }} catch (_) {{}}
                    document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
                }})();
            </script>
            </head><body>
            <div id="katex-render"></div>
            <div class="controls">
                <button class="btn" id="copy-png">复制为 PNG</button>
                <a class="btn" id="download-png" download style="text-decoration:none;">下载 PNG</a>
            </div>
            <script>
                var latex = {safe_latex_json};
                var rendered = katex.renderToString(latex, {{
                    throwOnError: false,
                    displayMode: true
                }});
                document.getElementById('katex-render').innerHTML = rendered;

                function captureToPng() {{
                    var el = document.getElementById('katex-render');
                    return html2canvas(el, {{
                        backgroundColor: null,
                        scale: 5,
                        useCORS: true,
                        logging: false,
                        onclone: function(clonedDocument) {{
                            clonedDocument.querySelectorAll('#katex-render, #katex-render .katex').forEach(function(node) {{
                                node.style.background = 'transparent';
                                node.style.color = '#0f172a';
                            }});
                        }}
                    }});
                }}

                function enablePngOps() {{
                    captureToPng().then(function(canvas) {{
                        canvas.toBlob(function(blob) {{
                            if (!blob) return;
                            var pngUrl = URL.createObjectURL(blob);
                            document.getElementById('download-png').href = pngUrl;
                            document.getElementById('copy-png').addEventListener('click', async function() {{
                                var btn = this;
                                try {{
                                    await navigator.clipboard.write([
                                        new ClipboardItem({{'image/png': blob}})
                                    ]);
                                    btn.textContent = '已复制';
                                    btn.classList.add('ok');
                                    setTimeout(function(){{btn.textContent='复制为 PNG';btn.classList.remove('ok');}}, 2500);
                                }} catch(e) {{
                                    btn.textContent = '失败: '+e.message;
                                    btn.classList.add('err');
                                    setTimeout(function(){{btn.textContent='复制为 PNG';btn.classList.remove('err');}}, 3000);
                                }}
                            }});
                        }}, 'image/png');
                    }}).catch(function(e) {{
                        var btn = document.getElementById('copy-png');
                        btn.textContent = '渲染失败';
                        btn.classList.add('err');
                        console.error(e);
                    }});
                }}

                enablePngOps();
            </script>
            </body></html>
            """,
            height=200,
        )

    else:
        st.markdown(
            """
            <div style="text-align:center; color:#cbd5e1; margin-top:2rem;">
                <div style="font-size:3.5rem; margin-bottom:0.6rem; opacity:0.6;">∑</div>
                <p style="font-size:0.95rem;">
                    在左侧按 <strong>Ctrl+V</strong> 粘贴截图后，结果将显示在此处
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ──────────────────────────────────────────────────────────────
# 底部信息栏
# ──────────────────────────────────────────────────────────────
st.markdown("---")
model_usage = get_model_usage()
standard_usage = model_usage.get("standard", {})
turbo_usage = model_usage.get("turbo", {})


def _usage_summary(name: str, stats: dict) -> str:
    count = stats.get("count", 0)
    average = stats.get("elapsed", 0) / count if count else 0
    return f"{name}：{count} 次 · 平均 {average:.2f} s"


st.markdown(
    f'<div style="text-align:center; font-size:0.82rem; color:#94a3b8;">'
    f'公式识别服务：<a href="https://simpletex.cn" style="color:#94a3b8;">SimpleTex</a>'
    f' &nbsp;·&nbsp; 累计识别次数：{get_usage()} 次'
    f' &nbsp;·&nbsp; {_usage_summary("标准", standard_usage)}'
    f' &nbsp;·&nbsp; {_usage_summary("轻量", turbo_usage)}'
    f'</div>',
    unsafe_allow_html=True,
)
