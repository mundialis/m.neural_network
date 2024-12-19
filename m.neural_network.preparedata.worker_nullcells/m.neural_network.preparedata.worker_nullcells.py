#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.preparedata.worker_nullcells
# AUTHOR(S):   Guido Riembauer, Anika Weinmann
# PURPOSE:     Worker module for m.neural_network.preparedata to check null
#              cells
# COPYRIGHT:   (C) 2024 by mundialis GmbH & Co. KG and the GRASS Development
#              Team.
#
# 		This program is free software under the GNU General Public
# 		License (v3). Read the file COPYING that comes with GRASS
# 		for details.
#
#############################################################################
"""

# %Module
# % description: Worker module for m.neural_network.preparedata to check null cells.
# % keyword: raster
# % keyword: statistics
# %end

# %option
# % key: n
# % type: string
# % required: no
# % multiple: no
# % key_desc: value
# % description: Value for the northern edge
# % guisection: Bounds
# %end

# %option
# % key: s
# % type: string
# % required: no
# % multiple: no
# % key_desc: value
# % description: Value for the southern edge
# % guisection: Bounds
# %end

# %option
# % key: e
# % type: string
# % required: no
# % multiple: no
# % key_desc: value
# % description: Value for the eastern edge
# % guisection: Bounds
# %end

# %option
# % key: w
# % type: string
# % required: no
# % multiple: no
# % key_desc: value
# % description: Value for the western edge
# % guisection: Bounds
# %end

# %option
# % key: res
# % type: string
# % required: no
# % multiple: no
# % key_desc: value
# % description: 2D grid resolution (north-south and east-west)
# % guisection: Resolution
# %end

# %option G_OPT_R_INPUT
# % key: map
# % label: The name of input raster map
# % guisection: Input
# %end

# %option
# % key: tile_name
# % type: string
# % required: yes
# % multiple: no
# % key_desc: name
# % label: Unique Name of the tile
# %end

# %option
# % key: new_mapset
# % type: string
# % required: yes
# % multiple: no
# % label: Name for new mapset
# %end

import os
import sys
import shutil

import grass.script as grass
from grass_gis_helpers.mapset import switch_to_new_mapset

newgisrc = None
gisrc = None
ID = grass.tempname(8)
new_mapset = None


def cleanup() -> None:
    """Clean up function calling general clean up from grass_gis_helpers."""
    grass.utils.try_remove(newgisrc)
    os.environ["GISRC"] = gisrc
    # delete the new mapset (doppelt haelt besser)
    gisenv = grass.gisenv()
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]
    mapset_dir = os.path.join(gisdbase, location, new_mapset)
    if os.path.isdir(mapset_dir):
        shutil.rmtree(mapset_dir)


def main() -> None:
    """Check null cells."""
    new_mapset = options["new_mapset"]
    tile_name = options["tile_name"]
    north = options["n"]
    south = options["s"]
    west = options["w"]
    east = options["e"]
    res = options["res"]
    map = options["map"]

    # switch to the new mapset
    gisrc, newgisrc, old_mapset = switch_to_new_mapset(new_mapset)

    # map full name
    if "@" not in map:
        map += f"@{old_mapset}"

    # set region
    grass.message(_(f"Set region for tile {tile_name} ..."))
    grass.run_command(
        "g.region",
        n=north,
        s=south,
        e=east,
        w=west,
        res=res,
        quiet=True,
    )

    # get number of null cells
    stats = grass.parse_command(
        "r.univar",
        map=map,
        flags="g",
    )
    sys.stdout.write(
        f"For tile {tile_name} the number of null cells is: {stats['null_cells']}\n",
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
