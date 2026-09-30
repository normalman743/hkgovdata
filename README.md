# hkgovdata

[中文说明](README_zh.md)

Find Hong Kong government open data, check historical archive coverage, and
download resources in batches using reusable JSON plans.

## Why this project exists

I wrote this tool while studying the relationship between rainstorms and road
traffic in Hong Kong. DATA.GOV.HK provides historical downloads, including
bundles, but repeatedly searching for resources, checking available dates, and
selecting downloads across many resources and months takes time. Finding the
right dataset through the website can also require several searches.

`hkgovdata` makes that workflow repeatable:

**Search datasets → inspect resources → check coverage → write a plan → download.**

The goal is to reduce manual work. Transfer speed still depends on the archive,
network, resource sizes, and requested dates.

## Features

- Search datasets and inspect the full resource metadata.
- List archived versions, monthly/daily bundles, data dictionaries, and schemas.
- Download whole bundles, or extract selected days from monthly bundles using
  HTTP Range requests.
- Download data dictionaries and schemas alongside data.
- Preview estimated sizes and ask for confirmation before downloading.
- Skip existing outputs, report failed download tasks, and retry by rerunning
  the same plan.

## Installation

Python 3.10 or newer. From a source checkout on macOS/Linux:

```bash
git clone https://github.com/normalman743/hkgovdata.git
cd hkgovdata
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows, activate with `.venv\Scripts\activate` in Command Prompt or
`.venv\Scripts\Activate.ps1` in PowerShell. An existing Conda environment also
works. The runtime dependencies are `requests`, `tqdm`, and `urllib3`; pip installs
them automatically. The package is not currently published on PyPI.

Once installed, commands work outside the source checkout. Plan paths and `--out`
are relative to the current working directory unless you use absolute paths.

## Quick start

### 1. Find a dataset and its resource URLs

```bash
python -m hkgovdata.discover search-datasets traffic --brief
python -m hkgovdata.discover dataset hk-td-sm_4-traffic-data-strategic-major-roads
```

Search uses relevance ranking rather than literal substring matching. Try
alternative keywords if a search returns nothing. To list a provider's datasets:

```bash
python -m hkgovdata.discover search-datasets "" --provider hk-hko --brief --limit 60
```

### 2. Check what is archived

Use a **resource URL**, rather than the dataset page URL:

```bash
python -m hkgovdata.discover coverage https://rss.weather.gov.hk/rss/CurrentWeather.xml --start 2024-05-01 --end 2024-07-31 --brief
```

Or check every resource in a dataset:

```bash
python -m hkgovdata.discover coverage --dataset hk-hko-rss-current-weather-report --start 2024-05-01 --end 2024-07-31 --brief
```

Not every catalogued resource has a historical archive. An error for one resource
does not establish that another resource or language variant is archived.
Individual snapshot lists can be truncated; compare their length with
`version-count`. Use the returned bundle information when planning bundle downloads.

### 3. Create a plan, then review it

```bash
python -m hkgovdata.download add plan.json https://rss.weather.gov.hk/rss/CurrentWeather.xml --range 2024-05 2024-07
python -m hkgovdata.download show plan.json --out data/raw
```

`add` looks up coverage and fills `dictionary` and `schema` dates. Review the plan
before downloading: a listed dictionary/schema may still have a broken server
link. See the module documentation for known archive quirks.

### 4. Download

```bash
python -m hkgovdata.download run plan.json --out data/raw
```

The command previews sizes and asks for confirmation. If a download task fails,
review its error and rerun the command; completed outputs are skipped.

## Plan format

A plan is a JSON list. Each entry has one resource URL, either `dates` or `range`,
and optional `dictionary` and `schema` dates:

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

The date formats have different meanings:

- `YYYY-MM`: request the whole bundle with `time=YYYYMM01`.
- `YYYYMMDD`: request the bundle timestamp exactly as written. Copy it from
  coverage when applicable, including daily bundles in an unfinished month.
- `YYYY-MM-DD`: extract members whose archive filename starts with that day
  from the bundle at `time=YYYYMM01`, using HTTP Range requests.

An archive filename's date describes its snapshot/fetch date; it is not
necessarily the measurement date inside the data. Day extraction preserves
member names, timestamps, contents, order, and duplicate members.

For an inclusive month range, optionally exclude whole months:

```json
[
  {
    "url": "https://rss.weather.gov.hk/rss/CurrentWeather.xml",
    "range": ["2024-01", "2024-12"],
    "exclude": ["2024-02"]
  }
]
```

Do not combine `dates` and `range` in one entry. Avoid overlapping requests for
the same output. Check coverage first: plans are sent as written, without an
automatic fallback to other dates or resources. An unfinished month may not
have a monthly bundle; the tool warns and still sends the requested timestamp.

## Existing example plans

The three plans in [`examples/plans/`](examples/plans/) were used successfully
for a rainstorm/traffic research project:

```bash
python -m hkgovdata.download show examples/plans/2024_2025_main.json --out data/raw
python -m hkgovdata.download show examples/plans/2024_2025_optional.json --out data/raw
python -m hkgovdata.download show examples/plans/road_network_2024_2025.json --out data/raw
```

They include large downloads across 2024–2025. Review sizes, dates, and archive
availability before replacing `show` with `run`. They are source examples;
installation does not copy them into your working directory.

## Output and reruns

Under `--out`, outputs are organised by the resource URL's host and path:

```text
<host>/<resource-path>/
├── bundle/<timestamp>.zip
├── day/<YYYYMMDD>.zip
├── data-dictionary/<requested-date>/<filename>
└── schema/<requested-date>/<filename>
```

The resource path can include a filename, which becomes a directory here.
Dictionary/schema directories use the requested date; the downloaded filename
may identify an older version served by the archive.

Useful options for `run`:

- `--yes`: accept the preview without an interactive confirmation.
- `--overwrite`: download again even when an output exists.
- `--workers N`: set parallel Range requests for day extraction. Whole-bundle
  concurrency is controlled separately by bundle size.

Interrupted files restart from zero; there is no byte-level resume. Existing
outputs are skipped without an integrity audit. Coverage/size preview errors
can stop the command before downloads begin. Download-stage task failures are
reported at the end and produce exit status 1.

## APIs, attribution, and responsible use

The tool uses the official [Historical Archive API](https://data.gov.hk/en/help/api-spec)
and [CKAN API](https://data.gov.hk/en/help/ckan-api-development-guide).
`search-datasets` uses the website's own search endpoint, whose public developer
documentation has not been found; that endpoint may change.

As of 2026-09-30, the reviewed official documentation did not specify a numeric
request/concurrency limit. This is not a guarantee for the tool's defaults.
The download session retries selected temporary errors and rate-limit responses;
reduce concurrency or wait when the service asks you to slow down.

Downloaded data is subject to [DATA.GOV.HK's terms](https://data.gov.hk/en/terms-and-conditions)
and the relevant providers' conditions. Acknowledge the government/provider and
DATA.GOV.HK when reusing data. The [official FAQ](https://data.gov.hk/en/faq)
excludes resale of the data. Follow separate terms for third-party resources.

## Development

In an activated virtual environment:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Tests cover plan dates, ranges, invalid combinations, archive member extraction,
CRC verification, completed-file skips, and continuing after a download failure.
They use local fixtures and do not download government data.

## More help

```bash
python -m hkgovdata.discover --help
python -m hkgovdata.download --help
python -m hkgovdata.discover search-params
python -m hkgovdata.discover search-params provider
```

See [`src/hkgovdata/search_params.md`](src/hkgovdata/search_params.md) for search parameter
values, and the module docstrings for archive behaviour and implementation details.

## License

The program is licensed under [MIT](LICENSE). This license covers the program
and its documentation, not the government data downloaded with it.
