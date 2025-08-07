#!/usr/bin/env python3
"""############################################################################
#
# MODULE:       m.neural_network.train
# AUTHOR(S):    Victoria-Leandra Brunn
# PURPOSE:      Trains a U-Net for a binary tree/ no-tree classification based 
#               on a smp framework and scripts by Markus Metz and Lina Krisztian
#               including the steps initial training and finetuning.
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
# % description: Trains a U-Net for a binary tree/ no-tree classification including the steps initial training and finetuning.
# % keyword: raster
# % keyword: vector
# % keyword: training
# % keyword: finetuning
# % keyword: neural network
# % keyword: classification
# %end

# %option G_OPT_M_DIR
# % key: data_dir
# % label: Name of the input data directory containing subfolders with training data
# % guisection: Input
# %end

# %option
# % key: img_size
# % type: integer
# % required: yes
# % answer: 512
# % label: Image size in pixels
# % guisection: Parameters
# %end

# %option
# % key: in_channels
# % type: integer
# % required: yes
# % answer: 5
# % label: Number of channels used as input for classification: R-G-B-I-ndsm (default 5)
# %end

# %option
# % key: out_classes
# % type: integer
# % required: no
# % label: Number of classes for classification: tree/ no-tree (default 2)
# %end

# %option
# % key: model_arch
# % type: string
# % required: no
# % multiple: no
# % label: Model architecture for classification (default Unet)
# %end

# %option
# % key: encoder_name
# % type: string
# % required: no
# % label: Encoder for the classification (default resnet34)
# %end

# %option
# % key: encoder_weights
# % type: string
# % required: no
# % label: Weights for encoder (default imagenet)
# %end

# %option
# % key: epochs
# % type: integer
# % required: no
# % label: Number of training epochs (default 50)
# %end

# %option
# % key: batch_size
# % type: integer
# % required: no
# % label: Number of tiles used per training unit (default 8)
# %end

# %option
# % key: input_model_path
# % type: string
# % required: no
# % label: Name of the input model directory.
# %end

# %option
# % key: output_model_path
# % type: string
# % required: yes
# % label: Name of the output model directory.
# %end

import os

import grass.script as grass

# import module library
grass.utils.set_path(
    modulename="m.neural_network", dirname="smp_lib", path=".."
)
from smp_lib.smp_train import smp_train


def main():
    """Run training"""
    # variables - the order of options values is obligatory
    model_dir_out = options["output_model_path"]
    options["img_size"] = int(options["img_size"])
    options["in_channels"] = int(options["in_channels"])
    if options["batch_size"]:
        options["batch_size"] = int(options["batch_size"])
    if options["out_classes"]:
        options["out_classes"] = int(options["out_classes"])
    if options["epochs"]:
        options["epochs"] = int(options["epochs"])

    kwargs = {
        key: val for key, val in options.items() if val not in (None, "")
    }

    grass.message("Training classification model...")
    smp_train(**kwargs)

    grass.message(
        f"Classification model is trained and saved to {model_dir_out}."
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
