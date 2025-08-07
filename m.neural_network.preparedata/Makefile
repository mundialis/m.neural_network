MODULE_TOPDIR = ../../..

PGM = m.neural_network.preparedata

include $(MODULE_TOPDIR)/include/Make/Script.make

QML_ETC = $(patsubst %,$(ETC)/$(PGM)/%,$(wildcard qml/*.qml))
mkdir:
	$(MKDIR) $(ETC)/$(PGM)/qml

default: script mkdir $(QML_ETC)

$(ETC)/$(PGM)/%: % | $(ETC)/$(PGM)
	$(INSTALL_DATA) $< $@
