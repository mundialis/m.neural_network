#!/bin/sh
#
# Small example script, for testing the m.neural_network Addons

# For testdata see also README.md within this folder

# TODO: adjust path
PATH_TO_TESTDATA=/path/to/testdata/

# ---- Don't change anything below

# -- Setup

# Check if in  GRASS session
if test "$GISBASE" = ""; then
    echo "You must be in GRASS GIS to run this program." >&2
    exit 1
fi

export GRASS_OVERWRITE=1

# Cleanup/Remove results from previous runs
rm ${PATH_TO_TESTDATA}/output -rf

errormsg()
{
    g.message -e message="$1"
    exit 1
}

r.import input=${PATH_TO_TESTDATA}/input/dop.tif output=dop
r.import input=${PATH_TO_TESTDATA}/input/ndsm.tif output=ndsm
g.region raster=dop.1 -p
v.import input=${PATH_TO_TESTDATA}/input/ref_data_trees.gpkg output=ref_data_trees

# -- Test Addons

# Data preparation

m.neural_network.preparedata_part1 image_bands=dop.1,dop.2,dop.3,dop.4 ndsm=ndsm output_dir=${PATH_TO_TESTDATA}/output/preparedata_part1 || errormsg "m.neural_network.preparedata_part1 failed"

m.neural_network.preparedata_part2 input_traindir=${PATH_TO_TESTDATA}/input/preparedata_part1/train input_applydir=${PATH_TO_TESTDATA}/output/preparedata_part1/apply test_percentage=10 output=${PATH_TO_TESTDATA}/output/preparedata_part2 || errormsg "m.neural_network.preparedata_part2 failed"

# Model Training and evaluation

m.neural_network.train data_dir=${PATH_TO_TESTDATA}/output/preparedata_part2/train output_model_path=${PATH_TO_TESTDATA}/output/model output_train_metrics_path=${PATH_TO_TESTDATA}/output/model_train_metrics epochs=2 || errormsg "m.neural_network.train failed"

m.neural_network.test data_dir=${PATH_TO_TESTDATA}/output/preparedata_part2/train input_model_path=${PATH_TO_TESTDATA}/input/example_model output_path=${PATH_TO_TESTDATA}/output/model_testdata_evaluation || errormsg "m.neural_network.test failed"

m.neural_network.apply data_dir=${PATH_TO_TESTDATA}/input/preparedata_part2/apply input_model_path=${PATH_TO_TESTDATA}/input/example_model/ output_path=${PATH_TO_TESTDATA}/output/applied_model || errormsg "m.neural_network.apply failed"

# Postprocessing

m.neural_network.postprocessing.patch tiles_path=${PATH_TO_TESTDATA}/output/applied_model output=applied_model_raster  || errormsg "m.neural_network.postprocessing.patch failed"

m.neural_network.postprocessing.vectorize input=applied_model_raster output=applied_model_vector || errormsg "m.neural_network.postprocessing.vectorize failed"

m.neural_network.postprocessing.snapref a_input_classification=applied_model_vector b_input_reference=ref_data_trees output=applied_model_vector_cleaned  merge_col=cat rmarea_thres_inside=20 rmarea_where_inside="b_cat" rmarea_thres_outside=20 rmarea_where_outside="b_cat" || errormsg "m.neural_network.postprocessing.snapref failed"
