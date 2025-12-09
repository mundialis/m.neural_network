#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.postprocessing.vectorize
# AUTHOR(S):   Lina Krisztian
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
    """Cleanup fuction."""
    general_cleanup(
        orig_region=orig_region,
        rm_rasters=rm_rasters,
        rm_vectors=rm_vectors,
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
        column="class_number",
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

    # Generalize:
    # due to rasterization no straight lines
    last_tmp_class_vect = classification_vect_rmarea

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
        classification_vect_tmp_s2 = f"{classification_vect}_tmp_s2"
        rm_vectors.append(classification_vect_tmp_s2)
        grass.run_command(
            "v.overlay",
            ainput=classification_vect_tmp_s1,
            atype="area",
            binput=classification_vect_tmp1,
            btype="area",
            operator="or",
            output=classification_vect_tmp_s2,
            olayer="1,0,0",
        )

        grass.run_command(
            "v.db.update",
            map=classification_vect_tmp_s2,
            column="a_class_number",
            query_column="b_class_number",
            where="a_class_number is null",
        )

        grass.run_command(
            "db.execute",
            sql=f"update {classification_vect_tmp_s2} set a_class_number = "
            "null where b_class_number is null",
        )

        grass.run_command(
            "v.db.dropcolumn",
            map=classification_vect_tmp_s2,
            columns="a_cat,b_cat,a_label,b_label,b_class_number",
        )

        grass.run_command(
            "v.db.renamecolumn",
            map=classification_vect_tmp_s2,
            column="a_class_number,class_number",
        )

        classification_vect_tmp_s3 = f"{classification_vect}_tmp_s3"
        rm_vectors.append(classification_vect_tmp_s3)
        grass.run_command(
            "v.extract",
            input=classification_vect_tmp_s2,
            output=classification_vect_tmp_s3,
            type="area",
            dissolve_column="class_number",
            where="class_number is not null",
            flags="d",
        )

        last_tmp_class_vect = classification_vect_tmp_s3

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
    grass.run_command(
        "v.generalize",
        input=classification_vect_tmp2,
        output=classification_vect,
        type="area",
        method="douglas",
        threshold=generalize_thres * 1.5,
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
