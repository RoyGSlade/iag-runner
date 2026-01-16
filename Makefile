.PHONY: dev test

dev:
\tdocker compose up --build

test:
\tPYTHONPATH=backend pytest
\tcd frontend && npm install && npm run test:run
