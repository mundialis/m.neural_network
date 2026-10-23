MODULE_TOPDIR = ../../..

PGM = m.neural_network.preparedata_part1

include $(MODULE_TOPDIR)/include/Make/Script.make

QML_ETC = $(patsubst %,$(ETC)/$(PGM)/%,$(wildcard qml/*.qml))
mkdir:
	$(MKDIR) $(ETC)/$(PGM)/qml

python-requirements:
	pip install geopandas

default: python-requirements script mkdir $(QML_ETC) $(PGM).md $(PGM).html

$(PGM).md: README.md
	$(INSTALL_DATA)  README.md $(PGM).md

$(PGM).html: $(PGM).md
	echo "Creating extensions html file..."
	pandoc -f markdown+hard_line_breaks-implicit_figures -t html $(PGM).md -o $(PGM).html
	sed -i -E 's#[[:space:]]*/>#>#g' $(PGM).html
	sed -i -E '/<col style="width: [0-9]+%">/d' $(PGM).html
	sed -i '/<colgroup>/d; /<\/colgroup>/d' $(PGM).html
	sed -i '/<hr>/d' $(PGM).html

$(ETC)/$(PGM)/%: % | $(ETC)/$(PGM)
	$(INSTALL_DATA) $< $@
