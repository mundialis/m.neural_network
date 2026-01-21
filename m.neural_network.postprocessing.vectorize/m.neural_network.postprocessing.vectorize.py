#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.postprocessing.vectorize
# AUTHOR(S):   Lina Krisztian.
#
# PURPOSE:     Vectorizes classification raster output and clean up results
# SPDX-FileCopyrightText: (c) 2025 by mundialis GmbH & Co. KG and the
#                             GRASS Development Team
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
#############################################################################
"""
# %Module
# % description: Vectorizes classification raster output and clean up results.
# % keyword: vector
# %end

# %option G_OPT_R_INPUT
# % key: input
# % required: yes
# % description: Input raster classification
# %end

# %option G_OPT_V_OUTPUT
# % key: output
# % required: yes
# % description: Output vector classification
# %end

# %option
# % key: rmarea_thres
# % type: double
# % required: no
# % type: double
# % description: Threshold for cleaning up small areas in square meters
# % answer: 5
# %end

# %option
# % key: generalize_thres
# % type: double
# % required: no
# % type: double
# % label: Threshold for generalization/straightening of area border lines
# % description: Default: input raster resolution
# %end

# %flag
# % key: s
# % label: Apply smoothing
# % description: This smoothes corners which is sometimes not desired
# %end

# %flag
# % key: c
# % label: Keep corners after generalization (only meaningful for single small tiles)
# % description: Keep corners after the generalization this is only meaningful for single tiles as the training tiles
# %end

# import needed libraries
import atexit

import grass.script as grass
from grass_gis_helpers.cleanup import general_cleanup

# initialize global variables
ID = grass.tempname(12)
orig_region = None  # pylint: disable=invalid-name
rm_rasters = []
rm_vectors = []


# cleanup function
def cleanup():
    """Cleanup function."""
    general_cleanup(
        orig_region=orig_region,
        rm_rasters=rm_rasters,
        rm_vectors=rm_vectors,
    )


def restore_corners(input_generalized, input_corners, output):
    """Restore corners. This is important after v.generalize, because
    sometimes the corners are generalized away.

    Args:
        input_generalized (str): The name of the input vector map with missing
                                    corners
        input_corners (str): The name of the input vector map before the
                                generalization
        output (str): The name of the output vector map including the corners

    """
    output_tmp = f"{output}_tmp"
    rm_vectors.append(output_tmp)
    grass.run_command(
        "v.overlay",
        ainput=input_generalized,
        atype="area",
        binput=input_corners,
        btype="area",
        operator="or",
        output=output_tmp,
        olayer="1,0,0",
    )

    for col in ["class_number", "label"]:
        grass.run_command(
            "v.db.update",
            map=output_tmp,
            column=f"a_{col}",
            query_column=f"b_{col}",
            where=f"a_{col} is null",
        )

        grass.run_command(
            "db.execute",
            sql=f"update {output_tmp} set a_{col} = "
            f"null where b_{col} is null",
        )
        grass.run_command(
            "v.db.renamecolumn",
            map=output_tmp,
            column=f"a_{col},{col}",
        )
    grass.run_command(
        "v.db.dropcolumn",
        map=output_tmp,
        columns="a_cat,b_cat,b_label,b_class_number",
    )
    grass.run_command(
        "v.extract",
        input=output_tmp,
        output=output,
        type="area",
        dissolve_column="class_number",
        where="class_number is not null",
        flags="d",
    )


def main():
    """Run the main function of m.neural_network.postprocessing.vectorize."""
    global orig_region

    classification_rast = options["input"]
    classification_vect = options["output"]
    rmarea_thres = options["rmarea_thres"]
    smoothing = flags["s"]

    # save original region
    orig_region = f"original_region_{ID}"
    grass.run_command("g.region", save=orig_region, quiet=True)

    grass.run_command(
        "g.region",
        raster=classification_rast,
    )

    if not options["generalize_thres"]:
        rinfo = grass.raster_info(classification_rast)
        generalize_thres = (rinfo["nsres"] + rinfo["ewres"]) / 2.0
    else:
        generalize_thres = float(options["generalize_thres"])

    # Removing small areas
    # do not use r.reclass.area method=rmarea because this module calls
    # r.to.vect + v.clean + v.to.rast
    # use v.clean directly below, this avoids r.to.vect + v.to.rast

    # Vectorize data
    grass.message(_("Vectorizing classification ..."))
    classification_vect_tmp1 = f"{classification_vect}_tmp1"
    rm_vectors.append(classification_vect_tmp1)
    # no "s" flag because this creates artifacts at the corners of the raster
    r_to_vect_flags = ""
    if tuple(int(x) for x in grass.version()["version"].split(".")[:2]) >= (
        8,
        5,
    ):
        r_to_vect_flags = "c"
    grass.run_command(
        "r.to.vect",
        input=classification_rast,
        output=classification_vect_tmp1,
        type="area",
        column="class_number_float",
        flags=r_to_vect_flags,
    )

    # remove small areas with v.clean
    grass.message(_("Removing small areas ..."))
    classification_vect_rmarea = f"{classification_vect}_rmarea"
    rm_vectors.append(classification_vect_rmarea)
    grass.run_command(
        "v.clean",
        input=classification_vect_tmp1,
        output=classification_vect_rmarea,
        tool="rmarea",
        threshold=rmarea_thres,
    )

    # Change column type to INT for dissolving
    grass.message(_("Updating column type ..."))
    grass.run_command(
        "v.db.addcolumn",
        map=classification_vect_rmarea,
        column="class_number INTEGER",
    )
    grass.run_command(
        "v.db.update",
        map=classification_vect_rmarea,
        column="class_number",
        query_column="class_number_float",
    )
    grass.run_command(
        "v.db.dropcolumn",
        map=classification_vect_rmarea,
        column="class_number_float",
    )

    # Dissolve areas with same class_number
    # (which can occur after v.clean)
    grass.message(_("Dissolving areas of same class_number ..."))
    classification_vect_dissolve = f"{classification_vect}_dissolve"
    rm_vectors.append(classification_vect_dissolve)
    # use v.extract with -d flag, instead of v.dissolve (faster)
    grass.run_command(
        "v.extract",
        input=classification_vect_rmarea,
        output=classification_vect_dissolve,
        type="area",
        dissolve_column="class_number",
        flags="d",
    )

    # Generalize:
    # due to rasterization no straight lines
    last_tmp_class_vect = classification_vect_dissolve

    if smoothing:
        classification_vect_tmp_s1 = f"{classification_vect}_tmp_s1"
        rm_vectors.append(classification_vect_tmp_s1)
        grass.run_command(
            "v.generalize",
            input=classification_vect_tmp1,
            output=classification_vect_tmp_s1,
            type="area",
            method="chaiken",
            threshold=generalize_thres,
        )

        # restore corners
        last_tmp_class_vect = f"{classification_vect}_tmp_s2"
        rm_vectors.append(last_tmp_class_vect)
        restore_corners(
            classification_vect_tmp_s1,
            classification_vect_tmp1,
            last_tmp_class_vect,
        )

    classification_vect_tmp2 = f"{classification_vect}_tmp2"
    rm_vectors.append(classification_vect_tmp2)
    grass.run_command(
        "v.generalize",
        input=last_tmp_class_vect,
        output=classification_vect_tmp2,
        type="area",
        method="douglas",
        threshold=generalize_thres,
    )

    # second run with slightly larger threshold
    classification_vect_tmp3 = f"{classification_vect}_tmp3"
    rm_vectors.append(classification_vect_tmp3)
    grass.run_command(
        "v.generalize",
        input=classification_vect_tmp2,
        output=classification_vect_tmp3,
        type="area",
        method="douglas",
        threshold=generalize_thres * 1.5,
    )

    # restore corners
    if flags["c"]:
        restore_corners(
            classification_vect_tmp3,
            last_tmp_class_vect,
            classification_vect,
        )
    else:
        grass.run_command(
            "g.rename",
            vector=f"{classification_vect_tmp3},{classification_vect}",
        )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
