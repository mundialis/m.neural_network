[![image-alt](grass_logo.png)](https://grass.osgeo.org/grass-stable/manuals/index.html)

------------------------------------------------------------------------

## NAME

***m.neural_network*** - GRASS GIS addons to train and apply a neural
network.

## KEYWORDS

[raster](https://grass.osgeo.org/grass-stable/manuals/raster.html),
[vector](https://grass.osgeo.org/grass-stable/manuals/vector.html)

## DESCRIPTION

The *m.neural_network* toolset consists of several modules.

- [m.neural_network.preparedata_part1](m.neural_network.preparedata_part1.md):
  Prepares and exports tiles for the label process
- [m.neural_network.preparedata_part1.worker_export](m.neural_network.preparedata_part1.worker_export.md):
  Worker for parallel processing for exporting for
  **m.neural_network.preparedata_part1**
- [m.neural_network.preparedata_part1.worker_nullcells](m.neural_network.preparedata_part1.worker_nullcells.md):
  Worker to analyse the number of null cells in parallel for
  **m.neural_network.preparedata_part1**
- [m.neural_network.preparedata_part2](m.neural_network.preparedata_part2.md):
  Prepares imagery and labelled data for training and application of a
  neural network.
- [m.neural_network.preparedata_part2](m.neural_network.preparedata_part2.worker_label.md):
  Worker to rasterize labelled data in parallel for
  **m.neural_network.preparedata_part2**
- [m.neural_network.train](m.neural_network.train.md): training of a
  semantic segmentation model with smp libraries
- [m.neural_nework.test](m.neural_network.test.md): calculation of
  statistics for quality assessment
- [m.neural_network.apply](m.neural_network.apply.md): application of a
  trained model to new data

## REQUIREMENTS

The following Python libraries are needed.

- grass-gis-helpers\>=2.2.0
- GDAL/OGR and Python bindings
- [pytorch](https://pytorch.org/get-started/locally/)
- [segmentation_models.pytorch](https://pypi.org/project/segmentation-models-pytorch/)
- [pytorch-lightning](https://pypi.org/project/pytorch-lightning/)
- [albumentations](https://pypi.org/project/albumentations/)

## AUTHORS

Anika Weinmann, [mundialis GmbH & Co. KG](https://www.mundialis.de/),
weinmann at mundialis.de

Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/),
riembauer at mundialis.de

Markus Metz, [mundialis GmbH & Co. KG](https://www.mundialis.de/), metz
at mundialis.de

Victoria-Leandra Brunn, [mundialis GmbH & Co.
KG](https://www.mundialis.de/), brunn at mundialis.de
