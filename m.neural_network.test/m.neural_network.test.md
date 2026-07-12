## DESCRIPTION

*m.neural_network.test* tests a neural network using the
[segmentation_models.pytorch](https://github.com/qubvel-org/segmentation_models.pytorch)
framework for semantic segmentation and provides statistics for quality
assessment.

A locally safed model is tested by providing a directory with test
images *data_dir*, the path where the model can be found
*input_model_path* and specifying the options *num_classes* and
*class_names*. The statistics are saved to *output_path*.

## NOTES

It is expected that all data lie in the directory structure and naming
format as created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1).

## EXAMPLES

```sh
  m.neural_network.test data_dir=path/to/data/train/ input_model_path=path/to/model output_path=/path/to/output
```

## SEE ALSO

*[v.import](https://grass.osgeo.org/grass-stable/manuals/v.import.html),
[g.region](https://grass.osgeo.org/grass-stable/manuals/g.region.html)
[r.mapcalc](https://grass.osgeo.org/grass-stable/manuals/r.mapcalc.html),
[v.to.rast](https://grass.osgeo.org/grass-stable/manuals/v.to.rast.html),*

## REQUIREMENTS

- GDAL and OGR Python bindings
- [pytorch](https://pytorch.org/get-started/locally/)
- [segmentation_models.pytorch](https://pypi.org/project/segmentation-models-pytorch/)
- [pytorch-lightning](https://pypi.org/project/pytorch-lightning/)
- [albumentations](https://pypi.org/project/albumentations/)

## AUTHORS

Victoria-Leandra Brunn, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)  
