# Security Policy

## Supported versions

This project is pre-1.0 and only the latest `v1.0.0-alphaN` tag is supported. Older alphas do not receive backports.

## Reporting a vulnerability

If you find a security issue, please **do not** open a public GitHub issue. Report it privately through GitHub's [security advisory system](https://github.com/mathys-lopinto/tabby-sync/security/advisories/new).

Include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof-of-concept.
- The affected version (commit hash or tag).

You will get an acknowledgement within a few days. Fixes for confirmed issues will be released as a new alpha tag and credited in the release notes unless you prefer to remain anonymous.

## Scope

In scope: the backend code in this repository, including the Django app, the Caddy reverse-proxy configuration, the Docker images built from this tree, and any management command or public API endpoint.

Out of scope: vulnerabilities in upstream dependencies that are not triggered by this project's usage (please report those to the relevant upstream), social engineering against operators, and misconfigurations in deployments that the project does not ship (e.g. a reverse proxy the operator set up themselves).
