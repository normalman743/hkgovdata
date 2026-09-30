import io
import struct
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from hkgovdata import download


URL = "https://example.org/traffic/readings.xml"


def test_date_formats_and_documents():
    result = download.tasks({
        "url": URL,
        "dates": ["2024-05", "20240501", "2024-05-02"],
        "dictionary": ["20240418"],
        "schema": ["20240301"],
    })
    assert [(t["time"], t["day"], t["doc"]) for t in result] == [
        ("20240501", None, None),
        ("20240501", None, None),
        ("20240501", "20240502", None),
        ("20240418", None, "data-dictionary"),
        ("20240301", None, "schema"),
    ]


def test_range_crosses_year_and_excludes_month():
    result = download.tasks({
        "url": URL, "range": ["2023-11", "2024-02"], "exclude": ["2023-12"],
    })
    assert [t["time"] for t in result] == ["20231101", "20240101", "20240201"]


@pytest.mark.parametrize("entry", [
    {"url": URL, "dates": ["2024-05"], "range": ["2024-01", "2024-02"]},
    {"url": URL, "range": ["2024-02", "2024-01"]},
    {"url": URL, "dates": ["2024-02-30"]},
    {"url": URL, "dates": ["2024-05"], "exclude": ["2024-05"]},
])
def test_invalid_plans_are_rejected(entry):
    with pytest.raises(ValueError):
        download.tasks(entry)


def test_finished_output_is_skipped_without_fetching(tmp_path, monkeypatch):
    task = download.tasks({"url": URL, "dates": ["2024-05"]})[0]
    path = download.output_path(tmp_path, task)
    assert path == tmp_path / "example.org/traffic/readings.xml/bundle/20240501.zip"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"existing output")

    def unexpected_fetch(*args, **kwargs):
        pytest.fail("an existing output must not trigger a download")

    monkeypatch.setattr(download, "_download_bundle", unexpected_fetch)
    assert download._run_one(task, tmp_path, None, False, False) == ("skip", path, None)
    assert path.read_bytes() == b"existing output"


def test_failed_download_does_not_stop_next_task(tmp_path, monkeypatch):
    first, second = download.tasks({"url": URL, "dates": ["2024-05", "2024-06"]})
    attempted = []

    def fetch(task, tmp, progress, on_bytes=None):
        attempted.append(task["time"])
        if task is first:
            tmp.write_bytes(b"incomplete")
            raise OSError("simulated interrupted transfer")
        tmp.write_bytes(b"completed")
        return "downloaded"

    monkeypatch.setattr(download, "_download_bundle", fetch)
    errors = download.run([first, second], tmp_path)
    assert attempted == ["20240501", "20240601"]
    assert len(errors) == 1 and errors[0][0] is first
    first_path = download.output_path(tmp_path, first)
    assert not first_path.exists()
    assert not first_path.with_name(first_path.name + ".part").exists()
    assert download.output_path(tmp_path, second).read_bytes() == b"completed"


def make_zip(entries, method, extra=b""):
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name:", category=UserWarning)
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in entries:
                info = zipfile.ZipInfo(name, (2024, 5, 2, 8, 0, 0))
                info.extra = extra
                archive.writestr(info, data, compress_type=method)
    return buffer.getvalue()


@pytest.fixture
def remote_zip(monkeypatch):
    def mount(raw):
        monkeypatch.setattr(download, "_fetch_range", lambda url, start, stop: raw[start:stop])
        response = SimpleNamespace(
            headers={"Content-Length": str(len(raw))}, raise_for_status=lambda: None,
        )
        monkeypatch.setattr(download, "_session", lambda: SimpleNamespace(head=lambda *a, **kw: response))
        monkeypatch.setattr(download, "_resolve", lambda *a, **kw: "https://example.org/bundle.zip")
        download._members.cache_clear()
        return download._members("https://example.org/bundle.zip")
    yield mount
    download._members.cache_clear()


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_remote_zip_index_and_member_with_long_extra_field(remote_zip, method):
    payload = b"traffic readings\n" * 500
    extra = struct.pack("<HH", 0xCAFE, 4000) + b"x" * 4000
    raw = make_zip([("20240502-0800-readings.xml", payload)], method, extra)
    members = remote_zip(raw)
    assert [info.filename for info in members] == ["20240502-0800-readings.xml"]
    assert download._read_member("https://example.org/bundle.zip", members[0]) == payload


def test_crc_mismatch_is_reported(remote_zip):
    raw = bytearray(make_zip([("20240502-0800-readings.xml", b"correct payload")], zipfile.ZIP_STORED))
    header = download.LOCAL_HEADER.unpack_from(raw)
    payload_start = download.LOCAL_HEADER.size + header[-2] + header[-1]
    raw[payload_start] ^= 1
    info = remote_zip(bytes(raw))[0]
    with pytest.raises(ValueError, match="CRC mismatch"):
        download._read_member("https://example.org/bundle.zip", info)


def test_day_extraction_keeps_order_content_timestamps_and_duplicates(tmp_path, remote_zip):
    entries = [
        ("folder/20240502-0800-readings.xml", b"first"),
        ("folder/20240503-0800-readings.xml", b"different day"),
        ("folder/20240502-0800-readings.xml", b"second with duplicate name"),
        ("20240502-0900-readings.xml", b"last"),
    ]
    remote_zip(make_zip(entries, zipfile.ZIP_DEFLATED))
    task = download.tasks({"url": URL, "dates": ["2024-05-02"]})[0]
    output = tmp_path / "day.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        download._download_day(task, output, workers=2)
    expected = [entry for entry in entries if Path(entry[0]).name.startswith("20240502-")]
    with zipfile.ZipFile(output) as archive:
        assert [(info.filename, archive.read(info)) for info in archive.infolist()] == expected
        assert all(info.date_time == (2024, 5, 2, 8, 0, 0) for info in archive.infolist())


@pytest.mark.parametrize("filename,count", [
    ("2024_2025_main.json", 96),
    ("2024_2025_optional.json", 84),
    ("road_network_2024_2025.json", 29),
])
def test_existing_example_plans(filename, count):
    plan = download.load(Path(__file__).resolve().parents[1] / "examples/plans" / filename)
    tasks = [task for entry in plan for task in download.tasks(entry)]
    assert len(tasks) == count
    paths = [download.output_path(Path("data/raw"), task) for task in tasks]
    assert len(paths) == len(set(paths))
