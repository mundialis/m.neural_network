## DESCRIPTION

*m.neural_network.postprocessing.patch* patches the tiles (GeoTIFFs)
which results from neural network inference.

## EXAMPLE

### Patch all files within given tiles_path with default edge_cut of 64 (Note: should be half of grid overlap)

```sh
m.neural_network.postprocessing.patch tiles_path=/path/to/classification/tifs output=classification_patch
```

## SEE ALSO

*[r.buildvrt](r.buildvrt.md),*

## AUTHORS

Lina Krisztian, [mundialis](https://www.mundialis.de/)
