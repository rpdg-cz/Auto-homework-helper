import argparse
import base64
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


DEFAULT_PROMPT_FILE = "prompt.txt"
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read local images from a folder, run OCR, then send text to DeepSeek."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the JSON config file. Default: config.json",
    )
    parser.add_argument(
        "--list-images",
        action="store_true",
        help="List supported images in the configured folder without processing them.",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Process only one image file name from the configured folder.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the output directory from config.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in config file: {exc}") from exc


def get_required_section(config: dict, key: str) -> dict:
    value = config.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"Missing required object in config: {key}")
    return value


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", name).strip("-")
    return cleaned or "image"


def load_prompt_file(path_value: str, config_path: Path) -> str:
    prompt_path = Path(path_value)
    if not prompt_path.is_absolute():
        prompt_path = config_path.parent / prompt_path

    if not prompt_path.exists():
        raise RuntimeError(f"Prompt file not found: {prompt_path}")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise RuntimeError(f"Prompt file is empty: {prompt_path}")
    return prompt


def load_ocr_prompt(config_path: Path, ocr_config: dict) -> str:
    prompt_file = str(ocr_config.get("prompt_file", DEFAULT_PROMPT_FILE)).strip() or DEFAULT_PROMPT_FILE
    prompt_path = Path(prompt_file)
    if not prompt_path.is_absolute():
        prompt_path = config_path.parent / prompt_path
    if not prompt_path.exists():
        raise RuntimeError(f"OCR prompt file not found: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise RuntimeError(f"OCR prompt file is empty: {prompt_path}")
    return prompt


def load_deepseek_prompt(config_path: Path, deepseek_config: dict) -> str:
    prompt_file = str(deepseek_config.get("prompt_file", "deepseek_prompt.txt")).strip() or "deepseek_prompt.txt"
    prompt_path = Path(prompt_file)
    if not prompt_path.is_absolute():
        prompt_path = config_path.parent / prompt_path
    if not prompt_path.exists():
        raise RuntimeError(f"DeepSeek prompt file not found: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise RuntimeError(f"DeepSeek prompt file is empty: {prompt_path}")
    return prompt


def resolve_input_dir(input_config: dict, config_path: Path) -> Path:
    image_dir_value = str(input_config.get("image_dir", "")).strip()
    if not image_dir_value:
        raise RuntimeError("Please set input.image_dir in config.json.")

    image_dir = Path(image_dir_value)
    if not image_dir.is_absolute():
        image_dir = config_path.parent / image_dir

    if not image_dir.exists():
        raise RuntimeError(f"Input image folder does not exist: {image_dir}")
    if not image_dir.is_dir():
        raise RuntimeError(f"Input image path is not a folder: {image_dir}")

    return image_dir


def list_image_files(image_dir: Path) -> list[Path]:
    files = [
        path for path in sorted(image_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]
    return files


def select_images(image_files: list[Path], image_name: str | None) -> list[Path]:
    if image_name:
        selected = [path for path in image_files if path.name == image_name]
        if not selected:
            raise RuntimeError(f"Image not found in configured folder: {image_name}")
        return selected

    if not image_files:
        raise RuntimeError("No supported image files found in the configured folder.")
    return image_files


def encode_image_as_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def call_siliconflow_ocr(
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    image_path: Path,
    detail: str,
) -> str:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": encode_image_as_data_url(image_path),
                            "detail": detail,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
        "stream": False,
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SiliconFlow API request failed: HTTP {exc.code}, response: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"SiliconFlow API network request failed: {exc}") from exc

    try:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to parse SiliconFlow response: {body}") from exc

    if not content:
        raise RuntimeError("SiliconFlow returned empty content.")
    return content.strip()


def call_deepseek(
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    ocr_text: str,
) -> str:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a careful and concise Chinese study assistant."},
            {"role": "user", "content": f"{prompt}\n\nOCR 提取文本如下：\n{ocr_text}"},
        ],
        "stream": False,
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API request failed: HTTP {exc.code}, response: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek API network request failed: {exc}") from exc

    try:
        result = json.loads(body)
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to parse DeepSeek response: {body}") from exc

    if not content:
        raise RuntimeError("DeepSeek returned empty content.")
    return content.strip()


def save_result(
    result_path: Path,
    image_name: str,
    metadata: dict[str, str],
    ocr_text: str,
    content: str,
) -> None:
    lines = [
        "# Result",
        "",
        f"- Image: {image_name}",
        f"- Time: {metadata['timestamp']}",
        f"- Source path: {metadata['source_path']}",
        f"- DeepSeek Model: `{metadata['deepseek_model']}`",
        f"- OCR Model: `{metadata['ocr_model']}`",
        "",
        "## OCR Text",
        "",
        "```text",
        ocr_text,
        "```",
        "",
        "## DeepSeek Output",
        "",
        content,
        "",
    ]
    result_path.write_text("\n".join(lines), encoding="utf-8")


def process_image(
    image_path: Path,
    deepseek_config: dict,
    siliconflow_config: dict,
    ocr_config: dict,
    ocr_prompt: str,
    deepseek_prompt: str,
    output_root: Path,
) -> None:
    deepseek_model = deepseek_config.get("model", "deepseek-v4-flash")
    deepseek_base_url = deepseek_config.get("base_url", "https://api.deepseek.com")
    deepseek_api_key = str(deepseek_config.get("api_key", "")).strip()
    if not deepseek_api_key:
        raise RuntimeError("Please set deepseek.api_key in config.json.")

    siliconflow_api_key = str(siliconflow_config.get("api_key", "")).strip()
    siliconflow_model = str(siliconflow_config.get("model", "")).strip()
    siliconflow_base_url = str(siliconflow_config.get("base_url", "https://api.siliconflow.cn/v1")).strip()
    detail = str(ocr_config.get("detail", "high")).strip() or "high"

    if not siliconflow_api_key:
        raise RuntimeError("Please set siliconflow.api_key in config.json.")
    if not siliconflow_model:
        raise RuntimeError("Please set siliconflow.model in config.json.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    image_stem = sanitize_name(image_path.stem)
    image_dir = output_root / image_stem
    image_dir.mkdir(parents=True, exist_ok=True)

    copied_image_path = image_dir / f"source-{timestamp}{image_path.suffix.lower()}"
    copied_image_path.write_bytes(image_path.read_bytes())
    ocr_path = image_dir / f"ocr-{timestamp}.txt"
    result_path = image_dir / f"result-{timestamp}.md"

    print(f"\n===== Processing: {image_path.name} =====")
    print(f"1/3 Running OCR with SiliconFlow model: {siliconflow_model} ...")
    ocr_text = call_siliconflow_ocr(
        api_key=siliconflow_api_key,
        base_url=siliconflow_base_url,
        model=siliconflow_model,
        prompt=ocr_prompt,
        image_path=image_path,
        detail=detail,
    )
    ocr_path.write_text(ocr_text, encoding="utf-8")

    print(f"2/3 Calling DeepSeek model {deepseek_model} ...")
    result = call_deepseek(
        api_key=deepseek_api_key,
        base_url=deepseek_base_url,
        model=deepseek_model,
        prompt=deepseek_prompt,
        ocr_text=ocr_text,
    )

    metadata = {
        "timestamp": timestamp,
        "source_path": str(image_path),
        "deepseek_model": deepseek_model,
        "ocr_model": siliconflow_model,
    }
    save_result(result_path, image_path.name, metadata, ocr_text, result)

    print("3/3 Done.")
    print(f"Copied image: {copied_image_path}")
    print(f"OCR text file: {ocr_path}")
    print(f"Result file: {result_path}")


def clear_output_dir(output_root: Path, config_path: Path) -> None:
    if output_root.exists():
        config_dir = config_path.parent.resolve()
        output_resolved = output_root.resolve()
        if output_resolved == config_dir or config_dir not in output_resolved.parents:
            raise RuntimeError(f"Refusing to clear unsafe output directory: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)


def print_images(image_files: list[Path]) -> None:
    if not image_files:
        print("No supported images found.")
        return

    print("Configured image folder contents:")
    for path in image_files:
        print(f"- {path.name}")


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
        deepseek_config = get_required_section(config, "deepseek")
        siliconflow_config = get_required_section(config, "siliconflow")
        ocr_config = get_required_section(config, "ocr")
        input_config = get_required_section(config, "input")

        ocr_prompt = load_ocr_prompt(config_path, ocr_config)
        deepseek_prompt = load_deepseek_prompt(config_path, deepseek_config)
        image_dir = resolve_input_dir(input_config, config_path)
        image_files = list_image_files(image_dir)

        if args.list_images:
            print_images(image_files)
            return 0

        output_dir_value = args.output_dir or config.get("output_dir") or "outputs"
        output_root = Path(output_dir_value)
        if not output_root.is_absolute():
            output_root = config_path.parent / output_root

        clear_output_dir(output_root, config_path)

        selected_images = select_images(image_files, args.image)
        for image_path in selected_images:
            process_image(image_path, deepseek_config, siliconflow_config, ocr_config, ocr_prompt, deepseek_prompt, output_root)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
