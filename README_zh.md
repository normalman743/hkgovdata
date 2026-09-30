# hkgovdata

[English](README.md)

查找香港政府开放数据、查看历史存档覆盖情况，并通过可复用的 JSON plan 批量下载。

## 为什么写这个工具

我在研究香港暴雨与道路交通的关系时写了这个程序。DATA.GOV.HK 提供历史数据下载，
也有打包文件，但当需要多个资源、多个连续月份的数据时，反复搜索、确认资源、
查看日期、逐项选择下载仍然很费时间。通过官网找到合适的数据集也可能需要尝试多次搜索。

`hkgovdata` 把这个过程变成可以重复执行的流程：

**搜索数据集 → 查看资源 → 查看 coverage → 编写 plan → 批量下载。**

主要目的就是减少手动操作。实际传输速度仍取决于官网服务、网络、文件大小和请求日期。

## 功能

- 搜索数据集，查看完整资源信息。
- 查询存档版本、月度/每日打包文件、数据字典和 schema。
- 下载完整打包文件，或通过 HTTP Range 请求从月度 ZIP 中提取指定日期。
- 同时下载数据字典和 schema。
- 下载前预览预计大小并询问确认。
- 跳过已有输出，汇总下载失败的任务；重复运行同一个 plan 可重试。

## 安装

使用 Python 3.10 或以上版本。macOS/Linux 从源码安装：

```bash
git clone https://github.com/normalman743/hkgovdata.git
cd hkgovdata
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Windows 的 Command Prompt 使用 `.venv\Scripts\activate` 激活，PowerShell 使用
`.venv\Scripts\Activate.ps1`。也可以使用已有的 Conda 环境。运行依赖只有
`requests`、`tqdm`、`urllib3`，安装时会自动获取。目前尚未发布到 PyPI。

安装后，可以离开源码目录运行命令。plan 路径和 `--out` 相对于当前工作目录，
也可以指定绝对路径。

## 快速开始

### 1. 查找数据集和资源 URL

```bash
python -m hkgovdata.discover search-datasets traffic --brief
python -m hkgovdata.discover dataset hk-td-sm_4-traffic-data-strategic-major-roads
```

搜索按相关性匹配，不是简单的子字符串搜索。没有结果时可换关键词。
也可以查看某个提供者的数据集：

```bash
python -m hkgovdata.discover search-datasets "" --provider hk-hko --brief --limit 60
```

### 2. 查看历史存档覆盖情况

这里填写的是**资源 URL**，不是数据集介绍页的 URL：

```bash
python -m hkgovdata.discover coverage https://rss.weather.gov.hk/rss/CurrentWeather.xml --start 2024-05-01 --end 2024-07-31 --brief
```

也可以查看数据集内的全部资源：

```bash
python -m hkgovdata.discover coverage --dataset hk-hko-rss-current-weather-report --start 2024-05-01 --end 2024-07-31 --brief
```

并非目录中的每个资源都有历史存档；一个资源报错，也不能推断另一资源或语言版本是否存档。
单份快照的时间戳列表可能被截断，应对照 `version-count` 判断是否完整。
下载打包文件时，使用返回的 bundle 信息来规划。

### 3. 创建并检查 plan

```bash
python -m hkgovdata.download add plan.json https://rss.weather.gov.hk/rss/CurrentWeather.xml --range 2024-05 2024-07
python -m hkgovdata.download show plan.json --out data/raw
```

`add` 会查询 coverage 并填入 `dictionary`、`schema` 日期。下载前仍应检查 plan：
官网列出的某个字典/schema 版本可能存在失效链接。模块说明记录了已遇到的存档情况。

### 4. 下载

```bash
python -m hkgovdata.download run plan.json --out data/raw
```

程序先显示大小并询问确认。下载任务失败后，查看错误并重新执行；已经完成的输出会跳过。

## plan 格式

plan 是一个 JSON 列表，每项包含一个资源 URL，使用 `dates` 或 `range` 指定时间，
可选填写 `dictionary`、`schema` 日期：

```json
[
  {
    "url": "https://resource.data.one.gov.hk/td/traffic-detectors/rawSpeedVol-all.xml",
    "dates": ["2024-05", "2025-07", "2025-08"],
    "dictionary": ["20240418"],
    "schema": []
  }
]
```

三种日期格式含义不同：

- `YYYY-MM`：请求 `time=YYYYMM01` 的完整打包文件。
- `YYYYMMDD`：原样请求该 bundle 时间戳。需要时从 coverage 复制，包括尚未结束月份的每日 bundle。
- `YYYY-MM-DD`：通过 HTTP Range，从 `time=YYYYMM01` 的打包文件中提取存档文件名以该日期开头的成员。

存档文件名中的日期是快照/抓取日期，不一定是文件内的观测日期。
按天提取会保留成员名称、时间、内容、顺序，以及重复成员。

连续月份使用包含首尾月份的 `range`，可以排除整月：

```json
[
  {
    "url": "https://rss.weather.gov.hk/rss/CurrentWeather.xml",
    "range": ["2024-01", "2024-12"],
    "exclude": ["2024-02"]
  }
]
```

同一项不能同时使用 `dates` 和 `range`。避免多个请求指向相同输出。
先查看 coverage；plan 会按原样发送，不会自动换日期或资源。
尚未结束的月份可能没有月度 bundle，程序会警告，但仍发送指定的时间戳。

## 已有示例 plan

[`examples/plans/`](examples/plans/) 中的三个 plan 曾用于暴雨与交通研究，实际下载成功：

```bash
python -m hkgovdata.download show examples/plans/2024_2025_main.json --out data/raw
python -m hkgovdata.download show examples/plans/2024_2025_optional.json --out data/raw
python -m hkgovdata.download show examples/plans/road_network_2024_2025.json --out data/raw
```

示例包含 2024–2025 年的大批量下载。把 `show` 改为 `run` 前，先确认大小、时间范围和当前存档可用性。
这些是源码示例；安装不会自动把它们复制到你的工作目录。

## 输出和重新运行

`--out` 下按资源 URL 的主机和路径组织文件：

```text
<主机>/<资源路径>/
├── bundle/<时间戳>.zip
├── day/<YYYYMMDD>.zip
├── data-dictionary/<请求日期>/<文件名>
└── schema/<请求日期>/<文件名>
```

资源路径可以包含文件名，这里会把它作为目录。字典/schema 的目录使用请求日期；
下载文件的名称可能标记官网实际返回的较早版本。

`run` 的常用参数：

- `--yes`：接受预览，跳过交互确认。
- `--overwrite`：即使输出已存在也重新下载。
- `--workers N`：指定按天提取的 Range 并发数；完整 bundle 的并发另按大小决定。

未完成的文件会从头重新下载，不支持按字节断点续传。跳过已有输出时不会检查其完整性。
coverage/大小预览报错可能在下载前终止命令；下载阶段的任务错误会在最后汇总，并返回退出码 1。

## API、出处与使用条件

工具使用官方的[历史存档 API](https://data.gov.hk/en/help/api-spec) 和
[CKAN API](https://data.gov.hk/en/help/ckan-api-development-guide)。
`search-datasets` 使用官网自身的搜索接口，目前未找到该接口的公开开发者文档；接口可能变化。

截至 2026-09-30，查阅的官方文档未明确给出请求频率或并发数量上限，
这不代表官方承诺支持工具的默认并发。下载会话会重试部分临时错误和限流响应；
服务要求降低请求速度时，应减少并发或稍后再试。

下载数据遵循 [DATA.GOV.HK 条款](https://data.gov.hk/en/terms-and-conditions)及相关提供者的使用条件。
使用数据时应注明政府/提供者和 DATA.GOV.HK 出处。
[官方 FAQ](https://data.gov.hk/en/faq) 排除了转售数据；第三方资源还须遵循其自身条款。

## 开发

在已激活的虚拟环境内运行：

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

测试覆盖 plan 日期、范围、无效组合、存档成员提取、CRC 校验、已有文件跳过，
以及下载失败后继续其他任务。测试使用本地样本，不下载政府数据。

## 更多帮助

```bash
python -m hkgovdata.discover --help
python -m hkgovdata.download --help
python -m hkgovdata.discover search-params
python -m hkgovdata.discover search-params provider
```

搜索参数值见 [`src/hkgovdata/search_params.md`](src/hkgovdata/search_params.md)，
存档行为和实现细节见模块说明。

## 许可证

程序及文档采用 [MIT License](LICENSE)，下载的政府数据仍遵循其自身使用条件。
