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
# Other utilities
########################################################################
.PHONY: clean
clean: ## Clean all symlinks aux reports
clean: clean_sl clean_sl_task

.PHONY: help
help: ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'