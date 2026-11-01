# www

<<<<<<< HEAD
This directory contains github action dependencies for deployment of content to the owasp.org project website.

- latest
- stable
- v41, etc.

## assets

This folder is a storage location for the project's social/graphic assets.
=======
This directory contains GitHub Action dependencies for deploying WSTG content to
the OWASP project website
([www-project-web-security-testing-guide](https://github.com/OWASP/www-project-web-security-testing-guide)).

Per-channel templates:

- `latest/`
- `stable/`
- `v41/`, `v42/`, `v43/`, etc.

Each channel typically has `prepend.txt` (front matter + asset tags), `prepend.nav`
(sidebar title), and `info.md` (includes the shared navigation partial).

## scripts/

Publish helpers. See [`scripts/README.md`](scripts/README.md).

- `generate_nav.py` - nested sidebar YAML/HTML + filter hints from `document/README.md`

## assets/

Project social/graphic assets for the website.
>>>>>>> branch-2-rag-cwe-wstg
