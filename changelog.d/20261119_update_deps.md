### Other changes

- Update pinned dependencies, including FastAPI 0.165, pydantic 2.14, Starlette 1.10, uvicorn 0.54, websockets 17, FastStream 0.7.8, Safir 15.2.3, and uv 0.13.9. This picks up the security fixes proposed by Dependabot for the documentation toolchain (soupsieve 4.1.2 and tornado 6.6.1) and setuptools 84.2.1 ([GHSA-xmj3-9gf7-h52w](https://github.com/advisories/GHSA-xmj3-9gf7-h52w)).
- Remove the `fastapi<0.140` version cap. The incompatibility between FastAPI 0.140 and FastStream that required it was fixed in FastStream 0.7.3.
