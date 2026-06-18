setup:
	@echo "Install dependencies here"

test:
	@echo "Run tests here"

typecheck:
	@echo "Run typecheck here"

lint:
	@echo "Run lint here"

build:
	@echo "Run build here"

verify: test typecheck lint build