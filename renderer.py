"""将 Markdown 内容块注入 HTML，并按浏览器实测高度分页导出 PNG。"""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
UPLOADS_DIR = PROJECT_ROOT / "static" / "uploads"
DEFAULT_TEMPLATE = "template_01_极简白底"
TEMPLATE_TEXT_KEYS = ("header_label", "footer_subtitle")
TEMPLATE_STYLE_KEYS = (
    "background",
    "background_type",
    "background_secondary",
    "title_color",
    "body_color",
    "accent_color",
    "title_size",
    "body_size",
    "line_height",
    "padding",
    "image_radius",
)
INLINE_FONT_SIZES = {"16px", "20px", "24px", "28px", "32px", "36px"}
INLINE_COLOR_NAMES = {
    "red",
    "blue",
    "green",
    "orange",
    "purple",
    "black",
    "white",
}

SHARED_LAYOUT_CSS = """
*{box-sizing:border-box;text-decoration:none}
html,body{width:1080px;height:1440px;margin:0;overflow:hidden}
body{background:var(--background);color:var(--body-color);font-family:var(--body-font);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.note{position:relative;width:100%;height:100%;padding:var(--page-padding);background:var(--background)}
.topbar{position:absolute;top:96px;left:96px;display:inline-flex;align-items:center;padding:8px 16px;border-radius:12px;background:color-mix(in srgb,var(--accent-color) 12%,var(--background));color:var(--accent-color);font-size:22px;font-weight:700;letter-spacing:.06em;line-height:1.35}
.topbar::before{display:none}
.markdown-content{position:absolute;top:180px;right:96px;bottom:116px;left:96px;overflow:hidden;font-size:var(--body-size);line-height:var(--line-height);counter-reset:section-item}
.content-block{display:flow-root;margin:0 0 26px}
.content-block:has(> .block-subtitle){counter-increment:section-item}
.content-block.align-center{text-align:center}
.content-block.align-center .block-title,.content-block.align-center .block-body,.content-block.align-center .block-quote{text-align:center}
.content-block.align-center .block-list{border-top:none}
.content-block.align-center .block-list li{padding:18px 0;border-bottom:none;text-align:center}
.content-block.align-center .block-list li::before{position:static;display:flex;margin:0 auto 12px}
.content-block.align-center .block-subtitle{min-height:auto;padding:80px 0 0;text-align:center}
.content-block.align-center .block-subtitle::before{top:0;right:auto;bottom:auto;left:50%;width:72px;height:4px;transform:translateX(-50%)}
.content-block.align-center .block-subtitle::after{top:16px;right:auto;left:50%;transform:translateX(-50%)}
.block-title{margin:0 0 44px;color:var(--title-color);font-family:var(--title-font);font-size:var(--title-size);font-weight:700;letter-spacing:.01em;line-height:1.28}
.block-title-cover-title{max-width:780px;margin:28px auto 18px;text-align:center;font-size:clamp(62px,calc(var(--title-size) * 1.04),92px);font-weight:860;letter-spacing:-.035em;line-height:1.16;text-wrap:balance}
.block-subtitle{position:relative;min-height:64px;margin:8px 0 20px;padding:6px 0 6px 84px;color:var(--title-color);font-family:var(--title-font);font-size:var(--subtitle-size);font-weight:600;line-height:1.45}
.block-subtitle::before{position:absolute;top:8px;bottom:8px;left:68px;width:4px;border-radius:4px;background:var(--accent-color);content:""}
.block-subtitle::after{position:absolute;top:4px;left:0;display:inline-flex;width:56px;height:56px;align-items:center;justify-content:center;border-radius:50%;background:color-mix(in srgb,var(--accent-color) 10%,var(--background));color:var(--accent-color);font-size:28px;font-weight:700;line-height:1;content:counter(section-item,decimal-leading-zero)}
.block-body{margin:0;color:var(--body-color);font-size:var(--body-size);font-weight:400;line-height:var(--line-height)}
.block-body-cover-subtitle{max-width:720px;margin:0 auto 40px;padding:14px 22px;border:1px solid color-mix(in srgb,var(--accent-color) 20%,transparent);border-radius:22px;text-align:center;color:color-mix(in srgb,var(--body-color) 76%,var(--accent-color) 24%);font-size:calc(var(--body-size) * .88);font-weight:650;line-height:1.6;background:linear-gradient(180deg,color-mix(in srgb,var(--accent-color) 8%,var(--background)),color-mix(in srgb,var(--accent-color) 3%,var(--background)))}
.block-list{margin:4px 0 0;padding:0;border-top:1px solid color-mix(in srgb,var(--body-color) 18%,transparent);list-style:none;counter-reset:note-item}
.block-list li{position:relative;min-height:92px;padding:18px 4px 18px 80px;border-bottom:1px solid color-mix(in srgb,var(--body-color) 18%,transparent);color:var(--body-color);font-size:var(--body-size);font-weight:500;line-height:var(--line-height);counter-increment:note-item}
.block-list li::before{position:absolute;top:18px;left:0;display:inline-flex;width:56px;height:56px;align-items:center;justify-content:center;border-radius:50%;background:color-mix(in srgb,var(--accent-color) 10%,var(--background));color:var(--accent-color);font-size:28px;font-weight:700;line-height:1;content:counter(note-item,decimal-leading-zero)}
ul.block-list li::before{content:"•";font-size:28px}
.block-quote{margin:4px 0;padding:20px 28px;border-left:7px solid var(--accent-color);background:color-mix(in srgb,var(--accent-color) 9%,var(--background));color:var(--body-color);font-size:var(--body-size);line-height:var(--line-height)}
.block-image{display:flex;width:100%;margin:32px 0;align-items:center;justify-content:center}.block-image img{display:block;width:100%;height:auto;max-height:520px;border-radius:var(--image-radius);object-fit:contain}.block-image-manual img{max-height:420px}
.block-sticker{display:flex;width:100%;margin:18px 0}.block-sticker.align-left{justify-content:flex-start}.block-sticker.align-center{justify-content:center}.block-sticker svg{display:block;width:88px;height:88px}
strong,code{color:var(--accent-color);font-weight:700}code{padding:3px 9px;border-radius:7px;background:color-mix(in srgb,var(--accent-color) 12%,var(--background));font-family:var(--body-font)}
.footer{position:absolute;right:96px;bottom:48px;left:96px;display:flex;align-items:center;justify-content:center;color:color-mix(in srgb,var(--body-color) 52%,transparent);font-size:24px;letter-spacing:.04em;text-align:center}
.footer>span:first-child{width:100%}
.page-number{position:absolute;right:0;color:var(--accent-color);font-size:20px;font-weight:800;letter-spacing:.12em}
body[data-page-mode="cover"] .markdown-content{top:240px;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;text-align:center}
body[data-page-mode="cover"] .content-block{width:100%;margin-bottom:34px}
body[data-page-mode="cover"] .block-title{max-width:780px;margin:0 auto 18px;font-size:clamp(62px,calc(var(--title-size) * 1.04),92px);font-weight:860;letter-spacing:-.035em;line-height:1.16;text-align:center;text-wrap:balance}
body[data-page-mode="cover"] .block-body{max-width:720px;margin:0 auto;font-size:calc(var(--body-size) * .9);text-align:center}
body[data-page-mode="cover"] .block-image{margin:18px 0 0}
body[data-page-mode="cover"] .block-image img{max-height:600px}
"""

STICKER_PATHS = {
    "sparkle": '<path d="M46 6l8 20 20 8-20 8-8 20-8-20-20-8 20-8z"/>',
    "heart": '<path d="M46 74S12 54 12 31c0-9 7-17 17-17 7 0 13 4 17 10 4-6 10-10 17-10 10 0 17 8 17 17 0 23-34 43-34 43z"/>',
    "star": '<path d="M46 10l10 20 22 3-16 15 4 22-20-10-20 10 4-22-16-15 22-3z"/>',
    "quote": '<path d="M22 56c0-13 8-23 20-30l4 7c-7 4-10 8-11 14h13v23H22V56zm34 0c0-13 8-23 20-30l4 7c-7 4-10 8-11 14h13v23H56V56z"/>',
    "check": '<path d="M34 61L18 45l7-7 9 9 25-25 7 7-32 32z"/>',
    "bolt": '<path d="M52 8L18 48h18l-8 32 34-40H44z"/>',
}


def load_config(config_path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    """读取项目 YAML 配置。"""
    with Path(config_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"配置文件格式错误：{config_path}")
    return config


def load_template(template_path: str | Path) -> str:
    """读取 UTF-8 HTML 模板。"""
    return Path(template_path).read_text(encoding="utf-8")


def load_template_style(style_path: str | Path) -> dict[str, Any]:
    """读取与 HTML 同名的 JSON 样式配置。"""
    with Path(style_path).open("r", encoding="utf-8") as file:
        style = json.load(file)
    if not isinstance(style, dict):
        raise ValueError(f"模板配置格式错误：{style_path}")
    return style


def load_template_style_defaults(template_name: str) -> dict[str, Any]:
    """读取模板的可调样式默认值。"""
    style_path = TEMPLATES_DIR / f"{template_name}.json"
    if not style_path.is_file():
        raise FileNotFoundError(f"找不到模板样式配置：{style_path}")
    style = load_template_style(style_path)
    return {
        key: style.get(key)
        for key in TEMPLATE_STYLE_KEYS
        if key in style
    }


def load_template_style_configs() -> dict[str, dict[str, Any]]:
    """读取全部模板的样式默认配置，供 Web 页面初始化使用。"""
    template_names = [
        path.stem
        for path in sorted(TEMPLATES_DIR.glob("template_*.html"))
        if path.with_suffix(".json").is_file()
    ]
    return {
        template_name: load_template_style_defaults(template_name)
        for template_name in template_names
    }


def load_template_text_config(template_name: str) -> dict[str, str]:
    """读取模板目录中的固定文字默认配置。"""
    config_path = TEMPLATES_DIR / template_name / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"找不到模板固定文字配置：{config_path}")
    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    if not isinstance(config, dict):
        raise ValueError(f"模板固定文字配置格式错误：{config_path}")

    result: dict[str, str] = {}
    for key in TEMPLATE_TEXT_KEYS:
        value = config.get(key)
        if not isinstance(value, str):
            raise ValueError(f"模板固定文字配置缺少字符串字段：{key}")
        result[key] = value
    return result


def load_template_text_configs() -> dict[str, dict[str, str]]:
    """读取全部模板的固定文字默认配置，供 Web 页面初始化使用。"""
    template_names = [
        path.stem
        for path in sorted(TEMPLATES_DIR.glob("template_*.html"))
        if path.with_suffix(".json").is_file()
    ]
    return {
        template_name: load_template_text_config(template_name)
        for template_name in template_names
    }


def _resolve_template_text(
    template_name: str,
    template_overrides: dict[str, dict[str, str]] | None,
) -> dict[str, str]:
    """合并磁盘默认文字与本次渲染的临时覆盖值。"""
    resolved = load_template_text_config(template_name)
    override = (template_overrides or {}).get(template_name, {})
    for key in TEMPLATE_TEXT_KEYS:
        if key in override:
            resolved[key] = override[key]
    return resolved


def _resolve_template_style(
    template_name: str,
    style: dict[str, Any],
    style_overrides: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """合并模板样式默认值与本次渲染的临时覆盖值。"""
    resolved = dict(style)
    override = (style_overrides or {}).get(template_name, {})
    for key in TEMPLATE_STYLE_KEYS:
        if key in override:
            resolved[key] = override[key]
    return resolved


def _sanitize_inline_style(style_text: str) -> str:
    """只保留编辑工具栏允许生成的三种行内样式。"""
    safe: list[str] = []
    for declaration in style_text.split(";"):
        if ":" not in declaration:
            continue
        property_name, raw_value = declaration.split(":", 1)
        property_name = property_name.strip().lower()
        value = raw_value.strip().lower()
        if property_name == "font-weight" and value in {"700", "bold"}:
            safe.append("font-weight:700")
        elif property_name == "font-size" and value in INLINE_FONT_SIZES:
            safe.append(f"font-size:{value}")
        elif property_name == "color":
            valid_color = (
                bool(re.fullmatch(r"#[0-9a-f]{6}", value))
                or bool(re.fullmatch(r"rgba?\([\d\s,.%]+\)", value))
                or value in INLINE_COLOR_NAMES
            )
            if valid_color:
                safe.append(f"color:{value}")
    return ";".join(safe)


class _InlineMarkupSanitizer(HTMLParser):
    """将用户行内标记限制为 span/strong，其他标签按文字显示。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag == "span":
            attributes = dict(attrs)
            style = _sanitize_inline_style(attributes.get("style") or "")
            style_attribute = (
                f' style="{html.escape(style, quote=True)}"' if style else ""
            )
            self.parts.append(f"<span{style_attribute}>")
        elif tag in {"strong", "b"}:
            self.parts.append("<strong>")
        else:
            self.parts.append(html.escape(self.get_starttag_text()))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "span":
            self.parts.append("</span>")
        elif tag in {"strong", "b"}:
            self.parts.append("</strong>")
        else:
            self.parts.append(html.escape(f"</{tag}>"))

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.parts.append(html.escape(self.get_starttag_text()))

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data))

    def handle_comment(self, data: str) -> None:
        self.parts.append(html.escape(f"<!--{data}-->"))

    def result(self) -> str:
        return "".join(self.parts)


def _sanitize_inline_markup(text: str) -> str:
    parser = _InlineMarkupSanitizer()
    parser.feed(text)
    parser.close()
    return parser.result()


def _inline_markdown(text: str) -> str:
    """安全保留工具栏格式，并兼容粗体与行内代码 Markdown。"""
    formatted = _sanitize_inline_markup(text)
    formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", formatted)
    formatted = re.sub(r"`(.+?)`", r"<code>\1</code>", formatted)
    return formatted


def _render_list(content: str, list_start: int | None = None) -> str:
    """将有序或无序列表块转换成 HTML。

    list_start 仅对有序列表生效：当长列表被拆分为多段时，
    后续段可通过 start 属性延续编号，而非从 1 重新开始。
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    ordered = bool(lines and re.match(r"^\d+\s*[.、．]\s*", lines[0]))
    tag = "ol" if ordered else "ul"
    items: list[str] = []

    start_attr = ""
    if ordered and list_start is not None and list_start > 1:
        start_attr = f' start="{list_start}"'

    for line in lines:
        pattern = r"^(\d+)\s*[.、．]\s*(.+)$" if ordered else r"^[-+*]\s+(.+)$"
        match = re.match(pattern, line)
        item_text = match.group(match.lastindex) if match else line
        items.append(f"<li>{_inline_markdown(item_text)}</li>")

    return f'<{tag} class="block-list"{start_attr}>{"".join(items)}</{tag}>'


def _resolve_image_source(source: str) -> str:
    """将 uploads 下的本地图片转为 data URI，保证截图时稳定加载。"""
    prefix = "/static/uploads/"
    if not source.startswith(prefix):
        return source

    filename = source.removeprefix(prefix)
    if not filename or Path(filename).name != filename:
        raise ValueError("上传图片路径不合法")
    image_path = UPLOADS_DIR / filename
    if not image_path.is_file():
        raise FileNotFoundError(f"上传图片不存在：{filename}")

    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _document_title(blocks: list[dict[str, str]]) -> str:
    """返回文档中的第一个标题。"""
    for block in blocks:
        if block.get("type") == "title" and str(block.get("content", "")).strip():
            return str(block["content"]).strip()
    return "图文笔记"


def _primary_title_index(
    blocks: list[dict[str, str]],
    document_title: str,
) -> int | None:
    """找出作为主标题渲染的第一个 title 块位置。"""
    for index, block in enumerate(blocks):
        if (
            block.get("type") == "title"
            and str(block.get("content", "")).strip() == document_title
        ):
            return index
    return None


def _is_secondary_title_block(
    blocks: list[dict[str, str]],
    index: int,
    document_title: str,
) -> bool:
    """判断当前 title 是否会被渲染成带编号的小标题。"""
    if blocks[index].get("type") != "title":
        return False
    primary_index = _primary_title_index(blocks, document_title)
    return primary_index is None or index != primary_index


def _subtitle_count_before(
    blocks: list[dict[str, str]],
    start_index: int,
    document_title: str,
) -> int:
    """统计本页之前已经渲染过多少个带编号的小标题。"""
    if start_index <= 0:
        return 0
    return sum(
        1
        for index in range(start_index)
        if _is_secondary_title_block(blocks, index, document_title)
    )


def _extract_cover_page(
    blocks: list[dict[str, str]],
    document_title: str,
    cover_settings: dict[str, Any] | None,
) -> tuple[list[dict[str, str]] | None, list[dict[str, str]], set[int]]:
    """按封面设置拆出单独封面页。"""
    settings = cover_settings or {}
    if not settings.get("enabled") or not settings.get("separate_page"):
        return None, blocks, set()

    title_index = _primary_title_index(blocks, document_title)
    if title_index is None:
        return None, blocks, set()

    cover_blocks: list[dict[str, str]] = [
        {"type": "title", "content": document_title, "align": "center"}
    ]
    covered_indices = {title_index}

    subtitle = str(settings.get("subtitle", "")).strip()
    if subtitle and subtitle != document_title:
        cover_blocks.append(
            {
                "type": "body",
                "content": subtitle,
                "align": "center",
                "variant": "cover-subtitle",
            }
        )

    if settings.get("prefer_cover_image"):
        cover_image_index = _find_preferred_cover_image_index(
            blocks,
            skip_indices=covered_indices,
        )
        if cover_image_index is not None:
            cover_image = dict(blocks[cover_image_index])
            cover_image["image_role"] = "cover"
            cover_blocks.append(cover_image)
            covered_indices.add(cover_image_index)

    rest_blocks = [
        dict(block)
        for index, block in enumerate(blocks)
        if index not in covered_indices
    ]
    return cover_blocks, rest_blocks, covered_indices


def _find_preferred_cover_image_index(
    blocks: list[dict[str, str]],
    *,
    skip_indices: set[int] | None = None,
) -> int | None:
    """优先找显式封面图，找不到就退回第一张可用图片。"""
    ignored = skip_indices or set()
    fallback_index: int | None = None
    for index, block in enumerate(blocks):
        if index in ignored or block.get("type") != "image":
            continue
        if block.get("image_role") == "cover":
            return index
        if fallback_index is None:
            fallback_index = index
    return fallback_index


def _apply_inline_cover_settings(
    blocks: list[dict[str, str]],
    document_title: str,
    cover_settings: dict[str, Any] | None,
) -> tuple[list[dict[str, str]], list[int]]:
    """未拆独立封面页时，也让第一页呈现明显的封面效果。"""
    settings = cover_settings or {}
    if not settings.get("enabled") or settings.get("separate_page"):
        return [dict(block) for block in blocks], list(range(len(blocks)))

    result = [dict(block) for block in blocks]
    source_indices = list(range(len(blocks)))
    title_index = _primary_title_index(result, document_title)
    if title_index is None:
        return result, source_indices

    result[title_index]["variant"] = "cover-title"
    result[title_index]["align"] = "center"

    insert_index = title_index + 1
    subtitle = str(settings.get("subtitle", "")).strip()
    if subtitle and subtitle != document_title:
        result.insert(
            insert_index,
            {
                "type": "body",
                "content": subtitle,
                "align": "center",
                "variant": "cover-subtitle",
            },
        )
        source_indices.insert(insert_index, title_index)
        insert_index += 1

    if settings.get("prefer_cover_image"):
        image_index = _find_preferred_cover_image_index(
            result,
            skip_indices={title_index},
        )
        if image_index is not None:
            cover_image = dict(result.pop(image_index))
            cover_image_source_index = source_indices.pop(image_index)
            cover_image["image_role"] = "cover"
            if image_index < insert_index:
                insert_index -= 1
            result.insert(insert_index, cover_image)
            source_indices.insert(insert_index, cover_image_source_index)

    return result, source_indices


def _render_sticker_svg(
    sticker_type: str,
    sticker_color: str,
    sticker_size: int = 88,
) -> str:
    path = STICKER_PATHS.get(sticker_type, STICKER_PATHS["sparkle"])
    color = (
        sticker_color
        if re.fullmatch(r"#[0-9a-fA-F]{6}", sticker_color or "")
        else "#D9363E"
    )
    safe_size = max(32, min(int(sticker_size), 240))
    return (
        f'<svg viewBox="0 0 92 92" aria-hidden="true" '
        f'width="{safe_size}" height="{safe_size}" '
        'xmlns="http://www.w3.org/2000/svg" fill="none">'
        f'<g fill="{html.escape(color, quote=True)}">{path}</g></svg>'
    )


def render_content_blocks(
    blocks: list[dict[str, str]],
    document_title: str,
    start_index: int = 0,
) -> str:
    """把结构化内容块转换为带测量标记的 HTML。"""
    rendered: list[str] = []
    primary_title_rendered = start_index > 0

    for offset, block in enumerate(blocks):
        block_type = block.get("type", "")
        content = str(block.get("content", "")).strip()
        align = str(block.get("align", "left")).strip().lower()
        if align not in {"left", "center"}:
            align = "left"
        if not content:
            continue

        if block_type == "title":
            if not primary_title_rendered and content == document_title:
                title_variant = str(block.get("variant", "")).strip().lower()
                variant_class = (
                    f' block-title-{title_variant}'
                    if title_variant in {"cover-title"}
                    else ""
                )
                markup = (
                    f'<h1 class="block-title{variant_class}">'
                    f"{_inline_markdown(content)}</h1>"
                )
                primary_title_rendered = True
            else:
                markup = f'<h2 class="block-subtitle">{_inline_markdown(content)}</h2>'
        elif block_type == "body":
            body = "<br>".join(_inline_markdown(line) for line in content.splitlines())
            body_variant = str(block.get("variant", "")).strip().lower()
            variant_class = (
                f' block-body-{body_variant}'
                if body_variant in {"cover-subtitle"}
                else ""
            )
            markup = f'<p class="block-body{variant_class}">{body}</p>'
        elif block_type == "list":
            list_start_raw = block.get("list_start")
            list_start = int(list_start_raw) if list_start_raw is not None else None
            markup = _render_list(content, list_start=list_start)
        elif block_type == "image":
            source = html.escape(_resolve_image_source(content), quote=True)
            image_role = str(block.get("image_role", "pagination"))
            if image_role not in {"cover", "pagination", "tail", "manual"}:
                image_role = "pagination"
            markup = (
                f'<figure class="block-image block-image-{image_role}">'
                f'<img src="{source}" alt="笔记配图">'
                "</figure>"
            )
        elif block_type == "sticker":
            sticker_type = str(block.get("sticker_type", content)).strip() or "sparkle"
            sticker_color = str(block.get("sticker_color", "#D9363E")).strip()
            sticker_size = int(block.get("sticker_size", 88) or 88)
            markup = (
                f'<div class="block-sticker align-{align}">'
                f"{_render_sticker_svg(sticker_type, sticker_color, sticker_size)}"
                "</div>"
            )
        elif block_type == "quote":
            quote = "<br>".join(_inline_markdown(line) for line in content.splitlines())
            markup = f'<blockquote class="block-quote">{quote}</blockquote>'
        else:
            raise ValueError(f"不支持的内容块类型：{block_type}")

        block_index = start_index + offset
        rendered.append(
            f'<div class="content-block align-{align}" data-block-index="{block_index}">{markup}</div>'
        )

    if not rendered:
        raise ValueError("没有可渲染的 Markdown 内容")
    return "".join(rendered)


def _style_override(style: dict[str, Any], body_size: int) -> str:
    """将 JSON 主题转换成 CSS 变量，并应用分页字号。"""
    configured_title_size = int(style.get("title_size", 64))
    configured_body_size = int(style.get("body_size", body_size))
    configured_line_height = float(style.get("line_height", 1.8))
    configured_padding = int(style.get("padding", 96))
    configured_image_radius = int(style.get("image_radius", 12))
    title_size = min(configured_title_size, max(50, body_size * 2))
    values = {
        "background": style.get("background", "#FFFFFF"),
        "title-color": style.get("title_color", "#2B2B2B"),
        "title-font": style.get(
        "title_font",
            '"Source Han Sans SC", "Microsoft YaHei", sans-serif',
        ),
        "title-size": f"{title_size}px",
        "subtitle-size": f"{max(34, round(configured_body_size * 1.42))}px",
        "body-color": style.get("body_color", "#444444"),
        "body-font": style.get(
            "body_font",
            '"Source Han Sans SC", "Microsoft YaHei", sans-serif',
        ),
        "body-size": f"{configured_body_size}px",
        "line-height": max(1.35, min(configured_line_height, 2.4)),
        "page-padding": f"{max(24, min(configured_padding, 140))}px",
        "accent-color": style.get("accent_color", "#D9363E"),
        "image-radius": f"{max(0, min(configured_image_radius, 48))}px",
    }
    declarations = "".join(f"--{key}:{value};" for key, value in values.items())
    return (
        f'<style id="template-config">:root{{{declarations}}}'
        f"{SHARED_LAYOUT_CSS}</style>"
    )


def _section_counter_override(subtitle_offset: int) -> str:
    """让分页后的每一页继续沿用全局小标题序号。"""
    safe_offset = max(0, int(subtitle_offset))
    return (
        '<style id="section-counter-override">'
        f'.markdown-content{{counter-reset:section-item {safe_offset};}}'
        "</style>"
    )


def render_html(
    template_html: str,
    blocks: list[dict[str, str]],
    style: dict[str, Any],
    body_size: int,
    document_title: str,
    template_text: dict[str, str],
    start_index: int = 0,
    page_number: int = 1,
    subtitle_offset: int = 0,
    page_mode: str = "default",
) -> str:
    """将一页内容块与 JSON 样式注入 HTML 模板。"""
    blocks_markup = render_content_blocks(blocks, document_title, start_index)
    result, replacements = re.subn(
        r'(<section\b[^>]*data-render-slot="content"[^>]*>).*?(</section>)',
        lambda match: f"{match.group(1)}{blocks_markup}{match.group(2)}",
        template_html,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise ValueError("HTML 模板缺少 data-render-slot=\"content\" 节点")

    result = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(document_title)} - 第 {page_number} 页</title>",
        result,
        count=1,
        flags=re.DOTALL,
    )
    result = re.sub(
        r'(<span\b[^>]*data-render-slot="page-number"[^>]*>).*?(</span>)',
        rf"\g<1>{page_number:02d}\g<2>",
        result,
        count=1,
        flags=re.DOTALL,
    )
    body_attribute = f'data-page-mode="{html.escape(page_mode, quote=True)}"'
    result = re.sub(
        r"<body\b",
        f"<body {body_attribute}",
        result,
        count=1,
    )
    for key in TEMPLATE_TEXT_KEYS:
        result = result.replace(
            f"{{{{ {key} }}}}",
            html.escape(template_text[key]),
        )
    result = result.replace(
        "</head>",
        (
            f"{_style_override(style, body_size)}"
            f"{_section_counter_override(subtitle_offset)}</head>"
        ),
        1,
    )
    if "{{" in result or "}}" in result:
        raise ValueError("渲染结果中存在未处理的双花括号占位符")
    return result


def _set_page_content(page: Page, rendered_html: str) -> None:
    """加载页面并等待字体和图片稳定。"""
    page.set_content(rendered_html, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_function(
        "() => Array.from(document.images).every(image => image.complete)"
    )


def _measure_blocks(page: Page, rendered_html: str) -> tuple[float, list[float]]:
    """让 Chromium 实测内容区容量和每个块的占用高度。"""
    _set_page_content(page, rendered_html)
    measurement = page.evaluate(
        """() => {
            const container = document.querySelector('[data-render-slot="content"]');
            const blocks = Array.from(document.querySelectorAll('.content-block'));
            return {
                available: container.clientHeight - 20,
                heights: blocks.map((block) => {
                    const style = getComputedStyle(block);
                    return block.getBoundingClientRect().height
                        + parseFloat(style.marginTop || 0)
                        + parseFloat(style.marginBottom || 0);
                })
            };
        }"""
    )
    return float(measurement["available"]), [
        float(height) for height in measurement["heights"]
    ]


def _page_content_fits(page: Page) -> bool:
    """确认当前页内容没有超过 1440px 画布中的可用内容区。"""
    return bool(
        page.evaluate(
            """() => {
                const container = document.querySelector('[data-render-slot="content"]');
                return container.scrollHeight <= container.clientHeight + 8;
            }"""
        )
    )


def _split_long_lists(
    blocks: list[dict[str, str]],
    source_indices: list[int],
    max_per_group: int = 3,
) -> tuple[list[dict[str, str]], list[int]]:
    """将超过 max_per_group 条的长列表拆成多个子块，使分页器可跨页拆分。

    每个子块继承原块全部字段（type / align / sticker_type 等），
    仅 content 替换为子集的文本行。
    有序列表额外写入 list_start，让子块 <ol> 延续编号。

    source_indices 同步扩展：同一原始列表的所有子块都指向同一个原始索引，
    因此 block_start / block_end / 图片插入定位不受影响。
    """
    new_blocks: list[dict[str, str]] = []
    new_indices: list[int] = []

    for idx, block in enumerate(blocks):
        if block.get("type") != "list":
            new_blocks.append(block)
            new_indices.append(source_indices[idx])
            continue

        content = str(block.get("content", ""))
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) <= max_per_group:
            new_blocks.append(block)
            new_indices.append(source_indices[idx])
            continue

        ordered = bool(lines and re.match(r"^\d+\s*[.、．]\s*", lines[0]))
        list_start = 1
        i = 0
        remaining = len(lines)
        while i < len(lines):
            # 不要让最后一组只剩 1 条
            if remaining == 4:
                size = 2
            elif remaining <= max_per_group:
                size = remaining
            else:
                size = min(max_per_group, remaining)
                if remaining - size == 1 and size > 2:
                    size -= 1

            chunk = lines[i : i + size]
            sub_block = dict(block)
            sub_block["content"] = "\n".join(chunk)
            if ordered:
                sub_block["list_start"] = list_start
                list_start += size

            new_blocks.append(sub_block)
            new_indices.append(source_indices[idx])
            i += size
            remaining -= size

    return new_blocks, new_indices


def _paginate(
    blocks: list[dict[str, str]],
    heights: list[float],
    available_height: float,
    document_title: str,
) -> list[tuple[int, int]]:
    """按实测高度分页，并尽量避免图片或小标题与后续内容拆页。"""
    pages: list[tuple[int, int]] = []
    page_start = 0
    used_height = 0.0
    index = 0

    while index < len(blocks):
        height = heights[index]
        next_index = index + 1
        next_type = (
            blocks[next_index].get("type") if next_index < len(blocks) else None
        )
        should_keep_image_with_next = (
            blocks[index].get("type") == "image"
            and next_type in {"body", "list", "quote", "title"}
        )
        if (
            should_keep_image_with_next
            and index > page_start
            and next_index < len(blocks)
        ):
            combined_height = used_height + height + heights[next_index]
            next_pair_fits_on_fresh_page = (
                height + heights[next_index] <= available_height
            )
            if combined_height > available_height and next_pair_fits_on_fresh_page:
                pages.append((page_start, index))
                page_start = index
                used_height = 0.0
                continue

        if index > page_start and used_height + height > available_height:
            pages.append((page_start, index))
            page_start = index
            used_height = 0.0
            continue

        used_height += height
        index += 1

    if page_start < len(blocks):
        pages.append((page_start, len(blocks)))
    return pages


def _open_chromium(playwright: Any) -> Any:
    """优先启动 bundled Chromium，添加服务器优化参数。"""
    launch_args = [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    try:
        return playwright.chromium.launch(headless=True, args=launch_args)
    except PlaywrightError as error:
        if "Executable doesn't exist" not in str(error):
            raise
        return playwright.chromium.launch(channel="chrome", headless=True, args=launch_args)


def _block_summary(block: dict[str, str], limit: int = 34) -> str:
    """生成用于分页清单的简短内容描述。"""
    content = re.sub(r"\s+", " ", str(block.get("content", ""))).strip()
    if len(content) > limit:
        content = f"{content[:limit]}…"
    labels = {
        "title": "标题",
        "body": "正文",
        "list": "列表",
        "image": "图片",
        "quote": "引用",
    }
    return f"{labels.get(block.get('type', ''), '内容')}：{content}"


def render_template(
    blocks: list[dict[str, str]],
    template_name: str = DEFAULT_TEMPLATE,
    template_overrides: dict[str, dict[str, str]] | None = None,
    style_overrides: dict[str, dict[str, Any]] | None = None,
    cover_settings: dict[str, Any] | None = None,
) -> list[str]:
    """用指定模板自动分页渲染，并返回所有 PNG 的绝对路径。"""
    if not blocks:
        raise ValueError("没有可渲染的内容块")

    safe_name = Path(template_name).stem
    if not safe_name or safe_name != template_name:
        raise ValueError("template_name 只能是 templates 目录下的模板名称")

    html_path = TEMPLATES_DIR / f"{safe_name}.html"
    style_path = TEMPLATES_DIR / f"{safe_name}.json"
    if not html_path.is_file():
        raise FileNotFoundError(f"找不到 HTML 模板：{html_path}")
    if not style_path.is_file():
        raise FileNotFoundError(f"找不到 JSON 配置：{style_path}")

    config = load_config()
    image_config = config.get("image", {})
    output_config = config.get("output", {})
    width = int(image_config.get("width", 1080))
    height = int(image_config.get("height", 1440))
    configured_output = Path(output_config.get("directory", "output"))
    output_root = (
        configured_output
        if configured_output.is_absolute()
        else PROJECT_ROOT / configured_output
    )
    output_dir = output_root / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)

    template_html = load_template(html_path)
    style = _resolve_template_style(
        template_name,
        load_template_style(style_path),
        style_overrides,
    )
    template_text = _resolve_template_text(template_name, template_overrides)
    document_title = _document_title(blocks)
    cover_page_blocks, paginated_blocks, covered_indices = _extract_cover_page(
        blocks,
        document_title,
        cover_settings,
    )
    paginated_source_indices = [
        index for index in range(len(blocks)) if index not in covered_indices
    ]
    if cover_page_blocks is None:
        paginated_blocks, paginated_source_indices = _apply_inline_cover_settings(
            blocks,
            document_title,
            cover_settings,
        )
    paginated_blocks, paginated_source_indices = _split_long_lists(
        paginated_blocks,
        paginated_source_indices,
    )
    configured_body_size = int(style.get("body_size", 36))
    total_characters = sum(
        len(str(block.get("content", ""))) for block in paginated_blocks
    )
    preferred_body_size = (
        min(configured_body_size, 30)
        if total_characters >= 500
        else configured_body_size
    )
    size_candidates = list(range(preferred_body_size, 13, -2))

    with sync_playwright() as playwright:
        browser = _open_chromium(playwright)
        try:
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page = context.new_page()

            pages: list[tuple[int, int]] = []
            selected_size: int | None = None
            if not paginated_blocks:
                selected_size = preferred_body_size
            else:
                for body_size in size_candidates:
                    measurement_html = render_html(
                        template_html,
                        paginated_blocks,
                        style,
                        body_size,
                        document_title,
                        template_text,
                    )
                    available_height, block_heights = _measure_blocks(
                        page,
                        measurement_html,
                    )
                    candidate_pages = _paginate(
                        paginated_blocks,
                        block_heights,
                        available_height,
                        document_title,
                    )
                    if all(height <= available_height for height in block_heights):
                        pages = candidate_pages
                        selected_size = body_size
                        break

            if selected_size is None:
                # 尝试给出具体哪个块导致的失败
                oversized_details: list[str] = []
                try:
                    for i, (block, h) in enumerate(zip(paginated_blocks, block_heights)):
                        if h > available_height:
                            oversized_details.append(
                                f"「{_block_summary(block, limit=28)}」({h:.0f}px)"
                            )
                except Exception:
                    oversized_details = []
                if oversized_details:
                    detail = "；".join(oversized_details[:3])
                    suffix = " 等" if len(oversized_details) > 3 else ""
                    raise RuntimeError(
                        f"以下内容块超过单页可用高度（{available_height:.0f}px），"
                        f"请将其拆成多个自然段：{detail}{suffix}"
                    )
                raise RuntimeError(
                    "存在无法完整放入单页的超长段落，请将该段拆成多个自然段"
                )

            # 最后一页稀疏检测：如果最后一页内容不足可用高度 30%，
            # 尝试从倒数第二页末尾回移 1 个 block，减少留白。
            if len(pages) >= 2:
                last_start, last_end = pages[-1]
                last_page_height = sum(
                    block_heights[last_start:last_end]
                )
                if last_page_height < available_height * 0.30:
                    prev_start, prev_end = pages[-2]
                    if prev_end > prev_start:
                        moved_height = block_heights[prev_end - 1]
                        if last_page_height + moved_height <= available_height:
                            pages[-2] = (prev_start, prev_end - 1)
                            pages[-1] = (prev_end - 1, last_end)

            for stale_file in output_dir.glob("page*.png"):
                stale_file.unlink()
            for stale_file in output_dir.glob("page*.html"):
                stale_file.unlink()

            generated: list[str] = []
            manifest_pages: list[dict[str, Any]] = []
            page_offset = 0
            if cover_page_blocks:
                cover_start = min(covered_indices) if covered_indices else 0
                cover_end = max(covered_indices) if covered_indices else 0
                rendered_cover_html = render_html(
                    template_html,
                    cover_page_blocks,
                    style,
                    selected_size,
                    document_title,
                    template_text,
                    start_index=cover_start,
                    page_number=1,
                    subtitle_offset=0,
                    page_mode="cover",
                )
                cover_html_path = output_dir / "page1.html"
                cover_image_path = output_dir / "page1.png"
                cover_html_path.write_text(rendered_cover_html, encoding="utf-8")
                _set_page_content(page, rendered_cover_html)
                if not _page_content_fits(page):
                    raise RuntimeError("封面内容过多，请缩短封面副标题或调整封面图。")
                page.screenshot(
                    path=str(cover_image_path),
                    type="png",
                    full_page=False,
                    animations="disabled",
                )
                generated.append(str(cover_image_path.resolve()))
                manifest_pages.append(
                    {
                        "page": 1,
                        "file": cover_image_path.name,
                        "block_start": cover_start,
                        "block_end": cover_end,
                        "content_start": _block_summary(blocks[cover_start]) if covered_indices else "标题页",
                        "content_end": _block_summary(blocks[cover_end]) if covered_indices else "标题页",
                    }
                )
                page_offset = 1

            for page_number, (start, end) in enumerate(pages, start=1 + page_offset):
                page_blocks = paginated_blocks[start:end]
                original_start = paginated_source_indices[start]
                original_end = paginated_source_indices[end - 1]
                rendered_html = render_html(
                    template_html,
                    page_blocks,
                    style,
                    selected_size,
                    document_title,
                    template_text,
                    start_index=original_start,
                    page_number=page_number,
                    subtitle_offset=_subtitle_count_before(
                        blocks,
                        original_start,
                        document_title,
                    ),
                )
                html_path_for_page = output_dir / f"page{page_number}.html"
                image_path = output_dir / f"page{page_number}.png"
                html_path_for_page.write_text(rendered_html, encoding="utf-8")
                _set_page_content(page, rendered_html)
                if not _page_content_fits(page):
                    raise RuntimeError(
                        f"第 {page_number} 页内容超过 1440px，已停止导出以避免截断"
                    )
                page.screenshot(
                    path=str(image_path),
                    type="png",
                    full_page=False,
                    animations="disabled",
                )
                generated.append(str(image_path.resolve()))
                manifest_pages.append(
                    {
                        "page": page_number,
                        "file": image_path.name,
                        "block_start": original_start,
                        "block_end": original_end,
                        "content_start": _block_summary(blocks[original_start]),
                        "content_end": _block_summary(blocks[original_end]),
                    }
                )

            manifest = {
                "template": safe_name,
                "image_size": {"width": width, "height": height},
                "body_size": selected_size,
                "page_count": len(pages),
                "pages": manifest_pages,
            }
            (output_dir / "pagination.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            context.close()
            return generated
        finally:
            browser.close()


def render_all_templates(
    content: str,
    template_overrides: dict[str, dict[str, str]] | None = None,
    style_overrides: dict[str, dict[str, Any]] | None = None,
    cover_settings: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """
    用 templates/ 下全部模板渲染同一段 Markdown。

    返回格式：
    {"template_01_极简白底": ["page1.png", "page2.png"], ...}
    """
    from markdown_parser import parse_markdown

    blocks = parse_markdown(content)
    return render_all_template_blocks(
        blocks,
        template_overrides,
        style_overrides=style_overrides,
        cover_settings=cover_settings,
    )


def render_all_template_blocks(
    blocks: list[dict[str, str]],
    template_overrides: dict[str, dict[str, str]] | None = None,
    style_overrides: dict[str, dict[str, Any]] | None = None,
    cover_settings: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """用全部模板渲染已经确认过顺序与内容的结构化内容块。"""
    return render_from_blocks(
        blocks,
        template_overrides=template_overrides,
        style_overrides=style_overrides,
        cover_settings=cover_settings,
    )


def render_from_blocks(
    blocks: list[dict[str, str]],
    selected_templates: list[str] | None = None,
    template_overrides: dict[str, dict[str, str]] | None = None,
    style_overrides: dict[str, dict[str, Any]] | None = None,
    cover_settings: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """使用编辑后的内容块渲染全部或指定模板。"""
    if not blocks:
        raise ValueError("输入内容不能为空")

    available_templates = [
        html_path.stem
        for html_path in sorted(TEMPLATES_DIR.glob("template_*.html"))
        if html_path.with_suffix(".json").is_file()
    ]
    if len(available_templates) != 10:
        raise RuntimeError(
            f"预期找到 10 套模板，实际找到 {len(available_templates)} 套"
        )

    if selected_templates:
        if not all(isinstance(name, str) for name in selected_templates):
            raise ValueError("selected_templates 必须是模板名称数组")
        unknown = set(selected_templates) - set(available_templates)
        if unknown:
            raise ValueError(f"存在未知模板：{', '.join(sorted(unknown))}")
        selected_set = set(selected_templates)
        template_names = [
            name for name in available_templates if name in selected_set
        ]
    else:
        template_names = available_templates

    result: dict[str, list[str]] = {}
    for template_name in template_names:
        generated_paths = render_template(
            blocks,
            template_name,
            template_overrides,
            style_overrides,
            cover_settings,
        )
        result[template_name] = [Path(path).name for path in generated_paths]
    return result
