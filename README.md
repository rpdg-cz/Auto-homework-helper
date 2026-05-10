# question-helper - 副本

这是一个本地图片处理版工具，当前流程是：

1. 从 `input_images` 目录读取图片
2. 使用 SiliconFlow 视觉模型做图片转文字
3. 将 OCR 文本发送给 DeepSeek 模型继续处理
4. 把原图副本、OCR 文本和最终结果写入 `outputs`

## 目录结构

- [question_helper.py](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\question_helper.py)
- [config.json](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\config.json)
- [prompt.txt](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\prompt.txt)
- [deepseek_prompt.txt](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\deepseek_prompt.txt)
- [input_images](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\input_images)
- [outputs](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\outputs)

## 配置文件

主要配置在 [config.json](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\config.json)。

你需要填写这些字段：

- `deepseek.api_key`
- `deepseek.model`
- `siliconflow.api_key`
- `siliconflow.model`

配置说明：

- `deepseek.base_url` 默认是 `https://api.deepseek.com`
- `siliconflow.base_url` 默认是 `https://api.siliconflow.cn/v1`
- `ocr.prompt_file` 指向 OCR 提示词文件，默认是 `prompt.txt`
- `deepseek.prompt_file` 指向 DeepSeek 提示词文件，默认是 `deepseek_prompt.txt`
- `input.image_dir` 是输入图片目录，默认是 `input_images`
- `output_dir` 是输出目录，默认是 `outputs`

## 输入图片

把要处理的图片放到：

`C:\Users\Lycro\Desktop\work\question-helper - 副本\input_images`

支持格式：

- `.png`
- `.jpg`
- `.jpeg`
- `.bmp`
- `.webp`
- `.tif`
- `.tiff`

## 运行方式

进入目录：

```powershell
cd "C:\Users\Lycro\Desktop\work\question-helper - 副本"
```

如果已经有虚拟环境，推荐直接用虚拟环境里的 Python：

```powershell
.\.venv\Scripts\python.exe question_helper.py --list-images
```

处理全部图片：

```powershell
.\.venv\Scripts\python.exe question_helper.py
```

只处理一张图片：

```powershell
.\.venv\Scripts\python.exe question_helper.py --image "example.png"
```

如果要临时改输出目录：

```powershell
.\.venv\Scripts\python.exe question_helper.py --output-dir "my_outputs"
```

## 输出说明

每次正式运行前，程序都会先清空当前输出目录。

默认输出目录：

`C:\Users\Lycro\Desktop\work\question-helper - 副本\outputs`

每张图片会生成一个单独子目录，例如：

- `outputs/example/source-时间戳.png`
- `outputs/example/ocr-时间戳.txt`
- `outputs/example/result-时间戳.md`

其中：

- `source-*.png` 是原图副本
- `ocr-*.txt` 是 SiliconFlow 返回的转写文本
- `result-*.md` 是 DeepSeek 的最终输出

## 提示词文件

[prompt.txt](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\prompt.txt)

- 控制 SiliconFlow OCR 阶段的提示词

[deepseek_prompt.txt](C:\Users\Lycro\Desktop\work\question-helper%20-%20副本\deepseek_prompt.txt)

- 控制 DeepSeek 阶段的提示词

如果你想调整输出风格，优先改这两个文件，不需要直接改 Python 代码。

## 常见问题

### `No supported images found.`

说明 `input_images` 目录里还没有受支持的图片格式，或者文件扩展名不在支持列表里。

### `Please set ... api_key in config.json`

说明对应服务的 API Key 还没有填写。

### `Please set ... model in config.json`

说明对应服务的模型名还没有填写。

### 每次运行结果都没了

这是当前脚本的设计行为：每次运行前会先清空输出目录，确保只保留最新一轮结果。
