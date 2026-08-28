.DEFAULT_GOAL := help

########################################################################\
Make gitignore file
########################################################################
.PHONY: giti
# WARNING: this rewrites .gitignore from scratch and drops the hand-maintained
# section at the top of the file (raw data paths, logs/, texcount scratch).
# Restore that section from git after running this.
giti: ## Make .gitignore from gitignore.io
	@echo "==> $@"
	rm -rf .gitignore
	echo "venv*" > .gitignore
	echo "Copy*.ipynb" >> .gitignore
	echo "scratch/*" >> .gitignore
	echo "*xlsx" >> .gitignore
	echo "**/*.tar.gz" >> .gitignore
	echo "**/*.csv*" >> .gitignore
	echo "**/*.xls" >> .gitignore
	echo "**/*.xlsx" >> .gitignore
	curl https://www.toptal.com/developers/gitignore/api/python >> .gitignore
	curl https://www.toptal.com/developers/gitignore/api/jupyternotebooks >> .gitignore
	curl https://www.toptal.com/developers/gitignore/api/tex >> .gitignore


# ============================================================================
# Set up the Python virtual environment and prepare the Jupyter distribution
# Installs packages from requirements.txt
# ============================================================================
.PHONY: setup
VENVPATH ?= bl_venv
ifeq ($(OS),Windows_NT)
	VENVPATH :=  c:/users/admin/$(VENVPATH)
	ACTIVATE_PATH := $(VENVPATH)/Scripts/activate
else
	ACTIVATE_PATH := $(VENVPATH)/bin/activate
endif
REQUIREMENTS := requirements.txt
setup: ## Set up venv	
setup: $(REQUIREMENTS)
	@echo "==> $@"
	@echo "==> Creating and initializing virtual environment..."
	rm -rf $(VENVPATH)
	python -m venv $(VENVPATH)
	. $(ACTIVATE_PATH) && \
		pip install --upgrade pip && \
		which pip && \
		pip list && \
		echo "==> Installing requirements" && \
		pip install -r $< && \
		jupyter contrib nbextensions install --sys-prefix --skip-running-check && \
		python -m ipykernel install --user --name=$(VENVPATH) --display-name "Python ($(VENVPATH))" && \
		echo "==> Packages available:" && \
		which pip && \
		pip list && \
		which jupyter && \
		deactivate
	@echo "==> Setup complete."


# ============================================================================
# Open Jupyter notebook in the venv
# ============================================================================
.PHONY: jn
jn: ## Launch jupyter notebook in venv
	@echo "==> $@"
	if [ -f $(VENVPATH)/Scripts/activate ]; then \
		. $(VENVPATH)/Scripts/activate && jupyter notebook; \
	elif [ -f $(VENVPATH)/bin/activate ]; then \
		. $(VENVPATH)/bin/activate && jupyter notebook; \
	else \
		@echo "No venv found"; \
	fi


########################################################################
# Analysis
#
# One command runs everything: scripts/R/99_run_all.R sources 00-08 in order
# and writes every table and figure the manuscript inputs. Data collection is
# separate and stays in Python (scripts/privacy_scraper, scripts/python).
########################################################################
.PHONY: analysis
analysis: ## Run the full R analysis pipeline (all tables and figures)
	@echo "==> $@"
	Rscript scripts/R/99_run_all.R

.PHONY: paper
paper: ## Compile ms/blacklight.pdf (runs the analysis first)
paper: analysis
	@echo "==> $@"
	BIBINPUTS="ms:" TEXINPUTS=".:ms:" latexmk -pdf -shell-escape \
		-interaction=nonstopmode -outdir=ms ms/blacklight.tex
	@echo "==> wrote ms/blacklight.pdf"

.PHONY: paper-clean
paper-clean: ## Remove LaTeX build artifacts
	@echo "==> $@"
	latexmk -C -outdir=ms ms/blacklight.tex


########################################################################
# Other utilities
########################################################################
.PHONY: clean
clean: ## Clean all symlinks aux reports
clean: clean_sl clean_sl_task

.PHONY: help
help: ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'