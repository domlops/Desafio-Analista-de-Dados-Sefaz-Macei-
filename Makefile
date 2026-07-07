PYTHON ?= python
MPLCONFIGDIR ?= /tmp/matplotlib

.PHONY: extrair consolidar validar outputs reproduzir

extrair:
	$(PYTHON) scripts/extrair_dados.py

consolidar:
	$(PYTHON) scripts/consolidar_dados.py

validar:
	$(PYTHON) scripts/validar_dados.py

outputs:
	MPLCONFIGDIR=$(MPLCONFIGDIR) $(PYTHON) scripts/gerar_outputs.py

reproduzir: extrair consolidar validar outputs
