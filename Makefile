# PT6A-114 design pipeline
#
#   make setup    create .venv and install requirements.txt
#   make          run tasks 2-6 and the T-s diagram from the committed Task 1 results
#   make full     also re-run the Task 1 cycle analysis first (falls back to the gas tables
#                 when the compiled gas-properties program cannot run on this machine)
#   make taskN    run a single task (and the tasks it depends on)
#   make test     check the table-based gas-properties fallback against the compiled program
#
# Plots are rendered headless by default. Add SHOW=1 to open the plot windows:
#   make task4 SHOW=1

PYTHON ?= python3
VENV   ?= .venv
PY     := $(abspath $(VENV))/bin/python

ifeq ($(SHOW),1)
  RUN := $(PY)
else
  RUN := MPLBACKEND=Agg $(PY)
endif

.DEFAULT_GOAL := all
.PHONY: help setup all full cycle ts test task1 task2 task3 task4 task5 task6 clean distclean

help:
	@sed -n '3,12p' Makefile | sed 's/^# \{0,1\}//'

# ---------------------------------------------------------------- environment
$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

setup: $(PY)

# ---------------------------------------------------------------- pipelines
all: task2 task3 task4 task5 task6 ts
	@echo "Done: tasks 2-6 and the T-s diagram."

full: cycle all

# ---------------------------------------------------------------- Task 1
# The cycle analysis calls the course's compiled gas-properties program
# (Windows build, or the macOS x86-64 build that needs gfortran's runtime).
# Where that program cannot run, task1/gasprop.py falls back to the gas tables;
# set GASPROP=fortran or GASPROP=tables to force one (e.g. make full GASPROP=tables).
cycle task1: | $(PY)
	@echo "==> Task 1: real-gas cycle analysis"
	cd task1 && $(RUN) main.py

test: | $(PY)
	@echo "==> Task 1: gas-properties fallback validation"
	cd task1 && $(RUN) test_gasprop.py

ts: | $(PY)
	@echo "==> Task 1: T-s diagram"
	cd task1 && $(RUN) ts_diagram.py

# ---------------------------------------------------------------- Tasks 2-6
task2: | $(PY)
	@echo "==> Task 2: axial compressor mean-line design"
	cd task2 && $(RUN) task2_main.py

task3: task2 | $(PY)
	@echo "==> Task 3: radial variation and blade geometry"
	cd task3 && $(RUN) task3_main.py

task5: task3 | $(PY)
	@echo "==> Task 5: cascade blade coordinates and CFD inlet conditions"
	@echo "    (the CFD solver itself runs on the jp1 cluster; see task5/README.md)"
	cd task5 && $(RUN) airfoil.py
	cd task5 && $(RUN) task5main.py

task6: task2 | $(PY)
	@echo "==> Task 6: operating line and off-design performance"
	cd task6 && $(RUN) task6main.py

# Task 4 overlays the Task 6 operating line on the compressor map
task4: task6 | $(PY)
	@echo "==> Task 4: compressor map"
	cd task4 && $(RUN) task4_main.py

# ---------------------------------------------------------------- cleanup
clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

distclean: clean
	rm -rf $(VENV)
