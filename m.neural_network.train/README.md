## DESCRIPTION

*m.neural_network.train* trains or fine-tunes a neural network using the
[segmentation_models.pytorch](https://github.com/qubvel-org/segmentation_models.pytorch)
framework for semantic segmentation.

A new model can be trained by specifying the options *img_size*,
*out_classes*, *model_arch*, *encoder_name*, *encoder_weights*,
*in_channels*. A locally saved model can be further trained (fine-tuned)
by giving the path to the previously saved model. For more information
about available encoder-decoder combinations, see the [smp
documentation.](https://smp.readthedocs.io/en/latest/)

A larger *batchsize* is generally better for training, but requires more
GPU RAM. A bit of experimentation is needed to find a batch size that
still fits into the GPU RAM.

## NOTES

It is expected that all data lie in the directory structure and naming
format as created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1).

## EXAMPLES

```sh
  m.neural_network.train data_dir=path/to/data/train/ output_model_path=path/to/model
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
