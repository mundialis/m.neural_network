## DESCRIPTION

*m.neural_network.apply* applies a locally safed neural network using
the
[segmentation_models.pytorch](https://github.com/qubvel-org/segmentation_models.pytorch)
framework for semantic segmentation to new data set.

A locally safed model is applied by providing a directory with images
*data_dir*, the path where the model is stored *input_model_path* and
specifying the options *num_classes*. The output is saved to
*output_path*.

## NOTES

It is expected that all data lie in the directory structure and naming
format as created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1).

## EXAMPLES

```sh
  m.neural_network.apply data_dir=path/to/data/apply input_model_path=/path/to/model output_path=path/to/output
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
