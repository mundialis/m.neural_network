#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.preparetraining.worker
# AUTHOR(S):   Guido Riembauer
# PURPOSE:     Worker module for m.neural_network.preparetraining to check
#              and rasterize label data
# COPYRIGHT:   (C) 2024 by mundialis GmbH & Co. KG and the GRASS Development
#              Team
#
# 		This program is free software under the GNU General Public
# 		License (v3). Read the file COPYING that comes with GRASS
# 		for details.
#
#############################################################################
"""

# %Module
# % description: Worker module for m.neural_network.preparetraining to check and rasterize label data
# % keyword: raster
# % keyword: statistics
# %end

# %option G_OPT_F_INPUT
# % required: yes
# % multiple: no
# % label: Path to the label vector file
# % guisection: Input
# %end

# %option G_OPT_F_INPUT
# % key: img_path
# % required: yes
# % multiple: no
# % label: Path to the corresponding imagery raster file
# % guisection: Input
# %end

# %option
# % key: class_column
# % type: string
# % required: yes
# % multiple: no
# % answer: class_number
# % label: Column of the label vector that holds the class number
# % guisection: Parameters
# %end

# %option
# % key: class_values
# % type: integer
# % required: yes
# % multiple: yes
# % answer: 2
# % label: Expected and output values for the class/es of interest
# % guisection: Parameters
# %end

# %option
# % key: no_class_value
# % type: integer
# % required: yes
# % multiple: no
# % answer: 1
# % label: Expected and output value for the non class of interest areas
# % description: Can be understood as a "rest" class for a multiclass system and a "no-class" for a binary classification
# % guisection: Parameters
# %end

# %option G_OPT_F_OUTPUT
# % required: yes
# % multiple: no
# % label: Path to the output label raster file
# % guisection: Output
# %end

# %option
# % key: new_mapset
# % type: string
# % required: yes
# % multiple: no
# % label: Name of the new mapset to work in
# % guisection: Parameters
# %end

import atexit
import os
import shutil

import grass.script as grass
from grass_gis_helpers.mapset import switch_to_new_mapset
from osgeo import gdal

NEWGISRC = None
GISRC = None
ID = grass.tempname(8)
NEW_MAPSET = None


def cleanup(): -> None
    """Switch mapsets and deleting the new one."""
    # switch back to original mapset
    grass.utils.try_remove(NEWGISRC)
    os.environ["GISRC"] = GISRC
    # delete the new mapset (doppelt haelt besser)
    gisenv = grass.gisenv()
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]
    mapset_dir = os.path.join(gisdbase, location, NEW_MAPSET)
    if os.path.isdir(mapset_dir):
        shutil.rmtree(mapset_dir)


def main():
    """Run label rasterization"""
    global NEWGISRC, GISRC, NEW_MAPSET
    input = options["input"]
    img_file = options["img_path"]
    NEW_MAPSET = options["new_mapset"]
    class_values = options["class_values"].split(",")
    no_class_value = options["no_class_value"]
    class_col = options["class_column"]
    output = options["output"]

    # switch to the new mapset
    GISRC, NEWGISRC, old_mapset = switch_to_new_mapset(NEW_MAPSET)

    # get extent from reference img file
    info = gdal.Info(img_file, format="json")
    south = info["cornerCoordinates"]["lowerLeft"][1]
    west = info["cornerCoordinates"]["lowerLeft"][0]
    north = info["cornerCoordinates"]["upperRight"][1]
    east = info["cornerCoordinates"]["upperRight"][0]
    cols, rows = info["size"]
    # set the region
    grass.run_command(
        "g.region",
        n=north,
        s=south,
        e=east,
        w=west,
        rows=rows,
        cols=cols,
        quiet=True,
    )

    # import the label dataset
    labelvect = f"labelvect_{ID}"
    labelrast = f"labelrast_{ID}"
    grass.run_command("v.import", input=input, output=labelvect, quiet=True)

    # check the values of the vector
    dbselect = list(grass.parse_command("v.db.select", map=labelvect).keys())
    colnames = dbselect[0].split("|")
    rows = [item.split("|") for item in dbselect[1:]]
    try:
        idx = colnames.index(class_col)
    except ValueError:
        grass.fatal(_(f"File {input} has no column {class_col}"))
    class_numbers = [item[idx] for item in rows]
    class_num_set_ref = set([*class_values, no_class_value])
    difference = set(class_numbers).difference(class_num_set_ref)
    if len(difference) > 0:

        grass.fatal(
            _(
                f"Label file {input} has features with unexpected values"
                f" in column {class_col}: {difference}. Allowed values "
                f"are [{','.join(class_values)}, {no_class_value}].",
            ),
        )

    tile_empty = False
    if len(class_numbers) == 0 or set(class_numbers) == set((no_class_value)):
        grass.warning(
            _(
                f"Label file {input} contains no features with the "
                f"expected class values {class_values} in "
                f"column {class_col}. It is assumed that the classes "
                "do not occur in this tile.",
            ),
        )
        tile_empty = True

    # rasterize
    if tile_empty is True:
        grass.run_command(
            "r.mapcalc",
            expression=f"{labelrast}={no_class_value}",
            quiet=True,
        )
    else:
        labelrast_tmp = f"{labelrast}_tmp"
        grass.run_command(
            "v.to.rast",
            input=labelvect,
            output=labelrast_tmp,
            type="area",
            use="attr",
            attribute_column=class_col,
            quiet=True,
        )
        # if there is any nodata left in the label, this will be assigned
        # to the no-class class
        exp = f"{labelrast}=if(isnull({labelrast_tmp}),{no_class_value},{labelrast_tmp})"
        grass.run_command("r.mapcalc", expression=exp, quiet=True)

    grass.run_command(
        "r.out.gdal",
        input=labelrast,
        output=output,
        type="Byte",
        createopt="COMPRESS=LZW",  # no tiles or overviews required for the small tiles (?)
        flags="c",
        quiet=True,
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
