#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.tindex
# AUTHOR(S):   Anika Weinmann, Lina Krisztian, Guido Riembauer and
#              Victoria-Leandra Brunn
# PURPOSE:     Create tile index for data preparation as first step
#              for the process of creating a neural network.
# SPDX-FileCopyrightText: (c) 2024-2026 by mundialis GmbH & Co. KG and the
#              GRASS Development Team
# SPDX-License-Identifier: GPL-3.0-or-later.
#
#############################################################################
"""

# %Module
# % description: Create tile index for data preparation as first step for the process of creating a neural network
# % keyword: raster
# % keyword: vector
# % keyword: export
# % keyword: neural network
# % keyword: preparation
# %end

# %option G_OPT_V_INPUT
# % key: aoi
# % required: no
# % label: Name of the area of interest vector map
# % description: if not given, the current region is used
# % guisection: Optional input
# %end

# %option G_OPT_R_INPUT
# % key: image_band
# % label: Name of an imagery raster band, e.g. first band
# % description: The raster defines the output resolution and will additionally be used for checking null-cells
# % guisection: Input
# %end

# %option
# % key: tile_size
# % type: integer
# % required: yes
# % label: Size of the created tiles in cells. Must be divisible by 16
# % description: Creates tiles of size <tile_size>,<tile_size>
# % answer: 512
# % guisection: Optional input
# %end

# %option
# % key: tile_overlap
# % type: integer
# % required: yes
# % label: Overlap of the created tiles in cells
# % answer: 128
# % guisection: Optional input
# %end

# TODO: check if needed for both: train & apply
# %option
# % key: suffix
# % type: string
# % required: no
# % label: Suffix to be added to each output file
# % description: Use the suffix to provide a unique ID for e.g. a specific flight campaign year
# % guisection: Optional input
# %end

# %option G_OPT_M_DIR
# % key: output_dir
# % multiple: no
# % label: Directory where the tile index should be stored
# % guisection: Output
# %end

# %option G_OPT_M_NPROCS
# %end

# %option
# % key: val_percentage
# % type: integer
# % required: yes
# % label: Percentage of training tiles to be used as validation during training
# % answer: 20
# % guisection: Input
# %end

# %option
# % key: test_percentage
# % type: integer
# % required: no
# % label: Percentage of training tiles to be used as testing data during training
# % answer: 0
# % guisection: Input
# %end

# TODO:(row and col indepent wenn möglich)
# %option
# % key: num_tiles_ind_group
# % type: integer
# % required: no
# % label: For two level tiling of training tiles: number of tiles in each independent group (level 1 tile)
# % guisection: Input
# %end

# %flag
# % key: t
# % label: training mode
# % description: Prepare data for training mode i.e. split into train, val and optional test
# %end

# %flag
# % key: s
# % label: Skip null cell check
# % description: Option for skipping the check for null cells in the training tiles (will lead to fail during training). This can be used if the user is sure that there are no null cells in the input data and wants to save time by skipping this step. If this flag is set, all tiles will be exported, even if they contain null cells. This speeds up processing.
# %end
# %rules

# % requires_all: val_percentage, -t
# % requires_all: test_percentage, -t
# %end
# t-flag requires always val_percentage, but it is as default given, so no rule needed/possible


import atexit
import json
import os
import random
import shutil
import sys

import geopandas as gpd
from math import ceil, floor
import numpy as np
from osgeo import gdal
import pandas as pd
from shapely.geometry import Polygon
import grass.script as grass
from grass.pygrass.modules import Module, ParallelModuleQueue
from grass.pygrass.utils import get_lib_path
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import check_installed_addon, set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass_gis_helpers.parallel import check_parallel_errors, create_grass_env

# import helper functions file
sys.path.insert(
    1,
    os.path.join(
        os.path.dirname(sys.path[0]), "etc", "m.neural_network.tindex"
    ),
)
from tindex_helper import make_grid, check_tile_intersection_with_aoi, remove_tiles_with_null_cells, export_tindex
# initialize global vars
ID = grass.tempname(8)
rm_files = list()
ORIG_REGION = None
rm_dirs = []
rm_vectors = []
rm_mapsets = []
rm_gisrcs = []


def cleanup() -> None:
    """Clean up function calling general clean up from grass_gis_helpers."""
    for gisrc in rm_gisrcs:
        grass.utils.try_remove(gisrc)
    # delete the new mapsets
    for mapset in rm_mapsets:
        gisenv = grass.gisenv()
        gisdbase = gisenv["GISDBASE"]
        location = gisenv["LOCATION_NAME"]
        mapset_dir = os.path.join(gisdbase, location, mapset)
        if os.path.isdir(mapset_dir):
            shutil.rmtree(mapset_dir)
    general_cleanup(
        orig_region=ORIG_REGION,
        rm_dirs=rm_dirs,
        rm_files=rm_files,
        rm_vectors=rm_vectors,
    )


def main() -> None:
    """Prepare training data.

    Main function for creation of the tile index and preparation of the
    training data. The function creates the tile index as GeoJson and exports
    it as GPKG.
    Two modes:
    application mode (default): all tiles for application
    train mode (via -t flag): split data into train, val and optinal test.
    Dependent on mode, do two-level-grid or single-level-grid. Tiles with null
    cells are excluded from training data.
    """
    global ORIG_REGION

    aoi = options["aoi"]
    tile_size = int(options["tile_size"])
    tile_overlap = int(options["tile_overlap"])
    output_dir = options["output_dir"]
    nprocs = set_nprocs(int(options["nprocs"]))
    image_band = options["image_band"]
    suffix = options["suffix"]
    val_percentage = int(options["val_percentage"])
    test_percentage = int(options["test_percentage"])
    num_tiles_ind_group = int(options["num_tiles_ind_group"]) if options["num_tiles_ind_group"] else options["num_tiles_ind_group"]

    # checks, which can't be captured via grass parser
    if not flags["t"]:
        grass_params = {
            "s-flag": flags["s"],
            "val_percentage": val_percentage,
            "test_percentage": test_percentage,
            "num_tiles_ind_group": num_tiles_ind_group,
        }
        for param in grass_params.items():
            if param[1]:
                # Only warning, cause val_percentage and test_percentage
                # always set (default values)
                grass.warning(
                    _(
                        f"Parameter <{param[0]}> is only used in training mode"
                    ),
                )
    
    # check tile_size devisible by 16
    if tile_size % 16 != 0:
        grass.fatal(_("<tile_size> is not devisible by 16!"))

    check_installed_addon(
        "v.out.geojson", url="https://github.com/mundialis/v.out.geojson"
    )

    # get addon etc path
    etc_path = get_lib_path(modname="m.neural_network.tindex")
    # TODO: update qml files (train and apply mode?)
    if etc_path is None:
        grass.fatal("Unable to find qml files!")

    os.makedirs(output_dir, exist_ok=True)

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]

    # check if input data exists
    if not grass.find_file(name=image_band, element="raster")["file"]:
        grass.fatal(_(f"Raster map <{image_band}> not found"))

    # save original region
    ORIG_REGION = f"orig_region_{ID}"
    grass.run_command("g.region", save=ORIG_REGION, quiet=True)

    # set region to raster or aoi
    grass.run_command("g.region", raster=image_band, quiet=True)
    reg = grass.region()
    res = reg["nsres"]
    if aoi:
        # for application mode: buffer aoi, to ensure gap free results
        if not flags["t"]:
            aoi_buf = f"aoi_buf_{ID}"
            rm_vectors.append(aoi_buf)
            grass.run_command(
                "v.buffer",
                input=aoi,
                output=aoi_buf,
                distance=res * tile_overlap,
            )
            grass.run_command("g.region", vector=aoi_buf, quiet=True)
        else:
            grass.run_command("g.region", vector=aoi, quiet=True)
        grass.run_command("g.region", align=image_band, quiet=True)
        reg = grass.region()

    # for apply mode
    if not flags["t"]:
        epsg_code, geojson_dict = make_grid(tile_size, tile_overlap, res, reg, suffix)
        if aoi:
            # -- (buffered) AOI intersects with tiles:
            # Used, when tindex is used for final application of model
            # i.e. when complete AOI should be classified, and even a little
            # more tiles are classifed, to ensure gap free classification
            # at the borders of AOI.
            check_tile_intersection_with_aoi(
                aoi_buf, "intersects", epsg_code, geojson_dict
            )
            # Update tindex attribute table
            for feat in geojson_dict["features"]:
                feat["properties"]["apply"] = "yes"

    # for training mode
    if flags["t"]:
        if not num_tiles_ind_group:
            epsg_code, geojson_dict = make_grid(tile_size, tile_overlap, res, reg, suffix)
        else:
            # TODO: two level grid
            None
    
        # TODO: below for two level grid??
        if aoi:
            # -- AOI completely within tiles:
            # Needed for training tiles i.e. when tiles should be completely
            # within AOI (for which input data are prepared).
            check_tile_intersection_with_aoi(
                aoi, "within", epsg_code, geojson_dict
            )
            
        if not flags["s"]:
            # Check if tile has no null cells inside and can be used for training
            geojson_dict, rm_mapsets_rm_ncells, rm_gisrcs_rm_ncells = (
                remove_tiles_with_null_cells(
                    nprocs,
                    ID,
                    image_band,
                    cur_mapset,
                    res,
                    geojson_dict,
                )
            )
            rm_mapsets.extend(rm_mapsets_rm_ncells)
            rm_gisrcs.extend(rm_gisrcs_rm_ncells)
        else:
            # TODO?: possible_tr_data
            grass.message(_("Skipping null cell check for tiles!"))

        # train-val-test split
        if flags["t"]:
            import pdb; pdb.set_trace()
            # TODO: use split_train_val_test??
            # num_val_tiles = round(val_percentage / 100.0 * len(possible_tr_data))
            # num_test_tiles = round(test_percentage / 100.0 * len(possible_tr_data))
            # random.shuffle(possible_tr_data)
            # val_tiles = possible_tr_data[:num_val_tiles]
            # test_tiles = possible_tr_data[num_val_tiles:num_val_tiles + num_test_tiles]
            # train_tiles = [
            #     x
            #     for x in possible_tr_data
            #     if x not in val_tiles and x not in test_tiles
            # ]
            # grass.message(
            #     _(
            #         f"Selected {len(val_tiles)} tiles as validation tiles, "
            #         f"{len(test_tiles)} as testing tiles and "
            #         f"{len(train_tiles)} as training tiles.",
            #     ),
            # )
            # # TODO: train, val, test
            # for tr_tile in train_tiles:
            #     geojson_dict["features"][tr_tile]["properties"][
            #         "training"
            #     ] = "TODO"

    # export tindex
    rm_files_exp_tind = export_tindex(output_dir, geojson_dict, etc_path)
    rm_files.extend(rm_files_exp_tind)

    grass.message(_("Prepare data done"))



if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
