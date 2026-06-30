#!/usr/bin/env python3
"""
add_screw_holes.py  --  Add Gridfinity Refined M15x1.5 thumbscrew holes to bins.

Uses the official "Bin Screw Hole" STL from Gridfinity Refined as the boolean
cutter, exactly as the spec intends: "There is a provided Bin Screw Hole STL
that can be used with a boolean operator in your 3D design package."

Requirements:
    pip install numpy-stl trimesh manifold3d

Usage:
    python add_screw_holes.py bin.stl bin_refined.stl
    python add_screw_holes.py bin.stl bin_refined.stl --grid 2x3
    python add_screw_holes.py bin.stl bin_refined.stl --dry-run
"""
from __future__ import annotations

import sys
import argparse
import math
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GRID_PITCH      = 42.0
CELL_CENTER_OFF = 21.0

# Official Bin Screw Hole STL properties (measured from Bin_Screw_Hole.stl)
# The STL is centred at XY=(21,21) and Z goes from -5.0122 to -0.9755
CUTTER_XY_CENTRE = 21.0   # mm - XY centre of the cutter STL
CUTTER_Z_MIN     = -5.0122  # mm - bottom of cutter in its own coordinate system

# Gridfinity Refined magnet hole constants (from standard.scad)
LAYER_HEIGHT             = 0.2    # mm
MAGNET_HOLE_RADIUS       = 6.5/2  # mm (3.25mm radius, 6.5mm diameter)
MAGNET_HOLE_DEPTH        = 2.0 + LAYER_HEIGHT*2  # = 2.4mm
REFINED_HOLE_RADIUS      = 5.86/2 # mm (2.93mm) - the round part of the slot
REFINED_HOLE_HEIGHT      = 2.0 - 0.1  # = 1.9mm
REFINED_HOLE_BOTTOM_LAYERS = 2    # layers of plastic below the magnet hole
REFINED_HOLE_OFFSET      = LAYER_HEIGHT * REFINED_HOLE_BOTTOM_LAYERS  # = 0.4mm
POKE_HOLE_RADIUS         = 2.5/2  # mm - toothpick hole for magnet removal
MAGIC_CONSTANT           = 5.60   # from the SCAD source

# Position of each magnet hole within a cell
# From standard.scad: HOLE_DISTANCE_FROM_BOTTOM_EDGE=4.8, BASE_TOP_DIMENSIONS=[41.5,41.5]
# hole_position = BASE_TOP_DIMENSIONS/2 - HOLE_DISTANCE_FROM_BOTTOM_EDGE
MAGNET_HOLE_OFFSET = 41.5/2 - 4.8  # = 15.95mm from cell centre
# 4 holes per cell, one at each corner of the foot
MAGNET_HOLE_CORNERS = [
    ( MAGNET_HOLE_OFFSET,  MAGNET_HOLE_OFFSET),
    ( MAGNET_HOLE_OFFSET, -MAGNET_HOLE_OFFSET),
    (-MAGNET_HOLE_OFFSET,  MAGNET_HOLE_OFFSET),
    (-MAGNET_HOLE_OFFSET, -MAGNET_HOLE_OFFSET),
]


# ---------------------------------------------------------------------------
# Bounding box / grid helpers
# ---------------------------------------------------------------------------

def get_bounding_box(path: Path):
    from stl import mesh as stl_mesh
    m = stl_mesh.Mesh.from_file(str(path))
    v = m.vectors.reshape(-1, 3)
    return (float(v[:,0].min()), float(v[:,1].min()), float(v[:,2].min()),
            float(v[:,0].max()), float(v[:,1].max()), float(v[:,2].max()))


def detect_grid(bb):
    xmin,ymin,zmin,xmax,ymax,zmax = bb
    cols = max(1, round((xmax-xmin) / GRID_PITCH))
    rows = max(1, round((ymax-ymin) / GRID_PITCH))
    return cols, rows


def cell_centres(cols, rows, bb):
    xmin,ymin,zmin,xmax,ymax,zmax = bb
    return [
        (xmin + CELL_CENTER_OFF + col*GRID_PITCH,
         ymin + CELL_CENTER_OFF + row*GRID_PITCH)
        for col in range(cols)
        for row in range(rows)
    ]


def find_floor_z(input_path: Path, centres) -> float:
    """
    Find the Z height at which the cutter should be placed.

    The cutter STL bottom (Z=-5.0122 in its own space) should align with the
    bin floor. After recentring to origin, the cutter bottom is at Z=0.
    We place it at floor_z so threads start at the bin floor and go upward.

    For standard Gridfinity bins, the foot is solid and the thread goes
    directly into the foot material from the bottom face.
    """
    from stl import mesh as stl_mesh
    m = stl_mesh.Mesh.from_file(str(input_path))
    verts = m.vectors.reshape(-1, 3)
    floor_z = float(verts[:,2].min())
    return floor_z


# ---------------------------------------------------------------------------
# Load and prepare the cutter STL
# ---------------------------------------------------------------------------

def load_cutter(cutter_stl_path: Path):
    """
    Load the official Bin Screw Hole STL and recentre it to origin.

    The STL is centred at XY=(21,21) with Z=-5.012..-0.975.
    After recentring:
      - XY centre moves to (0,0)
      - Z bottom moves to 0 (so placing at floor_z puts bottom at floor)
      - Z top at ~4mm (thread depth)
    """
    import trimesh

    m = trimesh.load(str(cutter_stl_path), force='mesh')

    # Recentre XY and shift Z so bottom is at 0
    m.apply_translation([-CUTTER_XY_CENTRE, -CUTTER_XY_CENTRE, -CUTTER_Z_MIN])

    v = np.array(m.vertices)
    r = np.sqrt(v[:,0]**2 + v[:,1]**2)
    print(f"  Cutter loaded: {len(m.faces)} faces, watertight={m.is_watertight}")
    print(f"  R: {r.min():.3f}..{r.max():.3f}  Z: {v[:,2].min():.3f}..{v[:,2].max():.3f}")

    return m


# ---------------------------------------------------------------------------
# Magnet hole geometry
# ---------------------------------------------------------------------------

def make_magnet_cutters_at(hx: float, hy: float, floor_z: float):
    """
    Build the Gridfinity Refined magnet hole cutter at a single hole position (hx, hy).

    From gridfinity-rebuilt-holes.scad refined_hole():
      - Circular magnet pocket: r=REFINED_HOLE_RADIUS, h=REFINED_HOLE_HEIGHT
      - Slot: 11mm x REFINED_HOLE_RADIUS*2, opens toward +X (magnet slides in)
      - Poke hole: d=2.5mm cylinder + channel for toothpick magnet removal

    All geometry sits at floor_z + REFINED_HOLE_OFFSET (0.4mm above bin floor).
    The hole position (hx, hy) is at ±15.95mm from the cell centre -- one per corner.
    """
    import trimesh
    from trimesh.creation import cylinder as make_cyl, box as make_box

    z_base = floor_z + REFINED_HOLE_OFFSET  # bottom of magnet pocket

    cutters = []

    # Circular magnet pocket
    mag_cyl = make_cyl(radius=REFINED_HOLE_RADIUS,
                       height=REFINED_HOLE_HEIGHT, sections=64)
    mag_cyl.apply_translation([hx, hy, z_base + REFINED_HOLE_HEIGHT/2])
    cutters.append(mag_cyl)

    # Magnet entry slot (11mm wide, opens toward +X from hole centre)
    slot = make_box([11.0, REFINED_HOLE_RADIUS*2, REFINED_HOLE_HEIGHT])
    slot.apply_translation([hx + 11.0/2, hy, z_base + REFINED_HOLE_HEIGHT/2])
    cutters.append(slot)

    # Poke hole: small cylinder for toothpick magnet removal
    ptl = REFINED_HOLE_OFFSET + LAYER_HEIGHT
    poke_height = REFINED_HOLE_HEIGHT + ptl
    poke_x = hx + (-12.53 + MAGIC_CONSTANT)
    poke_z = z_base - ptl

    poke_cyl = make_cyl(radius=POKE_HOLE_RADIUS, height=poke_height, sections=32)
    poke_cyl.apply_translation([poke_x, hy, poke_z + poke_height/2])
    cutters.append(poke_cyl)

    # Poke channel
    poke_box = make_box([10.0 - MAGIC_CONSTANT, POKE_HOLE_RADIUS*2, poke_height])
    poke_box.apply_translation([poke_x + (10.0-MAGIC_CONSTANT)/2,
                                hy, poke_z + poke_height/2])
    cutters.append(poke_box)

    return cutters


def make_magnet_cutters(cx: float, cy: float, floor_z: float):
    """
    Build all 4 magnet hole cutters for one cell (one per corner of the foot).
    Each corner is at ±MAGNET_HOLE_OFFSET from the cell centre.
    """
    cutters = []
    for dx, dy in MAGNET_HOLE_CORNERS:
        cutters.extend(make_magnet_cutters_at(cx + dx, cy + dy, floor_z))
    return cutters


# ---------------------------------------------------------------------------
# Main process
# ---------------------------------------------------------------------------

def process(
    input_path: Path,
    output_path: Path,
    cutter_path: Path | None,
    grid_override: tuple[int,int] | None = None,
    magnet_holes: bool = False,
    thumbscrew: bool = True,
    dry_run: bool = False,
) -> None:
    import trimesh
    import trimesh.boolean as tbool

    print("")
    print("=" * 60)
    print("  Gridfinity Refined - Add M15x1.5 Thumbscrew Holes")
    print("=" * 60)
    print(f"  Input : {input_path}")
    print(f"  Cutter: {cutter_path}")
    print(f"  Output: {output_path}")

    print("\n[1/4] Reading model ...")
    bb = get_bounding_box(input_path)
    xmin,ymin,zmin,xmax,ymax,zmax = bb
    floor_z = zmin
    print(f"  Bounding box: {xmax-xmin:.2f} x {ymax-ymin:.2f} x {zmax-zmin:.2f} mm")
    print(f"  Floor Z: {floor_z:.4f}")

    print("\n[2/4] Computing hole positions ...")
    if grid_override:
        cols, rows = grid_override
        print(f"  Grid (override): {cols} x {rows}")
    else:
        cols, rows = detect_grid(bb)
        print(f"  Grid (auto): {cols} x {rows}  "
              f"({(xmax-xmin)/GRID_PITCH:.2f} x {(ymax-ymin)/GRID_PITCH:.2f})")

    centres = cell_centres(cols, rows, bb)
    print(f"  Holes: {len(centres)}")
    for i, (cx,cy) in enumerate(centres):
        print(f"    [{i+1}] ({cx:.3f}, {cy:.3f})")

    # Validate all centres are inside the bin footprint
    for i, (cx,cy) in enumerate(centres):
        if not (xmin <= cx <= xmax and ymin <= cy <= ymax):
            print(f"  WARNING: hole {i+1} ({cx:.2f},{cy:.2f}) outside footprint!")

    if dry_run:
        print(f"\n  Cutter would be placed at floor Z={floor_z:.4f} for each centre.")
        print("  --dry-run: no output written.")
        return

    print("\n[3/4] Building cutters ...")
    cutter_template = load_cutter(cutter_path) if thumbscrew else None

    print("\n[4/4] Subtracting holes ...")
    bin_mesh = trimesh.load(str(input_path), force='mesh')
    print(f"  Bin: {len(bin_mesh.faces)} faces, watertight={bin_mesh.is_watertight}")

    vol_before = bin_mesh.volume if bin_mesh.is_watertight else -1

    cutters = []
    for i, (cx, cy) in enumerate(centres):
        if thumbscrew and cutter_template is not None:
            c = cutter_template.copy()
            c.apply_translation([cx, cy, floor_z])
            cutters.append(c)
            print(f"  Hole {i+1}: thumbscrew at ({cx:.2f}, {cy:.2f}, {floor_z:.4f})")
        if magnet_holes:
            mag_cutters = make_magnet_cutters(cx, cy, floor_z)
            cutters.extend(mag_cutters)
            print(f"  Hole {i+1}: {len(mag_cutters)} magnet cutter shapes "
                  f"at 4 corners of ({cx:.2f}, {cy:.2f})")

    print("  Running boolean difference ...", end="", flush=True)
    result = tbool.difference([bin_mesh] + cutters, engine='manifold')
    print(f" done")
    print(f"  Result: {len(result.faces)} faces, watertight={result.is_watertight}")

    if vol_before > 0 and result.is_watertight:
        removed = vol_before - result.volume
        print(f"  Volume removed: {removed:.1f} mm^3 "
              f"({removed/len(centres):.1f} mm^3 per hole)")
        if removed / len(centres) < 50:
            print("  WARNING: very little material removed per hole.")
            print("  Check that the bin has solid material in the foot at the cell centres.")

    print(f"\n  Saving to {output_path} ...")
    result.export(str(output_path))
    size_kb = output_path.stat().st_size / 1024
    print(f"\nDone! Output: {output_path}  ({size_kb:.0f} KB)\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_grid(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        cols, rows = int(w), int(h)
        if cols < 1 or rows < 1:
            raise ValueError
        return cols, rows
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(
            f"Grid must be WxH e.g. '2x3'. Got: {value!r}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add Gridfinity Refined M15x1.5 thumbscrew holes to a bin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Uses the official 'Bin Screw Hole' STL from Gridfinity Refined as the cutter.
Place Bin_Screw_Hole.stl in the same folder as this script, or use --cutter.

Requirements:
  pip install numpy-stl trimesh manifold3d

Examples:
  python add_screw_holes.py bin.stl bin_refined.stl
  python add_screw_holes.py bin.stl bin_refined.stl --grid 2x3
  python add_screw_holes.py bin.stl bin_refined.stl --dry-run
  python add_screw_holes.py bin.stl bin_refined.stl --cutter path/to/Bin_Screw_Hole.stl
""",
    )
    parser.add_argument("input",  type=Path, help="Input STL file")
    parser.add_argument("output", type=Path, help="Output STL file")
    parser.add_argument("--grid", "-g", type=parse_grid, metavar="WxH",
                        help="Grid dimensions e.g. --grid 2x3 (auto-detected if omitted)")
    parser.add_argument("--cutter", type=Path, default=None,
                        help="Path to Bin_Screw_Hole.stl (default: same folder as script)")
    parser.add_argument("--magnet-holes", "-m", action="store_true",
                        help="Add Gridfinity Refined magnet holes (side-entry, 6.5mm dia)")
    parser.add_argument("--no-thumbscrew", action="store_true",
                        help="Skip thumbscrew hole (use with --magnet-holes for magnet-only)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Print positions without writing output")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Find cutter STL
    if args.cutter:
        cutter_path = args.cutter
    else:
        cutter_path = Path(__file__).parent / "Bin_Screw_Hole.stl"

    thumbscrew = not args.no_thumbscrew
    if thumbscrew and not cutter_path.exists():
        print(f"ERROR: Cutter STL not found: {cutter_path}", file=sys.stderr)
        print("Download 'Bin Screw Hole' STL from:", file=sys.stderr)
        print("  https://www.printables.com/model/413761-gridfinity-refined", file=sys.stderr)
        print("Place Bin_Screw_Hole.stl next to this script, or use --cutter.", file=sys.stderr)
        sys.exit(1)

    if not args.magnet_holes and not thumbscrew:
        print("ERROR: Nothing to do. Use --magnet-holes and/or remove --no-thumbscrew.",
              file=sys.stderr)
        sys.exit(1)

    try:
        process(
            input_path=args.input,
            output_path=args.output,
            cutter_path=cutter_path if thumbscrew else None,
            grid_override=args.grid,
            magnet_holes=args.magnet_holes,
            thumbscrew=thumbscrew,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
