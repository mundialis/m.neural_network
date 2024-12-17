#!/usr/bin/env python3
"""
############################################################################
#
# MODULE:      m.neural_network.preparedata.worker_export
# AUTHOR(S):   Guido Riembauer, Anika Weinmann
# PURPOSE:     Worker module for m.neural_network.preparedata to export data
# COPYRIGHT:   (C) 2024 by mundialis GmbH & Co. KG and the GRASS Development
#              Team
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

import os

import grass.script as grass

from grass_gis_helpers.mapset import switch_to_new_mapset

EXPORT_PARAM = {
    "format": "GTiff",
    "type": "Byte",
    "flags": "mc",
    "createopt": "COMPRESS=LZW,TILED=YES,BIGTIFF=YES",
    "overviews": 5,
}


def main():
    new_mapset = options["new_mapset"]
    tile_name = options["tile_name"].split(",")
    image_bands = options["image_bands"]
    ndsm = options["ndsm"]
    reference = options["reference"]
    segmentation_minsize = int(options["segmentation_minsize"])
    segmentation_threshold = float(options["segmentation_threshold"])
    output_dir = options["output_dir"]
    tr_flag = flags["t"]

    # switch to the new mapset
    # TODO: switch_to_new_mapset muss in alte mapset wechseln können
    gisrc, newgisrc, old_mapset = switch_to_new_mapset(new_mapset)

    if ndsm and "@" not in ndsm:
        ndsm += f"@{old_mapset}"
    if reference and "@" not in reference:
        reference += f"@{old_mapset}"
    for num in range(len(image_bands)):
        if "@" not in image_bands[num]:
            image_bands[num] += f"@{old_mapset}"



    # image band export
    image_file = os.path.join(output_dir, f"image_{tile_name}.tif")
    image_bands_fn = [
        x for x in image_bands if "@" in x else f"{x}@{old_mapset}"
    ]
    grass.run_command("i.group", group="image_bands", input=image_bands_fn)
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

    # nDSM scalled + export (cut to [0 30] and rescale to [0 255]))
    ndsm_sc_file = os.path.join(output_dir, f"ndsm_0_255_{tile_name}.tif")
    ex_cut = f"ndsm_cut = if( {ndsm} >= 30, 30, if( {ndsm} < 0, 0, {ndsm} ) )"
    grass.run_command("r.mapcalc", expression=ex_cut)
    ex_scale = f"ndsm_scalled = int(ndsm_cut / 30. * 255.)"
    grass.run_command("r.mapcalc", expression=ex_scale)
    grass.run_command(
        "r.out.gdal",
        input="ndsm_scalled",
        output=ndsm_sc_file,
        **EXPORT_PARAM,
    )

    # segmentation or clip reference data
    if tr_flag:
        label_file = os.path.join()
        if reference:
            grass.run_command(
                "v.clip",
                input=reference,
                output="reference_clipped",
                flags="r",
                quiet=True,
            )
            grass.run_command(
                "v.db.addcolumn",
                map="segments",
                columns="class_number",
                quiet=True,
            )
            grass.run_command(
                "v.db.update",
                map="segments",
                column="class_number",
                value=0,
                quiet=True,
            )
            # TODO class_number=0?
            grass.run_command(
                "v.out.ogr",
                input="reference_clipped",
                output=label_file,
                flags="s",
                quiet=True,
            )
        else:
            grass.run_command(
                "i.group", group="image_bands", input=ndsm
            )  # TODO or ndsm_scalled
            grass.run_command(
                "i.segment",
                group="image_bands",
                output="segments",
                threshold=segmentation_threshold,
                minsize=segmentation_minsize,
                quiet=True,
            )
            grass.run_command(
                "r.to.vect",
                input="segments",
                output="segments",
                type="area",
                col="class_number",
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

    # switch back to original mapset
    grass.utils.try_remove(newgisrc)
    os.environ["GISRC"] = gisrc


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
