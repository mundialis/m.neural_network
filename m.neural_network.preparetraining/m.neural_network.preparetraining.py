#!/usr/bin/env python3

############################################################################
#
# MODULE:       m.neural_network.preparetraining
#
# AUTHOR(S):    Guido Riembauer
#
# PURPOSE:      TODO.
#
# COPYRIGHT:	(C) 2024 by mundialis and the GRASS Development Team
#
# 		This program is free software under the GNU General Public
# 		License (v3). Read the file COPYING that comes with GRASS
# 		for details.
#
#############################################################################

# %Module
# % description: TODO.
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
# % label: column of the label vector that holds the class number
# % guisection: Parameters
# %end

# %option
# % key: class_value
# % type: integer
# % required: yes
# % multiple: no
# % answer: 2
# % label: Expected and output value for the class of interest
# % guisection: Parameters
# %end

# %option
# % key: no_class_value
# % type: integer
# % required: yes
# % multiple: no
# % answer: 1
# % label: Expected and output value for the non class of interest areas (inverse of <class_value>)
# % guisection: Parameters
# %end

# %option G_OPT_M_NPROCS
# %end

import atexit
from multiprocessing import Pool
import os
import random

import grass.script as grass
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass.pygrass.modules import Module, ParallelModuleQueue
from osgeo import gdal


# initialize global vars
ID = grass.tempname(8)
orig_region = None
rm_dirs = []

def cleanup():
    general_cleanup(orig_region=orig_region, rm_dirs=rm_dirs)

def check_parallel_errors(queue):
    for proc_num in range(queue.get_num_run_procs()):
        proc = queue.get(proc_num)
        if proc.returncode != 0:
            # save all stderr to a variable and pass it to a GRASS
            # exception
            errmsg = proc.outputs["stderr"].value.strip()
            grass.fatal(
                _(f"\nERROR processing <{proc.get_bash()}>: {errmsg}"),
            )

def check_parallel_warnings(queue):
    for mod in queue.get_finished_modules():
        stderr = mod.outputs["stderr"].value.strip()
        # the WARNING might get translated...
        if "WARN" in stderr:
            grass.warning(_(f"\nWARNING processing <{mod.get_bash()}>: {stderr}"))

def get_tile_infos(in_dir, type):
    all_tiles = []
    # get all training_tiles and split into training and validation
    for tile in os.listdir(in_dir):
        tiledir = os.path.join(in_dir, tile)
        tiledict = {}
        if os.path.isdir(tiledir) and tile.startswith("tile_"):
            tiledict["id"] = tile
            tiledict["type"] = type
            tiledict["dop_tif"] = os.path.join(tiledir, f"image_{tile}.tif")
            tiledict["ndom_tif"] = os.path.join(tiledir, f"ndsm_1_255_{tile}.tif")
            checklist = [tiledict["dop_tif"], tiledict["ndom_tif"]]
            if type == "training":
                tiledict["label_gpkg"] = os.path.join(tiledir, f"label_{tile}.gpkg")
                checklist.append(tiledict["label_gpkg"])

            # check if they exist
            for f in checklist:
                if not os.path.isfile(f):
                    grass.fatal(_(f"File {f} expected but no found."))

            all_tiles.append(tiledict)
    return all_tiles

def build_vrts(outdir, dop, ndom, tile_id):
    src_ds = gdal.Open(dop)
    band_count = 0
    if src_ds is not None:
        band_count = int(src_ds.RasterCount)
    else:
        grass.fatal(_(f"File {dop} is empty."))
    src_ds = None

    vrt_input = []
    for num in range(1, band_count + 1):
        band_vrt = os.path.join(outdir, f"{tile_id}_{num}.tif")
        vrt_options_sep = gdal.BuildVRTOptions(bandList=[num])
        gdal.BuildVRT(band_vrt, [dop], options=vrt_options_sep)
        vrt_input.append(band_vrt)
    # create vrt
    vrt_input.append(ndom)
    bands_e_vrt = os.path.join(outdir, f"{tile_id}.vrt")
    vrt_options = gdal.BuildVRTOptions(separate=True)
    gdal.BuildVRT(bands_e_vrt, vrt_input, options=vrt_options)
    return bands_e_vrt

def main():
    global orig_region, rm_dirs

    train_dir = options["input_traindir"]
    apply_dir = options["input_applydir"]
    val_percentage = int(options["val_percentage"])
    nprocs = set_nprocs(int(options["nprocs"]))
    class_col = options["class_column"]
    class_value = options["class_value"]
    no_class_value = options["no_class_value"]

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]

    # save orginal region
    orig_region = f"orig_region_{ID}"
    grass.run_command("g.region", save=orig_region, quiet=True)

    # create folders if they dont exist
    train_train_img_dir = os.path.join(train_dir, "train_images")
    train_train_masks_dir = os.path.join(train_dir, "train_masks")
    train_val_images_dir = os.path.join(train_dir, "val_images")
    train_val_masks_dir = os.path.join(train_dir, "val_masks")
    apply_train_img_dir = os.path.join(apply_dir, "train_images")
    apply_train_masks_dir = os.path.join(apply_dir, "train_masks")
    apply_val_images_dir = os.path.join(apply_dir, "val_images")
    apply_val_masks_dir = os.path.join(apply_dir, "val_masks")
    for c_dir in [train_train_img_dir, train_train_masks_dir, train_val_images_dir, train_val_masks_dir, apply_train_img_dir, apply_train_masks_dir, apply_val_images_dir, apply_val_masks_dir]:
        os.makedirs(c_dir, exist_ok=True)

    all_train_tiles = get_tile_infos(train_dir, type="training")
    all_apply_tiles = get_tile_infos(apply_dir, type="apply")

    # split into training and validation
    num_val_tiles = round(val_percentage / 100.0 * len(all_train_tiles))
    random.shuffle(all_train_tiles)
    val_tiles = all_train_tiles[:num_val_tiles]
    train_tiles = [x for x in all_train_tiles if x not in val_tiles]
    grass.message(_(f"Selected {len(val_tiles)} tiles as validation tiles and "
                    f"{len(train_tiles)} as training tiles."))
    for d in val_tiles:
        d["type"] = "validation"

    # prepare imagery/ndsm data as needed
    # argument list for parallel processing
    arglist = []
    for tiledict in train_tiles + val_tiles + all_apply_tiles:
        out_img_dir = None
        if tiledict["type"] == "training":
            out_img_dir = train_train_img_dir
        elif tiledict["type"] == "validation":
            out_img_dir = train_val_images_dir
        elif tiledict["type"] == "apply":
            out_img_dir = apply_val_images_dir
        tiledict["out_img_dir"] = out_img_dir
        args = (out_img_dir, tiledict["dop_tif"], tiledict["ndom_tif"], tiledict["id"])
        arglist.append(args)

    # execute in Parallel
    # source: https://miguendes.me/how-to-pass-multiple-arguments-to-a-map
    # -function-in-python#problem-2-passing-multiple-parameters-to-
    # multiprocessing-poolmap
    # actually it is not really necessary to do in parallel as we only create
    # .vrts... but here is the code
    grass.message(_("Compiling required .vrt files..."))
    with Pool(processes=nprocs) as pool:
        vrts = pool.starmap(build_vrts, arglist)

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
                class_value=class_value,
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
    grass.message(_("Training data preparation completed."))

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
