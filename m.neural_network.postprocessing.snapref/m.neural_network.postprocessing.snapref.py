#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.postprocessing.snapref
# AUTHOR(S):   Lina Krisztian.
# PURPOSE:     Merges classification vector with reference data.
# SPDX-FileCopyrightText: (c) 2025 by mundialis GmbH & Co. KG and the
#                             GRASS Development Team
# SPDX-License-Identifier: GPL-3.0-or-later.
#
#############################################################################
"""
# %Module
# % description: Merges classification vector with reference data.
# % keyword: vector
# %end

# %option G_OPT_V_INPUT
# % key: a_input_classification
# % required: yes
# % description: Input vector classification (a_<...> for attribute columns)
# %end

# %option G_OPT_V_INPUT
# % key: b_input_reference
# % required: yes
# % description: Reference data for merging (b_<...> for attribute columns)
# %end

# %option G_OPT_V_OUTPUT
# % key: output
# % required: yes
# % description: merged vector output
# %end

# %option G_OPT_DB_COLUMN
# % key: class_col
# % required: yes
# % description: Attribute column containing attribute of class number
# % answer: class_number
# %end

# %option G_OPT_DB_COLUMN
# % key: merge_col
# % required: yes
# % description: Attribute column containing attribute of reference data, along which should be merged
# %end

# %option
# % key: merge_col_null_value
# % type: integer
# % required: no
# % description: Dummy value for null value areas of reference data (should be value, which is not contained within the not-null attributes)
# % answer: -1
# %end

# %option
# % key: rmarea_thres_inside
# % type: double
# % required: yes
# % description: Threshold for removing small areas, inside reference area
# %end

# %option G_OPT_DB_WHERE
# % key: rmarea_where_inside
# % required: yes
# % description: User specific SQL query for cleaning up, inside reference area (Use a_ and b_ attributes)
# %end

# %option
# % key: rmarea_thres_outside
# % type: double
# % required: yes
# % description: Threshold for removing small areas, outside reference area
# %end

# %option G_OPT_DB_WHERE
# % key: rmarea_where_outside
# % required: yes
# % description: User specific SQL query for cleaning up, outside reference area (Use a_ and b_ attributes)
# %end

# import needed libraries
import atexit

import grass.script as grass
from grass_gis_helpers.cleanup import general_cleanup

# initialize global variables
ID = grass.tempname(12)
rm_vectors = []


# cleanup function
def cleanup():
    """Cleanup function."""
    general_cleanup(
        rm_vectors=rm_vectors,
    )


def get_attributes(vecmap):
    """Get Attributes."""
    return list(
        next(
            iter(
                grass.parse_command("v.db.select", map=vecmap, separator=","),
            ),
        ).split(","),
    )


def main():
    """Run the main function of m.neural_network.postprocessing.snapref."""
    # check if v.rmarea installed
    if not grass.find_program("v.rmarea", "--help"):
        grass.fatal(
            _(
                "The 'v.rmarea' addon was not found, "
                "install it first:\n"
                "g.extension v.rmarea "
                "url=https://github.com/mundialis/v.rmarea",
            ),
        )

    classification = options["a_input_classification"]
    reference = options["b_input_reference"]
    output = options["output"]
    class_col = f"a_{options['class_col']}"
    merge_col = f"b_{options['merge_col']}"
    merge_col_null_value = options["merge_col_null_value"]
    rmarea_thres_inside = options["rmarea_thres_inside"]
    rmarea_where_inside = options["rmarea_where_inside"]
    rmarea_thres_outside = options["rmarea_thres_outside"]
    rmarea_where_outside = options["rmarea_where_outside"]

    # Get reference data only for classification
    ref_select_of_class = f"ref_select_of_class_{ID}"
    rm_vectors.append(ref_select_of_class)
    grass.run_command(
        "v.select",
        ainput=reference,
        atype="area",
        binput=classification,
        btype="area",
        out=ref_select_of_class,
        operator="overlap",
    )

    # Dissolve reference data
    ref_bin_col = f"ref_binary_{ID}"
    grass.run_command(
        "v.db.addcolumn",
        map=ref_select_of_class,
        column=f"{ref_bin_col} integer",
    )
    grass.run_command(
        "v.db.update",
        map=ref_select_of_class,
        column=ref_bin_col,
        value=1,
    )
    ref_select_of_class_diss = f"ref_select_of_class_diss_{ID}"
    rm_vectors.append(ref_select_of_class_diss)
    grass.run_command(
        "v.extract",
        input=ref_select_of_class,
        output=ref_select_of_class_diss,
        dissolve_column=ref_bin_col,
        flags="d",
    )

    # merge data
    classification_with_ref = f"classification_with_ref_{ID}"
    rm_vectors.append(classification_with_ref)
    grass.run_command(
        "v.overlay",
        ainput=classification,
        binput=ref_select_of_class_diss,
        output=classification_with_ref,
        operator="or",
        snap=0.000001,
    )

    # set dummy value for null-value of merge_col of reference data (no reference data)
    grass.run_command(
        "v.db.update",
        map=classification_with_ref,
        column=merge_col,
        value=merge_col_null_value,
        where=f"{merge_col} is null",
    )

    # Compute compactness
    grass.run_command(
        "v.to.db",
        map=classification_with_ref,
        column="compact",
        option="compact",
    )

    # Cleanup within reference areas
    classification_with_ref_clean_1 = f"classification_with_ref_clean_1_{ID}"
    rm_vectors.append(classification_with_ref_clean_1)
    grass.run_command(
        "v.rmarea",
        input=classification_with_ref,
        output=classification_with_ref_clean_1,
        column=merge_col,
        where=rmarea_where_inside,
        threshold=rmarea_thres_inside,
        flags="n",
    )

    # Cleanup outside reference areas
    classification_with_ref_clean_2 = f"classification_with_ref_clean_2_{ID}"
    rm_vectors.append(classification_with_ref_clean_2)
    grass.run_command(
        "v.rmarea",
        input=classification_with_ref_clean_1,
        output=classification_with_ref_clean_2,
        column=merge_col,
        where=rmarea_where_outside,
        threshold=rmarea_thres_outside,
        flags="n",
    )

    # Dissolve areas of same class number
    classification_with_ref_clean_diss = (
        f"classification_with_ref_clean_diss_{ID}"
    )
    rm_vectors.append(classification_with_ref_clean_diss)
    grass.run_command(
        "v.extract",
        input=classification_with_ref_clean_2,
        output=classification_with_ref_clean_diss,
        dissolve_column=class_col,
        flags="d",
    )

    # Cut to region extent (cut of reference data outside of classification AOI)
    region_vect = f"region_vect_{ID}"
    rm_vectors.append(region_vect)
    grass.run_command("v.in.region", output=region_vect)
    grass.run_command(
        "v.clip",
        input=classification_with_ref_clean_diss,
        output=output,
        clip=region_vect,
    )

    # -- Cleanup attributes

    # Rename remaining columns from overlay
    class_col_list = get_attributes(classification)
    # a_cat: Won't be renamed, will be removed below
    class_col_list.remove("cat")
    for col in class_col_list:
        grass.run_command(
            "v.db.renamecolumn",
            map=output,
            column=f"a_{col},{col}",
        )
    # Remove all attributes from reference
    ref_col_list = get_attributes(reference)
    del_col_list = [f"b_{el}" for el in ref_col_list]
    del_col_list.extend(("a_cat", "compact", f"b_{ref_bin_col}"))
    grass.run_command(
        "v.db.dropcolumn",
        map=output,
        columns=del_col_list,
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
