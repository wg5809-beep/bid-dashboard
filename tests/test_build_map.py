import re
from pathlib import Path

from tools.build_map import merge_regions, topo_to_paths, write_svg

# 손으로 만든 TopoJSON: 두 폴리곤이 arc 1개를 공유한다. transform(scale/translate) + delta 인코딩.
TOPO = {
    "type": "Topology",
    "transform": {"scale": [1, 1], "translate": [10, 20]},
    "arcs": [
        [[0, 0], [2, 0], [0, 2]],      # arc0: (10,20)→(12,20)→(12,22)
        [[2, 2], [-2, 0]],             # arc1: (12,22)→(10,22)
        [[2, 0], [2, 0], [0, 2], [-2, 0]],  # arc2: (12,20)→(14,20)→(14,22)→(12,22)
    ],
    "objects": {
        "p": {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Polygon", "arcs": [[0, 1]], "properties": {"name": "광주광역시"}},
                {"type": "Polygon", "arcs": [[2, -1]], "properties": {"name": "전라남도"}},
            ],
        }
    },
}


def test_topo_to_paths_decodes_small_synthetic_topology():
    paths = topo_to_paths(TOPO, name_key="name")
    assert [name for name, _ in paths] == ["광주광역시", "전라남도"]
    d0 = paths[0][1]
    assert d0.startswith("M10,20") or d0.startswith("M10.0,20.0")
    assert "12,22" in d0.replace(".0", "") and d0.strip().endswith("Z")
    # 공유 arc를 반대로 쓴 두 번째 폴리곤도 닫힌 경로
    assert paths[1][1].strip().endswith("Z")


def test_merge_regions_joins_gwangju_and_jeonnam():
    paths = [("광주광역시", "M0,0 L1,0 Z"), ("전라남도", "M5,5 L6,5 Z"), ("경기도", "M9,9 Z")]
    merged = merge_regions(paths, {"광주광역시": "전남광주", "전라남도": "전남광주", "경기도": "경기"})
    assert merged == [("전남광주", "M0,0 L1,0 Z M5,5 L6,5 Z"), ("경기", "M9,9 Z")]


def test_write_svg_has_16_regions_plus_unclassified(tmp_path: Path):
    from collector.rules.region import REGIONS
    paths = [(r, f"M{i},0 L{i + 1},0 L{i + 1},1 Z") for i, r in enumerate(REGIONS)]
    out = tmp_path / "map.svg"
    write_svg(paths, out, viewbox="0 0 20 10", source="https://example.org/topo")
    svg = out.read_text(encoding="utf-8")
    regions = re.findall(r'data-region="([^"]+)"', svg)
    assert sorted(regions) == sorted([*REGIONS, "미분류"])
    assert svg.count('data-region="전남광주"') == 1
    assert "https://example.org/topo" in svg and 'viewBox="0 0 20 10"' in svg


def test_topo_to_paths_min_step_drops_close_points():
    dense = {
        "type": "Topology",
        "arcs": [[[0, 0], [0.2, 0], [0.2, 0], [5, 0], [0, 5], [-5.4, 0]]],
        "objects": {"p": {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "arcs": [[0]], "properties": {"name": "x"}}]}},
    }
    full = topo_to_paths(dense, name_key="name")[0][1]
    thin = topo_to_paths(dense, name_key="name", min_step=1.0)[0][1]
    assert full.count("L") == 5 and thin.count("L") == 3


def test_label_point_uses_largest_ring():
    from tools.build_map import label_point
    d = "M0,0 L1,0 L1,1 L0,1 Z M10,10 L20,10 L20,20 L10,20 Z"
    assert label_point("x", d) == (15.0, 15.0)
