<!-- markdownlint-disable MD041 -->

[![image-alt](https://github.com/OSGeo/grass/raw/main/man/grass_logo.png)](https://grass.osgeo.org/grass-stable/manuals/index.html)

------------------------------------------------------------------------

## NAME

***m.neural_network*** - GRASS GIS addons to prepare data, train and apply, and postprocess data for neural network.

## KEYWORDS

[raster](https://grass.osgeo.org/grass-stable/manuals/raster.html),
[vector](https://grass.osgeo.org/grass-stable/manuals/vector.html)

## DESCRIPTION

The *m.neural_network* toolset consists of several modules.

Data preparation:
- [m.neural_network.tindex](m.neural_network.tindex/README.md): Creates a tile index of the possible tiles for
the data preparation either in apply or training mode
- [m.neural_network.worker_nullcells](m.neural_network.worker_nullcells/README.md):
  Worker to analyse the number of null cells of imagery data for training mode
- [m.neural_network.preparedata_part1](m.neural_network.preparedata_part1/README.md):
  Prepares and exports tiles for the label process
- [m.neural_network.preparedata_part1.worker_export](m.neural_network.preparedata_part1.worker_export/README.md):
  Worker for parallel processing for exporting for
  *m.neural_network.preparedata_part1*
- [m.neural_network.preparedata_part2](m.neural_network.preparedata_part2/README.md):
  Prepares imagery and labelled data for training and application of a neural network.
- [m.neural_network.preparedata_part2.worker_label](m.neural_network.preparedata_part2.worker_label/README.md):
  Worker to rasterize labelled data in parallel for
  *m.neural_network.preparedata_part2*

Model development and usage:
- [m.neural_network.train](m.neural_network.train/README.md): training of a
  semantic segmentation model with [smp](https://pypi.org/project/segmentation-models-pytorch/) libraries
- [m.neural_nework.test](m.neural_network.test/README.md): calculation of
  statistics for quality assessment
- [m.neural_network.apply](m.neural_network.apply/README.md): application of a
  trained model to new data

Postprocessing:
- [m.neural_network.postprocessing.patch](m.neural_network.postprocessing.patch/README.md): patches the tiles (GeoTIFFs) which results from neural network inference.
- [m.neural_network.postprocessing.vectorize](m.neural_network.postprocessing.vectorize/README.md) vectorizes the classification raster output and clean results: remove small areas, if set straighten lines.
- [m.neural_network.postprocessing.snapref](m.neural_network.postprocessing.snapref/README.md): merges classification vector with reference data.

## REQUIREMENTS

`v.out.geojson` from [mundialis](https://github.com/mundialis/v.out.geojson).  
For required python libraries see [requirements_all.txt](./requirements_all.txt).

This includes:
- GDAL/OGR and Python bindings
- [pytorch](https://pytorch.org/get-started/locally/)
- [segmentation_models.pytorch](https://pypi.org/project/segmentation-models-pytorch/)
- [pytorch-lightning](https://pypi.org/project/pytorch-lightning/)
- [albumentations](https://pypi.org/project/albumentations/)

## AUTHORS

Anika Weinmann, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Markus Metz, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Victoria-Leandra Brunn, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Lina Krisztian, [mundialis GmbH & Co. KG](https://www.mundialis.de/)
