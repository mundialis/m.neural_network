## DESCRIPTION

*m.neural_network.preparedata_part1* export tiles for the labeling
process (as part of the training data preparation of a neural network) or for model application, using imagery (e.g. DOPs) and optional nDSM as input data.<br>
Additionally, reference labels can be given for training data preparation. Expect attribute `class_number` with the labeled class values within reference data.
If attribute not given, these column will be added and initialized with value `0`.<br>
The addon expects a tileindex as input, including information about the extent of the tiles and if they are used for training or application of a neural network.


## EXAMPLES

### Prepare the training or apply data for a neural network

Note: information which type (training or apply) given within tindex

```sh
m.neural_network.preparedata_part1 tindex=/mnt/data/tindex.gpkg image_bands=top_red_02,top_green_02,top_blue_02,top_nir_02 ndsm=ndsm output_dir=/mnt/data/prepare_part1 nprocs=7
```

### Prepare data and computing ndsm on the fly

Note: will be kept within mapset, where Addon is executed

```sh
m.neural_network.preparedata_part1 tindex=/mnt/data/tindex.gpkg image_bands=top_red_02,top_green_02,top_blue_02,top_nir_02 dsm=dsm dtm=dtm ndsm_out=ndsm output_dir=/mnt/data/prepare_part1 nprocs=7
```

### Prepare training data without ndsm but reference labels

Note: label preparation, requires flag `-l`

```sh
m.neural_network.preparedata_part1 tindex=/mnt/data/tindex.gpkg image_bands=top_red_02,top_green_02,top_blue_02,top_nir_02 reference=reference_labels -l output_dir=/mnt/data/prepare_part1 nprocs=7
```

## SEE ALSO

*[g.region](g.region.md), [r.univar](r.univar.md),*

## AUTHORS

Anika Weinmann, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Victoria-Leandra Brunn, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)
