#!/usr/bin/env python3
"""
############################################################################
#
# MODULE:      r.postprocessing.patch
# AUTHOR(S):   Lina Krisztian

# PURPOSE:     Patches tiles resulting from neural network inference
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
# % required: yes
# % description: list of tiles, which should be patched (filename)
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

# import needed libraries
import atexit
import os

import grass.script as grass

# initialize global variables
rm_rast = []


# cleanup function (can be extended)
def cleanup():
    """Cleanup fuction (can be extended)"""
    # TODO (use grass gis helpers)


def main():
    """Main function of r.postprocessing.patch"""
    global rm_rast

    tiles_filelist = options["tiles_filelist"]
    tiles_path = options["tiles_path"]
    edge_cut = options["edge_cut"]
    output = options["output"]

    # Read all files into a list
    with open(tiles_filelist, "r") as file:
        tiles_list = [line.strip() for line in file]
    
    grass.message(_("Importing tiles and cutting of edges ..."))
    rast_list = []
    for tiles in tiles_list:
        tiles_rast = f"{tiles.split('.')[0]}_tmp"
        rm_rast.append(tiles_rast)
        # Import data
        grass.run_command(
            "r.import",
            input = os.path.join(tiles_path, tiles),
            output = tiles_rast,
        )
        # Cut edges
        grass.run_command(
            "g.region",
            raster = tiles_rast,
            # todo: set dest_res if given
        )
        grass.run_command(
            "g.region",
            n = f"n-{edge_cut}",
            s = f"s+{edge_cut}",
            e = f"e-{edge_cut}",
            w = f"w+{edge_cut}",
        )
        tiles_rast_cut = tiles.split(".")[0]
        grass.run_command(
            "r.mapcalc",
            expression = f"{tiles_rast_cut} = {tiles_rast}",
        )
        rast_list.append(tiles_rast_cut)

    # Patch raster to VRT
    # Create file for input to buildvrt, in case of many input files
    tmpfile = grass.tempfile()
    with open(tmpfile, 'w') as f:
        for rast in rast_list:
            f.write(f"{rast}\n")
    grass.message(_("Creating VRT ..."))
    grass.run_command(
        "r.buildvrt",
        file = tmpfile,
        output = output,
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
