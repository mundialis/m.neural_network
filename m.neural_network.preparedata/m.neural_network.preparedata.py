#!/usr/bin/env python3

############################################################################
#
# MODULE:       m.neural_network.preparedata
#
# AUTHOR(S):    Anika Weinmann, Guido Riembauer and Victoria-Leandra Brunn
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
# % keyword: export
# % keyword: neural network
# % keyword: preparation
# %end

# %option G_OPT_R_INPUTS
# % key: image_bands
# % label: The names of imagery raster bands, e.g. for DOPs RGBI raster bands
# % description: The first raster defines the output resolution
# % guisection: Input
# %end

# %option G_OPT_R_INPUT
# % key: ndsm
# % label: Name of the nDSM raster
# % answer: ndsm
# % guisection: Input
# %end

# %option G_OPT_V_INPUT
# % key: reference
# % required: no
# % label: Name of the reference vector map
# % guisection: Optional input
# %end

# %option
# % key: tile_size
# % type: integer
# % required: yes
# % label: Size of the created tiles in cells
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

# %option
# % key: train_percentage
# % type: integer
# % required: no
# % label: The percentage of data set for which the training data should be prepared
# % answer: 30
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

import atexit
import json
import os
import random

import grass.script as grass
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass.pygrass.modules import Module, ParallelModuleQueue


# initialize global vars
ID = grass.tempname(8)
# rm_rasters = list()
# rm_groups = list()
# rm_vectors = list()
rm_files = list()
# rm_regions = list()
orig_region = None
rm_dirs = []
# nprocs = -2


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


def cleanup():
    general_cleanup(orig_region=orig_region)  # TODO rm_dirs, rm_files


def export_tindex(output_dir, geojson_dict):
    """Export tile index from geojson_dict.

    Export of tile index and verification of correct gpkg file.

    Args:
        output_dir (str): The output directory where the tile index should be
                          exported
        geojson_dict (dict): The dictionary with the tile index
    """
    geojson_file = os.path.join(output_dir, "tindex.geojson")
    gpkg_file = os.path.join(output_dir, "tindex.gpkg")
    rm_files.append(geojson_file)
    with open(geojson_file, "w") as f:
        json.dump(geojson_dict, f, indent=4)
    # create GPKG from GeoJson
    stream = os.popen(f"ogr2ogr {gpkg_file} {geojson_file}")
    stream.read()

    # verify
    print("Verifying vector tile index:")
    stream = os.popen(f"ogrinfo -so -al {gpkg_file}")
    tindex_verification = stream.read()
    print(tindex_verification)


def main():
    global orig_region, rm_files

    image_bands = options["image_bands"].split(",")
    ndsm = options["ndsm"]
    reference = options["reference"]
    tile_size = int(options["tile_size"])
    tile_overlap = int(options["tile_overlap"])
    segmentation_minsize = int(options["segmentation_minsize"])
    segmentation_threshold = float(options["segmentation_threshold"])
    train_percentage = int(options["train_percentage"])
    output_dir = options["output_dir"]
    nprocs = set_nprocs(int(options["nprocs"]))

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]

    # save orginal region
    orig_region = f"orig_region_{ID}"
    grass.run_command("g.region", save=orig_region, quiet=True)

    # set region
    grass.run_command("g.region", raster=image_bands[0], quiet=True)
    reg = grass.region()

    # parameter for tiles
    res = reg["nsres"]
    tile_size_map_units = tile_size * res
    tile_overlap_map_units = tile_overlap * res

    # create GeoJson for tindex
    epsg_code = grass.parse_command("g.proj", flags="g")["srid"].split(":")[-1]

    geojson_dict = {
        "type": "FeatureCollection",
        "name": "tindex",
        "crs": {
            "type": "name",
            "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_code}"},
        },
        "features": [],
    }

    # start values
    north = reg["n"]
    num_tiles_row = round(reg["rows"] / (tile_size - tile_overlap) + 0.5)
    num_tiles_col = round(reg["cols"] / (tile_size - tile_overlap) + 0.5)
    num_zeros = max([len(str(num_tiles_row)), len(str(num_tiles_col))])

    # loop over tiles
    queue = ParallelModuleQueue(nprocs=nprocs)
    num = 0
    try:
        for row in range(num_tiles_row):
            west = reg["w"]
            for col in range(num_tiles_col):
                print(f"row {row} - col {col}")
                row_str = str(row).zfill(num_zeros)
                col_str = str(col).zfill(num_zeros)
                tile_id = f"{row_str}{col_str}"
                tile_name = f"tile_{row_str}_{col_str}"
                new_mapset = f"tmp_mapset_{ID}_{tile_id}"
                rm_dirs.append(os.path.join(gisdbase, location, new_mapset))

                # set tile region
                south = north - tile_size_map_units
                east = west + tile_size_map_units

                # worker to request the null cells to get the info if the tile
                # can be a training data tile
                worker_nullcells = Module(
                    "m.neural_network.preparedata.worker_nullcells",
                    n=north,
                    s=south,
                    e=east,
                    w=west,
                    res=res,
                    map=image_bands[0],
                    tile_name=num,
                    new_mapset=new_mapset,
                    run_=False,
                )
                worker_nullcells.stdout_ = grass.PIPE
                queue.put(worker_nullcells)

                # create tile for tindex
                feat = {
                    "type": "Feature",
                    "properties": {
                        "fid": tile_id,
                        "name": tile_name,
                        "path": "",
                        "training": "false",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [west, north],
                                [east, north],
                                [east, south],
                                [west, south],
                                [west, north],
                            ]
                        ],
                    },
                }
                geojson_dict["features"].append(feat)

                # set region west for next tile
                west += tile_size_map_units - tile_overlap_map_units
                num += 1
            north -= tile_size_map_units - tile_overlap_map_units
        queue.wait()
    except Exception:
        check_parallel_errors(queue)

    verify_mapsets(cur_mapset)

    possible_tr_data = []
    tiles_with_data = []
    for proc in queue.get_finished_modules():
        stdout_strs = proc.outputs["stdout"].value.strip().split(":")
        null_cells = int(stdout_strs[1].strip())
        num = int(stdout_strs[0].split(" ")[2])
        if null_cells == 0:
            possible_tr_data.append(num)
        if null_cells != tile_size * tile_size:
            tiles_with_data.append(num)

    # random split into train and apply data tiles
    num_tr_tiles = round(train_percentage / 100.0 * len(possible_tr_data))
    random.shuffle(possible_tr_data)
    tr_tiles = possible_tr_data[:num_tr_tiles]
    ap_tiles = [x for x in tiles_with_data if x not in tr_tiles]

    # loop over training data
    queue_export_tr = ParallelModuleQueue(nprocs=nprocs)
    try:
        for tr_tile in tr_tiles:
            tile_name = geojson_dict["features"][tr_tile]["properties"]["name"]
            tile_path = os.path.join(output_dir, "train", tile_name)
            # update jeojson values
            geojson_dict["features"][tr_tile]["properties"][
                "training"
            ] = "TODO"
            geojson_dict["features"][tr_tile]["properties"]["path"] = tile_path
            # worker for export
            worker_export_tr = Module(
                "m.neural_network.preparedata.worker_export",
                image_bands=image_bands,
                ndsm=ndsm,
                reference=reference,
                segmentation_minsize=segmentation_minsize,
                segmentation_threshold=segmentation_threshold,
                output_dir=tile_path,
                new_mapset=new_mapset,
                flags="t",
                run_=False,
            )
            worker_export_tr.stdout_ = grass.PIPE
            queue_export_tr.put(worker_export_tr)
        queue_export_tr.wait()
    except Exception:
        check_parallel_errors(queue_export_tr)
    verify_mapsets(cur_mapset)

    # loop over apply data
    queue_export_ap = ParallelModuleQueue(nprocs=nprocs)
    try:
        for ap_tile in ap_tiles:
            tile_name = geojson_dict["features"][ap_tile]["properties"]["name"]
            tile_path = os.path.join(output_dir, "apply", tile_name)
            # update jeojson values
            geojson_dict["features"][ap_tile]["properties"]["training"] = "no"
            geojson_dict["features"][ap_tile]["properties"]["path"] = tile_path
            # worker for export
            worker_export_ap = Module(
                "m.neural_network.preparedata.worker_export",
                image_bands=image_bands,
                ndsm=ndsm,
                output_dir=tile_path,
                new_mapset=new_mapset,
                run_=False,
            )
            worker_export_ap.stdout_ = grass.PIPE
            queue_export_ap.put(worker_export_ap)
        queue_export_ap.wait()
    except Exception:
        check_parallel_errors(queue_export_ap)
    verify_mapsets(cur_mapset)

    import pdb

    pdb.set_trace()

    # export tindex
    export_tindex(output_dir, geojson_dict)
    grass.message(_("Prepare data done"))
    # TODO: tile XY soll doch auch gelabelt werden, wie da trees / segementierung noch erstellen


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
