# gridfinity-refined-converter
A tool to take gridfinity stl files and add the refined thumbscrew programmatically. This is a work in progress, so far it has been tested with a few different input files. It was coded using Claude.

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
