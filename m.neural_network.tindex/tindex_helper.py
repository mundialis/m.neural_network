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

def make_grid(tile_size, tile_overlap, resolution, region, suffix):
    # parameter for tiles
    tile_size_map_units = tile_size * resolution
    tile_overlap_map_units = tile_overlap * resolution

    # start values
    north = region["n"]
    num_tiles_row = round(region["rows"] / (tile_size - tile_overlap) + 0.5)
    num_tiles_col = round(region["cols"] / (tile_size - tile_overlap) + 0.5)
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
                "properties": {
                    "fid": "fid_TODO",
                    "name": "tile_name_TODO",
                    "path": "",
                    "training": "no",
                    "validation": "no",
                    "testing": "no",
                    "apply": "no",
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
    # TODO: blcok hier drunter weg -> nur noch mit dict direkt weiter arbeiten??
        # siehe dazu auch funktion split_train_val_test anpassen und testen
    import pdb; pdb.set_trace()
    no_possible_tr_data.reverse()
    for num in no_possible_tr_data:
        del geojson_dict["features"][num]
        # # TODO: wofür??
        # possible_tr_data = [x - 1 if x > num else x for x in possible_tr_data]
        # no_possible_tr_data = [
        #     x - 1 if x > num else x for x in no_possible_tr_data
        # ]
    
    # return possible_tr_data, no_possible_tr_data, rm_mapsets, rm_gisrcs
    return geojson_dict, rm_mapsets, rm_gisrcs


def split_train_val_test(geojson_dict, val_percentage, test_percentage, seed=None):
    features = geojson_dict["features"]
    n = len(features)

    n_val = round(n * val_percentage / 100)
    n_test = round(n * test_percentage / 100)

    # random split of train-val-test tiles
    idx = list(range(n))
    random.Random(seed).shuffle(idx)

    val_idx = set(idx[:n_val])
    test_idx = set(idx[n_val:n_val + n_test])

    for i, feat in enumerate(features):
        props = feat["properties"]
        # TODO: exclude the no part
        props["validation"] = "yes" if i in val_idx else "no"
        props["testing"] = "yes" if i in test_idx else "no"
        props["training"] = "no" if (i in val_idx or i in test_idx) else "yes"

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











#########################

#########################
#########################
#########################
#########################


def mkgrid_old(gdf, config, level):
    """Computes the coordinates of the bottom left corner of each tile.
    
    Parameters:
        gdf:        GeoDataFrame for which grid will be calculated
        config:     config dictionary with required settings
        level:      level of grid creation (l1 or l2)

    Returns:
        grid:       numpy array with coordinates of bottom left corner
    """

    # Get bounding box coordinates:
    x_min, y_min, x_max, y_max = gdf.total_bounds
    x_min = floor(x_min)
    y_min = floor(y_min)
    x_max = ceil(x_max)
    y_max = ceil(y_max)

    # For level 1 grid: if given, set start coordinate from config
    if level == "l1":
        if ("long_min" in config) and ("lat_min" in config):
            x_min = config["long_min"]
            y_min = config["lat_min"]

    # Align start coordinates (bottom left corner) of grid
    # with reference raster:
    ref_rast = gdal.Open(config["reference_rast"], gdal.GA_ReadOnly)
    # See also https://gdal.org/en/stable/tutorials/raster_api_tut.html
    # (Note that n-s pixel resolution is negative because rows are counted from top to bottom.)
    ref_rast_geotransform = ref_rast.GetGeoTransform()
    x_ref = ref_rast_geotransform[0]
    x_ref_res = ref_rast_geotransform[1]
    y_ref = ref_rast_geotransform[3]
    # make n-s resolution positive
    y_ref_res = -ref_rast_geotransform[5]
    # close GDAL dataset
    ref_rast = None
    # alignment of bottom left corner:
    # aligned values must not be larger than original values in order to fully cover the aoi
    x_min_align = x_ref + floor((x_min - x_ref) / x_ref_res) * x_ref_res
    y_min_align = y_ref - ceil((y_ref - y_min) / y_ref_res) * y_ref_res
    # same as:
    # y_min_align = y_ref + floor((y_min - y_ref) / y_ref_res) * y_ref_res
    # Give warning if l1 start coordinate differs from configuration settings
    if level == "l1" and ("long_min" in config) and ("lat_min" in config):
        if x_min != x_min_align:
            print(f"WARNING: Given start coordinate long_min {config['long_min']} "
                   "does not align with reference raster. "
                   f"Adjusting start coordinate to {x_min_align}.")
        if y_min != y_min_align:
            print(f"WARNING: Given start coordinate lat_min {config['lat_min']} "
                   "does not align with reference raster. "
                   f"Adjusting start coordinate to {y_min_align}.")
    x_min = x_min_align
    y_min = y_min_align

    height = y_max - y_min
    width = x_max - x_min

    if f"overlap_{level}" in config:
        overlap = config[f"overlap_{level}"]
        # if overlap/level2 -> remove tile size from max height, to avoid exceeding bounding box
        tile_size_key = f"tile_size_{level}"
        height -= config[tile_size_key]
        width -= config[tile_size_key]
    elif "overlap" in config:
        overlap = config["overlap"]
        tile_size_key = "tile_size"
    else:
        overlap = 0
        tile_size_key = f"tile_size_{level}"
    # Set stride (if not given, no overlap => stride = tile_size)
    stride = config[tile_size_key] - overlap

    # Calculate coordinates of bottom left corner
    grid = []
    for y in np.arange(0, height + 1, stride):
        for x in np.arange(0, width + 1, stride):
            grid.append([x_min + x, y_min + y])
    
    # Return grid as numpy array
    grid = np.array(grid)

    return grid

def grid_np2gdf(grid_np, tile_size, epsg, ind_l1 = None):
    """Transfrom numpy grid to GeoDataFrame grid

    Parameters:
        grid_np:    grid as numpy array with coordinates of bottom left corner
        tile_size:  tile size for grid for generation of polygon tiles
        epsg:       EPSG-code for creation of GeoDataFrame
        ind_l1:     Index of corresponding level1 tile (only needed for two level tiling)

    Returns
        grid_gdf:   grid as GeoDataFrame (with polygon geometry of tiles) 
    """

    arr_xmin = np.ravel(grid_np[:,0])
    arr_xmax =arr_xmin + tile_size
    arr_ymin = np.ravel(grid_np[:,1])
    arr_ymax = arr_ymin + tile_size
    df1 = pd.DataFrame({
        "xmin": arr_xmin,
        "xmax": arr_xmax,
        "ymin": arr_ymin,
        "ymax": arr_ymax,
    })

    # Only for level two tiling:
    # set an index of level 1 tile
    if ind_l1 is not None:
        arr_ind_l1 = ((arr_ymin*0)+ind_l1).astype("uint32")
        df2 = pd.DataFrame({"level1_index": arr_ind_l1})
        # Concat along column axis
        df1 = pd.concat([df1,df2],axis=1)

    # Create polygons from bottom left corner coordinates + tile size
    XY_zip = list(zip(df1['xmin'], df1['ymin']))
    XY_zip_polygon = []
    for el in XY_zip:
        list_entry = [
            el,
            (el[0],el[1]+tile_size),
            (el[0]+tile_size,el[1]+tile_size),
            (el[0]+tile_size,el[1]),
            el
            ]
        XY_zip_polygon.append(list_entry)

    # Append polygon to dataframe
    df1["coords"] = XY_zip_polygon
    df1["coords"] = df1["coords"].apply(Polygon)

    # Create GeoDataFrame
    grid_gdf = gpd.GeoDataFrame(df1, geometry="coords")
    grid_gdf = grid_gdf.set_crs(epsg)

    return grid_gdf

def grid_within_aoi(grid_gdf, aoi_gdf, predicate):
    """Extract grid, with given relation to AOI

    Parameters:
        grid_gdf:       GeoDataFrame of grid
        aoi_gdf:        GeoDataFrame of AOI
        predicate:      condition for joining/extraction of GeoDataFrame

    Returns
        grid_aoi_gdf:   GeoDataFrame of grid for AOI 
    """
    # predicate argument see also:
    # https://geopandas.org/en/stable/docs/user_guide/mergingdata.html#binary-predicate-joins
    grid_aoi_gdf = gpd.sjoin(
        left_df = grid_gdf,
        right_df = aoi_gdf,
        how = "inner",
        predicate = predicate)
    
    # drop not needed column, created during previous join
    grid_aoi_gdf = grid_aoi_gdf.drop(columns="index_right")
    
    return grid_aoi_gdf

def row_col_index(gdf, tile_size_l1 = None):
    """Add row and column index for given grid

    Parameters:
        gdf:            GeoDataFrame of grid
                        (columns will be appended to given GeoDataFrame)
        tile_size_l1:   tile size of level1 (only needed for two level grid)
    """
    for coord, coord_ind in zip(["ymin", "xmin"],["row", "col"]):
        # Get unique corrdinates and sort ascending
        coord_min_unique = gdf[coord].unique()
        coord_min_unique.sort()
        coord_min_unique_minimum = coord_min_unique.min()
        # Map coordinate to index value
        coord_map_dict = {}
        rc_ind = 0
        for val in coord_min_unique:
            # for level1-tile border: skip one index value
            if tile_size_l1:
                if not (val - coord_min_unique_minimum) % tile_size_l1:
                    rc_ind += 1
            coord_map_dict[val] = rc_ind
            rc_ind += 1
        gdf[coord_ind] = gdf[coord].map(coord_map_dict)
