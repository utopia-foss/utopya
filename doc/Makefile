# Makefile for Sphinx documentation of dantro

# You can set these variables from the command line
# For available options, see:
# 	http://www.sphinx-doc.org/en/stable/man/sphinx-build.html
SPHINXOPTS    = -W --keep-going -w build_errors.log
SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# A target to build the whole HTML documentation, including API documentation
doc:
	make html
	@echo "Built HTML documentation."

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
