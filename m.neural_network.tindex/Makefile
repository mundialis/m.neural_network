MODULE_TOPDIR = ../../..

PGM = m.neural_network.tindex

ETCFILES = tindex_helper

include $(MODULE_TOPDIR)/include/Make/Python.make
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
	pandoc -f markdown+hard_line_breaks -t html $(PGM).md -o $(PGM).html
	sed -i 's+<br />+<br>+g' $(PGM).html
	sed -i 's+"image-alt" />+"image-alt">+g' $(PGM).html

$(ETC)/$(PGM)/%: % | $(ETC)/$(PGM)
	$(INSTALL_DATA) $< $@
