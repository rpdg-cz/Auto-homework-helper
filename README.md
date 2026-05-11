# question-helper

这是一个题目截图采集与解析的本地辅助工具集合。

该仓库包含三个主要部分：

1. `web-capture-tool/web_capture.py`：从网页截图并提取可见文字。
2. `question_helper.py`：从 `input_images` 读取图片，调用 OCR 提取文字，并将结果发送给 DeepSeek 解析。
3. `run_all.py`：一个总控脚本，先调用 `web_capture.py` 生成 `input_images`，再调用 `question_helper.py` 处理图片。

## 目录结构

- `config.json`：`question_helper.py` 的主配置文件。
- `prompt.txt`：OCR 提示词。
- `deepseek_prompt.txt`：DeepSeek 解析提示词。
- `question_helper.py`：题目图片处理入口。
- `run_all.py`：集成网页截图和题目处理的控制入口。
- `input_images/`：题目截图输入目录。
- `outputs/`：`question_helper.py` 的处理结果输出目录。
- `web-capture-tool/`：网页截图工具目录。

## 运行前准备

### 1. 安装 Python

请确保已安装 Python 3.8+。

### 2. 安装 `web-capture-tool` 依赖

进入网页截图工具目录并创建虚拟环境：

```powershell
cd web-capture-tool
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. 配置 DeepSeek 和 OCR

修改根目录下的 `config.json`，确保以下字段正确填写：

- `deepseek.api_key`
- `deepseek.base_url`
- `deepseek.model`
- `siliconflow.api_key`
- `siliconflow.model`
- `ocr.prompt_file`
- `input.image_dir`

如果你使用本地 OCR，需要确认系统安装了对应的 OCR 工具，并在配置中正确设置。

## 使用说明

### 1. 只运行网页截图

进入根目录后：

```powershell
cd c:\Users\Lycro\Desktop\work\question-helper
python web-capture-tool\web_capture.py
```

可选参数：

- `--config`：指定 `web_capture.py` 使用的配置文件，默认 `web-capture-tool/config.json`
- `--site`：仅运行指定站点
- `--list-sites`：列出配置中的网站

> `web_capture.py` 在程序启动时会清空 `output_dir` 目录，确保旧截图不会影响本次采集。

### 2. 只运行题目处理

```powershell
python question_helper.py
```

可选参数：

- `--config`：指定配置文件，默认 `config.json`
- `--list-images`：列出 `input_images` 中可处理的图片
- `--image`：只处理单张图片
- `--output-dir`：覆盖配置中的输出目录

### 3. 运行总控脚本（推荐）

```powershell
python run_all.py
```

该脚本会按顺序执行：

1. 使用 `web_capture.py` 从网页截图，输出到 `input_images`。
2. 将 `input_images` 目录中的截图逐一交给 `question_helper.py` 处理。

如果需要指定配置文件或脚本路径，可使用：

```powershell
python run_all.py --web-config web-capture-tool/config.json --question-config config.json
```

## `web-capture-tool` 配置

`web-capture-tool/config.json` 示例：

```json
{
  "output_dir": "outputs",
  "sites": [
    {
      "name": "示例网页",
      "enabled": true,
      "url": "https://example.com",
      "mode": "both",
      "wait_ms": 2000,
      "headless": false,
      "selector": null
    }
  ]
}
```

字段说明：

- `name`：站点名称
- `enabled`：是否启用
- `url`：网页地址
- `mode`：`screenshot` / `text` / `both`
- `wait_ms`：额外等待时间（毫秒）
- `headless`：是否无头浏览器
- `selector`：可选 CSS 选择器，仅截取指定区域

## `question_helper.py` 输入与输出

- 输入目录：`input_images/`
- 支持图片格式：`.png`、`.jpg`、`.jpeg`、`.bmp`、`.webp`、`.tif`、`.tiff`
- 输出目录：默认 `outputs/`
- 每张图片会生成一个单独目录，包含：
  - `source-<timestamp>.<ext>`
  - `ocr-<timestamp>.txt`
  - `result-<timestamp>.md`

## 其他说明

- `run_all.py` 用于把网页截图与题目处理串联起来，适合一键运行整个流程。
- `web_capture.py` 的截图流程支持交互：每次截图后保留页面，用户可选择继续截图或关闭页面。
- `question_helper.py` 只处理本地图片，不会自动填写或提交任何网页内容。

## 联系

如果你有其他功能需求，例如自动筛选题目、支持更多网页模式或自定义输出格式，可继续拓展该项目。