## DESCRIPTION

*m.neural_network.preparedata_part2* prepares imagery and optional elevation and/or labelled data for training or application of a neural network.

While
[m.neural_network.preparedata_part1](../m.neural_network.preparedata_part1)
initially provides a setup for labelling tiles of imagery,
*m.neural_network.preparedata_part2* rasterizes the vector labels and
restructures the imagery data.

It uses the tindex created by [m.neural_network.tindex](../m.neural_network.tindex/) to get information about application or training (and further training, validation, testing split) data

## Notes

It is expected that all data lie in the directory structure and naming
format as created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1).
This data is provided to *m.neural_network.preparedata_part2* via the
*input_dir* parameter.
*m.neural_network.preparedata_part2* creates within given *output*-directory
following directories/data:

Always:
- *singleband_vrts:*: contains singleband .vrts for each imagery band of
  each tile. They are stored here as a basis to create the tilewise
  multiband .vrts.

If tileindex contains trainining data:
- *train_images/* and *val_images/* and optional *test_images/*:
  contains tilewise multiband .vrt-files with all
  imagery bands and optional an ndsm band to be used for training.
- *train_masks/* and *val_masks/* and optional *test_masks/*:
  contains tilewise rasterized .tif label files to be used for training.

If tileindex contains application data:
- *apply_images/*:
  contains tilewise multiband .vrt-files with all
  imagery bands and optional an ndsm band to be used for application.


In order to save diskspace, all imagery is stored as .vrts, so the
original datasets (created by
[m.neural_network.preparedata_part1](m.neural_network.preparedata_part1))
should not be moved (or *m.neural_network.preparedata_part2* should be
run again afterwards).

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
  m.neural_network.preparedata_part2 input_dir=/mnt/data/prepare_part1 tindex=/mnt/data/tindex.gpkg nprocs=6 class_column=class_number class_values=2 no_class_value=1 output=/mnt/data/prepare_part2
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
