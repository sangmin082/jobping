.PHONY: install test verify verify-all dry-run validate build deploy deploy-first logs invoke

STAGE ?= dev

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

test:
	.venv/bin/pytest -q

# 예: make verify A=naver
verify:
	.venv/bin/python scripts/verify.py $(A)

verify-all:
	.venv/bin/python scripts/verify.py --all --limit 1

# 실제 소스를 수집하고 신규 판정·매칭·알림 계획까지 돌리되 아무것도 보내지 않는다.
dry-run:
	.venv/bin/python scripts/dry_run.py $(ARGS)

validate:
	.venv/bin/sam validate --lint

# --use-container: cryptography 같은 네이티브 휠을 Lambda(arm64) 용으로 받는다.
# Mac 에서 컨테이너 없이 빌드하면 macOS 휠이 들어가 Lambda 에서 import 가 실패한다.
build:
	.venv/bin/sam build --use-container

deploy-first:
	.venv/bin/sam deploy --guided --parameter-overrides Stage=$(STAGE)

deploy: build
	.venv/bin/sam deploy --no-confirm-changeset --parameter-overrides Stage=$(STAGE)

logs:
	.venv/bin/sam logs -n CollectorFunction --stack-name jobping-$(STAGE) --tail

invoke:
	aws lambda invoke --function-name jobping-$(STAGE)-collector --payload '{}' /dev/stdout
