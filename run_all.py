import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="先执行网页截图，再处理生成的图片。"
    )
    parser.add_argument(
        "--web-config",
        default="web-capture-tool/config.json",
        help="web_capture.py 的配置文件路径。",
    )
    parser.add_argument(
        "--question-config",
        default="config.json",
        help="question_helper.py 的配置文件路径。",
    )
    parser.add_argument(
        "--input-dir",
        default="input_images",
        help="question_helper.py 读取图片的输入目录。",
    )
    parser.add_argument(
        "--web-script",
        default="web-capture-tool/web_capture.py",
        help="web_capture.py 的脚本路径。",
    )
    parser.add_argument(
        "--question-script",
        default="question_helper.py",
        help="question_helper.py 的脚本路径。",
    )
    return parser.parse_args()


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", value).strip("-")
    return cleaned or "image"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"配置文件找不到：{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"配置文件 JSON 格式错误：{path}：{exc}") from exc


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def find_supported_images(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]


def build_unique_name(target_dir: Path, original_name: str) -> Path:
    target = target_dir / original_name
    if not target.exists():
        return target
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    index = 1
    while True:
        candidate = target_dir / f"{stem}-{index:02d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def copy_nested_images_to_root(root: Path) -> list[Path]:
    copied = []
    for path in sorted(find_supported_images(root)):
        if path.parent == root:
            continue
        target_name = sanitize_name(str(path.parent.name)) + "-" + path.name
        target_path = build_unique_name(root, target_name)
        shutil.copy2(path, target_path)
        copied.append(target_path)
    return copied


def run_web_capture(web_script: Path, web_config: Path, input_dir: Path) -> None:
    config_data = load_json(web_config)
    config_data["output_dir"] = str(input_dir.resolve())

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = Path(temp_dir) / "web_capture_temp_config.json"
        write_json(temp_config_path, config_data)

        print("开始执行 web_capture.py，将截图输出到：", input_dir)
        result = subprocess.run(
            [sys.executable, str(web_script), "--config", str(temp_config_path)],
            cwd=web_script.parent,
        )
        if result.returncode != 0:
            raise RuntimeError(f"web_capture.py 运行失败，退出码：{result.returncode}")


def run_question_helper(question_script: Path, question_config: Path) -> None:
    print("开始执行 question_helper.py 处理图片。")
    result = subprocess.run(
        [sys.executable, str(question_script), "--config", str(question_config)],
        cwd=question_script.parent,
    )
    if result.returncode != 0:
        raise RuntimeError(f"question_helper.py 运行失败，退出码：{result.returncode}")


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent
    web_script = (workspace / args.web_script).resolve()
    question_script = (workspace / args.question_script).resolve()
    web_config = (workspace / args.web_config).resolve()
    question_config = (workspace / args.question_config).resolve()
    input_dir = (workspace / args.input_dir).resolve()
    input_dir.mkdir(parents=True, exist_ok=True)

    if not web_script.exists():
        print(f"找不到 web_capture 脚本：{web_script}", file=sys.stderr)
        return 1
    if not question_script.exists():
        print(f"找不到 question_helper 脚本：{question_script}", file=sys.stderr)
        return 1
    if not web_config.exists():
        print(f"找不到 web_capture 配置：{web_config}", file=sys.stderr)
        return 1
    if not question_config.exists():
        print(f"找不到 question_helper 配置：{question_config}", file=sys.stderr)
        return 1

    try:
        run_web_capture(web_script, web_config, input_dir)
        copied = copy_nested_images_to_root(input_dir)
        if copied:
            print("已将嵌套目录中的截图复制到 input_images 根目录：")
            for path in copied:
                print(f"- {path.name}")
        else:
            print("未发现嵌套目录中的截图需要复制。")

        run_question_helper(question_script, question_config)
        print("全部完成。")
        return 0
    except Exception as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
