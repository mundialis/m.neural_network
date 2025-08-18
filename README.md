# `m.neural_network` - Toolset for creating training data and training a neural network

For now the toolset only includes add-ons for data preparation for training data creation.

The `m.neural_network` toolset consists of following modules:
* `m.neural_network.preparedata_part1`: prepare training data as first step for the process of creating a neural network.
  * `m.neural_network.preparedata_part1.worker_nullcells`: Worker module for `m.neural_network.preparedata_part1` to check null cells
  * `m.neural_network.preparedata_part1.worker_export`: Worker module for `m.neural_network.preparedata_part1` to export data
* `m.neural_network.preparedata_part2`: prepare training data for use in model training
  * `m.neural_network.preparedata_part2.worker`: Worker module for `m.neural_network.preparedata_part2` to check and rasterize label data
* `m.neural_network.train`: training of a semantic segmentation model with smp libraries
* `m.neural_network.test`: calculation of statistics for quality assessment
* `m.neural_network.apply`: application of a trained model to new data