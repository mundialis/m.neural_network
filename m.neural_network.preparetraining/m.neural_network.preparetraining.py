#!/usr/bin/env python3
"""############################################################################
#
# MODULE:       m.neural_network.preparetraining
# AUTHOR(S):    Guido Riembauer
# PURPOSE:      Prepares tiled imagery and labelled data for training and application
#               in a Neural Network (NN).
#
# COPYRIGHT:	(C) 2024 by mundialis and the GRASS Development Team.
#
# 		This program is free software under the GNU General Public
# 		License (v3). Read the file COPYING that comes with GRASS
# 		for details.
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

# %option G_OPT_M_DIR
# % key: input_traindir
# % label: Name of the input training data directory containing subfolders with imagery and labels per tile
# % guisection: Input
# %end

# %option G_OPT_M_DIR
# % key: input_applydir
# % label: Name of the input apply data directory containing subfolders with imagery per tile
# % guisection: Input
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

# %option
# % key: output
# % type: string
# % required: yes
# % multiple: no
# % label: Name of the output directory
# % guisection: Output
# %end

# %option G_OPT_M_NPROCS
# %end

import atexit
import os
import random
from multiprocessing import Pool

import grass.script as grass
from grass.pygrass.modules import Module, ParallelModuleQueue
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass_gis_helpers.parallel import (
    check_parallel_errors,
    check_parallel_warnings,
)
from osgeo import gdal, ogr

# initialize global vars
ID = grass.tempname(8)
ORIG_REGION = None
rm_dirs = []


def cleanup():
    """Pass args to the general cleanup from grass-gis-helpers."""
    general_cleanup(orig_region=ORIG_REGION, rm_dirs=rm_dirs)


def get_tile_infos(in_dir, ttype):
    """Read tile-wise directory and saves metadata in a list of dicts."""
    all_tiles = []
    # get all training_tiles and split into training and validation
    for tile in os.listdir(in_dir):
        tiledir = os.path.join(in_dir, tile)
        tiledict = {}
        if os.path.isdir(tiledir) and tile.startswith("tile_"):
            tiledict["id"] = tile
            tiledict["type"] = ttype
            tiledict["dop_tif"] = os.path.join(tiledir, f"image_{tile}.tif")
            tiledict["ndom_tif"] = os.path.join(
                tiledir,
                f"ndsm_1_255_{tile}.tif",
            )
            checklist = [tiledict["dop_tif"], tiledict["ndom_tif"]]
            if ttype == "training":
                tiledict["label_gpkg"] = os.path.join(
                    tiledir,
                    f"label_{tile}.gpkg",
                )
                checklist.append(tiledict["label_gpkg"])

            # check if they exist
            for f in checklist:
                if not os.path.isfile(f):
                    grass.fatal(_(f"File {f} expected but no found."))

            all_tiles.append(tiledict)
    return all_tiles


def vrt_absolute_paths(vrt, abs_paths, rel_paths):
    """
    Change absolute to relative paths in a .vrt
    :param vrt: String: Path to the vrt
    :param abs_paths: List: absolute paths to be replaced
    :param rel_paths: List: relative paths to replace the absolute paths with
    """
    with open(vrt, "r") as file:
        data = file.read()
        data = data.replace('relativeToVRT="0"', 'relativeToVRT="1"')
        for abs_path, rel_path in zip(abs_paths, rel_paths):
            data = data.replace(abs_path, rel_path)
    with open(vrt, "w") as file:
        file.write(data)


def build_vrts(outdir, dop, ndom, tile_id, singleband_vrt_dir):
    """Build the required .vrt files."""
    src_ds = gdal.Open(dop)
    band_count = 0
    if src_ds is not None:
        band_count = int(src_ds.RasterCount)
    else:
        grass.fatal(_(f"File {dop} is empty."))
    src_ds = None

    vrt_input = []
    for num in range(1, band_count + 1):
        band_vrt = os.path.join(singleband_vrt_dir, f"{tile_id}_{num}.vrt")
        vrt_options_sep = gdal.BuildVRTOptions(bandList=[num])
        gdal.BuildVRT(band_vrt, [dop], options=vrt_options_sep)
        # replace absolute with relative path
        rel_path = os.path.relpath(dop, start=singleband_vrt_dir)
        vrt_absolute_paths(band_vrt, abs_paths=[dop], rel_paths=[rel_path])
        vrt_input.append(band_vrt)

    # create vrt
    vrt_input.append(ndom)
    rel_paths = [os.path.relpath(target, start=outdir) for target in vrt_input]
    bands_e_vrt = os.path.join(outdir, f"{tile_id}.vrt")
    vrt_options = gdal.BuildVRTOptions(separate=True)
    gdal.BuildVRT(bands_e_vrt, vrt_input, options=vrt_options)
    # replace absolute with relative paths
    vrt_absolute_paths(bands_e_vrt, abs_paths=vrt_input, rel_paths=rel_paths)
    return bands_e_vrt


def main():
    """Run training and apply data preparation."""
    global ORIG_REGION, rm_dirs

    train_dir_in = options["input_traindir"]
    apply_dir_in = options["input_applydir"]
    val_percentage = int(options["val_percentage"])
    nprocs = set_nprocs(int(options["nprocs"]))
    class_col = options["class_column"]
    class_values = options["class_values"].split(",")
    no_class_value = options["no_class_value"]
    output = options["output"]

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]

    # save orginal region
    ORIG_REGION = f"orig_region_{ID}"
    grass.run_command("g.region", save=ORIG_REGION, quiet=True)

    try:
        os.makedirs(output, exist_ok=False)
    except FileExistsError:
        grass.fatal(_(f"Directory {output} exists already."))

    rm_dirs.append(output)
    # create folders if they dont exist
    train_dir_out = os.path.join(output, "train")
    apply_dir_out = os.path.join(output, "apply")
    train_train_img_dir = os.path.join(train_dir_out, "train_images")
    train_train_masks_dir = os.path.join(train_dir_out, "train_masks")
    train_val_images_dir = os.path.join(train_dir_out, "val_images")
    train_val_masks_dir = os.path.join(train_dir_out, "val_masks")
    train_singleband_vrt_dir = os.path.join(train_dir_out, "singleband_vrts")
    apply_train_img_dir = os.path.join(apply_dir_out, "train_images")
    apply_train_masks_dir = os.path.join(apply_dir_out, "train_masks")
    apply_val_images_dir = os.path.join(apply_dir_out, "val_images")
    apply_val_masks_dir = os.path.join(apply_dir_out, "val_masks")
    apply_singleband_vrt_dir = os.path.join(apply_dir_out, "singleband_vrts")
    for c_dir in [
        train_dir_out,
        apply_dir_out,
        train_train_img_dir,
        train_train_masks_dir,
        train_val_images_dir,
        train_val_masks_dir,
        apply_train_img_dir,
        apply_train_masks_dir,
        apply_val_images_dir,
        apply_val_masks_dir,
        train_singleband_vrt_dir,
        apply_singleband_vrt_dir,
    ]:
        os.makedirs(c_dir, exist_ok=True)

    all_train_tiles = get_tile_infos(train_dir_in, ttype="training")
    all_apply_tiles = get_tile_infos(apply_dir_in, ttype="apply")

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

    # split into training and validation
    num_val_tiles = round(val_percentage / 100.0 * len(all_train_tiles))
    random.shuffle(all_train_tiles)
    val_tiles = all_train_tiles[:num_val_tiles]
    train_tiles = [x for x in all_train_tiles if x not in val_tiles]
    grass.message(
        _(
            f"Selected {len(val_tiles)} tiles as validation tiles and "
            f"{len(train_tiles)} as training tiles.",
        ),
    )
    for d in val_tiles:
        d["type"] = "validation"

    # prepare imagery/ndsm data as needed
    # argument list for parallel processing
    arglist = []
    args = []
    for tiledict in train_tiles + val_tiles + all_apply_tiles:
        out_img_dir = None
        singleband_vrt_dir = None
        if tiledict["type"] == "training":
            out_img_dir = train_train_img_dir
            singleband_vrt_dir = train_singleband_vrt_dir
        elif tiledict["type"] == "validation":
            out_img_dir = train_val_images_dir
            singleband_vrt_dir = train_singleband_vrt_dir
        elif tiledict["type"] == "apply":
            out_img_dir = apply_val_images_dir
            singleband_vrt_dir = apply_singleband_vrt_dir
        tiledict["out_img_dir"] = out_img_dir
        args = [
            out_img_dir,
            tiledict["dop_tif"],
            tiledict["ndom_tif"],
            tiledict["id"],
            singleband_vrt_dir,
        ]
        arglist.append(args)

    # a single .vrt should be placed next to the train dirs for the NN code
    # to read the number of bands
    example_args = arglist[0]
    example_args[0] = train_dir_out
    build_vrts(*example_args)

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
    grass.message(_("Checking and rasterizing labels..."))
    queue = ParallelModuleQueue(nprocs=nprocs)
    try:
        for tiledict in train_tiles + val_tiles:
            outdir = None
            if tiledict["type"] == "training":
                outdir = train_train_masks_dir
            elif tiledict["type"] == "validation":
                outdir = train_val_masks_dir
            outfile = os.path.join(outdir, f"{tiledict['id']}.tif")
            new_mapset = f"tmp_mapset_{tiledict['id']}_{ID}"
            rm_dirs.append(os.path.join(gisdbase, location, new_mapset))
            worker = Module(
                "m.neural_network.preparetraining.worker",
                input=tiledict["label_gpkg"],
                img_path=tiledict["dop_tif"],
                class_values=class_values,
                no_class_value=no_class_value,
                class_column=class_col,
                output=outfile,
                new_mapset=new_mapset,
                run_=False,
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
    grass.message(_("Training data preparation completed."))


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
