"""矩阵图文笔记批量生成器命令行入口。"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from markdown_parser import parse_markdown
from renderer import PROJECT_ROOT, TEMPLATES_DIR, load_config, render_template


def discover_templates() -> list[str]:
    """发现所有同时具有 HTML 和 JSON 的模板。"""
    template_names = [
        html_path.stem
        for html_path in sorted(TEMPLATES_DIR.glob("template_*.html"))
        if html_path.with_suffix(".json").is_file()
    ]
    if len(template_names) != 10:
        raise RuntimeError(f"预期找到 10 套模板，实际找到 {len(template_names)} 套")
    return template_names


def _output_root() -> Path:
    """从 config.yaml 解析输出根目录。"""
    config = load_config()
    configured = Path(config.get("output", {}).get("directory", "output"))
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


def create_images_zip(image_paths: list[str]) -> str:
    """仅把本轮生成的 PNG 图片打包到 output/全部图片.zip。"""
    output_root = _output_root()
    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / "全部图片.zip"
    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for image_path_text in image_paths:
            image_path = Path(image_path_text)
            archive.write(image_path, image_path.relative_to(output_root))
    return str(zip_path.resolve())


def generate_images(markdown_text: str) -> tuple[list[str], str]:
    """解析 Markdown，遍历 10 套模板并打包全部图片。"""
    blocks = parse_markdown(markdown_text)
    if not blocks:
        raise ValueError("输入内容不能为空")

    image_paths: list[str] = []
    for template_name in discover_templates():
        image_paths.extend(render_template(blocks, template_name))
    zip_path = create_images_zip(image_paths)
    return image_paths, zip_path


def _read_interactive_input() -> str:
    """从终端读取多行 Markdown，以单独一行 END 结束。"""
    print("请输入 Markdown 内容，输入单独一行 END 后开始生成：")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def _read_piped_input() -> str:
    """兼容 PowerShell UTF-8 管道和 Windows GB18030 管道。"""
    data = sys.stdin.buffer.read()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError("无法识别标准输入的文字编码")


def _content_preview(markdown_text: str) -> str:
    """返回去除 Markdown 标记后的前 30 个字符。"""
    compact = " ".join(markdown_text.split())
    compact = compact.lstrip("#").strip()
    return compact[:30]


def main() -> None:
    """接收文字，生成 10 套分页图片并打包。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="用 10 套模板批量生成图文笔记")
    parser.add_argument("--text", help="直接传入 Markdown 文字")
    args = parser.parse_args()

    if args.text is not None:
        markdown_text = args.text
    elif sys.stdin.isatty():
        markdown_text = _read_interactive_input()
    else:
        markdown_text = _read_piped_input()

    image_paths, zip_path = generate_images(markdown_text)
    relative_zip = Path(zip_path).relative_to(PROJECT_ROOT).as_posix()
    print("✅ 生成完成！")
    print(f"📄 输入内容：{_content_preview(markdown_text)}...")
    print("🎨 生成套数：10 套")
    print(f"🖼️ 总图片数：{len(image_paths)} 张")
    print(f"📦 打包文件：{relative_zip}")


if __name__ == "__main__":
    main()
