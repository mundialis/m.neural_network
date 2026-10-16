MODULE_TOPDIR = ../..

PGM = m.neural_network

# note: to deactivate a module, just place a file "DEPRECATED" into the subdir
ALL_SUBDIRS := ${sort ${dir ${wildcard */.}}}
DEPRECATED_SUBDIRS := ${sort ${dir ${wildcard */DEPRECATED}}}
RM_SUBDIRS := bin/ docs/ etc/ scripts/
SUBDIRS_1 := $(filter-out $(DEPRECATED_SUBDIRS), $(ALL_SUBDIRS))
SUBDIRS := $(filter-out $(RM_SUBDIRS), $(SUBDIRS_1))

include $(MODULE_TOPDIR)/include/Make/Dir.make

python-requirements:
	pip install -r requirements.txt

default: python-requirements parsubdirs htmldir $(PGM).md $(PGM).html

install: installsubdirs
	$(INSTALL_DATA) $(PGM).html $(INST_DIR)/docs/html/

$(PGM).md: README.md
	$(INSTALL_DATA)  README.md $(PGM).md

$(PGM).html: $(PGM).md
	echo "Creating extensions html file..."
	pandoc -f markdown+hard_line_breaks-implicit_figures -t html $(PGM).md -o $(PGM).html
	sed -i -E 's#[[:space:]]*/>#>#g' $(PGM).html
	sed -i -E '/<col style="width: [0-9]+%">/d' $(PGM).html
	sed -i '/<colgroup>/d; /<\/colgroup>/d' $(PGM).html
	sed -i '/<hr>/d' $(PGM).html
