## DESCRIPTION

*m.neural_network.postprocessing.vectorize* vectorizes the
classification raster output and clean results: remove small areas, if
set straighten lines.

## NOTE

Requires GRASS 8.5 for the new *-c* flag of *r.to.vect*

## EXAMPLE

### Vectorize and cleanup given classification

```sh
m.neural_network.postprocessing.vectorize input=classification_patch output=classification_vect
```

### Vectorize and cleanup given classification, including straightening of lines

```sh
m.neural_network.postprocessing.vectorize input=classification_patch output=classification_vect generalize_thres=0.2
```

## SEE ALSO

*[r.to.vect](r.to.vect.md),*

## AUTHORS

Lina Krisztian, [mundialis](https://www.mundialis.de/)
