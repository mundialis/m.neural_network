#!/usr/bin/env python3
"""############################################################################
#
# MODULE:       m.neural_network.apply
# AUTHOR(S):    Victoria-Leandra Brunn
# PURPOSE:      Applies a neural network for semantic segmentation on a
#               untrained data set based on a smp framework and scripts.
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
# % description: Applies a neural network for semantic segmentation.
# % keyword: raster
# % keyword: apply
# % keyword: neural network
# % keyword: classification
# % keyword: semantic segmentation
# %end

# %option G_OPT_M_DIR
# % key: data_dir
# % label: Name of the input data directory containing subfolder with unlabled images
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

import os

import grass.script as grass

# import module library
grass.utils.set_path(modulename="m.neural_network", dirname="smp_lib", path="..")
from smp_lib.smp_inference import smp_infer


def main():
    """Run inference."""
    # variables
    kwargs = {}
    kwargs["data_dir"] = os.path.join(options["data_dir"], "apply_images")
    kwargs["input_model_path"] = options["input_model_path"]
    if options["num_classes"]:
        kwargs["num_classes"] = int(options["num_classes"])
    kwargs["output_path"] = options["output_path"]

    grass.message("Applying classification model...")
    smp_infer(**kwargs)

    grass.message(
        f"Applying model completed. Results in {kwargs['output_path']}.",
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
