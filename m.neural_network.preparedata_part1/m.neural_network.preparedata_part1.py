#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.preparedata_part1
# AUTHOR(S):   Anika Weinmann, Guido Riembauer and Victoria-Leandra Brunn
# PURPOSE:     Prepare training data as first step for the process of
#              creating a neural network.
# SPDX-FileCopyrightText: (c) 2024-2025 by mundialis GmbH & Co. KG and the
#              GRASS Development Team
# SPDX-License-Identifier: GPL-3.0-or-later.
#
#############################################################################
"""

# %Module
# % description: Prepare training data for creating a neuronal network
# % keyword: raster
# % keyword: vector
# % keyword: export
# % keyword: neural network
# % keyword: preparation
# %end

# %option G_OPT_F_INPUT
# % key: tindex
# % required: yes
# % label: tindex file for tiling.
# % description: must be created with m.neural_network.tindex
# %end

# %option G_OPT_R_INPUTS
# % key: image_bands
# % label: The names of imagery raster bands, e.g. for DOPs RGBI raster bands
# % description: The first raster defines the output resolution
# % guisection: Input
# %end

# %option G_OPT_R_INPUT
# % key: ndsm
# % required: no
# % label: Name of the nDSM raster
# % answer: ndsm
# % guisection: Input
# %end

# %option G_OPT_R_INPUT
# % key: dsm
# % required: no
# % label: Name of the DSM raster
# % guisection: Input
# %end

# %option G_OPT_R_INPUT
# % key: dtm
# % required: no
# % label: Name of the DTM raster
# % guisection: Input
# %end

# %option G_OPT_R_OUTPUT
# % key: ndsm_out
# % required: no
# % label: Name for the computed nDSM raster
# % guisection: Output
# %end

# %option G_OPT_V_INPUT
# % key: reference
# % required: no
# % label: Name of the reference vector map
# % guisection: Optional input
# %end

# %option
# % key: segmentation_minsize
# % type: integer
# % required: no
# % label: Minimum number of cells in a segment
# % answer: 80
# % guisection: Optional input
# %end

# %option
# % key: segmentation_threshold
# % type: double
# % required: no
# % label: Difference threshold between 0 and 1 for the segments
# % description: Threshold = 0 merges only identical segments; threshold = 1 merges all
# % answer: 0.3
# % guisection: Optional input
# %end

# %option G_OPT_M_DIR
# % key: output_dir
# % multiple: no
# % label: Directory where the prepared data should be stored
# % description: The directory will be split into train and apply
# % guisection: Output
# %end

# %option G_OPT_M_NPROCS
# %end

# %flag
# % key: t
# % label: Only training and testing tiles
# % description: Option for only exporting training and testing tiles
# %end

# %flag
# % key: l
# % label: Prepare labels for training and testing data
# % description: Option for preparing labels for training and testing data. If not set, only the tiles for the image bands and nDSM are exported, but no segmentation and labeling is performed.
# %end

# %rules
# % exclusive: ndsm, ndsm_out
# % requires_all: dsm, dtm, ndsm_out
# %end


import atexit
import os
import shutil

import geopandas as gpd
import grass.script as grass
import numpy as np
import pandas as pd
from grass.pygrass.modules import Module, ParallelModuleQueue
from grass.pygrass.utils import get_lib_path
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass_gis_helpers.parallel import check_parallel_errors

# initialize global vars
ID = grass.tempname(8)
rm_files = list()
ORIG_REGION = None
rm_vectors = []
rm_rasters = []
rm_groups = []


def cleanup() -> None:
    """Clean up function calling general clean up from grass_gis_helpers."""
    general_cleanup(
        orig_region=ORIG_REGION,
        rm_files=rm_files,
        rm_vectors=rm_vectors,
        rm_rasters=rm_rasters,
        rm_groups=rm_groups,
    )


def main() -> None:
    """Prepare training data.

    Main function for data preparation.
    Importing tileindex. Creating tiles for label process
    with DOPs and nDOM split in train and apply tiles. Exporting tiles
    regarding to tileindex and update tileindex with path variable.
    """
    global ORIG_REGION

    tindex = options["tindex"]
    image_bands = options["image_bands"].split(",")
    ndsm = options["ndsm"]
    dsm = options["dsm"]
    dtm = options["dtm"]
    ndsm_out = options["ndsm_out"]
    reference = options["reference"]
    segmentation_minsize = int(options["segmentation_minsize"])
    segmentation_threshold = float(options["segmentation_threshold"])
    output_dir = options["output_dir"]
    nprocs = set_nprocs(int(options["nprocs"]))

    # get addon etc path
    etc_path = get_lib_path(modname="m.neural_network.preparedata_part1")
    if etc_path is None:
        grass.fatal("Unable to find qml files!")

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]

    # check if input data exists
    for img_band in image_bands:
        if not grass.find_file(name=img_band, element="raster")["file"]:
            grass.fatal(_(f"Raster map <{img_band}> not found"))
    if dsm and not grass.find_file(name=dsm, element="raster")["file"]:
        grass.fatal(_(f"Raster map <{dsm}> not found"))
    if dtm and not grass.find_file(name=dtm, element="raster")["file"]:
        grass.fatal(_(f"Raster map <{dtm}> not found"))
    if ndsm and not grass.find_file(name=ndsm, element="raster")["file"]:
        if not (dsm and dtm):
            grass.fatal(
                _(
                    f"Raster map <{ndsm}>, <{dtm}> and <{dsm}> not set or "
                    "found!"
                )
            )
        ndsm = None
    if ndsm == ndsm_out:
        grass.fatal(
            _(
                f"Parameter <ndsm_out> is set to <{ndsm}>, but the raster "
                "map already exists!"
            )
        )
    if (
        reference
        and not grass.find_file(name=reference, element="vector")["file"]
    ):
        grass.fatal(_(f"Vector map <{reference}> not found"))

    # save original region
    ORIG_REGION = f"orig_region_{ID}"
    grass.run_command("g.region", save=ORIG_REGION, quiet=True)

    # set region to raster and tindex to compute data only for tindex area
    grass.run_command("v.external", input=tindex, output="tindex", quiet=True)
    rm_vectors.append("tindex")
    grass.run_command("g.region", vector="tindex", quiet=True)
    grass.run_command("g.region", align=image_bands[0], quiet=True)
    reg = grass.region()
    res = reg["nsres"]

    # compute nDSM if not directly given
    if dsm and dtm and ndsm_out:
        ndsm = ndsm_out
        grass.run_command(
            "r.mapcalc",
            expression=f"{ndsm} = float({dsm} - {dtm})",
        )

    # nDSM scaled + export (cut to [0 30] and rescale to [1 255]))
    ndsm_cut = "ndsm_cut"
    ex_cut = (
        f"{ndsm_cut} = if( {ndsm} >= 30, 30, if( {ndsm} < 0, 0, {ndsm} ) )"
    )
    rm_rasters.append(ndsm_cut)
    grass.run_command("r.mapcalc", expression=ex_cut)

    ndsm_scaled = "ndsm_scaled"
    ex_scale = f"{ndsm_scaled} = int(({ndsm_cut} / 30. * 254.) + 1)"
    rm_rasters.append(ndsm_scaled)
    grass.run_command("r.mapcalc", expression=ex_scale)

    # Image Bands:
    # convert to byte, if not integer or values out of range [1 255]
    image_bands_new = []
    for image in image_bands:
        if (
            grass.raster_info(image)["datatype"] != "CELL"
            or grass.raster_info(image)["max"] > 255
            or grass.raster_info(image)["min"] < 1
        ):
            image_new = f"{image.split('@')[0]}_new"
            rm_rasters.append(image_new)
            grass.run_command(
                "r.mapcalc",
                expression=f"{image_new} = int(if({image} < 1, 1, if({image} > "
                f"255, 255, {image})))",
            )
            image_bands_new.append(image_new)
        else:
            image_bands_new.append(image)
    image_bands = image_bands_new

    image_bands_group = "image_bands"
    rm_groups.append(image_bands_group)
    grass.run_command(
        "i.group",
        group=image_bands_group,
        input=image_bands,
        quiet=True,
    )

    # import tindex
    tindex_gdf = gpd.read_file(tindex)

    tindex_gdf_tr_tiles = tindex_gdf[
        (tindex_gdf["training"] == "TODO") | (tindex_gdf["training"] == "yes")
    ].copy()
    tindex_gdf_te_tiles = tindex_gdf[
        (tindex_gdf["testing"] == "TODO") | (tindex_gdf["testing"] == "yes")
    ].copy()
    if flags["t"]:
        tindex_gdf_ap_tiles = gpd.GeoDataFrame()
    else:
        tindex_gdf_ap_tiles = tindex_gdf[
            (tindex_gdf["training"] == "no") & (tindex_gdf["testing"] == "no")
        ].copy()
    # get number of digits of resolution for correct rounding of coordinates
    round_decimals = len(str(res).split(".")[1])

    # loop over training data
    queue_export_tr = ParallelModuleQueue(nprocs=nprocs)
    try:
        for i, tr_tile in enumerate(tindex_gdf_tr_tiles.itertuples(), start=1):
            worker_export_tr = export_training_test_tile(
                ndsm,
                reference,
                segmentation_minsize,
                segmentation_threshold,
                output_dir,
                res,
                ndsm_scaled,
                image_bands_group,
                tindex_gdf_tr_tiles,
                round_decimals,
                i,
                tr_tile,
            )
            queue_export_tr.put(worker_export_tr)
        queue_export_tr.wait()
    except Exception:
        check_parallel_errors(queue_export_tr)
    verify_mapsets(cur_mapset)

    # loop over testing data
    queue_export_te = ParallelModuleQueue(nprocs=nprocs)
    try:
        for i, te_tile in enumerate(tindex_gdf_te_tiles.itertuples(), start=1):
            worker_export_te = export_training_test_tile(
                ndsm,
                reference,
                segmentation_minsize,
                segmentation_threshold,
                output_dir,
                res,
                ndsm_scaled,
                image_bands_group,
                tindex_gdf_te_tiles,
                round_decimals,
                i,
                te_tile,
                tr_te_type="test",
            )
            queue_export_te.put(worker_export_te)
        queue_export_te.wait()
    except Exception:
        check_parallel_errors(queue_export_te)
    verify_mapsets(cur_mapset)

    # If only apply data -> skip existing tiles
    # TODO: if two times interrupted/restarted -> missing files in the middle
    if tindex_gdf.shape[0] == tindex_gdf_ap_tiles.shape[0]:
        tindex_gdf_ap_tiles_skip_existing = tindex_gdf_ap_tiles.copy()
        n = 0
        for ap_tile in tindex_gdf_ap_tiles[::-1].itertuples():
            tile_path = os.path.join(output_dir, "apply", ap_tile.name)
            if os.path.isdir(tile_path):
                # add also last processed dirs, which prob. not completely exported
                if n < nprocs:
                    n += 1
                    # remove these dirs before exporting newly
                    shutil.rmtree(tile_path)
                else:
                    tindex_gdf_ap_tiles_skip_existing = (
                        tindex_gdf_ap_tiles_skip_existing[
                            tindex_gdf_ap_tiles_skip_existing["name"]
                            != ap_tile.name
                        ]
                    )
        tindex_gdf_ap_tiles = tindex_gdf_ap_tiles_skip_existing

    # loop over apply data
    queue_export_ap = ParallelModuleQueue(nprocs=nprocs)
    try:
        for i, ap_tile in enumerate(tindex_gdf_ap_tiles.itertuples(), start=1):
            worker_export_ap = export_apply_tile(
                ndsm,
                output_dir,
                res,
                ndsm_scaled,
                image_bands_group,
                tindex_gdf_ap_tiles,
                round_decimals,
                i,
                ap_tile,
            )
            queue_export_ap.put(worker_export_ap)
        queue_export_ap.wait()
    except Exception:
        check_parallel_errors(queue_export_ap)
    verify_mapsets(cur_mapset)

    # Update tindex
    tindex_gdf_updated = pd.concat(
        [tindex_gdf_tr_tiles, tindex_gdf_te_tiles, tindex_gdf_ap_tiles],
        ignore_index=True,
    )
    if "fid" in tindex_gdf_updated.columns:
        tindex_gdf_updated = tindex_gdf_updated.drop(columns=["fid"])
    tindex_gdf_updated.to_file(tindex, driver="GPKG")

    grass.message(_("Prepare data done"))


def export_apply_tile(
    ndsm,
    output_dir,
    res,
    ndsm_scaled,
    image_bands_group,
    tindex_gdf_ap_tiles,
    round_decimals,
    i,
    ap_tile,
):
    """Export apply tile."""
    tile_name = ap_tile.name
    tile_path = os.path.join(output_dir, "apply", tile_name)
    tile_bounds = np.round(ap_tile.geometry.bounds, round_decimals)
    north = str(tile_bounds[3])
    south = str(tile_bounds[1])
    west = str(tile_bounds[0])
    east = str(tile_bounds[2])
    if i % 100 == 0:
        # print only every 100-th entry
        grass.message(
            _(f"Exporting: apply tile {i} of {len(tindex_gdf_ap_tiles)}"),
        )
    new_mapset = f"tmp_mapset_{ID}_{tile_name}"
    # update jeojson values
    tindex_gdf_ap_tiles.at[ap_tile.Index, "path"] = tile_path
    # worker for export
    worker_export_ap = Module(
        "m.neural_network.preparedata_part1.worker_export",
        n=north,
        s=south,
        e=east,
        w=west,
        res=res,
        image_bands_group=image_bands_group,
        tile_name=tile_name,
        ndsm=ndsm,
        ndsm_scaled=ndsm_scaled,
        output_dir=tile_path,
        new_mapset=new_mapset,
        run_=False,
    )
    worker_export_ap.stdout_ = grass.PIPE
    return worker_export_ap


def export_training_test_tile(
    ndsm,
    reference,
    segmentation_minsize,
    segmentation_threshold,
    output_dir,
    res,
    ndsm_scaled,
    image_bands_group,
    tindex_gdf_tiles,
    round_decimals,
    i,
    tile,
    tr_te_type="train",
):
    """Export training/test tile."""
    tile_name = tile.name
    tile_path = os.path.join(output_dir, tr_te_type, tile_name)
    tile_bounds = np.round(tile.geometry.bounds, round_decimals)
    north = str(tile_bounds[3])
    south = str(tile_bounds[1])
    west = str(tile_bounds[0])
    east = str(tile_bounds[2])
    grass.message(
        _(
            f"Segmenting and/or Exporting: "
            f"{tr_te_type}ing tile {i} of {len(tindex_gdf_tiles)}",
        ),
    )
    new_mapset = f"tmp_mapset_{ID}_{tile_name}"
    # update gdf values
    tindex_gdf_tiles.at[tile.Index, "path"] = tile_path

    # worker for export
    worker_export_tr = Module(
        "m.neural_network.preparedata_part1.worker_export",
        n=north,
        s=south,
        e=east,
        w=west,
        res=res,
        image_bands_group=image_bands_group,
        ndsm=ndsm,
        ndsm_scaled=ndsm_scaled,
        tile_name=tile_name,
        reference=reference,
        segmentation_minsize=segmentation_minsize,
        segmentation_threshold=segmentation_threshold,
        output_dir=tile_path,
        new_mapset=new_mapset,
        flags="l" if flags["l"] else "",
        run_=False,
    )
    worker_export_tr.stdout_ = grass.PIPE
    worker_export_tr.stderr_ = grass.PIPE

    return worker_export_tr


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
