#!/usr/bin/env python3
"""############################################################################
#
# MODULE:      m.neural_network.test
# AUTHOR(S):   Victoria-Leandra Brunn
# PURPOSE:     Tests a neural network for semantic segmentation based
#              on a smp framework and scripts.
# SPDX-FileCopyrightText: (c) 2025 by mundialis GmbH & Co. KG and the
#              GRASS Development Team
# SPDX-License-Identifier: GPL-3.0-or-later
#
#############################################################################
"""
# %Module
# % description: Tests a U-Net for a binary tree/ no-tree classification and provides statistical validation parameters.
# % keyword: raster
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

# pylint: disable=C0413
from geo_neural_network.smp_lib.smp_test import smp_test


def main():
    """Run testing."""
    # variables
    kwargs = {}
    kwargs["data_dir"] = options["data_dir"]
    kwargs["input_model_path"] = options["input_model_path"]
    if options["num_classes"]:
        kwargs["num_classes"] = int(options["num_classes"])
    kwargs["class_names"] = options["class_names"]
    kwargs["output_path"] = options["output_path"]

    grass.message("Testing classification model...")
    smp_test(**kwargs)

    grass.message(
        f"Testing the model with the {kwargs['num_classes']} classes "
        f"{kwargs['class_names']} completed. Statistics are stored under "
        f"{kwargs['output_path']}.",
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
