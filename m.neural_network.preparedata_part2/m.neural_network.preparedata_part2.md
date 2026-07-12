## DESCRIPTION

*m.neural_network.preparedata_part2* prepares imagery and labelled data
for training and application of a neural network.

While
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1)
initially provides a setup for labelling tiles of imagery,
*m.neural_network.preparedata_part2* rasterizes the vector labels and
restructures the imagery data.

## Notes

It is expected that all data lie in the directory structure and naming
format as created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1).
This data is provided to *m.neural_network.preparedata_part2* via the
*input_traindir* and *input_applydir* parameters.
*m.neural_network.preparedata_part2* creates a new directory with the
two directories *train* and *apply*. Each of these contains the
following directories/data:

- *train_images:*: contains tilewise multiband .vrt-files with all
  imagery bands and an ndsm band to be used for training. This directory
  is empty in the *apply* dir.
- *train_masks:*: contains tilewise rasterized .tif label files to be
  used for training. This directory is empty in the *apply* dir.
- *val_images:*: contains tilewise multiband .vrt-files with all imagery
  bands and an ndsm band to be used for validation. This directory holds
  data both in the *train* and *apply* dirs. In the *train* dir, this
  data is used for validation during training, while in the *apply* dir,
  this directory holds all imagery used for prediction.
- *val_masks:*: contains tilewise rasterized .tif label files to be used
  for training. This directory is empty in the *apply* dir.
- *singleband_vrts:*: contains singleband .vrts for each imagery band of
  each tile. They are stored here as a basis to create the tilewise
  multiband .vrts.

In order to save diskspace, all imagery is stored as .vrts, so the
original datasets (created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1))
should not be moved (or *m.neural_network.preparedata_part2* should be
run again afterwards).

The user can indicate what percentage of the training tiles are used for
validation and testing (during training) with the *val_percentage* and
*test_percentage* parameter.

It is not possible to run *m.neural_network.preparedata_part2*
repeatedly with the same *output* directory, as the training/validation
split up happens during runtime. Hence,
*m.neural_network.preparedata_part2* expects that the *output* directory
does not exist.

With the *class_values* and the *no_class_value* parameters, the user
defines the allowed range of values in the *class_column* of the
labelled data. In case an unexpected value is found, an error is thrown
which indicates the affected tile.

To ensure effective binary classification operators in case of two
output classes the first class in *class_values* is mapped to class 0.

If a tile is not completely covered either by *class_values* or
*no_class_value*, the not allocated areas will be filled with
*no_class_value* in the rasterized version.

## EXAMPLES

```sh
  m.neural_network.preparedata_part2 input_traindir=nn_data_with_labels/train input_applydir=nn_data_with_labels/apply nprocs=6 class_column=class_number class_values=2 no_class_value=1 output=nn_data_structured
```

## SEE ALSO

*[v.import](https://grass.osgeo.org/grass-stable/manuals/v.import.html),
[g.region](https://grass.osgeo.org/grass-stable/manuals/g.region.html)
[r.mapcalc](https://grass.osgeo.org/grass-stable/manuals/r.mapcalc.html),
[v.to.rast](https://grass.osgeo.org/grass-stable/manuals/v.to.rast.html),*

## REQUIREMENTS

- GDAL and OGR Python bindings
- [grass-gis-helpers](https://pypi.org/project/grass-gis-helpers/)
  Python library \>= 2.2.0

## AUTHORS

Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Victoria-Leandra Brunn, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)  
