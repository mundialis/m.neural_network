#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.index
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
# % description: The raster defines the output resolution and will be used for checking null-cells
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

# %option
# % key: train_percentage
# % type: integer
# % required: no
# % label: The percentage of data set for which the training data should be prepared
# % answer: 30
# % guisection: Optional input
# %end

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

# %flag
# % key: t
# % label: Only training
# % description: Option for all input data should be used as training data for the neural network
# %end

# %flag
# % key: a
# % label: Only application
# % description: Option for only neural network application and no data are prepared for training
# %end

# %flag
# % key: s
# % label: Skip null cell check
# % description: Option for skipping the check for null cells in the tiles. This can be used if the user is sure that there are no null cells in the input data and wants to save time by skipping this step. If this flag is set, all tiles will be exported as training and application data according to the given percentage, even if they contain null cells. This speeds up processing.
# %end

# %flag
# % key: b
# % label: (buffered) AOI intersects with tiles
# % description: Recommended, when tindex is used for final application of model. I.e. when complete AOI should be classified, and even a little more tiles are classifed, to ensure gap free classification at the borders of AOI.
# %end

# %flag
# % key: w
# % label: AOI completely within tiles
# % description: Recommended, e.g. for training tiles. I.e. when tiles should be completely within AOI (for which input data are prepared).
# %end

# %rules
# % excludes: -s,-a
# % exclusive: -t,-a
# % excludes: -t, train_percentage
# % excludes: -a, train_percentage
# % requires: aoi,-b,-w
# % requires: -w,aoi
# % requires: -b,aoi
# % exclusive: -b,-w
# %end


import atexit
import json
import os
import random
import shutil

import geopandas as gpd
import grass.script as grass
from grass.pygrass.modules import Module, ParallelModuleQueue
from grass.pygrass.utils import get_lib_path
from grass_gis_helpers.cleanup import general_cleanup
from grass_gis_helpers.general import check_installed_addon, set_nprocs
from grass_gis_helpers.mapset import verify_mapsets
from grass_gis_helpers.parallel import check_parallel_errors

# initialize global vars
ID = grass.tempname(8)
rm_files = list()
ORIG_REGION = None
rm_dirs = []
rm_vectors = []


def cleanup() -> None:
    """Clean up function calling general clean up from grass_gis_helpers."""
    general_cleanup(
        orig_region=ORIG_REGION,
        rm_dirs=rm_dirs,
        rm_files=rm_files,
        rm_vectors=rm_vectors,
    )


def export_tindex(output_dir, geojson_dict, etc_path) -> None:
    """Export tile index from geojson_dict.

    Export of tile index and verification of correct gpkg file.

    Args:
        output_dir (str): The output directory where the tile index should be
                          exported
        geojson_dict (dict): The dictionary with the tile index
        etc_path (str): The addon etc path

    """
    geojson_file = os.path.join(output_dir, "tindex.geojson")
    gpkg_file = os.path.join(output_dir, "tindex.gpkg")
    rm_files.append(geojson_file)
    with open(geojson_file, "w", encoding="utf-8") as f:
        json.dump(geojson_dict, f, indent=4)
    # create GPKG from GeoJson
    stream = os.popen(f"ogr2ogr {gpkg_file} {geojson_file}")
    stream.read()

    # verify
    print("Verifying vector tile index:")
    stream = os.popen(f"ogrinfo -so -al {gpkg_file}")
    tindex_verification = stream.read()
    print(tindex_verification)

    # copy qml file
    qml_src_file = os.path.join(etc_path, "qml", "tindex.qml")
    qml_dest_file = os.path.join(output_dir, "tindex.qml")
    shutil.copyfile(qml_src_file, qml_dest_file)


def main() -> None:
    """Prepare training data.

    Main function for creation of the tile index and preparation of the
    training data. The function creates the tile index as GeoJson and exports
    it as GPKG. It also checks which tiles can be used for training
    (no null cells) and which tiles have no data at all (only null cells).
    The tiles with no data are removed from the tile index and the tiles with
    possible training data are randomly split into train and apply data
    according to the given percentage.
    """
    global ORIG_REGION

    # TODO:
    # automatic test/train split aus split_train_test_data.py übernehmen, dabei
    # nochmal auf die flags sehen, ob diese alle Sinn machen

    aoi = options["aoi"]
    tile_size = int(options["tile_size"])
    tile_overlap = int(options["tile_overlap"])
    output_dir = options["output_dir"]
    nprocs = set_nprocs(int(options["nprocs"]))
    image_band = options["image_band"]
    suffix = options["suffix"]

    # check tile_size devisible by 16
    if tile_size % 16 != 0:
        grass.fatal(_("<tile_size> is not devisible by 16!"))
    if flags["a"]:
        train_percentage = 0  # no training, only application preparation
    elif flags["t"]:
        train_percentage = 100  # all input for training
    else:
        train_percentage = int(options["train_percentage"])

    check_installed_addon(
        "v.out.geojson", url="https://github.com/mundialis/v.out.geojson"
    )

    # get addon etc path
    etc_path = get_lib_path(modname="m.neural_network.tindex")
    if etc_path is None:
        grass.fatal("Unable to find qml files!")

    os.makedirs(output_dir, exist_ok=True)

    # get location infos
    gisenv = grass.gisenv()
    cur_mapset = gisenv["MAPSET"]
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]

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
        if flags["b"]:
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

    # parameter for tiles
    tile_size_map_units = tile_size * res
    tile_overlap_map_units = tile_overlap * res

    # start values
    north = reg["n"]
    num_tiles_row = round(reg["rows"] / (tile_size - tile_overlap) + 0.5)
    num_tiles_col = round(reg["cols"] / (tile_size - tile_overlap) + 0.5)
    num_zeros = max([len(str(num_tiles_row)), len(str(num_tiles_col))])
    num_tiles_total = num_tiles_col * num_tiles_row

    # create GeoJson for tindex
    epsg_code = grass.parse_command("g.proj", flags="g")["srid"].split(":")[-1]
    geojson_dict = init_tindex(num_tiles_total, epsg_code)
    # loop over tiles
    idx = 0
    for row in range(num_tiles_row):
        west = reg["w"]
        for col in range(num_tiles_col):
            grass.message(
                _(
                    f"Creating polygon for: row {row} - col {col} (total "
                    f"{num_tiles_row} x {num_tiles_col})"
                ),
            )
            # set tile region
            south = north - tile_size_map_units
            east = west + tile_size_map_units

            add_tile_to_tindex(
                suffix,
                north,
                num_zeros,
                geojson_dict,
                idx,
                row,
                west,
                col,
                south,
                east,
            )

            # set region west for next tile
            west += tile_size_map_units - tile_overlap_map_units
            idx += 1
        north -= tile_size_map_units - tile_overlap_map_units

    # check which polygons intersects with aoi otherwise take all grid tiles
    if aoi:
        if flags["b"]:
            check_tile_intersection_with_aoi(
                aoi_buf, "intersects", epsg_code, geojson_dict
            )
        if flags["w"]:
            check_tile_intersection_with_aoi(
                aoi, "within", epsg_code, geojson_dict
            )

    # only for training data
    if not flags["a"]:
        if not flags["s"]:
            # Check if tile has no null cells inside and can be used for training
            possible_tr_data, no_possible_tr_data = (
                remove_tiles_with_null_cells(
                    tile_size,
                    nprocs,
                    image_band,
                    cur_mapset,
                    gisdbase,
                    location,
                    res,
                    geojson_dict,
                )
            )

            # remove null-cell-tiles when t-flag (all tiles for training)
            # null-cell-tiles are then not exported at all (not even as apply tile)
            if flags["t"]:
                no_possible_tr_data.reverse()
                for num in no_possible_tr_data:
                    del geojson_dict["features"][num]
        else:
            grass.message(_("Skipping null cell check for tiles!"))

        # random split into train and apply data tiles
        num_tr_tiles = round(train_percentage / 100.0 * num_tiles_total)
        if len(possible_tr_data) < num_tr_tiles:
            num_tr_tiles = len(possible_tr_data)
            true_train_percentage = round(num_tr_tiles / num_tiles_total * 100)
            grass.warning(
                _(
                    "Too many border tiles including null values. To "
                    "ensure valid train tiles, the train percentage is "
                    f"reduced to {true_train_percentage}.",
                ),
            )
        random.shuffle(possible_tr_data)
        tr_tiles = possible_tr_data[:num_tr_tiles]
        for tr_tile in tr_tiles:
            geojson_dict["features"][tr_tile]["properties"][
                "training"
            ] = "TODO"

    # export tindex
    export_tindex(output_dir, geojson_dict, etc_path)

    grass.message(_("Prepare data done"))


def remove_tiles_with_null_cells(
    tile_size,
    nprocs,
    image_band,
    cur_mapset,
    gisdbase,
    location,
    res,
    geojson_dict,
):
    """Remove tiles with null cells."""
    queue_nullcheck = ParallelModuleQueue(nprocs=nprocs)
    num = 0
    try:
        for tile in geojson_dict["features"]:
            tile_id = tile["properties"]["fid"]
            grass.message(
                _(f"Checking null cells for tile: {tile_id}"),
            )
            north = tile["geometry"]["coordinates"][0][0][1]
            south = tile["geometry"]["coordinates"][0][2][1]
            west = tile["geometry"]["coordinates"][0][0][0]
            east = tile["geometry"]["coordinates"][0][1][0]
            new_mapset = f"tmp_mapset_{ID}_{tile_id}"
            rm_dirs.append(os.path.join(gisdbase, location, new_mapset))
            # worker to request the null cells to get the info if the tile
            # can be a training data tile
            worker_nullcells = Module(
                "m.neural_network.preparedata_part1.worker_nullcells",
                n=north,
                s=south,
                e=east,
                w=west,
                res=res,
                map=image_band,
                tile_name=num,
                new_mapset=new_mapset,
                run_=False,
            )
            worker_nullcells.stdout_ = grass.PIPE
            worker_nullcells.stderr_ = grass.PIPE
            queue_nullcheck.put(worker_nullcells)
            num += 1
        queue_nullcheck.wait()
    except Exception:
        check_parallel_errors(queue_nullcheck)
    verify_mapsets(cur_mapset)

    # create lists with possible training data tiles and tiles with no
    # possible training data (tiles with null cells) based on the number of
    # null cells in the tile. Also create a list with tiles without data
    # (only null cells) to remove the latter from the tile index.
    possible_tr_data = []
    no_possible_tr_data = []
    tiles_wo_data = []
    for proc in queue_nullcheck.get_finished_modules():
        stdout_strs = proc.outputs["stdout"].value.strip().split(":")
        null_cells = int(stdout_strs[1].strip())
        num = int(stdout_strs[0].split(" ")[2])
        if null_cells == 0:
            # tile with possible training data, no null cells
            possible_tr_data.append(num)
        else:
            no_possible_tr_data.append(num)
        if null_cells != tile_size * tile_size:
            # tile with data, can be used for application
            continue
        # tile without data, only null cells, remove from tile index
        tiles_wo_data.append(num)
    # remove tiles without data
    tiles_wo_data.reverse()
    for num in tiles_wo_data:
        del geojson_dict["features"][num]
    return possible_tr_data, no_possible_tr_data


def check_tile_intersection_with_aoi(
    aoi_buf, aoi_intersection, epsg_code, geojson_dict
):
    """Check which tiles of the grid intersect with the area of interest (AOI)
    and keep only those in the tile index.
    """
    grid_gdf = gpd.GeoDataFrame.from_features(geojson_dict["features"])
    aoi_dict = json.loads(
        grass.read_command(
            "v.out.geojson", input=aoi_buf, output="-", epsg=epsg_code
        )
    )
    aoi_gdf = gpd.GeoDataFrame.from_features(aoi_dict["features"])
    aoi_gdf.drop(
        aoi_gdf.columns.difference(["geometry"]), axis=1, inplace=True
    )
    # intersection of aoi_buf and grid (https://geopandas.org/en/stable/
    # docs/user_guide/mergingdata.html#binary-predicate-joins)
    grid_aoi_gdf = gpd.sjoin(
        left_df=grid_gdf,
        right_df=aoi_gdf,
        how="inner",
        predicate=aoi_intersection,
    )
    # cleanup columns
    for col in grid_aoi_gdf.columns:
        print(col)
        if col not in {
            "geometry",
            "fid",
            "name",
            "path",
            "training",
            "testing",
        }:
            grid_aoi_gdf.drop(col, axis=1, inplace=True)
    geojson_dict["features"] = grid_aoi_gdf.to_geo_dict()["features"]


def add_tile_to_tindex(
    suffix, north, num_zeros, geojson_dict, idx, row, west, col, south, east
):
    """Add tile to tindex GeoJson dictionary."""
    row_str = str(row).zfill(num_zeros)
    col_str = str(col).zfill(num_zeros)
    tile_id = f"{row_str}{col_str}"
    tile_name = f"tile_{row_str}_{col_str}"
    if options["suffix"]:
        tile_name += f"_{suffix}"

    # create tile for tindex
    feat = {
        "type": "Feature",
        "properties": {
            "fid": tile_id,
            "name": tile_name,
            "path": "",
            "training": "no",
            "testing": "no",
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
                ],
            ],
        },
    }
    geojson_dict["features"][idx] = feat


def init_tindex(num_tiles_total, epsg_code):
    """Initialize tile index as GeoJson dictionary."""
    return {
        "type": "FeatureCollection",
        "name": "tindex",
        "crs": {
            "type": "name",
            "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_code}"},
        },
        "features": [
            # Polygon initialized with default values to allocate memory
            {
                "type": "Feature",
                "properties": {
                    "fid": "fid_TODO",
                    "name": "tile_name_TODO",
                    "path": "",
                    "training": "no",
                    "testing": "no",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [99999.9, 99999.9],
                            [99999.9, 99999.9],
                            [99999.9, 99999.9],
                            [99999.9, 99999.9],
                            [99999.9, 99999.9],
                        ],
                    ],
                },
            }
        ]
        * num_tiles_total,
    }


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
