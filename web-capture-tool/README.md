# web-capture-tool

这是一个独立的小工具，用来：

- 从 `config.json` 读取网页列表
- 打开指定网页并截图
- 提取网页当前可见文字内容

## 文件

- [web_capture.py](C:\Users\Lycro\Desktop\work\question-helper\web-capture-tool\web_capture.py)
- [config.json](C:\Users\Lycro\Desktop\work\question-helper\web-capture-tool\config.json)
- [requirements.txt](C:\Users\Lycro\Desktop\work\question-helper\web-capture-tool\requirements.txt)

## 安装

```powershell
cd C:\Users\Lycro\Desktop\work\question-helper\web-capture-tool
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## 配置文件

网页列表写在 [config.json](C:\Users\Lycro\Desktop\work\question-helper\web-capture-tool\config.json) 里。

示例：

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
- `wait_ms`：页面加载后额外等待时间
- `headless`：是否无头运行
- `selector`：可选，只截图某个区域；设为 `null` 时截整页

## 用法

列出配置里的网页：

```powershell
.\.venv\Scripts\python.exe web_capture.py --list-sites
```

运行所有启用的网页：

```powershell
.\.venv\Scripts\python.exe web_capture.py
```

只运行某一个网页：

```powershell
.\.venv\Scripts\python.exe web_capture.py --site "示例网页"
```

## 输出

默认输出到 `outputs` 目录。

每次运行某个网页时会新建一个带时间戳的目录，包含：

- `screenshot-时间戳.png`
- `text-时间戳.txt`
- `meta-时间戳.md`
