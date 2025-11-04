#!/usr/bin/env pwsh
# Runs Backstage without auto-opening a browser. Uses Yarn 4 from repo.
$env:BROWSER = "none"
$env:BROWSER_ARGS = "--no-sandbox"
node .yarn\releases\yarn-4.4.1.cjs start
