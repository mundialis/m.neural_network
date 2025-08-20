#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.postprocessing_patch
# AUTHOR(S):   Lina Krisztian.

# PURPOSE:     Patches tiles resulting from neural network inference.
# COPYRIGHT:   (C) 2025 by mundialis GmbH & Co. KG and the GRASS Development
#              Team
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#############################################################################
"""
# %Module
# % description: Patches tiles resulting from neural network inference.
# % keyword: raster
# % keyword: patch
# %end

# %option G_OPT_F_INPUT
# % key: tiles_filelist
# % required: no
# % description: list of tiles, which should be patched (filename) (if not all files within tiles_path should be used)
# %end

# %option G_OPT_M_DIR
# % key: tiles_path
# % required: yes
# % description: general path to tiles
# %end

# %option
# % key: edge_cut
# % type: double
# % required: no
# % description: edge width of tiles in meter, which will be cut of before patching
# % answer: 0
# %end

# %option G_OPT_R_OUTPUT
# % key: output
# % required: yes
# % description: patched tiles output
# %end

# %flag
# % key: b
# % description: No cutting of edges at border tiles
# %end

# import needed libraries
import atexit
import os

import grass.script as grass
from grass_gis_helpers.cleanup import general_cleanup

# initialize global variables
ID = grass.tempname(12)
ORIG_REGION = None
rm_rasters = []


# cleanup function
def cleanup():
    """Cleanup fuction."""
    general_cleanup(
        orig_region=ORIG_REGION,
        rm_rasters=rm_rasters,
    )


def main():
    """r.postprocessing.patch main function."""
    global ID, ORIG_REGION, rm_rasters

    tiles_filelist = options["tiles_filelist"]
    tiles_path = options["tiles_path"]
    edge_cut = options["edge_cut"]
    output = options["output"]
    keep_border_tile_edges = flags["b"]

    # save original region
    ORIG_REGION = f"original_region_{ID}"
    grass.run_command("g.region", save=ORIG_REGION, quiet=True)

    # Read all files into a list
    if tiles_filelist:
        with open(tiles_filelist, encoding="utf-8") as file:
            tiles_list = [line.strip() for line in file]
    else:
        tiles_list = [f for f in os.listdir(tiles_path) if f.endswith(".tif")]

    grass.message(_("Importing tiles and cutting of edges ..."))
    rast_list = []
    for tiles in tiles_list:
        tiles_rast = f"{tiles.split('.')[0]}_tmp"
        rm_rasters.append(tiles_rast)
        # Import data
        grass.run_command(
            "r.import",
            input=os.path.join(tiles_path, tiles),
            output=tiles_rast,
        )
        # Cut edges
        grass.run_command(
            "g.region",
            raster=tiles_rast,
            # todo: set dest_res if given
        )
        grass.run_command(
            "g.region",
            n=f"n-{edge_cut}",
            s=f"s+{edge_cut}",
            e=f"e-{edge_cut}",
            w=f"w+{edge_cut}",
        )
        tiles_rast_cut = tiles.split(".")[0]
        rm_rasters.append(tiles_rast_cut)
        grass.run_command(
            "r.mapcalc",
            expression=f"{tiles_rast_cut} = {tiles_rast}",
        )
        rast_list.append(tiles_rast_cut)

    # Patch raster
    if not keep_border_tile_edges:
        patch_out = output
    else:
        patch_out = f"{output}_without_border_tile_edges_{ID}"
        rm_rasters.append(patch_out)
    # region to all tiles
    grass.run_command("g.region", raster=rast_list)
    grass.message(_("Patching tiles ..."))
    grass.run_command(
        "r.patch",
        input=rast_list,
        output=patch_out,
    )

    # If edges of border tiles should be kept
    if keep_border_tile_edges:
        # add width of cutted tile edges to region
        grass.run_command(
            "g.region",
            n=f"n+{edge_cut}",
            s=f"s-{edge_cut}",
            e=f"e+{edge_cut}",
            w=f"w-{edge_cut}",
        )
        tmpfile = grass.tempfile()
        # Create file for input to buildvrt, in case of many input files
        with open(tmpfile, "w", encoding="utf-8") as f:
            for rast in rast_list:
                f.write(f"{rast}_tmp\n")
        buildvrt_out = f"vrt_all_no_edges_cut_{ID}"
        rm_rasters.append(buildvrt_out)
        grass.message(_("Creating VRT without cutted edges ..."))
        grass.run_command(
            "r.buildvrt",
            file=tmpfile,
            output=buildvrt_out,
        )
        grass.message(_("Patching tiles, while keeping border edges..."))
        grass.run_command(
            "r.patch",
            input=f"{patch_out},{buildvrt_out}",
            output=output,
        )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
