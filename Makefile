IMAGE?=contract-auditor
OUT?=out

.PHONY: build
build:
	docker build -t $(IMAGE) .

.PHONY: audit-one
audit-one: # make audit-one PATH=contracts/evm/Sample.sol KIND=evm
	docker run --rm -v "$$PWD:/work" -w /work $(IMAGE) \
		audit $(PATH) --kind $(KIND) --out $(OUT) \
		--risk on --risk-export csv --slither auto --eop auto --llm off

.PHONY: discover
discover:
	python3 scripts/discover_contracts.py

.PHONY: test-discovery
test-discovery:
	@echo "Testing contract discovery..."
	@python3 scripts/discover_contracts.py | jq '.'
