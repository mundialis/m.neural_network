MODULE_TOPDIR = ../../..

PGM = m.neural_network.tindex

include $(MODULE_TOPDIR)/include/Make/Script.make

QML_ETC = $(patsubst %,$(ETC)/$(PGM)/%,$(wildcard qml/*.qml))
mkdir:
	$(MKDIR) $(ETC)/$(PGM)/qml

python-requirements:
	pip install geopandas

default: python-requirements script mkdir $(QML_ETC)

$(ETC)/$(PGM)/%: % | $(ETC)/$(PGM)
	$(INSTALL_DATA) $< $@
