# 图文笔记批量生成器

一个本地运行的 Web 工具，用来把同一段内容快速生成 10 套不同风格的小红书图文笔记图片。

当前版本已经不是初始化空壳，而是可运行的本地 Web 应用。

## 当前能力

- 网页输入内容
- 生成 10 套模板预览
- 自动分页
- 上传图片并插入任意页
- 左侧 blocks 微调
- 文本加粗 / 改颜色 / 改字号
- 每段居左 / 居中
- 模板固定文字自定义
- 内置素材元素与改色
- 自动保存草稿
- 清空草稿 / 撤销
- 导出 ZIP

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

## 安装

```bash
cd notebook-generator
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
```

## 启动

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000/
```

## 字体说明

模板优先使用：

- 思源黑体（Source Han Sans SC / Noto Sans CJK SC）
- 思源宋体（Source Han Serif SC / Noto Serif CJK SC）

如果没有安装，会回退到：

- 微软雅黑（Microsoft YaHei）
- 系统可用无衬线字体

## 推荐阅读顺序

如果你是接手开发的人，先看：

1. `PROJECT_HANDOFF.md`
2. `CHANGELOG.md`
3. `app.py`
4. `renderer.py`
5. `static/script.js`

## 项目结构

```text
notebook-generator/
├── app.py
├── main.py
├── markdown_parser.py
├── renderer.py
├── ocr_fetcher.py
├── config.yaml
├── requirements.txt
├── README.md
├── PROJECT_HANDOFF.md
├── CHANGELOG.md
├── templates/
├── templates_web/
├── static/
└── output/
```
