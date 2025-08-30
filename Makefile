setup:
	docker build -t contract-auditor .

help:
	docker run --rm contract-auditor --help

audit-example:
	docker run --rm -v $$PWD:/work -w /work contract-auditor audit examples/sample.sol --kind evm --out out --llm off
