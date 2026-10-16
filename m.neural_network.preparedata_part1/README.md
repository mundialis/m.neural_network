## DESCRIPTION

*m.neural_network.preparedata_part1* prepares tiles for the labeling
process as part of the training data preparation of a neural network
using DOPs and nDSM as input data. Additionally, a tile index containing
information about the labeled status is created.

The *suffix* option may be used to add a suffix to each output tile/file
in order to create unique tile IDs that can later be combined with
results from other runs.

## EXAMPLES

### Prepare the labeling of training data for a neural network with a tile_size of 512

```sh
m.neural_network.preparedata_part1 image_bands=top_red_02,top_green_02,top_blue_02,top_nir_02 ndsm=ndsm tile_size=512 output_dir=/mnt/data/ nprocs=7
```

### Prepare training data and computing ndsm on the fly (Note: will be kept within mapset, where Addon is executed)

```sh
m.neural_network.preparedata_part1 image_bands=top_red_02,top_green_02,top_blue_02,top_nir_02 dsm=dsm dtm=dtm ndsm_out=ndsm tile_size=512 output_dir=/mnt/data/ nprocs=7
```

## SEE ALSO

*[g.region](g.region.md), [r.univar](r.univar.md),*

## AUTHORS

Anika Weinmann, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Victoria-Leandra Brunn, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)
