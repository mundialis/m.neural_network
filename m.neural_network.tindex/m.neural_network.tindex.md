## DESCRIPTION

*m.neural_network.tindex* creates a tile index of the possible tiles for
the data preparation. It will be used with
*m.neural_network.preparedata_part1*.

The *suffix* option may be used to add a suffix to each output tile/file
in order to create unique tile IDs that can later be combined with
results from other runs.

## EXAMPLES

### Create tile index

```sh
m.neural_network.tindex image_band=top_red_02 tile_size=512 output_dir=/mnt/data/ nprocs=7
m.neural_network.tindex aoi=aoi image_band=top_red_02 tile_size=512 output_dir=/mnt/data/ nprocs=7 -aw
```

## SEE ALSO

*[g.region](g.region.md), [r.univar](r.univar.md),*

## AUTHORS

Anika Weinmann, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Lina Krisztian, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Victoria-Leandra Brunn, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)
