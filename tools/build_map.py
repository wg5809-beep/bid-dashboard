"""TopoJSON(시도) → web/assets/korea-sido.svg 변환 (1회성 도구, 외부 의존성 없음).

출처: https://github.com/southkorea/southkorea-maps (kostat/2018/json/skorea-provinces-2018-topo-simple.json)
사용: python tools/build_map.py --out web/assets/korea-sido.svg [--topo <local json>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector.rules.region import REGIONS, UNCLASSIFIED  # noqa: E402

SOURCE_URL = ("https://raw.githubusercontent.com/southkorea/southkorea-maps/master/"
              "kostat/2018/json/skorea-provinces-2018-topo-simple.json")
# KOSTAT 2018 영문명 → 대시보드 지역 (광주·전남은 전남광주로 병합)
ENG_TO_REGION = {
    "Seoul": "서울", "Busan": "부산", "Daegu": "대구", "Incheon": "인천", "Gwangju": "전남광주",
    "Daejeon": "대전", "Ulsan": "울산", "Sejongsi": "세종", "Gyeonggi-do": "경기", "Gangwon-do": "강원",
    "Chungcheongbuk-do": "충북", "Chungcheongnam-do": "충남", "Jeollabuk-do": "전북",
    "Jeollanam-do": "전남광주", "Gyeongsangbuk-do": "경북", "Gyeongsangnam-do": "경남", "Jeju-do": "제주",
}
LAT_MID_DEG = 36.0


def _decode_arcs(topo: dict) -> list[list[tuple[float, float]]]:
    transform = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        points, x, y = [], 0.0, 0.0
        for dx, dy in arc:
            x, y = x + dx, y + dy
            if transform:
                sx, sy = transform["scale"]
                tx, ty = transform["translate"]
                points.append((x * sx + tx, y * sy + ty))
            else:
                points.append((x, y))
        arcs.append(points)
    return arcs


def _ring(arc_indexes: list[int], arcs) -> list[tuple[float, float]]:
    ring: list[tuple[float, float]] = []
    for idx in arc_indexes:
        pts = arcs[idx] if idx >= 0 else list(reversed(arcs[~idx]))
        ring.extend(pts if not ring else pts[1:])
    return ring


def _rings(geom: dict, arcs) -> list[list[tuple[float, float]]]:
    if geom["type"] == "Polygon":
        return [_ring(r, arcs) for r in geom["arcs"]]
    if geom["type"] == "MultiPolygon":
        return [_ring(r, arcs) for poly in geom["arcs"] for r in poly]
    return []


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else str(int(round(v)))


def _thin(pts: list[tuple[float, float]], min_step: float) -> list[tuple[float, float]]:
    """투영 후 min_step 미만으로 붙어 있는 점을 건너뛴다(마지막 점은 유지)."""
    if min_step <= 0 or len(pts) < 4:
        return pts
    kept = [pts[0]]
    for p in pts[1:-1]:
        if math.dist(kept[-1], p) >= min_step:
            kept.append(p)
    kept.append(pts[-1])
    return kept


def _path_d(rings, project, min_step: float = 0.0) -> str:
    parts = []
    for ring in rings:
        pts = _thin([project(x, y) for x, y in ring], min_step)
        parts.append("M" + " L".join(f"{_fmt(x)},{_fmt(y)}" for x, y in pts) + " Z")
    return " ".join(parts)


def topo_to_paths(topo: dict, name_key: str = "name_eng", project=None, min_step: float = 0.0) -> list[tuple[str, str]]:
    """TopoJSON의 첫 객체를 (이름, SVG path d) 목록으로. project=None이면 좌표를 그대로 쓴다."""
    arcs = _decode_arcs(topo)
    obj = next(iter(topo["objects"].values()))
    project = project or (lambda x, y: (x, y))
    return [
        (geom.get("properties", {}).get(name_key, ""), _path_d(_rings(geom, arcs), project, min_step))
        for geom in obj["geometries"]
    ]


def merge_regions(paths: list[tuple[str, str]], mapping: dict[str, str]) -> list[tuple[str, str]]:
    merged: dict[str, list[str]] = {}
    for name, d in paths:
        region = mapping.get(name)
        if region:
            merged.setdefault(region, []).append(d)
    return [(region, " ".join(ds)) for region, ds in merged.items()]


LABEL_NUDGE = {"경기": (18, 42), "인천": (-30, 10)}  # 서울을 감싸는 경기·인천 라벨이 서울과 겹치지 않도록


def _bbox(d: str) -> tuple[float, float, float, float]:
    coords = [tuple(map(float, token.split(","))) for token in d.replace("M", " ").replace("L", " ").replace("Z", " ").split()]
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def label_point(name: str, d: str) -> tuple[float, float]:
    """가장 큰(bbox 면적) 링의 중심. 섬이 많은 지역의 라벨이 바다에 찍히지 않게 한다."""
    rings = [r for r in d.split("M") if r.strip()]
    boxes = [_bbox("M" + r) for r in rings]
    x0, y0, x1, y1 = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    dx, dy = LABEL_NUDGE.get(name, (0, 0))
    return (x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy


def write_svg(paths: list[tuple[str, str]], out: Path, viewbox: str, source: str = SOURCE_URL) -> None:
    vb = [float(v) for v in viewbox.split()]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="img" aria-label="대한민국 시도 지도">',
        f"<!-- 출처: {source} (KOSTAT 2018 행정구역, 광주·전남은 전남광주로 병합) -->",
        "<g id=\"regions\">",
    ]
    for i, (name, d) in enumerate(paths):
        lines.append(f'<path id="r-{i}" data-region="{name}" d="{d}"/>')
    lines.append("</g><g id=\"labels\">")
    for name, d in paths:
        x, y = label_point(name, d)
        lines.append(f'<text x="{_fmt(x)}" y="{_fmt(y)}" text-anchor="middle">{name}</text>')
    w, h = vb[2], vb[3]
    rx, ry, rw, rh = vb[0] + w * 0.74, vb[1] + h * 0.88, w * 0.24, h * 0.09
    lines.append(f'<rect id="r-unclassified" data-region="{UNCLASSIFIED}" x="{_fmt(rx)}" y="{_fmt(ry)}" width="{_fmt(rw)}" height="{_fmt(rh)}" rx="6"/>')
    lines.append(f'<text x="{_fmt(rx + rw / 2)}" y="{_fmt(ry + rh * 0.62)}" text-anchor="middle">전국/{UNCLASSIFIED}</text>')
    lines.append("</g></svg>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _load_topo(path: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as resp:  # noqa: S310 - 고정된 공개 URL
        return json.loads(resp.read().decode("utf-8"))


def build(topo: dict, out: Path, width: float = 600.0) -> None:
    lon0, lat0, lon1, lat1 = topo["bbox"]
    kx = math.cos(math.radians(LAT_MID_DEG))
    scale = width / ((lon1 - lon0) * kx)
    height = (lat1 - lat0) * scale

    def project(lon, lat):
        return (lon - lon0) * kx * scale, (lat1 - lat) * scale

    paths = merge_regions(topo_to_paths(topo, "name_eng", project, min_step=0.7), ENG_TO_REGION)
    missing = set(REGIONS) - {name for name, _ in paths}
    if missing:
        raise RuntimeError(f"지도에 빠진 지역: {missing}")
    write_svg(paths, out, f"0 0 {_fmt(width)} {_fmt(height)}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="web/assets/korea-sido.svg")
    parser.add_argument("--topo", default=None, help="로컬 TopoJSON 경로(없으면 다운로드)")
    args = parser.parse_args(argv)
    build(_load_topo(args.topo), Path(args.out))
    print(f"wrote {args.out} ({Path(args.out).stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
