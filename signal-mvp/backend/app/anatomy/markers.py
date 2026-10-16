from __future__ import annotations

import json
from bisect import bisect_left
import heapq
import os
import re
import struct
from functools import lru_cache
from pathlib import Path
from typing import Any


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][index] * right[index][column] for index in range(4)) for column in range(4)]
        for row in range(4)
    ]


def _local_transform(node: dict[str, Any]) -> list[list[float]]:
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = node.get("scale", [1, 1, 1])
    tx, ty, tz = node.get("translation", [0, 0, 0])
    rotation = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), tx],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), ty],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), tz],
        [0, 0, 0, 1],
    ]
    for row in range(3):
        for column, scale in enumerate((sx, sy, sz)):
            rotation[row][column] *= scale
    return rotation


def _read_model_document() -> tuple[dict[str, Any], bytes]:
    configured_path = os.getenv("ANATOMY_MODEL_PATH")
    model_path = Path(configured_path) if configured_path else (
        Path(__file__).resolve().parents[3] / "frontend" / "public" / "models" / "neutral-mannequin.glb"
    )
    raw = model_path.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError(f"Anatomy model is not a binary glTF file: {model_path}")
    json_length, chunk_type = struct.unpack_from("<I4s", raw, 12)
    if chunk_type != b"JSON":
        raise ValueError(f"Anatomy model has no JSON glTF chunk: {model_path}")
    document = json.loads(raw[20 : 20 + json_length].decode("utf-8").rstrip("\x00 \t\r\n"))
    binary_header = 20 + json_length
    binary_length, binary_type = struct.unpack_from("<I4s", raw, binary_header)
    if binary_type != b"BIN\x00":
        raise ValueError(f"Anatomy model has no binary glTF chunk: {model_path}")
    binary_start = binary_header + 8
    return document, raw[binary_start : binary_start + binary_length]


def _readable_name(name: str) -> str:
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").split()
    side = {"l": "left", "r": "right"}
    words = [side.get(word.casefold(), word) for word in words if not word.isdigit()]
    return " ".join(word.capitalize() for word in words)


def _mesh_positions(document: dict[str, Any], binary: bytes, mesh_node_index: int) -> list[tuple[float, float, float]]:
    node = document["nodes"][mesh_node_index]
    mesh = document["meshes"][node["mesh"]]
    positions: list[tuple[float, float, float]] = []
    for primitive in mesh.get("primitives", []):
        accessor = document["accessors"][primitive["attributes"]["POSITION"]]
        view = document["bufferViews"][accessor["bufferView"]]
        if accessor.get("componentType") != 5126 or accessor.get("type") != "VEC3":
            continue
        stride = view.get("byteStride", 12)
        start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        for offset in range(start, start + accessor["count"] * stride, stride):
            positions.append(struct.unpack_from("<3f", binary, offset))
    return positions


def _weighted_joint_positions(
    document: dict[str, Any], binary: bytes, mesh_node_index: int, joint_index: int
) -> list[tuple[float, float, float]]:
    """Return mesh vertices materially weighted to a skin joint."""
    mesh_node = document["nodes"][mesh_node_index]
    skin = document["skins"][mesh_node["skin"]]
    try:
        joint_slot = skin["joints"].index(joint_index)
    except (KeyError, ValueError):
        return []

    positions: list[tuple[float, float, float]] = []
    mesh = document["meshes"][mesh_node["mesh"]]
    for primitive in mesh.get("primitives", []):
        attributes = primitive.get("attributes", {})
        if not all(key in attributes for key in ("POSITION", "JOINTS_0", "WEIGHTS_0")):
            continue
        accessors = {key: document["accessors"][attributes[key]] for key in ("POSITION", "JOINTS_0", "WEIGHTS_0")}
        views = {key: document["bufferViews"][value["bufferView"]] for key, value in accessors.items()}
        starts = {
            key: views[key].get("byteOffset", 0) + accessors[key].get("byteOffset", 0)
            for key in accessors
        }
        strides = {
            "POSITION": views["POSITION"].get("byteStride", 12),
            "JOINTS_0": views["JOINTS_0"].get("byteStride", 4),
            "WEIGHTS_0": views["WEIGHTS_0"].get("byteStride", 16),
        }
        joint_format = {5121: "4B", 5123: "4H", 5125: "4I"}.get(accessors["JOINTS_0"].get("componentType"))
        weight_format = {5126: "4f", 5123: "4H", 5121: "4B"}.get(accessors["WEIGHTS_0"].get("componentType"))
        if not joint_format or not weight_format:
            continue
        for vertex in range(accessors["POSITION"]["count"]):
            joint_offset = starts["JOINTS_0"] + vertex * strides["JOINTS_0"]
            weight_offset = starts["WEIGHTS_0"] + vertex * strides["WEIGHTS_0"]
            joint_values = struct.unpack_from("<" + joint_format, binary, joint_offset)
            weight_values = struct.unpack_from("<" + weight_format, binary, weight_offset)
            joint_weight = sum(
                weight_values[index]
                for index, value in enumerate(joint_values)
                if value == joint_slot
            )
            if joint_weight < 0.2:
                continue
            position_offset = starts["POSITION"] + vertex * strides["POSITION"]
            positions.append(struct.unpack_from("<3f", binary, position_offset))
    return positions


def _position_vector(anchor: dict[str, str]) -> tuple[float, float, float]:
    return tuple(float(value.removesuffix("m")) for value in anchor["position"].split())  # type: ignore[return-value]


def _nearest_surface_points_by_xy(
    sorted_points: list[tuple[float, int, tuple[float, float, float]]],
    x_coordinates: list[float],
    x: float,
    y: float,
    limit: int = 24,
) -> list[tuple[float, float, float]]:
    """Find the exact nearest XY points without scanning the whole mesh per joint."""
    if not sorted_points or limit <= 0:
        return []
    right = bisect_left(x_coordinates, x)
    left = right - 1
    nearest: list[tuple[float, int, int, tuple[float, float, float]]] = []

    while left >= 0 or right < len(sorted_points):
        left_dx = abs(sorted_points[left][0] - x) if left >= 0 else float("inf")
        right_dx = abs(sorted_points[right][0] - x) if right < len(sorted_points) else float("inf")
        if len(nearest) == limit and min(left_dx, right_dx) ** 2 > -nearest[0][0]:
            break
        if left_dx <= right_dx:
            _point_x, index, point = sorted_points[left]
            left -= 1
        else:
            _point_x, index, point = sorted_points[right]
            right += 1
        distance_squared = (point[0] - x) ** 2 + (point[1] - y) ** 2
        entry = (-distance_squared, -index, index, point)
        if len(nearest) < limit:
            heapq.heappush(nearest, entry)
        elif (distance_squared, index) < (-nearest[0][0], -nearest[0][1]):
            heapq.heapreplace(nearest, entry)

    return [entry[3] for entry in nearest]


def _derived_anchor(
    marker_id: str,
    body_part: str,
    model_node: str,
    start: dict[str, str],
    end: dict[str, str] | None = None,
    ratio: float = 0.5,
) -> dict[str, str]:
    """Interpolate a virtual surface anchor from existing model joint anchors."""
    first = _position_vector(start)
    second = _position_vector(end or start)
    position = tuple(a + (b - a) * ratio for a, b in zip(first, second))
    return {
        "id": marker_id,
        "body_part": body_part,
        "model_node": model_node,
        "position": " ".join(f"{coordinate:.5f}m" for coordinate in position),
        "normal": "0 0 1",
        "class_name": "anatomy-callout-right",
    }


@lru_cache(maxsize=1)
def get_model_body_parts() -> tuple[dict[str, str], ...]:
    """Build marker anchors from the active GLB's named skin joints."""
    document, binary = _read_model_document()
    nodes = document.get("nodes", [])
    skins = document.get("skins", [])
    if not nodes or not skins:
        return ()

    parents: dict[int, int] = {}
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", []):
            parents[child_index] = parent_index

    world_cache: dict[int, list[list[float]]] = {}

    def world_transform(index: int) -> list[list[float]]:
        if index not in world_cache:
            local = _local_transform(nodes[index])
            parent_index = parents.get(index)
            world_cache[index] = _multiply(world_transform(parent_index), local) if parent_index is not None else local
        return world_cache[index]

    joints = dict.fromkeys(skins[0].get("joints", []))
    mesh_node_index = next(
        (index for index, node in enumerate(nodes) if node.get("skin") == 0 and "mesh" in node),
        None,
    )
    surface_positions = _mesh_positions(document, binary, mesh_node_index) if mesh_node_index is not None else []
    surface_by_x = sorted(
        ((point[0], index, point) for index, point in enumerate(surface_positions)),
        key=lambda item: (item[0], item[1]),
    )
    surface_x_coordinates = [item[0] for item in surface_by_x]
    anchors: list[dict[str, str]] = []
    for index in joints:
        name = nodes[index].get("name")
        if not name or name.casefold() == "root":
            continue
        transform = world_transform(index)
        coordinates = [transform[row][3] for row in range(3)]
        if surface_positions:
            # Bone origins are inside the body. Use their nearest front-facing
            # mesh vertices so model-viewer hotspots are attached to the skin.
            nearest_surface = _nearest_surface_points_by_xy(
                surface_by_x,
                surface_x_coordinates,
                coordinates[0],
                coordinates[1],
            )
            if nearest_surface:
                coordinates[2] = max(point[2] for point in nearest_surface) + 0.003
        marker_id = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        anchors.append({
            "id": marker_id,
            "body_part": _readable_name(name),
            "model_node": name,
            "position": " ".join(f"{coordinate:.5f}m" for coordinate in coordinates),
            "normal": "0 0 1",
            "class_name": "anatomy-callout-right",
        })

    # The active mannequin has no eye joints. Derive a virtual eye-level anchor
    # from the head-weighted mesh vertices so eye findings do not point at the
    # head joint. Its position follows the loaded model's geometry.
    head_index = next(
        (index for index, node in enumerate(nodes) if node.get("name", "").casefold() == "head"),
        None,
    )
    if mesh_node_index is not None and head_index is not None:
        head_vertices = _weighted_joint_positions(document, binary, mesh_node_index, head_index)
        if head_vertices:
            head_y = sorted(point[1] for point in head_vertices)
            eye_y = head_y[len(head_y) // 2]
            head_mid_x = (min(point[0] for point in head_vertices) + max(point[0] for point in head_vertices)) / 2
            head_half_width = (max(point[0] for point in head_vertices) - min(point[0] for point in head_vertices)) / 2
            head_height = head_y[-1] - head_y[0]
            eye_band_height = head_height * 0.025
            eye_band = [
                point for point in head_vertices
                if abs(point[1] - eye_y) <= eye_band_height
                and abs(point[0] - head_mid_x) <= head_half_width * 0.2
            ]
            if eye_band:
                eye_position = (head_mid_x, eye_y, max(point[2] for point in eye_band) + 0.003)
                anchors.append({
                    "id": "eyes",
                    "body_part": "Eyes",
                    "model_node": "eyes",
                    "position": " ".join(f"{coordinate:.5f}m" for coordinate in eye_position),
                    "normal": "0 0 1",
                    "class_name": "anatomy-callout-right",
                })

    # Add clinically useful landmarks between the mannequin's named joints.
    # These use the GLB-derived joint positions above, so their positions track
    # the active model instead of duplicating frontend coordinates.
    by_id = {anchor["id"]: anchor for anchor in anchors}
    derived_specs = [
        ("face", "Face", "head", "head", None, 0.5),
        ("chest", "Chest", "spine_02", "spine-02", None, 0.5),
        ("abdomen", "Abdomen", "spine_01", "spine-01", "pelvis", 0.55),
        ("torso", "Torso", "spine_02", "spine-02", "pelvis", 0.45),
        ("trunk", "Trunk", "spine_02", "spine-02", "pelvis", 0.45),
        ("back", "Back", "spine_02", "spine-02", None, 0.5),
    ]
    for side in ("left", "right"):
        suffix = "l" if side == "left" else "r"
        derived_specs.extend([
            (f"{side}-shoulder", f"{side.title()} shoulder", f"clavicle_{suffix}", f"clavicle-{suffix}", None, 0.5),
            (f"{side}-elbow", f"{side.title()} elbow", f"upperarm_{suffix}", f"upperarm-{suffix}", f"lowerarm-{suffix}", 0.5),
            (f"{side}-wrist", f"{side.title()} wrist", f"lowerarm_{suffix}", f"lowerarm-{suffix}", f"hand-{suffix}", 0.8),
            (f"{side}-hip", f"{side.title()} hip", "pelvis", "pelvis", f"thigh-{suffix}", 0.65),
            (f"{side}-knee", f"{side.title()} knee", f"thigh_{suffix}", f"thigh-{suffix}", f"calf-{suffix}", 0.5),
            (f"{side}-ankle", f"{side.title()} ankle", f"calf_{suffix}", f"calf-{suffix}", f"foot-{suffix}", 0.8),
        ])
    for marker_id, body_part, model_node, start_id, end_id, ratio in derived_specs:
        start = by_id.get(start_id)
        end = by_id.get(end_id) if end_id else None
        if start is not None and (end_id is None or end is not None):
            anchor = _derived_anchor(marker_id, body_part, model_node, start, end, ratio)
            anchors.append(anchor)
            by_id[marker_id] = anchor
    paired_centers = [
        ("shoulders", "Shoulders", "clavicle-l", "clavicle-r"),
        ("arms", "Arms", "upperarm-l", "upperarm-r"),
        ("elbows", "Elbows", "left-elbow", "right-elbow"),
        ("wrists", "Wrists", "left-wrist", "right-wrist"),
        ("hands", "Hands", "hand-l", "hand-r"),
        ("hips", "Hips", "left-hip", "right-hip"),
        ("thighs", "Thighs", "thigh-l", "thigh-r"),
        ("knees", "Knees", "left-knee", "right-knee"),
        ("calves", "Calves", "calf-l", "calf-r"),
        ("ankles", "Ankles", "left-ankle", "right-ankle"),
        ("feet", "Feet", "foot-l", "foot-r"),
    ]
    for marker_id, body_part, left_id, right_id in paired_centers:
        left, right = by_id.get(left_id), by_id.get(right_id)
        if left is not None and right is not None:
            anchor = _derived_anchor(marker_id, body_part, marker_id, left, right)
            anchors.append(anchor)
            by_id[marker_id] = anchor
    return tuple(anchors)


def get_model_body_part_catalog() -> list[dict[str, str]]:
    return [dict(anchor) for anchor in get_model_body_parts()]


def get_anatomy_marker_for_region(body_region: str | None) -> dict[str, str] | None:
    """Resolve an explicit clinical region to a model joint or derived landmark."""
    region = re.sub(r"[^a-z0-9]+", " ", (body_region or "").casefold()).strip()
    anchors = list(get_model_body_parts())
    if not region or not anchors:
        return None

    # Exact semantic aliases prevent e.g. chest from matching a clavicle or
    # face from landing on the neck just because those names share a substring.
    aliases = {
        "face": "face", "facial": "face", "head": "head",
        "eye": "eyes", "eyes": "eyes", "conjunctiva": "eyes",
        "neck": "neck-01", "throat": "neck-01",
        "chest": "chest", "thorax": "chest", "pectoral": "chest",
        "abdomen": "abdomen", "abdominal": "abdomen", "stomach": "abdomen",
        "belly": "abdomen", "torso": "torso", "trunk": "trunk",
        "back": "back", "spine": "back", "pelvis": "pelvis", "groin": "pelvis",
        "shoulder": "shoulders", "clavicle": "shoulders",
        "upper arm": "arms", "arm": "arms", "elbow": "elbows",
        "forearm": "arms", "lower arm": "arms", "wrist": "wrists",
        "hand": "hands", "thigh": "thighs", "upper leg": "thighs",
        "knee": "knees", "calf": "calves", "lower leg": "calves",
        "ankle": "ankles", "foot": "feet", "feet": "feet",
    }
    terms = region.split()
    for side in ("left", "right"):
        if side not in terms:
            continue
        if any(term in terms for term in ("shoulder", "clavicle")):
            target = f"{side}-shoulder"
        elif "elbow" in terms:
            target = f"{side}-elbow"
        elif any(term in terms for term in ("wrist",)):
            target = f"{side}-wrist"
        elif any(term in terms for term in ("hip",)):
            target = f"{side}-hip"
        elif any(term in terms for term in ("knee",)):
            target = f"{side}-knee"
        elif any(term in terms for term in ("ankle",)):
            target = f"{side}-ankle"
        else:
            side_suffix = "l" if side == "left" else "r"
            side_targets = (
                ("upper arm", f"upperarm-{side_suffix}"),
                ("arm", f"upperarm-{side_suffix}"),
                ("forearm", f"lowerarm-{side_suffix}"),
                ("lower arm", f"lowerarm-{side_suffix}"),
                ("hand", f"hand-{side_suffix}"),
                ("thigh", f"thigh-{side_suffix}"),
                ("upper leg", f"thigh-{side_suffix}"),
                ("calf", f"calf-{side_suffix}"),
                ("lower leg", f"calf-{side_suffix}"),
                ("foot", f"foot-{side_suffix}"),
                ("feet", f"foot-{side_suffix}"),
            )
            target = next((target for phrase, target in side_targets if phrase in region), "")
        match = next((anchor for anchor in anchors if anchor["id"] == target), None)
        if match:
            return dict(match)

    for alias, target in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", region):
            match = next((anchor for anchor in anchors if anchor["id"] == target), None)
            if match:
                return dict(match)

    # Fall back to a model node name for explicit regions such as fingers,
    # forearms, or lower legs that retain their original joint-level anchors.
    normalized = region.replace(" ", "-")
    match = next((anchor for anchor in anchors if anchor["id"] == normalized), None)
    if match:
        return dict(match)
    model_match = next((anchor for anchor in anchors if anchor["model_node"].casefold().replace("_", "-") == normalized), None)
    return dict(model_match) if model_match else None


def get_anatomy_marker(marker_id: str | None) -> dict[str, str] | None:
    anchor = next((part for part in get_model_body_parts() if part["id"] == marker_id), None)
    return dict(anchor) if anchor else None
