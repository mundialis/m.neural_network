#!/usr/bin/env python3
"""############################################################################
#
# MODULE:       m.neural_network.train
# AUTHOR(S):    Victoria-Leandra Brunn
# PURPOSE:      Trains a neural network for semantic segmentation based
#               on a smp framework and scripts including the steps initial
#               training and finetuning.
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
# % description: Trains a neural network for semantic segmentation including the steps for initial training and finetuning.
# % keyword: raster
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
# % answer: 2
# % label: Number of classes for classification: tree/ no-tree (default 2)
# %end

# %option
# % key: model_arch
# % type: string
# % required: no
# % multiple: no
# % answer: Unet
# % label: Model architecture for classification (default Unet)
# %end

# %option
# % key: encoder_name
# % type: string
# % required: no
# % answer: resnet34
# % label: Encoder for the classification (default resnet34)
# %end

# %option
# % key: encoder_weights
# % type: string
# % required: no
# % answer: imagenet
# % label: Weights for encoder (default imagenet)
# %end

# %option
# % key: epochs
# % type: integer
# % required: no
# % answer: 50
# % label: Number of training epochs (default 50)
# %end

# %option
# % key: batch_size
# % type: integer
# % required: no
# % answer: 8
# % label: Number of tiles used per training unit (default 8)
# %end

# %option
# % key: input_model_path
# % type: string
# % required: no
# % label: Name of the input model directory for finetuning.
# %end

# %option
# % key: output_model_path
# % type: string
# % required: yes
# % label: Name of the output model directory.
# %end

# %option
# % key: output_train_metrics_path
# % type: string
# % required: yes
# % label: Name of the output directory containing the metrics of the training.
# %end


import os

# pylint: disable=C0413
import pathlib

import grass.script as grass
import matplotlib.pyplot as plt
import pandas as pd

from geo_neural_network.smp_lib.smp_train import smp_train


def plot_curve(epoch, y_train, y_val, y_label, outpath, ylim=None):
    """Plot metric curves."""
    plt.figure()
    # query non-Nan values -> val and train metrics saved alternating per row
    plt.plot(
        epoch.drop_duplicates(),
        y_train.dropna(),
        "blue",
        label="Training",
    )
    plt.plot(
        epoch.drop_duplicates(),
        y_val.dropna(),
        "orange",
        label="Validation",
    )
    if ylim:
        plt.ylim(ylim)
    plt.xlabel("Epoch")
    plt.ylabel(y_label)
    plt.legend()
    plt.savefig(outpath)


def main():
    """Run training."""
    # variables - the order of options values is obligatory
    kwargs = {}
    kwargs["data_dir"] = options["data_dir"]
    kwargs["img_size"] = int(options["img_size"])
    kwargs["in_channels"] = int(options["in_channels"])
    if options["out_classes"]:
        kwargs["out_classes"] = int(options["out_classes"])
    kwargs["model_arch"] = options["model_arch"]
    kwargs["encoder_name"] = options["encoder_name"]
    kwargs["encoder_weights"] = options["encoder_weights"]
    kwargs["input_model_path"] = options["input_model_path"]
    kwargs["output_model_path"] = options["output_model_path"]
    kwargs["output_train_metrics_path"] = options["output_train_metrics_path"]
    if options["epochs"]:
        kwargs["epochs"] = int(options["epochs"])
    if options["batch_size"]:
        kwargs["batch_size"] = int(options["batch_size"])

    grass.message("Training classification model...")
    smp_train(**kwargs)

    # -- Remove not needed README.me created by smp
    pathlib.Path(
        os.path.join(options["output_model_path"], "README.md"),
    ).unlink()

    # -- Create plots from train metrics
    train_metrics_file = os.path.join(
        options["output_train_metrics_path"],
        "metrics.csv",
    )
    train_metrics = pd.read_csv(train_metrics_file, sep=",", header=0)
    # Loss curve
    plot_curve(
        train_metrics["epoch"],
        train_metrics["train_dataset_loss"],
        train_metrics["valid_dataset_loss"],
        "Loss",
        os.path.join(options["output_train_metrics_path"], "loss.png"),
    )
    # Accuracy curve
    plot_curve(
        train_metrics["epoch"],
        train_metrics["train_dataset_accuracy"],
        train_metrics["valid_dataset_accuracy"],
        "Accuracy",
        os.path.join(options["output_train_metrics_path"], "accuracy.png"),
        ylim=[0, 1],
    )
    # IoU curve
    plot_curve(
        train_metrics["epoch"],
        train_metrics["train_dataset_iou"],
        train_metrics["valid_dataset_iou"],
        "Intersection over Union (IoU)",
        os.path.join(options["output_train_metrics_path"], "iou.png"),
        ylim=[0, 1],
    )
    # F1 curve
    plot_curve(
        train_metrics["epoch"],
        train_metrics["train_dataset_f1_score"],
        train_metrics["valid_dataset_f1_score"],
        "F1 score",
        os.path.join(options["output_train_metrics_path"], "f1_score.png"),
        ylim=[0, 1],
    )

    grass.message(
        f"Classification model is trained and saved to {options['output_model_path']}\n"
        f"Training metrics are saved to {options['output_train_metrics_path']}",
    )


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
