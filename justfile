default:
	@just --list

setup:
	npx lefthook install

ci:
	chmod +x ci-monitoring/packages/src/index.ts && \
	ci-monitoring/packages/src/index.ts

vfr:
	uv run video-frame-reader/scripts/extract_frames.py


