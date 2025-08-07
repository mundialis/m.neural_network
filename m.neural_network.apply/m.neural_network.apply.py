#!/usr/bin/env python3
"""############################################################################
#
# MODULE:       m.neural_network.apply
# AUTHOR(S):    Victoria-Leandra Brunn
# PURPOSE:      Applies a neural network for semantic segmentation on a 
#               untrained data set based on a smp framework and scripts
#               by Markus Metz and Lina Krisztian.
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
# % keyword: apply
# % keyword: neural network
# % keyword: classification
# % keyword: semantic segmentation
# %end

# %option G_OPT_M_DIR
# % key: data_dir
# % label: Name of the input data directory containing unlabled images
# % guisection: Input
# %end

# %option G_OPT_M_DIR
# % key: input_model_path
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
# % key: output_path
# % type: string
# % required: yes
# % label: Name of the output directory
# %end

import grass.script as grass

# import module library
grass.utils.set_path(modulename="m.neural_network", dirname="smp_lib", path="..")
from smp_lib.smp_inference import smp_infer


def main():
    """Run inference"""
    # variables
    output_path = options["output_path"]
    if options["num_classes"]:
        options["num_classes"] = int(options["num_classes"])

    kwargs = {key: val for key, val in options.items() if val not in (None, "")}

    grass.message("Testing classification model...")
    smp_infer(**kwargs)

    grass.message(
        f"Applying model completed."
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
