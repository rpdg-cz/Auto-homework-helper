import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 JSON 配置读取网页列表，保存截图或提取页面文字内容。"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="配置文件路径，默认 config.json",
    )
    parser.add_argument(
        "--site",
        default=None,
        help="只运行指定站点名称；不传则运行所有 enabled=true 的站点",
    )
    parser.add_argument(
        "--list-sites",
        action="store_true",
        help="只列出配置里的站点，不执行采集",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise RuntimeError(f"找不到配置文件：{config_path}")
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"配置文件 JSON 格式错误：{exc}") from exc


def get_sites(config: dict) -> list[dict]:
    sites = config.get("sites")
    if not isinstance(sites, list):
        raise RuntimeError("配置文件缺少 sites 列表。")
    return sites


def clear_output_directory(output_root: Path) -> None:
    if output_root.exists() and output_root.is_dir():
        for child in output_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", value).strip("-")
    return cleaned or "page"


def build_paths(output_root: Path, site_name: str) -> dict[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = output_root / f"{sanitize_name(site_name)}-{timestamp}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": target_dir,
        "text": target_dir / f"text-{timestamp}.txt",
        "meta": target_dir / f"meta-{timestamp}.md",
    }


def extract_visible_text(page) -> str:
    text = page.evaluate(
        """
        () => {
            const text = document.body ? document.body.innerText : "";
            return text.replace(/\\n{3,}/g, "\\n\\n").trim();
        }
        """
    )
    if not text:
        raise RuntimeError("未提取到可见文字内容。")
    return text


def prompt_screenshot_decision() -> bool:
    while True:
        choice = input(
            "是否对当前页面截图？输入 y 继续截图，输入 N 关闭网页并继续下一个页面："
        ).strip().lower()
        if choice == "y":
            return True
        if choice == "n":
            return False
        print("请输入 y 或 N。")


def capture_page(
    site: dict,
    output_root: Path,
) -> dict[str, Path]:
    site_name = site["name"]
    url = site["url"]
    mode = site.get("mode", "both")
    wait_ms = int(site.get("wait_ms", 2000))
    headless = bool(site.get("headless", False))
    selector = site.get("selector")

    paths = build_paths(output_root, site_name)
    screenshot_files: list[Path] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            if wait_ms > 0:
                page.wait_for_timeout(wait_ms)

            print(
                f"\n浏览器已打开：{site_name}"
                "\n请确认页面内容已加载完成。"
            )

            if mode in {"screenshot", "both"}:
                if prompt_screenshot_decision():
                    screenshot_index = 0
                    while True:
                        screenshot_index += 1
                        screenshot_path = (
                            paths["dir"] / f"screenshot-{screenshot_index:02d}.png"
                        )
                        if selector:
                            locator = page.locator(selector).first
                            locator.wait_for(state="visible", timeout=30_000)
                            locator.screenshot(path=str(screenshot_path))
                        else:
                            page.screenshot(path=str(screenshot_path), full_page=True)
                        screenshot_files.append(screenshot_path)
                        print(
                            f"截图已保存：{screenshot_path}\n"
                            "页面保持打开。请在页面上完成后续操作，"
                            "然后选择 y 继续截图，或选择 N 关闭网页并继续下一个页面。"
                        )
                        if not prompt_screenshot_decision():
                            break
                else:
                    print("用户选择不截图，关闭当前网页并继续下一个页面。")

            if mode in {"text", "both"}:
                text = extract_visible_text(page)
                paths["text"].write_text(text, encoding="utf-8")

            meta_lines = [
                "# 网页采集结果",
                "",
                f"- 站点：{site_name}",
                f"- URL：{url}",
                f"- 模式：{mode}",
                f"- 截图区域：`{selector or 'full_page'}`",
                f"- 采集时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
            ]
            if screenshot_files:
                screenshot_list = [f"- {file.name}" for file in screenshot_files]
                meta_lines.append("- 截图文件：")
                meta_lines.extend(screenshot_list)
            paths["meta"].write_text("\n".join(meta_lines), encoding="utf-8")

            return {**paths, "screenshots": screenshot_files}
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"页面等待超时：{exc}") from exc
        finally:
            browser.close()


def validate_site(site: dict) -> None:
    for key in ("name", "url"):
        value = site.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"站点配置缺少必填字段：{key}")

    mode = site.get("mode", "both")
    if mode not in {"screenshot", "text", "both"}:
        raise RuntimeError(f"站点 {site.get('name', '<未命名>')} 的 mode 无效：{mode}")


def resolve_sites(sites: list[dict], site_name: str | None) -> list[dict]:
    if site_name:
        matched = [site for site in sites if site.get("name") == site_name]
        if not matched:
            raise RuntimeError(f"配置中不存在站点：{site_name}")
        return matched

    enabled_sites = [site for site in sites if site.get("enabled", True)]
    if not enabled_sites:
        raise RuntimeError("没有可运行的站点。请在 config.json 中添加并启用网页。")
    return enabled_sites


def list_sites(sites: list[dict]) -> None:
    if not sites:
        print("配置中还没有站点。")
        return

    print("配置中的站点：")
    for site in sites:
        name = site.get("name", "<未命名>")
        mode = site.get("mode", "both")
        enabled = site.get("enabled", True)
        marker = "enabled" if enabled else "disabled"
        print(f"- {name} [{marker}] mode={mode}")


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
        sites = get_sites(config)

        if args.list_sites:
            list_sites(sites)
            return 0

        output_dir_value = config.get("output_dir", "outputs")
        output_root = Path(output_dir_value)
        if not output_root.is_absolute():
            output_root = config_path.parent / output_root
        output_root.mkdir(parents=True, exist_ok=True)
        clear_output_directory(output_root)

        selected_sites = resolve_sites(sites, args.site)
        for site in selected_sites:
            validate_site(site)
            try:
                paths = capture_page(site, output_root)
            except RuntimeError as exc:
                if str(exc) == "用户取消了本次采集。":
                    print(f"\n已取消：{site['name']}")
                    continue
                raise
            print("\n完成。")
            print(f"输出目录：{paths['dir']}")
            if site.get('mode', 'both') in {'screenshot', 'both'}:
                if paths.get('screenshots'):
                    print(f"截图文件：{', '.join(str(p.name) for p in paths['screenshots'])}")
                else:
                    print("截图文件：无")
            if site.get('mode', 'both') in {'text', 'both'}:
                print(f"文字文件：{paths['text']}")
            print(f"说明文件：{paths['meta']}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
