#!/usr/bin/env python3
"""############################################################################
#
# MODULE:       m.neural_network.test
# AUTHOR(S):    Victoria-Leandra Brunn
# PURPOSE:      Tests a neural network for semantic segmentation based
#               on a smp framework and scripts by Markus Metz and Lina Krisztian.
#
# COPYRIGHT:	(C) 2025 by mundialis
#
# 		This program is free software under the GNU General Public
# 		License (v3). Read the file COPYING that comes with GRASS
# 		for details.
#
#############################################################################
"""
# %Module
# % description: Tests a U-Net for a binary tree/ no-tree classification and provides statistical validation parameters.
# % keyword: raster
# % keyword: vector
# % keyword: test
# % keyword: neural network
# % keyword: classification
# %end

# %option G_OPT_M_DIR
# % key: data_dir
# % label: Name of the input data directory containing subfolders with test images and masks
# % guisection: Input
# %end

# %option
# % key: input_model_path
# % type: string
# % required: yes
# % label: Name of the input model directory
# % guisection: Input
# %end

# %option
# % key: num_classes
# % type: integer
# % required: no
# % answer: 2
# % label: Number of classes for classification (default 2)
# %end

# %option
# % key: class_names
# % type: string
# % required: no
# % answer: tree,no tree
# % label: Class names (default tree/ no-tree)
# %end

# %option
# % key: output_path
# % type: string
# % required: yes
# % label: Name of the output directory
# %end

import grass.script as grass

# import module library
grass.utils.set_path(modulename="m.neural_network", dirname="smp_lib", path="..")
from smp_lib.smp_test import smp_test


def main():
    """Run training."""
    # variables
    output_path = options["output_path"]
    class_names = options["class_names"]
    if options["num_classes"]:
        options["num_classes"] = int(options["num_classes"])
        num_classes = options["num_classes"]

    kwargs = {key: val for key, val in options.items() if val not in (None, "")}

    grass.message("Testing classification model...")
    smp_test(**kwargs)

    grass.message(
        f"Testing the model with the {num_classes} classes "
        f"{class_names} completed. Statistics are stored under {output_path}.",
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
