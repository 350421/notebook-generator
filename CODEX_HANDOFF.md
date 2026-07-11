# notebook-generator 交接文档

> 给下一个 Codex / Claude Code 实例的完整项目文档。
> 阅读这份文档即可了解项目全貌、代码进度、部署方式，无需额外上下文。

---

## 1. 项目概述

**图文笔记批量生成器** — 输入一段文案，自动生成 10 套小红书风格的图文卡片，支持微调编辑后下载 ZIP。

- 技术栈：Python Flask + Playwright (Chromium 截图) + 原生 JS
- 运行方式：本地 `127.0.0.1:5010` 或 Railway 云部署
- 项目目录：`C:\Users\冯\Documents\Codex\2026-07-05\python-10-10-1-2-1\notebook-generator`

---

## 2. 快速启动

### 本地开发
```bash
cd notebook-generator
pip install -r requirements.txt
python -m playwright install chromium
python run_5010.py
# 打开 http://127.0.0.1:5010/
```

### Docker 构建
```bash
docker build -t notebook-generator .
docker run -p 8080:8080 notebook-generator
```

### Railway 部署
- GitHub: `github.com/350421/notebook-generator` (master 分支)
- Dockerfile 在项目根目录
- Railway 会自动检测 Dockerfile 并构建
- 环境变量 PORT=8080

---

## 3. 文件结构

```
notebook-generator/
├── app.py              # Flask 入口 (路由/校验/接口)
├── renderer.py         # 核心渲染引擎 (1330 行)
├── markdown_parser.py  # 文案解析器 (370 行)
├── run_5010.py         # 本地启动脚本 (端口 5010)
├── main.py             # 旧版 CLI 入口 (不再使用)
├── ocr_fetcher.py      # OCR 工具 (不再使用)
├── config.yaml         # 图片尺寸配置
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 构建配置
├── .dockerignore       # Docker 忽略文件
├── .gitignore          # Git 忽略文件
│
├── static/
│   ├── script.js       # 前端主逻辑 (2430 行，单个大文件)
│   ├── style.css       # 前端样式 (1594 行)
│   └── uploads/        # 用户上传的图片
│
├── templates_web/
│   └── index.html      # Web 页面模板 (427 行)
│
├── templates/          # 10 套图文模板
│   ├── template_01_极简白底.html  + .json + /config.json
│   ├── template_02_黑金商务.html  + .json + /config.json
│   ├── ... (共 10 套)
│   └── template_10_杂志风.html   + .json + /config.json
│
└── output/             # 生成图片的输出目录 (gitignore)
```

---

## 4. 代码架构

### 请求流程

```
用户输入文案 → POST /preview
  → app.py: validate_* 系列校验函数
  → markdown_parser.py: parse_markdown() → 返回 blocks[]
  → app.py: inject_uploaded_images() 穿插图片
  → renderer.py: render_all_template_blocks()
    → render_from_blocks() 遍历 10 套模板
      → render_template() 核心渲染:
        1. _extract_cover_page() 处理封面
        2. _split_long_lists() 长列表拆分 (Fix #1)
        3. 字号自适应 (递减 body_size 直到所有块能放入单页)
        4. _split_oversized_blocks() 过长 body 块拆分 (Fix #2)
        5. _measure_blocks() Chromium 实测高度
        6. _paginate() 贪心分页
        7. 逐个渲染页面截图 → page*.png
  → 返回 JSON: {success, blocks, images}
```

### 数据模型

```python
# Block 是核心数据结构，从前端到后端全链路使用
block = {
    "type": "title" | "body" | "list" | "image" | "quote" | "sticker",
    "content": "文本内容或图片URL",
    "align": "left" | "center",      # 可选
    # 以下字段仅在特定类型存在:
    "sticker_type": "sparkle" | ...,   # sticker 专属
    "sticker_color": "#D9363E",        # sticker 专属
    "sticker_size": 88,                # sticker 专属 (32-240)
    "list_start": 4,                   # 有序列表拆分后的起始编号
    "image_role": "cover" | "pagination" | "tail",  # image 专属
}
```

### 模板系统

每套模板由 3 个文件组成：
- `template_NN_名称.html` — HTML 骨架，含模板专属 CSS (`.theme-NN`)
- `template_NN_名称.json` — 默认样式参数 (background, title_color 等)
- `template_NN_名称/config.json` — 固定文字 (header_label, footer_subtitle)

模板 HTML 必须包含 `data-render-slot="content"` 的节点用于注入内容。
模板样式通过 `_style_override()` 注入为 CSS 变量。

---

## 5. 已完成功能清单

### 核心链路
- [x] 输入文案 → 10 套模板预览 → 微调编辑 → 选中下载 ZIP
- [x] Markdown 解析 + 中文前缀解析 (标题：/小标题：/正文：)
- [x] 纯文本智能标题识别 (50 字以内无前缀文本)
- [x] 纯文本小标题识别 (22 字以内)
- [x] 封面模式 (独立第一页 / 封面标题样式 / 封面图优先)
- [x] 图片上传 + 插入任意页 + 替换图片
- [x] 素材元素 (星芒/爱心/五角星/引号/对勾/闪电)
- [x] 素材大小调节 (32-240px 滑块)
- [x] 模板固定文字 (顶部标签 / 底部副标题，可批量应用)
- [x] 模板样式参数面板 (背景色/主色/标题色/正文字色/字号/行距/页边距/圆角)
- [x] 分页 — 小标题跨页连续编号
- [x] 分页 — 图片与后续内容尽量同页
- [x] 分页 — 长列表 (超过3条) 自动跨页拆分
- [x] 分页 — 最后一页稀疏检测 (不足30%时回移1个block)
- [x] 分页 — 长正文多级自动拆分 (句号→分号→逗号→固定长度)
- [x] 分页 — 渲染时单块过高自动拆分重试

### 编辑体验
- [x] Block 编辑 (上下移动、左对齐/居中)
- [x] 行内格式 (加粗/改色/改字号)
- [x] 细粒度撤销/重做 (Ctrl+Z/Y)
- [x] 预览自动同步 (改字/改色/改参后 650ms 防抖自动刷新)
- [x] 草稿自动保存 (localStorage，刷新恢复)
- [x] 项目保存/导入/导出 JSON
- [x] 项目删除确认弹窗

### 部署
- [x] Dockerfile (python:3.12-slim + Playwright Chromium)
- [x] Railway 云部署
- [x] Chromium 启动优化参数 (--disable-gpu 等)
- [x] JSON 错误返回 (500/404 全局处理)
- [x] 前端非 JSON 响应容错

---

## 6. 当前已知问题

1. **Railway 部署后 URL 地址变化** — 每次重建项目会获得新 URL，需要手动复制。
2. **长文本生成较慢** — 3000 字约 80 秒（因为 Chromium 需要逐模板渲染测量）。
3. **首次请求较慢** — 冷启动 Chromium 需要 10-15 秒。
4. **上传图片存储** — 图片存在 `static/uploads/`，超过 20 张无自动清理。
5. **前端 script.js 单体文件** — 2430 行，后续可考虑拆分模块。

---

## 7. 关键设计决策（不要随意推翻）

1. **不要改 blocks 数据模型** — 前后端全链路共享，改一处影响全局。
2. **不要改 `_paginate()` 的贪心算法** — 已有大量优化在上面（列表拆分、稀疏检测、过长拆分），贪心算法本身是稳定的。
3. **不要改 SHARED_LAYOUT_CSS 中的定位数值** — 已精确适配 1080×1440 画布，随便改会导致元素重叠。
4. **不要改 `_split_long_lists()` 的 source_indices 映射** — block_start/block_end/图片插入都依赖它。
5. **模板 HTML 必须保留 `data-render-slot="content"` 和 `data-render-slot="page-number"`** — 渲染器通过正则匹配注入内容。
6. **Chromium 不能跨线程复用** — Playwright sync API 绑定线程，持久化浏览器在 Flask 多线程模式下会报 greenlet 错误。
7. **本地端口是 5010**（`run_5010.py`），Docker 端口是 8080（Railway 标准）。

---

## 8. 下一步建议

按优先级排序：
1. **模板差异增强** — 10 套模板之间的视觉差异还不够大，建议丰富背景纹理、排版变化
2. **后端缓存** — 相同内容 + 相同模板参数可以缓存，避免重复渲染
3. **下载进度提示** — 生成超过 30 秒时给用户一个进度条
4. **移动端适配** — 当前只适配了桌面端
5. **Logo/水印** — 品牌定制能力

---

## 9. GitHub 信息

- 仓库：https://github.com/350421/notebook-generator
- 分支：`master`
- 最近提交：`af4c443` — chore: remove railway.exe binary

---

## 10. 给新 Codex 的第一条指令

> 请先阅读 `CODEX_HANDOFF.md`，基于项目目录 `C:\Users\冯\Documents\Codex\2026-07-05\python-10-10-1-2-1\notebook-generator` 继续开发。当前项目已完成文案解析、10套模板渲染、分页、编辑微调、保存导入导出等全部核心功能。优先基于现有结构迭代，不要大规模重构。
