build: doc cov
	npm run minify

cov:
	npm run cov
	CODECLIMATE_REPO_TOKEN=$(shell cat .climatecoverage) \
		codeclimate < coverage/lcov.info

doc:
	npm run doc

test:
	npm run lint
	npm test
