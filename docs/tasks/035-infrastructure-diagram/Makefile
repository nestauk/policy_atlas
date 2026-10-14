.PHONY: setup render render-bedrock

# Override PYTHON and PDFTOPPM to use the local document runtime.
PYTHON ?= python3
PDFTOPPM ?= pdftoppm
OUT := ../../../output/pdf

# build_diagram.py needs ReportLab; pinned in requirements.txt beside it.
setup:
	$(PYTHON) -m pip install -r requirements.txt

render:
	$(PYTHON) build_diagram.py
	$(PDFTOPPM) -scale-to 3840 -singlefile -png $(OUT)/policy-atlas-infrastructure.pdf $(OUT)/policy-atlas-infrastructure

render-bedrock:
	$(PYTHON) build_diagram.py --bedrock
	$(PDFTOPPM) -scale-to 3840 -singlefile -png $(OUT)/policy-atlas-infrastructure-bedrock-proposed.pdf $(OUT)/policy-atlas-infrastructure-bedrock-proposed
