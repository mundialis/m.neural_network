#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      tindex_helper.py
# AUTHOR(S):   Anika Weinmann, Lina Krisztian, Guido Riembauer and
#              Victoria-Leandra Brunn
# PURPOSE:     Helper functions for tile index creation.
# SPDX-FileCopyrightText: (c) 2024-2026 by mundialis GmbH & Co. KG and the
#              GRASS Development Team
# SPDX-License-Identifier: GPL-3.0-or-later.
#
#############################################################################
"""

import json
import os
import random
import shutil

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

TINDEX_ATTR_DEFAULT = {
    "fid": "fid_TODO",
    "name": "tile_name_TODO",
    "path": "",
    "training": "no",
    "validation": "no",
    "testing": "no",
    "apply": "no",
}

def make_grid(tile_size, tile_overlap, resolution, region, suffix):
    # parameter for tiles
    tile_size_map_units = tile_size * resolution
    tile_overlap_map_units = tile_overlap * resolution

    # start values
    north = region["n"]
    num_tiles_row = ceil(region["rows"] / (tile_size - tile_overlap))
    num_tiles_col = ceil(region["cols"] / (tile_size - tile_overlap))
    num_zeros = max([len(str(num_tiles_row)), len(str(num_tiles_col))])
    num_tiles_total = num_tiles_col * num_tiles_row

    # create GeoJson for tindex
    epsg_code = grass.parse_command("g.proj", flags="g")["srid"].split(":")[-1]
    geojson_dict = init_tindex(num_tiles_total, epsg_code)
    # loop over tiles
    idx = 0
    for row in range(num_tiles_row):
        west = region["w"]
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
    
    return epsg_code, geojson_dict


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
            # Do via function to ensure independent objects 
            init_tindex_elements() for _ in range(num_tiles_total)
        ]
    }


def init_tindex_elements():
    """Generate single feature elements for tile index"""
    return {
                "type": "Feature",
                "properties": TINDEX_ATTR_DEFAULT.copy(),
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


def add_tile_to_tindex(
    suffix, north, num_zeros, geojson_dict, idx, row, west, col, south, east
):
    """Add tile to tindex GeoJson dictionary."""
    row_str = str(row).zfill(num_zeros)
    col_str = str(col).zfill(num_zeros)
    tile_id = f"{row_str}{col_str}"
    tile_name = f"tile_{row_str}_{col_str}"
    if suffix:
        tile_name += f"_{suffix}"

    # create tile for tindex
    geojson_dict["features"][idx]["properties"]["fid"] = tile_id
    geojson_dict["features"][idx]["properties"]["name"] = tile_name
    geojson_dict["features"][idx]["geometry"]["coordinates"] = [
        [
            [west, north],
            [east, north],
            [east, south],
            [west, south],
            [west, north],
        ],
    ]

def make_2level_grid(
        num_tiles_ind_group_row,
        num_tiles_ind_group_col,
        tile_size,
        tile_overlap,
        res,
        reg,
        suffix,
    ):

    step_px = tile_size - tile_overlap
    # level1-block tile-size
    block_px_r = num_tiles_ind_group_row * step_px + tile_overlap
    block_px_c = num_tiles_ind_group_col * step_px + tile_overlap
    # level1-block tile-size in map units
    block_r_mu = block_px_r * res
    block_c_mu = block_px_c * res
    # total fitting number of level1-blocks in row and column direction
    num_blocks_row = ceil(reg["rows"] / block_px_r)
    num_blocks_col = ceil(reg["cols"] / block_px_c)
    # helper variable for formatting indices
    ind_zeros = max(len(str(num_blocks_row)), len(str(num_blocks_col)))

    all_features = []
    for brow in range(num_blocks_row):
        for bcol in range(num_blocks_col):
            # index for level1-block
            block_id = f"{str(brow).zfill(ind_zeros)}{str(bcol).zfill(ind_zeros)}"

            # adjust region-dict for current level1-block
            # (starting from top left)
            # (just parse dict, no need to change region)
            block_region = {
                "n": reg["n"] - brow * block_r_mu,
                "w": reg["w"] + bcol * block_c_mu,
                "rows": num_tiles_ind_group_row * step_px,
                "cols": num_tiles_ind_group_col * step_px,
            }
            block_suffix = f"block_{block_id}" + (f"_{suffix}" if suffix else "")

            epsg_code, block_geojson_dict = make_grid(
                tile_size, tile_overlap, res, block_region, block_suffix
            )
            for feat in block_geojson_dict["features"]:
                # combine block id and tile id for unique tile id in tindex
                feat["properties"]["fid"] = f"{block_id}_{feat['properties']['fid']}"
                # add attribute with only block id
                feat["properties"]["block"] = block_id
                all_features.append(feat)

    # initialize tindex and append all features of all blocks
    geojson_dict = init_tindex(0, epsg_code)
    geojson_dict["features"] = all_features
    return epsg_code, geojson_dict


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
        # print(col)
        # "block"-attributes only for 2-level-grid 
        if col not in TINDEX_ATTR_DEFAULT.keys() and col != "geometry" and col != "block":
            grid_aoi_gdf.drop(col, axis=1, inplace=True)
    geojson_dict["features"] = grid_aoi_gdf.to_geo_dict()["features"]
    
    return geojson_dict


def remove_tiles_with_null_cells(
    nprocs,
    ID,
    image_band,
    cur_mapset,
    res,
    geojson_dict,
):
    """Remove tiles with null cells."""
    rm_mapsets = list()
    rm_gisrcs = list()
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
            rm_mapsets.append(new_mapset)
            # Create new env with new GISRC, to avoid parallel access of same GISRC
            orig_mapset, worker_env, worker_gisrc = create_grass_env(
                new_mapset
            )
            rm_gisrcs.append(worker_gisrc)
            # worker to request the null cells to get the info if the tile
            # can be a training data tile
            worker_nullcells = Module(
                "m.neural_network.worker_nullcells",
                n=north,
                s=south,
                e=east,
                w=west,
                res=res,
                map=image_band,
                tile_name=num,
                orig_mapset=orig_mapset,
                run_=False,
                env_=worker_env,
            )
            worker_nullcells.stdout_ = grass.PIPE
            worker_nullcells.stderr_ = grass.PIPE
            queue_nullcheck.put(worker_nullcells)
            num += 1
        queue_nullcheck.wait()
    except Exception:
        check_parallel_errors(queue_nullcheck)
    verify_mapsets(cur_mapset)

    # splits tiles into tiles with possible training data
    # and tiles with no possible training data (i.e. including null cells)
    # to remove the latter from the tile index.
    possible_tr_data = []
    no_possible_tr_data = []
    for proc in queue_nullcheck.get_finished_modules():
        stdout_strs = proc.outputs["stdout"].value.strip().split(":")
        null_cells = int(stdout_strs[1].strip())
        num = int(stdout_strs[0].split(" ")[2])
        if null_cells == 0:
            # tile with possible training data, no null cells
            possible_tr_data.append(num)
        else:
            no_possible_tr_data.append(num)
    # remove tiles without data
    no_possible_tr_data.reverse()
    for num in no_possible_tr_data:
        del geojson_dict["features"][num]

    
    return geojson_dict, rm_mapsets, rm_gisrcs


def split_train_val_test(
        geojson_dict,
        val_percentage,
        test_percentage,
        seed=None,
        by_block=False,
    ):

    features = geojson_dict["features"]

    # Determine keys for splitting: 
    # per default: each tile
    # for two level: level1-block attribute
    if by_block and all("block" in f["properties"] for f in features):
        keys = [f["properties"]["block"] for f in features]
    else:
        keys = list(range(len(features)))

    # unique groups, dependent on splitting keys
    groups = sorted(set(keys))
    n = len(groups)
    n_val = round(n * val_percentage / 100)
    n_test = round(n * test_percentage / 100)

    # random split of train-val-test tile groups
    random.Random(seed).shuffle(groups)
    val_groups = set(groups[:n_val])
    test_groups = set(groups[n_val:n_val + n_test])

    n_val_tiles = n_test_tiles = 0
    # for each feature check which train-val-test group it is part of
    for feat, key in zip(features, keys):
        props = feat["properties"]
        is_val = key in val_groups
        is_test = key in test_groups
        props["validation"] = "yes" if is_val else "no"
        props["testing"] = "yes" if is_test else "no"
        props["training"] = "no" if (is_val or is_test) else "yes"
        n_val_tiles += is_val
        n_test_tiles += is_test

    n_train_tiles = len(features) - n_val_tiles - n_test_tiles
    if by_block:  
        grass.message(
            _(
                f"Selected {n - n_val - n_test} training blocks, {n_val} validation "
                f"blocks and {n_test} testing blocks, i.e.:",
            ),
        )
    grass.message(
        _(
            f"Selected {n_train_tiles} tiles as training tiles,"
            f" {n_val_tiles} tiles as validation tiles,"
            f" {n_test_tiles} tiles as testing tiles."
        ),
    )

    return geojson_dict


def export_tindex(output_dir, geojson_dict, etc_path) -> list:
    """Export tile index from geojson_dict.

    Export of tile index and verification of correct gpkg file.

    Args:
        output_dir (str): The output directory where the tile index should be
                          exported
        geojson_dict (dict): The dictionary with the tile index
        etc_path (str): The addon etc path

    """
    rm_files = list()
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

    return rm_files
