#!/usr/bin/env bash
set -e

VERSION=$(uv version --short)
git tag "v$VERSION"
git push && git push --tags