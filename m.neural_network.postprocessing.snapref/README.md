## DESCRIPTION

*m.neural_network.postprocessing.snapref* merges classification vector
with reference data.

## EXAMPLE

### Cleanup with ALKIS Gebäude

```sh
m.neural_network.postprocessing.snapref \
    a_input_classification=classification_vect b_input_reference=AX_Gebaeude \
    output=classification_vect_clean_v01 \
    merge_col=gebaeudefunktion \
    rmarea_thres_inside=50 rmarea_where_inside="a_class_number <> 1 and b_gebaeudefunktion <> -1" \
    rmarea_thres_outside=150 rmarea_where_outside="a_class_number = 1 and b_gebaeudefunktion = -1 and compact > 3.8"


```

## SEE ALSO

*[v.overlay](v.overlay.md),*

## AUTHORS

Lina Krisztian, [mundialis](https://www.mundialis.de/)
