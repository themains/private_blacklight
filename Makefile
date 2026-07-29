.DEFAULT_GOAL := help

########################################################################\
Make gitignore file
########################################################################
.PHONY: giti
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
# HTTP Archive validity checks (see scripts/httparchive/README.md)
# Runs the free steps and stops at the cost gate. BigQuery extraction is
# billed and run manually after you review the dry-run estimate:
#     python 03_ha_extract.py --confirm
# Requires: gcloud auth application-default login; export BQ_BILLING_PROJECT=...
########################################################################
.PHONY: httparchive
httparchive: ## Build HA targets + print BigQuery cost estimate (no billed queries)
	@echo "==> $@"
	cd scripts/httparchive && \
		$(abspath $(VENVPATH))/bin/python 01_build_ha_targets.py && \
		$(abspath $(VENVPATH))/bin/python 02_ha_dryrun.py
	@echo "==> Review the estimate, then: cd scripts/httparchive && python 03_ha_extract.py --confirm"


########################################################################
# Wayback validity checks (see scripts/wayback/README.md)
# Step 2 fetches ~3k snapshots from archive.org (~2h, resumable).
########################################################################
.PHONY: wayback
wayback: ## Build WB targets, fetch June-2022 snapshots, parse static measures
	@echo "==> $@"
	cd scripts/wayback && \
		$(abspath $(VENVPATH))/bin/python 01_build_wb_targets.py && \
		$(abspath $(VENVPATH))/bin/python 02_fetch_snapshots.py --preflight && \
		$(abspath $(VENVPATH))/bin/python 02_fetch_snapshots.py && \
		$(abspath $(VENVPATH))/bin/python 03_parse_static_requests.py

.PHONY: selection-audit
selection-audit: ## Parse scan failures, draw audit sample, probe + rescan, validate codes
	@echo "==> $@"
	cd scripts/selection_audit && \
		$(abspath $(VENVPATH))/bin/python 01_parse_scan_errors.py && \
		$(abspath $(VENVPATH))/bin/python 02_draw_audit_sample.py && \
		$(abspath $(VENVPATH))/bin/python 03_probe_and_rescan.py && \
		$(abspath $(VENVPATH))/bin/python 04_code_sample.py

.PHONY: implications
implications: ## Demographic robustness to coverage/timing threats + Google reach on unscanned
	@echo "==> $@"
	cd scripts/implications && \
		$(abspath $(VENVPATH))/bin/python 01_build_user_scenario_rates.py && \
		$(abspath $(VENVPATH))/bin/python 02_demo_robustness.py && \
		$(abspath $(VENVPATH))/bin/python 03_google_reach_audit.py && \
		$(abspath $(VENVPATH))/bin/python 04_gap_benchmarks.py


########################################################################
# Residual exposure under best-available defenses
# (see scripts/blocking/README.md and scripts/residual_exposure.md)
# Step 02 fetches EasyList/EasyPrivacy/Disconnect from GitHub, pinned to the
# commit nearest the Blacklight scan window.
########################################################################
.PHONY: blocking
blocking: ## Attribute behaviors to third parties, apply blocklists, recompute exposure
	@echo "==> $@"
	cd scripts/blocking && \
		$(abspath $(VENVPATH))/bin/python 01_extract_attribution.py && \
		$(abspath $(VENVPATH))/bin/python 02_fetch_blocklists.py && \
		$(abspath $(VENVPATH))/bin/python 03_apply_blocklists.py && \
		$(abspath $(VENVPATH))/bin/python 04_residual_measures.py && \
		$(abspath $(VENVPATH))/bin/python 05_residual_analysis.py && \
		$(abspath $(VENVPATH))/bin/python 06_robustness.py && \
		$(abspath $(VENVPATH))/bin/python 07_placebo.py

# Needs data/yg/realityMine_web_desktop_2022-06-01_2022-06-30.csv (287 MB,
# public on Harvard Dataverse). 09 prints the download command if it is absent.
.PHONY: residual
residual: ## Category, device, projection and security analyses on the residual measures
	@echo "==> $@"
	cd scripts && \
		$(abspath $(VENVPATH))/bin/python 09_build_visit_panel.py && \
		$(abspath $(VENVPATH))/bin/python 10_sensitive_categories.py && \
		$(abspath $(VENVPATH))/bin/python 11_age_gap_decomposition.py && \
		$(abspath $(VENVPATH))/bin/python 12_device_age_gradient.py && \
		$(abspath $(VENVPATH))/bin/python 13_security_privacy_link.py && \
		$(abspath $(VENVPATH))/bin/python 14_poststrat_weights.py && \
		$(abspath $(VENVPATH))/bin/python 16_who_coverage.py
	cd scripts/blocking && \
		$(abspath $(VENVPATH))/bin/python 09_allzero_sensitivity.py && \
		$(abspath $(VENVPATH))/bin/python 08_figures.py


########################################################################
# Manuscript
#
# Compiled from the REPO ROOT, not from ms/: \input{tables/...} and
# \includegraphics{figures/...} are root-relative while \bibliography is
# ms-relative, so BIBINPUTS/TEXINPUTS reconcile the two without editing the
# .tex. -shell-escape is required by the \quickwordcount macro, which shells
# out to texcount.
########################################################################
.PHONY: tables-ms
tables-ms: ## Wrap pipeline fragments into the tab*_formatted files the ms inputs
	@echo "==> $@"
	cd scripts && $(abspath $(VENVPATH))/bin/python 15_format_ms_tables.py

.PHONY: paper
paper: ## Compile ms/blacklight.pdf (runs tables-ms first)
paper: tables-ms
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