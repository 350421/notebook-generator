# 图文笔记批量生成器 - 团队协作交接文档

## 文档用途

这份文档是当前项目的统一交接入口。

适用场景：

- 你自己隔天继续开发
- 换电脑迁移项目
- 团队成员接手优化
- 把项目交给新的 Codex 继续开发

建议规则：

- 先读这份文档，再看代码
- 先延续现有结构，不要急着重构
- 每次做完一轮功能后，同时更新本文档和 `CHANGELOG.md`
- 产品体验与后续路线可参考 `PRODUCT_EXPERIENCE_CHECKLIST.md`

---

## 1. 项目定位

项目名称：`图文笔记批量生成器`

项目目标：

- 本地运行
- 免费使用
- 无需登录
- 打开网页即可生成图文笔记
- 同一段内容一键生成 10 套模板图
- 支持先预览、后微调、再下载 ZIP

当前技术路线：

- 后端：Flask
- 渲染：Playwright + Chromium 截图
- 内容模型：`blocks`
- 模板：`templates/*.html + *.json`
- 前端：原生 HTML / CSS / JS

---

## 2. 当前完成状态

### 2.1 已完成的核心功能

- Flask Web 应用已跑通
- 支持 10 套模板批量生成
- 支持输出 PNG
- 支持 ZIP 打包下载
- 支持本地上传图片
- 支持图片插入任意页
- 支持自动分页
- 支持浮层大图预览
- 支持预览缓存，不重复渲染
- 支持选择部分模板下载

### 2.2 已完成的内容解析功能

- 支持原生 Markdown
- 支持中文前缀识别：
  - `标题：`
  - `小标题：`
  - `正文：`
- 支持纯文本智能识别
- 支持列表识别
- 支持 URL 密集文本的自动拆段

### 2.3 已完成的编辑能力

- 左侧 blocks 内容块编辑
- 内容块上下移动
- 文本局部格式：
  - 加粗
  - 改颜色
  - 改字号
- 每个文字块支持：
  - 居左
  - 居中

### 2.4 已完成的图片与封面逻辑

- 图片块已经改成真正随 blocks 顺序渲染
- 第 1 页插图默认放在主标题下方
- 其他页插图默认避开页首标题
- 图片参与分页，不截断

### 2.5 已完成的模板固定文字能力

- 顶部标签可改
- 底部副标题可改
- 可批量应用到全部模板

### 2.6 已完成的体验能力

- 自动保存草稿
- 清空草稿
- 撤销
- 重做
- 键盘撤销：
  - `Ctrl + Z`
  - `Cmd + Z`
- 键盘重做：
  - `Ctrl + Y`
  - `Ctrl + Shift + Z`
  - `Cmd + Shift + Z`
- 预览自动同步：
  - 微调区改字、加粗、改色、改字号后会自动刷新预览
  - 封面设置、模板样式参数变更后也会自动同步到预览

### 2.7 已完成的素材元素能力

- 新增素材元素面板
- 当前内置素材：
  - 星芒
  - 爱心
  - 五角星
  - 引号
  - 对勾
- 闪电

### 2.8 已完成的封面增强

- 启用封面模式后支持两种表现：
  - 独立第一页封面
  - 非独立第一页的首页封面化布局
- “优先使用封面图”规则已放宽：
  - 先找显式封面图
  - 找不到时自动回退到第一张可用图片
- 封面主标题、副标题的字号、间距、视觉层次已优化
- 支持插入到内容流
- 支持改颜色
- 支持移动位置
- 支持导出到最终图片

---

## 3. 当前项目结构

以后交接、迁移、协作，统一以这个文件夹为准：

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
├── output/
└── __pycache__/   (忽略)
```

说明：

- 需要交接的核心项目文件已经集中在 `notebook-generator/`
- 工作区外层的 `outputs/`、`work/` 不是核心源码
- 以后换电脑时，直接复制整个 `notebook-generator/` 即可

---

## 4. 核心文件职责

### 后端

- `app.py`
  - Web 服务入口
  - 处理预览、下载、上传接口
  - 校验 `blocks`

- `renderer.py`
  - 模板读取
  - 内容注入 HTML
  - Playwright 截图
  - 自动分页
  - 10 套模板批量渲染

- `markdown_parser.py`
  - 文本识别与结构化解析
  - 输出 `blocks`

### 前端

- `templates_web/index.html`
  - 页面结构

- `static/style.css`
  - 页面样式

- `static/script.js`
  - 页面核心交互
  - 预览、编辑、图片、素材、草稿、撤销等

### 模板

- `templates/`
  - 10 套图文模板
  - HTML + JSON

---

## 5. 当前数据模型

当前前后端都围绕 `blocks` 工作。

示例：

```json
[
  { "type": "title", "content": "标题", "align": "center" },
  { "type": "sticker", "content": "sparkle", "sticker_type": "sparkle", "sticker_color": "#D9363E", "align": "center" },
  { "type": "image", "content": "/static/uploads/demo.png", "url": "/static/uploads/demo.png", "width": "100%" },
  { "type": "body", "content": "正文内容", "align": "left" },
  { "type": "quote", "content": "引用内容", "align": "center" }
]
```

支持的 `type`：

- `title`
- `body`
- `list`
- `image`
- `quote`
- `sticker`

---

## 6. 当前行为规则

### 图片规则

- 图片块按 blocks 顺序渲染
- 插入任意页时，会根据该页内容位置插入
- 第 1 页默认插在主标题后
- 图片和后面紧邻正文会优先留在同一页

### 素材规则

- 素材块属于内容流，不是绝对定位元素
- 当前支持改颜色，不支持自由拖拽坐标
- 当前不支持素材缩放大小

### 预览规则

- 浮层预览关闭后不重新生成
- 只有重新生成预览时才重新渲染
- 下载 ZIP 使用当前编辑后的内容
- 小标题编号按整篇内容连续递增，不因翻页重置
- 分页时会尽量避免“小标题单独留在页尾、正文跑到下一页”

### 草稿规则

- 草稿保存在浏览器本地
- 刷新页面后会恢复
- 清空草稿会重置当前输入和缓存状态

### 撤销规则

- 文本编辑优先走细粒度撤销：
  - 多输入几个字时，撤销会优先只撤回这一步输入
  - 误删文字时，撤销会优先只恢复刚删掉的内容
- 文本编辑同样支持细粒度重做
- 图片、素材、块顺序、对齐等结构性操作仍使用快照级撤销 / 重做

---

## 7. 团队协作约定

### 开发前

每个接手的人先做 3 件事：

1. 先看 `PROJECT_HANDOFF.md`
2. 再看 `CHANGELOG.md`
3. 最后看：
   - `app.py`
   - `renderer.py`
   - `static/script.js`

### 开发中

建议规则：

- 优先延续现有结构
- 尽量不要大改 blocks 数据模型
- 尽量不要重构 `renderer.py` 的主流程，除非确实必要
- 新功能优先在现有路径上增量实现

### 开发后

每轮开发结束后至少更新：

- `CHANGELOG.md`
- `PROJECT_HANDOFF.md` 中的“当前完成状态”或“下一步计划”

---

## 8. 给新 Codex 的标准提示词

如果以后交给另一个 Codex，建议你直接给它这段：

```text
请先阅读 PROJECT_HANDOFF.md 和 CHANGELOG.md，再继续开发。
这是一个已经跑通的 Flask + Playwright 本地图文笔记生成工具。
请优先保持当前项目结构，不要大改架构。
请基于现有 blocks 数据模型、renderer.py 和 static/script.js 增量开发。
```

---

## 9. 当前优先级最高的下一步功能

### 第一优先级

- 模板参数面板
  - 标题字号
  - 正文字号
  - 行距
  - 图片圆角
  - 页边距

- 封面模式
  - 标题居中
  - 图片在标题下
  - 正文自动从第 2 页开始

### 第二优先级

- 素材大小调节
- 更多素材种类
- 上传 SVG 素材
- 自由摆件模式

### 第三优先级

- 历史项目列表
- 导出项目配置 JSON
- 导入项目配置 JSON

---

## 10. 如何启动

进入项目目录：

```bash
cd notebook-generator
```

安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
```

启动：

```bash
python app.py
```

访问地址：

```text
http://127.0.0.1:5010/
```

---

## 11. 关于“给另一个 Codex 会不会乱”

结论：不会。

只要你把下面两样一起给出去：

- 整个 `notebook-generator/`
- `PROJECT_HANDOFF.md`

再加上 `CHANGELOG.md`，新的 Codex 基本就能知道：

- 项目现在做到哪里
- 现有架构怎么跑
- 接下来应该从哪里继续

---

## 12. 关于“换电脑和团队协作”

推荐做法：

1. 复制整个 `notebook-generator/`
2. 到新电脑执行依赖安装
3. 打开 `PROJECT_HANDOFF.md`
4. 查看 `CHANGELOG.md`
5. 再继续开发

这就是当前最稳的交接方式。
