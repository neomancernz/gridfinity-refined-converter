# gridfinity-refined-holes

A Python command-line tool that adds [Gridfinity Refined](https://www.printables.com/model/413761-gridfinity-refined) features to any existing Gridfinity bin STL — without needing the original CAD source.

Supported features:

- **Thumbscrew hole** — M15×1.5 ISO metric threaded hole in the centre of each grid cell, compatible with the Gridfinity Refined thumbscrew

---

## Requirements

- Python 3.10+
- [numpy-stl](https://pypi.org/project/numpy-stl/)
- [trimesh](https://trimsh.org/)
- [manifold3d](https://github.com/elalish/manifold)

Install all dependencies with:

```bash
pip install numpy-stl trimesh manifold3d
```

For the thumbscrew hole, you also need the official **Bin Screw Hole** STL from the [Gridfinity Refined Printables page](https://www.printables.com/model/413761-gridfinity-refined). Download it and rename it to `Bin_Screw_Hole.stl`. (also available in this repo)

---

## File layout

```
add_screw_holes.py
Bin_Screw_Hole.stl        ← from Gridfinity Refined (required for thumbscrew)
```

---

## Usage

### Thumbscrew hole only (default)

```bash
python add_screw_holes.py bin.stl bin_refined.stl
```

### Override grid detection

If auto-detection gives the wrong result, specify the grid manually:

```bash
python add_screw_holes.py bin.stl bin_refined.stl --grid 3x2
```

### All options

```
positional arguments:
  input                 Input STL file
  output                Output STL file

options:
  --grid WxH, -g WxH    Grid dimensions e.g. --grid 2x3 (auto-detected if omitted)
  --cutter PATH         Path to Bin_Screw_Hole.stl if not in same folder as script
  --dry-run, -n         Print hole positions without writing output
```

---

## How it works

**Grid detection** reads the bounding box of the input STL and divides by 42mm (the Gridfinity grid pitch) to infer grid dimensions. Use `--grid` to override if needed.

**Thumbscrew hole** uses the official `Bin_Screw_Hole.stl` from Gridfinity Refined directly as a boolean cutter, exactly as the spec intends. The cutter STL is recentred to the origin and placed once per cell at the bin floor Z.

All boolean operations use [manifold3d](https://github.com/elalish/manifold), which produces guaranteed watertight manifold output.

---

## Input requirements

- Input must be an STL file
- The bin should have solid feet (standard Gridfinity bins do — the magnet holes are in the baseplate, not the bin)
- Export at any resolution; mesh quality does not affect the boolean

---

## Credits

- [grizzie17](https://www.printables.com/@grizzie17) — Gridfinity Refined design and Bin Screw Hole STL
- [Zack Freedman](https://www.youtube.com/c/ZackFreedman) — Original Gridfinity system
- [kennetek](https://github.com/kennetek/gridfinity-rebuilt-openscad) — Gridfinity Rebuilt OpenSCAD library (magnet hole geometry reference)
