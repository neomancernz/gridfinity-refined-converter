# gridfinity-refined-converter
A tool to take gridfinity stl files and add the refined thumbscrew programmatically. This is a work in progress, so far it has been tested with a few different input files. It was coded using Claude.

Requires both add_screw_holes.py and Bin_Screw_Hole.stl in the operating directory along with the input file. The input file needs to be a functional stl file. 

Note: The thread holes do not appear in the initially loaded stl, (at least in BambuStudio) but are present once slied.

Credit: This tool uses the Grdfinity Refined spec designed by @grizzie17 that can be found here (https://www.printables.com/model/413761-gridfinity-refined) and which is an extension of the original Gridfinity spec designed by Zack Freedman (https://thangs.com/designer/ZackFreedman). It is licensed under the MIT license and you are free to remix or use as you see fit.
 
Requirements:
    pip install numpy-stl trimesh manifold3d
 
Usage:
    python add_screw_holes.py bin.stl bin_refined.stl
    python add_screw_holes.py bin.stl bin_refined.stl --grid 2x3
    python add_screw_holes.py bin.stl bin_refined.stl --dry-run
