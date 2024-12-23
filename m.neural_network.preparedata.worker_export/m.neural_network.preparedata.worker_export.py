#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.preparedata.worker_export
# AUTHOR(S):   Guido Riembauer, Anika Weinmann
# PURPOSE:     Worker module for m.neural_network.preparedata to export data
# COPYRIGHT:   (C) 2024 by mundialis GmbH & Co. KG and the GRASS Development
#              Team.
#
# 		This program is free software under the GNU General Public
# 		License (v3). Read the file COPYING that comes with GRASS
# 		for details.
#
#############################################################################
"""

# %Module
# % description: Worker module for m.neural_network.preparedata to export data.
# % keyword: raster
# % keyword: export
# % keyword: segmentation
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

# %option
# % key: tile_name
# % type: string
# % required: yes
# % multiple: no
# % key_desc: name
# % label: Unique Name of the tile
# %end

# %option
# % key: new_mapset
# % type: string
# % required: yes
# % multiple: no
# % label: Name for new mapset
# %end

# %flag
# % key: t
# % label: Export reference or segmentation data as training data suggestion
# %end

import os
import shutil

import grass.script as grass
from grass.pygrass.utils import get_lib_path
from grass.script.vector import vector_info_topo
from grass_gis_helpers.mapset import switch_to_new_mapset

EXPORT_PARAM = {
    "format": "GTiff",
    "flags": "mc",
    "createopt": "COMPRESS=LZW,TILED=YES,BIGTIFF=YES",
    "overviews": 5,
    "quiet": True,
}
NEWGISRC = None
GISRC = None
ID = grass.tempname(8)
NEW_MAPSET = None


def cleanup() -> None:
    """Clean up function switching mapsets and deleting the new one."""
    grass.utils.try_remove(NEWGISRC)
    os.environ["GISRC"] = GISRC
    # delete the new mapset (doppelt haelt besser)
    gisenv = grass.gisenv()
    gisdbase = gisenv["GISDBASE"]
    location = gisenv["LOCATION_NAME"]
    mapset_dir = os.path.join(gisdbase, location, NEW_MAPSET)
    if os.path.isdir(mapset_dir):
        shutil.rmtree(mapset_dir)


def main() -> None:
    """Export tiles and training data suggestion."""
    global NEW_MAPSET, NEWGISRC, GISRC

    NEW_MAPSET = options["new_mapset"]
    tile_name = options["tile_name"]
    image_bands = options["image_bands"].split(",")
    ndsm = options["ndsm"]
    reference = options["reference"]
    segmentation_minsize = int(options["segmentation_minsize"])
    segmentation_threshold = float(options["segmentation_threshold"])
    output_dir = options["output_dir"]
    tr_flag = flags["t"]

    # get addon etc path
    etc_path = get_lib_path(modname="m.neural_network.preparedata")
    if etc_path is None:
        grass.fatal("Unable to find qml files!")

    # make new output directory
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    # switch to the new mapset
    GISRC, NEWGISRC, old_mapset = switch_to_new_mapset(NEW_MAPSET, new=False)

    if ndsm and "@" not in ndsm:
        ndsm += f"@{old_mapset}"
    if reference and "@" not in reference:
        reference += f"@{old_mapset}"
    for num in range(len(image_bands)):
        if "@" not in image_bands[num]:
            image_bands[num] += f"@{old_mapset}"

    # image band export
    image_file = os.path.join(output_dir, f"image_{tile_name}.tif")
    grass.run_command(
        "i.group",
        group="image_bands",
        input=image_bands,
        quiet=True,
    )
    grass.run_command(
        "r.out.gdal",
        input="image_bands",
        output=image_file,
        **EXPORT_PARAM,
    )

    # ndom export
    grass.run_command(
        "r.out.gdal",
        input=ndsm,
        output=os.path.join(output_dir, f"ndsm_{tile_name}.tif"),
        **EXPORT_PARAM,
    )

    # nDSM scaled + export (cut to [0 30] and rescale to [1 255]))
    ndsm_sc_file = os.path.join(output_dir, f"ndsm_1_255_{tile_name}.tif")
    ex_cut = f"ndsm_cut = if( {ndsm} >= 30, 30, if( {ndsm} < 0, 0, {ndsm} ) )"
    grass.run_command("r.mapcalc", expression=ex_cut)
    ex_scale = "ndsm_scaled = int((ndsm_cut / 30. * 254.) + 1)"
    grass.run_command("r.mapcalc", expression=ex_scale)
    grass.run_command(
        "r.out.gdal",
        input="ndsm_scaled",
        output=ndsm_sc_file,
        type="Byte",
        **EXPORT_PARAM,
    )

    # segmentation or clip reference data
    if tr_flag:
        label_file = os.path.join(output_dir, f"label_{tile_name}.gpkg")
        create_seg = False
        if reference:
            grass.run_command(
                "v.clip",
                input=reference,
                output="reference_clipped",
                flags="r",
                quiet=True,
            )
            if vector_info_topo("reference_clipped")["centroids"] == 0:
                create_seg = True
            else:
                grass.run_command(
                    "v.db.addcolumn",
                    map="reference_clipped",
                    columns="class_number INTEGER",
                    quiet=True,
                )
                grass.run_command(
                    "v.db.update",
                    map="reference_clipped",
                    column="class_number",
                    value=0,
                    quiet=True,
                )
                grass.run_command(
                    "v.out.ogr",
                    input="reference_clipped",
                    output=label_file,
                    flags="s",
                    quiet=True,
                )
        else:
            create_seg = True
        if create_seg:
            ndsm_range = grass.parse_command(
                "r.info",
                map="ndsm_scaled",
                flags="r",
            )
            if ndsm_range["min"] != ndsm_range["max"]:
                grass.run_command(
                    "i.group",
                    group="image_bands",
                    input="ndsm_scaled",
                    quiet=True,
                )
            grass.run_command(
                "i.segment",
                group="image_bands",
                output="segments",
                threshold=segmentation_threshold,
                minsize=segmentation_minsize,
                memory=1000,
                quiet=True,
            )
            grass.run_command(
                "r.to.vect",
                input="segments",
                output="segments",
                type="area",
                col="class_number",
                flags="s",
                quiet=True,
            )
            grass.run_command(
                "v.db.update",
                map="segments",
                column="class_number",
                value=0,
                quiet=True,
            )
            grass.run_command(
                "v.out.ogr",
                input="segments",
                output=label_file,
                flags="s",
                quiet=True,
            )
        # copy qml file
        qml_src_file = os.path.join(etc_path, "qml", "label.qml")
        qml_dest_file = os.path.join(output_dir, f"label_{tile_name}.qml")
        shutil.copyfile(qml_src_file, qml_dest_file)


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
