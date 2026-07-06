"""矩阵图文笔记批量生成器 Web 应用。"""

from __future__ import annotations

import io
import json
import threading
import time
import uuid
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory, url_for
from PIL import Image, UnidentifiedImageError

from markdown_parser import parse_markdown
from renderer import (
    PROJECT_ROOT,
    TEMPLATE_STYLE_KEYS,
    TEMPLATE_TEXT_KEYS,
    load_template_style_configs,
    load_template_text_configs,
    render_all_template_blocks,
    render_from_blocks,
)


OUTPUT_DIR = PROJECT_ROOT / "output"
ZIP_PATH = OUTPUT_DIR / "全部图片.zip"
UPLOAD_DIR = PROJECT_ROOT / "static" / "uploads"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
STYLE_COLOR_FIELDS = {"background", "background_secondary", "title_color", "body_color", "accent_color"}
STYLE_INT_FIELDS = {"title_size", "body_size", "padding", "image_radius"}
STYLE_FLOAT_FIELDS = {"line_height"}
generation_lock = threading.Lock()

app = Flask(
    __name__,
    template_folder="templates_web",
    static_folder="static",
)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

ALLOWED_BLOCK_TYPES = {"title", "body", "list", "image", "quote", "sticker"}
ALLOWED_BLOCK_ALIGNMENTS = {"left", "center"}
ALLOWED_STICKER_TYPES = {
    "sparkle",
    "heart",
    "star",
    "quote",
    "check",
    "bolt",
}


def validate_blocks(value: object) -> list[dict]:
    """校验前端回传的可编辑内容块。"""
    if not isinstance(value, list) or not value:
        raise ValueError("没有可生成的内容块")

    blocks: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("内容块格式错误")
        block_type = item.get("type")
        content = item.get("content")
        if content is None:
            content = (
                item.get("url")
                if block_type == "image"
                else item.get("text")
            )
        if block_type not in ALLOWED_BLOCK_TYPES:
            raise ValueError(f"不支持的内容类型：{block_type}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("内容块不能为空")
        block = {"type": block_type, "content": content.strip()}
        align = item.get("align")
        if align is not None:
            if align not in ALLOWED_BLOCK_ALIGNMENTS:
                raise ValueError("内容块对齐方式不合法")
            block["align"] = align
        if block_type == "image":
            block["width"] = "100%"
            image_role = item.get("image_role")
            if image_role in {"cover", "pagination", "tail"}:
                block["image_role"] = image_role
        if block_type == "sticker":
            sticker_type = item.get("sticker_type") or content.strip()
            if sticker_type not in ALLOWED_STICKER_TYPES:
                raise ValueError("素材类型不合法")
            sticker_color = item.get("sticker_color", "#D9363E")
            if not isinstance(sticker_color, str) or not sticker_color.startswith("#"):
                raise ValueError("素材颜色不合法")
            block["content"] = sticker_type
            block["sticker_type"] = sticker_type
            block["sticker_color"] = sticker_color
        blocks.append(block)
    return blocks


def validate_template_overrides(
    value: object,
) -> dict[str, dict[str, str]]:
    """校验本次请求里的模板固定文字，且不写回磁盘。"""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("template_overrides 必须是对象")

    defaults = load_template_text_configs()
    unknown_templates = set(value) - set(defaults)
    if unknown_templates:
        raise ValueError(
            f"存在未知模板：{', '.join(sorted(unknown_templates))}"
        )

    result: dict[str, dict[str, str]] = {}
    for template_name, fields in value.items():
        if not isinstance(fields, dict):
            raise ValueError(f"{template_name} 的固定文字配置必须是对象")
        unknown_fields = set(fields) - set(TEMPLATE_TEXT_KEYS)
        if unknown_fields:
            raise ValueError(
                f"{template_name} 存在未知配置项："
                f"{', '.join(sorted(unknown_fields))}"
            )
        result[template_name] = {}
        for key in TEMPLATE_TEXT_KEYS:
            if key not in fields:
                continue
            text = fields[key]
            if not isinstance(text, str):
                raise ValueError(f"{template_name}.{key} 必须是文字")
            if len(text) > 80:
                raise ValueError(f"{template_name}.{key} 最多 80 个字符")
            result[template_name][key] = text
    return result


def validate_template_style_overrides(
    value: object,
) -> dict[str, dict[str, int | float | str]]:
    """校验本次请求里的模板样式参数。"""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("template_style_overrides 必须是对象")

    defaults = load_template_style_configs()
    unknown_templates = set(value) - set(defaults)
    if unknown_templates:
        raise ValueError(
            f"存在未知模板样式：{', '.join(sorted(unknown_templates))}"
        )

    result: dict[str, dict[str, int | float | str]] = {}
    for template_name, fields in value.items():
        if not isinstance(fields, dict):
            raise ValueError(f"{template_name} 的样式配置必须是对象")
        unknown_fields = set(fields) - set(TEMPLATE_STYLE_KEYS)
        if unknown_fields:
            raise ValueError(
                f"{template_name} 存在未知样式项：{', '.join(sorted(unknown_fields))}"
            )

        result[template_name] = {}
        for key, raw_value in fields.items():
            if key in STYLE_COLOR_FIELDS:
                if not isinstance(raw_value, str) or not raw_value.startswith("#"):
                    raise ValueError(f"{template_name}.{key} 必须是颜色值")
                result[template_name][key] = raw_value
            elif key in STYLE_INT_FIELDS:
                if not isinstance(raw_value, (int, float)):
                    raise ValueError(f"{template_name}.{key} 必须是数字")
                result[template_name][key] = int(raw_value)
            elif key in STYLE_FLOAT_FIELDS:
                if not isinstance(raw_value, (int, float)):
                    raise ValueError(f"{template_name}.{key} 必须是数字")
                result[template_name][key] = float(raw_value)
            else:
                result[template_name][key] = str(raw_value)
    return result


def validate_cover_settings(value: object) -> dict[str, object]:
    """校验封面控制参数。"""
    defaults = {
        "enabled": False,
        "separate_page": False,
        "subtitle": "",
        "prefer_cover_image": True,
    }
    if value is None:
        return defaults
    if not isinstance(value, dict):
        raise ValueError("cover_settings 必须是对象")

    result = dict(defaults)
    if "enabled" in value:
        result["enabled"] = bool(value["enabled"])
    if "separate_page" in value:
        result["separate_page"] = bool(value["separate_page"])
    if "prefer_cover_image" in value:
        result["prefer_cover_image"] = bool(value["prefer_cover_image"])
    if "subtitle" in value:
        subtitle = value["subtitle"]
        if not isinstance(subtitle, str):
            raise ValueError("cover_settings.subtitle 必须是文字")
        if len(subtitle) > 120:
            raise ValueError("封面副标题最多 120 个字符")
        result["subtitle"] = subtitle.strip()
    return result


def validate_uploaded_images(value: object) -> list[dict[str, str]]:
    """校验并返回本次参与渲染的已上传图片。"""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("uploaded_images 必须是数组")
    if len(value) > 20:
        raise ValueError("每次最多使用 20 张图片")

    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("上传图片配置格式错误")
        if item.get("enabled", True) is False:
            continue
        url = item.get("url")
        position = item.get("position", "pagination")
        if not isinstance(url, str) or not url.startswith("/static/uploads/"):
            raise ValueError("上传图片 URL 不合法")
        if position not in {"cover", "pagination", "tail"}:
            raise ValueError("图片插入位置不合法")

        filename = url.removeprefix("/static/uploads/")
        if (
            not filename
            or Path(filename).name != filename
            or Path(filename).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS
            or not (UPLOAD_DIR / filename).is_file()
        ):
            raise ValueError("上传图片不存在或文件名不合法")
        result.append({"url": url, "position": position})
    return result


def inject_uploaded_images(
    blocks: list[dict[str, str]],
    uploaded_images: list[dict[str, str]],
) -> list[dict[str, str]]:
    """按封面、分页、尾图位置将上传图片穿插进内容块。"""
    result = [dict(block) for block in blocks]
    if not uploaded_images:
        return result

    cover_images = [
        {"type": "image", "content": item["url"], "image_role": "cover"}
        for item in uploaded_images
        if item["position"] == "cover"
    ]
    middle_images = [
        {"type": "image", "content": item["url"], "image_role": "pagination"}
        for item in uploaded_images
        if item["position"] == "pagination"
    ]
    tail_images = [
        {"type": "image", "content": item["url"], "image_role": "tail"}
        for item in uploaded_images
        if item["position"] == "tail"
    ]

    cover_index = 1 if result and result[0].get("type") == "title" else 0
    result[cover_index:cover_index] = cover_images

    if middle_images:
        candidate_indexes = [
            index + 1
            for index, block in enumerate(result)
            if block.get("type") in {"body", "list", "quote"}
        ]
        if not candidate_indexes:
            candidate_indexes = [len(result)]
        inserted = 0
        for number, image_block in enumerate(middle_images, start=1):
            candidate = candidate_indexes[
                min(
                    len(candidate_indexes) - 1,
                    round(number * (len(candidate_indexes) - 1) / (len(middle_images) + 1)),
                )
            ]
            result.insert(candidate + inserted, image_block)
            inserted += 1

    result.extend(tail_images)
    return result


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"success": False, "error": "单张图片不能超过 5MB"}), 413


@app.post("/upload")
def upload_image():
    """接收并校验本地图片，保存到 static/uploads。"""
    uploaded = request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return jsonify({"success": False, "error": "请选择图片"}), 400

    original_name = Path(uploaded.filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify(
            {"success": False, "error": "仅支持 jpg/png/gif/webp 图片"}
        ), 400

    data = uploaded.stream.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify(
            {"success": False, "error": "单张图片不能超过 5MB"}
        ), 413

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        return jsonify({"success": False, "error": "图片文件已损坏或格式不正确"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (UPLOAD_DIR / filename).write_bytes(data)
    return jsonify(
        {
            "success": True,
            "filename": filename,
            "original_name": original_name,
            "url": url_for("static", filename=f"uploads/{filename}"),
        }
    )


@app.delete("/upload/<filename>")
def delete_uploaded_image(filename: str):
    """删除 uploads 目录内的一张图片。"""
    if (
        Path(filename).name != filename
        or Path(filename).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS
    ):
        return jsonify({"success": False, "error": "文件名不合法"}), 400
    image_path = UPLOAD_DIR / filename
    if not image_path.is_file():
        return jsonify({"success": False, "error": "图片不存在"}), 404
    image_path.unlink()
    return jsonify({"success": True})


def image_response_items(
    rendered: dict[str, list[str]],
    cache_token: str,
) -> list[dict[str, str]]:
    """将渲染结果转换成浏览器可访问的图片描述。"""
    items: list[dict] = []
    for template_name, filenames in rendered.items():
        manifest_path = OUTPUT_DIR / template_name / "pagination.json"
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.is_file()
            else {"pages": []}
        )
        page_details = {
            page["file"]: page for page in manifest.get("pages", [])
        }
        for fallback_page, filename in enumerate(filenames, start=1):
            detail = page_details.get(filename, {})
            items.append(
                {
                    "template": template_name,
                    "filename": filename,
                    "url": url_for(
                        "output_file",
                        filename=f"{template_name}/{filename}",
                        v=cache_token,
                    ),
                    "page": int(detail.get("page", fallback_page)),
                    "block_start": int(detail.get("block_start", 0)),
                    "block_end": int(detail.get("block_end", -1)),
                }
            )
    return items


def create_zip(rendered: dict[str, list[str]]) -> Path:
    """把本轮生成的所有 PNG 打包到 output/全部图片.zip。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        ZIP_PATH,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for template_name, filenames in rendered.items():
            for filename in filenames:
                image_path = OUTPUT_DIR / template_name / filename
                archive.write(image_path, image_path.relative_to(OUTPUT_DIR))
    return ZIP_PATH


@app.get("/")
def index() -> str:
    """返回主页。"""
    return render_template(
        "index.html",
        template_text_defaults=load_template_text_configs(),
        template_style_defaults=load_template_style_configs(),
    )


@app.post("/generate")
def generate():
    """接收原始文字或调整后的内容块，生成 10 套图片。"""
    payload = request.get_json(silent=True) or {}
    content = payload.get("content")
    raw_blocks = payload.get("blocks")
    if raw_blocks is None and (not isinstance(content, str) or not content.strip()):
        return jsonify({"success": False, "error": "请输入笔记内容"}), 400

    try:
        template_overrides = validate_template_overrides(
            payload.get("template_overrides")
        )
        template_style_overrides = validate_template_style_overrides(
            payload.get("template_style_overrides")
        )
        cover_settings = validate_cover_settings(payload.get("cover_settings"))
        uploaded_images = validate_uploaded_images(payload.get("uploaded_images"))
        blocks = (
            validate_blocks(raw_blocks)
            if raw_blocks is not None
            else parse_markdown(content)
        )
        render_blocks = inject_uploaded_images(blocks, uploaded_images)
        with generation_lock:
            rendered = render_all_template_blocks(
                render_blocks,
                template_overrides,
                style_overrides=template_style_overrides,
                cover_settings=cover_settings,
            )
            create_zip(rendered)

        cache_token = str(time.time_ns())
        images = image_response_items(rendered, cache_token)
        return jsonify({"success": True, "images": images})
    except (ValueError, RuntimeError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception:
        app.logger.exception("生成图文笔记失败")
        return jsonify(
            {
                "success": False,
                "error": "生成失败，请稍后重试。如果是长文案，请拆短段落或关闭封面独立页后再试。",
            }
        ), 500


@app.post("/preview")
def preview():
    """解析文字或接收内容块，返回全部 10 套缓存预览。"""
    payload = request.get_json(silent=True) or {}
    raw_blocks = payload.get("blocks")
    content = payload.get("content")
    if raw_blocks is None and (not isinstance(content, str) or not content.strip()):
        return jsonify({"success": False, "error": "请输入笔记内容"}), 400

    try:
        template_overrides = validate_template_overrides(
            payload.get("template_overrides")
        )
        template_style_overrides = validate_template_style_overrides(
            payload.get("template_style_overrides")
        )
        cover_settings = validate_cover_settings(payload.get("cover_settings"))
        uploaded_images = validate_uploaded_images(payload.get("uploaded_images"))
        blocks = (
            validate_blocks(raw_blocks)
            if raw_blocks is not None
            else parse_markdown(content)
        )
        if not blocks:
            raise ValueError("输入内容不能为空")
        render_blocks = inject_uploaded_images(blocks, uploaded_images)

        with generation_lock:
            rendered = render_all_template_blocks(
                render_blocks,
                template_overrides,
                style_overrides=template_style_overrides,
                cover_settings=cover_settings,
            )

        cache_token = str(time.time_ns())
        return jsonify(
            {
                "success": True,
                "blocks": blocks,
                "images": image_response_items(rendered, cache_token),
            }
        )
    except (ValueError, RuntimeError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception:
        app.logger.exception("生成预览失败")
        return jsonify(
            {
                "success": False,
                "error": "预览失败，请稍后重试。如果是长文案，请拆短段落、减少图片，或先关闭封面独立页。",
            }
        ), 500


@app.post("/download")
def download():
    """使用当前编辑 blocks 渲染选中模板，并直接返回 ZIP。"""
    payload = request.get_json(silent=True) or {}
    raw_blocks = payload.get("blocks")
    selected_templates = payload.get("selected_templates")

    try:
        blocks = validate_blocks(raw_blocks)
        template_overrides = validate_template_overrides(
            payload.get("template_overrides")
        )
        template_style_overrides = validate_template_style_overrides(
            payload.get("template_style_overrides")
        )
        cover_settings = validate_cover_settings(payload.get("cover_settings"))
        uploaded_images = validate_uploaded_images(payload.get("uploaded_images"))
        render_blocks = inject_uploaded_images(blocks, uploaded_images)
        if selected_templates is not None and not isinstance(
            selected_templates,
            list,
        ):
            raise ValueError("selected_templates 必须是数组")

        with generation_lock:
            rendered = render_from_blocks(
                render_blocks,
                selected_templates,
                template_overrides,
                style_overrides=template_style_overrides,
                cover_settings=cover_settings,
            )
            zip_path = create_zip(rendered)

        download_name = (
            "选中模板图片.zip"
            if selected_templates and len(rendered) < 10
            else "全部图片.zip"
        )
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/zip",
        )
    except (ValueError, RuntimeError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception:
        app.logger.exception("生成下载 ZIP 失败")
        return jsonify(
            {
                "success": False,
                "error": "下载生成失败，请稍后重试。如果预览能成功但下载失败，请先重新生成预览再下载。",
            }
        ), 500


@app.get("/output/<path:filename>")
def output_file(filename: str):
    """提供已生成图片的只读访问。"""
    return send_from_directory(OUTPUT_DIR, filename)


@app.get("/download_zip")
def download_zip():
    """下载最近一次生成的 ZIP。"""
    if not ZIP_PATH.is_file():
        return jsonify({"success": False, "error": "请先生成图片"}), 404
    return send_file(
        ZIP_PATH,
        as_attachment=True,
        download_name="全部图片.zip",
        mimetype="application/zip",
    )


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"success": False, "error": "服务器内部错误，请稍后重试"}), 500


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"success": False, "error": "接口不存在"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
