# Makefile for AWS Lambda deployment package

# Variables
ZIP_NAME = agent.zip
BUILD_DIR = build
PYTHON_VERSION = python3.11

# Default target
all: clean install package

# Clean previous builds
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(ZIP_NAME)

# Create build directory and install dependencies
install:
	mkdir -p $(BUILD_DIR)
	pip install -r requirements.txt -t $(BUILD_DIR)

# Package everything into a zip file
package:
	cp lambda_function.py $(BUILD_DIR)/
	cd $(BUILD_DIR) && zip -r ../$(ZIP_NAME) .
	@echo "Lambda deployment package created: $(ZIP_NAME)"

# Alternative target using virtual environment (more isolated)
venv-package: clean
	python3 -m venv temp_venv
	./temp_venv/bin/pip install -r requirements.txt -t $(BUILD_DIR)
	cp lambda_function.py $(BUILD_DIR)/
	cd $(BUILD_DIR) && zip -r ../$(ZIP_NAME) .
	rm -rf temp_venv
	@echo "Lambda deployment package created with venv: $(ZIP_NAME)"

# Show package contents
show:
	unzip -l $(ZIP_NAME)

# Test the package structure
test-package:
	@if [ -f $(ZIP_NAME) ]; then \
		echo "Checking package contents:"; \
		unzip -l $(ZIP_NAME) | grep -E "(main\.py|openai)"; \
	else \
		echo "Package $(ZIP_NAME) not found. Run 'make' first."; \
	fi

.PHONY: all clean install package venv-package show test-package
