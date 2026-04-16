"""Snapshot extraction helpers for GLB/GTLF files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from pygltflib import GLTF2  # type: ignore
except ImportError:  # pragma: no cover
    GLTF2 = None


@dataclass
class SnapshotRecord:
    """Represents a Snapshot defect embedded in the GLB."""

    snapshot_id: str
    label: str
    coordinates: Tuple[float, float, float]
    source_node: Optional[str]
    element: Optional[str] = None  # Extracted from mesh/node name


def _as_dict(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None

    data = obj
    if hasattr(data, "to_dict"):
        try:
            data = data.to_dict()
        except TypeError:
            data = dict(data)  # type: ignore[arg-type]

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None

    return data if isinstance(data, dict) else None


def _snapshot_from_name(name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not name or "Snapshot" not in name:
        return None
    identifier = name.split("/")[-1]
    return {"id": identifier, "label": name}


def _snapshot_from_extras(extras: Any) -> Optional[Dict[str, Any]]:
    data = _as_dict(extras)
    if not data:
        return None

    snapshot = data.get("Snapshot") or data.get("snapshot")
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except json.JSONDecodeError:
            return None

    return snapshot if isinstance(snapshot, dict) else None


def _coerce_coordinates(snapshot: Dict[str, Any], translation: Optional[Sequence[float]]) -> Optional[Tuple[float, float, float]]:
    coords = snapshot.get("coordinates") or snapshot.get("Coordinates")
    if isinstance(coords, dict):
        try:
            return (
                float(coords.get("x") or coords.get("X")),
                float(coords.get("y") or coords.get("Y")),
                float(coords.get("z") or coords.get("Z")),
            )
        except (TypeError, ValueError):
            return None

    if isinstance(coords, (list, tuple)) and len(coords) >= 3:
        try:
            return (float(coords[0]), float(coords[1]), float(coords[2]))
        except (TypeError, ValueError):
            return None

    if translation and len(translation) == 3:
        try:
            return tuple(float(axis) for axis in translation)  # type: ignore[return-value]
        except (TypeError, ValueError):
            return None

    return None


def extract_snapshots_from_nodes(nodes: Iterable[Any]) -> List[SnapshotRecord]:
    snapshots: List[SnapshotRecord] = []
    for idx, node in enumerate(nodes):
        node_name = getattr(node, "name", None)
        snapshot = _snapshot_from_extras(getattr(node, "extras", None)) or _snapshot_from_name(node_name)
        if not snapshot:
            continue

        coords = _coerce_coordinates(snapshot, getattr(node, "translation", None))
        if coords is None:
            continue

        snapshot_id = (
            snapshot.get("id")
            or snapshot.get("Id")
            or snapshot.get("ID")
            or node_name
            or f"snapshot_{idx}"
        )
        label = snapshot.get("label") or snapshot.get("description") or node_name or "Snapshot"
        
        # Extract element from node name (e.g., "IfcBuildingElementProxy/Snapshot-xxx")
        element = None
        if node_name:
            parts = node_name.split("/")
            if len(parts) >= 2:
                element = parts[0]  # e.g., "IfcBuildingElementProxy"

        snapshots.append(
            SnapshotRecord(
                snapshot_id=str(snapshot_id),
                label=str(label),
                coordinates=coords,
                source_node=node_name,
                element=element,
            )
        )

    return snapshots


def extract_snapshots(glb_file: Path | str) -> List[SnapshotRecord]:
    if GLTF2 is None:
        raise RuntimeError("pygltflib is not installed; run `pip install pygltflib`." )

    gltf = GLTF2().load(str(glb_file))
    nodes = gltf.nodes or []
    return extract_snapshots_from_nodes(nodes)
