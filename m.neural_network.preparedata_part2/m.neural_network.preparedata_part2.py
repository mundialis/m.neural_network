#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.preparedata_part2
# AUTHOR(S):   Guido Riembauer, Victoria-Leandra Brunn
# PURPOSE:     Prepares tiled imagery and labelled data for training and application
#              in a Neural Network (NN).
# SPDX-FileCopyrightText: (c) 2024-2025 by mundialis GmbH & Co. KG and the
#              GRASS Development Team
# SPDX-License-Identifier: GPL-3.0-or-later.
#
#############################################################################
"""

# %Module
# % description: Prepares tiled imagery and labelled data for training and application in a Neural Network (NN).
# % keyword: raster
# % keyword: vector
# % keyword: import
# % keyword: export
# % keyword: training
# % keyword: neural network
# % keyword: preparation
# %end

# %option G_OPT_F_INPUT
# % key: tindex
# % required: yes
# % label: tindex file for tiling.
# % description: must be created with m.neural_network.tindex
# %end

# %option G_OPT_M_DIR
# % key: input_dir
# % label: Name of the input directory with data prepared from part1 containing subfolders with imagery and optional ndom and/or labels per tile
# % required: yes
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
# % label: Expected and output value for the class/es of interest
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

# %option G_OPT_F_INPUT
# % key: reclassify_rules
# % required: no
# % multiple: no
# % label: If desired, file with rules for reclassification of input class values
# %end

# %option
# % key: num_null_cells_label
# % type: integer
# % answer: 0
# % label: Number of null cells in the rasterized label, which are accepted (will be filled with neighbouring classes).
# % description: This can be used to account for small acceptable gaps in the vector data, which would lead to null cells in the rasterized label.
# %end

# %option
# % key: output
# % type: string
# % required: yes
# % multiple: no
# % label: Name of the output directory
# % guisection: Output
# %end

# %option
# % key: nprocs
# % type: integer
# % required: no
# % multiple: no
# % label: Number of parallel processes
# % description: Number of cores for multiprocessing, -2 is the number of available cores - 1
# % answer: -2
# %end


import atexit
import os
import shutil
from multiprocessing import Pool
from pathlib import Path

import geopandas as gpd
import grass.script as grass
from grass.pygrass.modules import Module, ParallelModuleQueue
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass_gis_helpers.parallel import (
    check_parallel_errors,
    check_parallel_warnings,
    create_grass_env,
)
from osgeo import gdal, ogr

# initialize global vars
ID = grass.tempname(8)
ORIG_REGION = None
rm_dirs = []
rm_mapsets = []
rm_gisrcs = []


def cleanup():
    """Pass args to the general cleanup from grass-gis-helpers."""
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
    general_cleanup(orig_region=ORIG_REGION, rm_dirs=rm_dirs)


def get_tile_infos(in_dir, ttype, tindex_gdf=None):
    """Read tile-wise directory and saves metadata in a list of dicts."""
    all_tiles = []
    # get all training_tiles and split into training, validation and testing
    for tile in os.listdir(in_dir):
        tiledir = os.path.join(in_dir, tile)
        tiledict = {}
        if os.path.isdir(tiledir) and tile.startswith("tile_"):
            tiledict["id"] = tile
            tiledict["type"] = ttype
            tiledict["imagery_tif"] = os.path.join(
                tiledir, f"image_{tile}.tif"
            )
            tiledict["ndom_tif"] = os.path.join(
                tiledir,
                f"ndsm_1_255_{tile}.tif",
            )
            checklist = [tiledict["imagery_tif"], tiledict["ndom_tif"]]
            if ttype == "training":
                tiledict["label_gpkg"] = os.path.join(
                    tiledir,
                    f"label_{tile}.gpkg",
                )
                checklist.append(tiledict["label_gpkg"])
                # check train/val/test type
                tindex_gdf_tile = tindex_gdf[tindex_gdf["name"] == tile]
                if (tindex_gdf_tile["training"] == "yes").any():
                    tiledict["type"] = "training"
                elif (tindex_gdf_tile["validation"] == "yes").any():
                    tiledict["type"] = "validation"
                elif (tindex_gdf_tile["testing"] == "yes").any():
                    tiledict["type"] = "testing"

            # check if they exist
            for f in checklist:
                if not os.path.isfile(f):
                    if "ndsm" in f:
                        tiledict["ndom_tif"] = None
                        grass.warning(
                            _(
                                f"File {f} not found. "
                                "Expecting no need of ndsm."
                            )
                        )
                    else:
                        grass.fatal(_(f"File {f} expected but not found."))

            all_tiles.append(tiledict)
    return all_tiles


def vrt_relative_paths(vrt, abs_paths):
    """Change absolute to relative paths in a .vrt
    :param vrt: String: Path to the vrt
    :param abs_paths: List: absolute paths to be replaced.
    """
    with open(vrt, encoding="utf-8") as file:
        data = file.read()
        data = data.replace('relativeToVRT="0"', 'relativeToVRT="1"')
        for abs_path in abs_paths:
            rel_path = os.path.relpath(abs_path, start=os.path.dirname(vrt))
            data = data.replace(abs_path, rel_path)
    with open(vrt, "w", encoding="utf-8") as file:
        file.write(data)


def build_vrts(outdir, imagery, ndom, tile_id, singleband_vrt_dir):
    """Build the required .vrt files."""
    bands_e_vrt = os.path.join(outdir, f"{tile_id}.vrt")
    if ndom:
        # If ndom will be added: first separate imagery bands to single bands
        # (singleband-vrts) then append ndom as additional channel (final vrts)
        src_ds = gdal.Open(imagery)
        band_count = 0
        if src_ds is not None:
            band_count = int(src_ds.RasterCount)
        else:
            grass.fatal(_(f"File {imagery} is empty."))
        src_ds = None

        vrt_input = []
        for num in range(1, band_count + 1):
            band_vrt = os.path.join(singleband_vrt_dir, f"{tile_id}_{num}.vrt")
            vrt_options_sep = gdal.BuildVRTOptions(bandList=[num])
            gdal.BuildVRT(band_vrt, [imagery], options=vrt_options_sep)
            # replace absolute with relative path
            vrt_relative_paths(band_vrt, abs_paths=[imagery])
            vrt_input.append(band_vrt)

        # create vrt
        vrt_input.append(ndom)
        vrt_options = gdal.BuildVRTOptions(separate=True)
        gdal.BuildVRT(bands_e_vrt, vrt_input, options=vrt_options)
        # replace absolute with relative paths
        vrt_relative_paths(bands_e_vrt, abs_paths=vrt_input)
    else:
        # If no additional channel added to imagery,
        # just create (final) vrt with all imagery bands
        # (simply reference to part1-folder tif)
        # (Note: results in empty singleband_vrts-folder)
        gdal.BuildVRT(bands_e_vrt, imagery)
        # replace absolute with relative paths
        vrt_relative_paths(bands_e_vrt, abs_paths=[imagery])
    return bands_e_vrt


def main():
    """Run training and apply data preparation."""
    global ORIG_REGION

    input_dir = options["input_dir"]
    tindex = options["tindex"]
    nprocs = set_nprocs(int(options["nprocs"]))
    class_col = options["class_column"]
    class_values = options["class_values"].split(",")
    no_class_value = options["no_class_value"]
    reclassify_rules = options["reclassify_rules"]
    num_null_cells_label = options["num_null_cells_label"]
    output = options["output"]

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]

    # save original region
    ORIG_REGION = f"orig_region_{ID}"
    grass.run_command("g.region", save=ORIG_REGION, quiet=True)

    if not os.path.isdir(output):
        os.makedirs(output)
    rm_dirs.append(output)

    # import tindex and select train or apply tiles
    tindex_gdf = gpd.read_file(tindex)
    tindex_gdf_tr_tiles = tindex_gdf[
        (tindex_gdf["training"] == "yes")
        | (tindex_gdf["validation"] == "yes")
        | (tindex_gdf["testing"] == "yes")
    ].copy()
    tindex_gdf_ap_tiles = tindex_gdf[(tindex_gdf["apply"] == "yes")].copy()

    # create folders if they dont exist
    create_dirs = {}
    dir_out = Path(output)
    create_dirs["singleband_vrt_dir"] = dir_out / "singleband_vrts"

    if not tindex_gdf_ap_tiles.empty:
        create_dirs["apply_images_dir"] = dir_out / "apply_images"

    if not tindex_gdf_tr_tiles.empty:
        create_dirs["train_images_dir"] = dir_out / "train_images"
        create_dirs["train_masks_dir"] = dir_out / "train_masks"
        create_dirs["val_images_dir"] = dir_out / "val_images"
        create_dirs["val_masks_dir"] = dir_out / "val_masks"
        # Note: Only create dir, if test data given
        if any(tindex_gdf_tr_tiles["testing"] == "yes"):
            create_dirs["test_images_dir"] = dir_out / "test_images"
            create_dirs["test_masks_dir"] = dir_out / "test_masks"

    for create_dir in create_dirs.values():
        create_dir.mkdir(parents=True, exist_ok=True)

    tile_dict_all = []
    if not tindex_gdf_ap_tiles.empty:
        all_apply_tiles = get_tile_infos(input_dir, ttype="apply")
        tile_dict_all += all_apply_tiles

    if not tindex_gdf_tr_tiles.empty:
        all_train_tiles = get_tile_infos(
            input_dir,
            ttype="training",
            tindex_gdf=tindex_gdf_tr_tiles,
        )

        # check the train tiles for wrong values in the label file
        train_gpkgs = [tile["label_gpkg"] for tile in all_train_tiles]
        allowed_vals_str = set([*class_values, no_class_value])
        allowed_vals = [int(i) for i in allowed_vals_str]
        for gpkg in train_gpkgs:
            driver = ogr.GetDriverByName("GPKG")
            ds = driver.Open(gpkg, 0)
            layer = ds.GetLayer()
            for feature in layer:
                val = feature.GetField(class_col)
                if val not in allowed_vals:
                    grass.fatal(
                        _(
                            f"File {gpkg} contains unexpected value {val} "
                            f"in column {class_col}. Allowed values are "
                            f"{allowed_vals}.",
                        ),
                    )
        tile_dict_all += all_train_tiles

    # prepare imagery/ndsm data as needed
    # argument list for parallel processing
    arglist = []
    args = []
    for tiledict in tile_dict_all:
        out_img_dir = None
        singleband_vrt_dir = create_dirs["singleband_vrt_dir"]
        if tiledict["type"] == "training":
            out_img_dir = create_dirs["train_images_dir"]
        elif tiledict["type"] == "validation":
            out_img_dir = create_dirs["val_images_dir"]
        elif tiledict["type"] == "testing":
            out_img_dir = create_dirs["test_images_dir"]
        elif tiledict["type"] == "apply":
            out_img_dir = create_dirs["apply_images_dir"]
        tiledict["out_img_dir"] = out_img_dir
        args = [
            out_img_dir,
            tiledict["imagery_tif"],
            tiledict["ndom_tif"],
            tiledict["id"],
            singleband_vrt_dir,
        ]
        arglist.append(args)

    # execute in Parallel
    # source: https://miguendes.me/how-to-pass-multiple-arguments-to-a-map
    # -function-in-python#problem-2-passing-multiple-parameters-to-
    # multiprocessing-poolmap
    # actually it is not really necessary to do in parallel as we only create
    # .vrts... but here is the code
    grass.message(_("Compiling required .vrt files..."))
    with Pool(processes=nprocs) as pool:
        pool.starmap(build_vrts, arglist)

    # loop over tiles
    if not tindex_gdf_tr_tiles.empty:
        grass.message(_("Checking and rasterizing labels..."))
        queue = ParallelModuleQueue(nprocs=nprocs)
        try:
            for tiledict in tile_dict_all:
                outdir = None
                if tiledict["type"] == "training":
                    outdir = create_dirs["train_masks_dir"]
                elif tiledict["type"] == "validation":
                    outdir = create_dirs["val_masks_dir"]
                elif tiledict["type"] == "testing":
                    outdir = create_dirs["test_masks_dir"]
                outfile = os.path.join(outdir, f"{tiledict['id']}.tif")
                new_mapset = f"tmp_mapset_{tiledict['id']}_{ID}"
                rm_mapsets.append(new_mapset)
                # Create new env with new GISRC, to avoid parallel access of same GISRC
                _orig_mapset, worker_env, worker_gisrc = create_grass_env(
                    new_mapset
                )
                rm_gisrcs.append(worker_gisrc)
                worker = Module(
                    "m.neural_network.preparedata_part2.worker_label",
                    input=tiledict["label_gpkg"],
                    img_path=tiledict["imagery_tif"],
                    class_values=class_values,
                    no_class_value=no_class_value,
                    class_column=class_col,
                    reclassify_rules=reclassify_rules,
                    num_null_cells_label=num_null_cells_label,
                    output=outfile,
                    run_=False,
                    env_=worker_env,
                )
                worker.stdout_ = grass.PIPE
                worker.stderr_ = grass.PIPE
                queue.put(worker)
            queue.wait()
        except Exception:
            check_parallel_errors(queue)
        # needed to catch the warnings from the worker
        check_parallel_warnings(queue)
        verify_mapsets(cur_mapset)
    # only keep the output if everything worked
    rm_dirs.remove(output)
    grass.message(_("Data preparation completed."))


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
