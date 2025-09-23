# `m.neural_network` - Toolset for creating training data and training a neural network

The `m.neural_network` toolset consists of following modules:
* `m.neural_network.preparedata_part1`: prepare training and/or apply data as first step for the process of creating a neural network.
  * `m.neural_network.preparedata_part1.worker_nullcells`: Worker module for `m.neural_network.preparedata_part1` to check null cells
  * `m.neural_network.preparedata_part1.worker_export`: Worker module for `m.neural_network.preparedata_part1` to export data
* `m.neural_network.preparedata_part2`: prepare training and/or apply data for use in model training and application
  * `m.neural_network.preparedata_part2.worker_label`: Worker module for `m.neural_network.preparedata_part2` to check and rasterize label data
* `m.neural_network.train`: training of a semantic segmentation model with [smp](https://pypi.org/project/segmentation-models-pytorch/) libraries
* `m.neural_network.test`: calculation of statistics for quality assessment
* `m.neural_network.apply`: application of a trained model to new data
* `m.neural_network.postprocessing.patch`: patches the tiles (GeoTIFFs) which results from neural network inference
* `m.neural_network.postprocessing.vectorize`: vectorizes the classification raster output and clean results (remove small areas, if set straighten lines)
* `m.neural_network.postprocessing.snapref`: snaps classification vector with reference data.
