.PHONY: setup check-deps install test serve

setup: check-deps install
	@echo ""
	@echo "Setup complete."
	@echo "  1. Copy config:  cp config.example.json config.json"
	@echo "  2. Copy books:   cp books.example.json books.json"
	@echo "  3. See README.md for next steps."

check-deps:
	@which python3 > /dev/null 2>&1 || \
		(echo "ERROR: python3 not found. Install Python 3.9+." && exit 1)
	@which pdftotext > /dev/null 2>&1 || \
		(echo "ERROR: pdftotext not found. Install poppler:" && \
		 echo "  macOS:  brew install poppler" && \
		 echo "  Ubuntu: sudo apt install poppler-utils" && \
		 exit 1)
	@echo "All dependencies found."

install:
	pip3 install -e .

serve:
	./start.sh

test:
	@test -f books.json || (echo "Run: cp books.example.json books.json" && exit 1)
	@echo '{"plant":"test","sources":[]}' | python3 compile_precis.py
	@echo "Basic test passed."
