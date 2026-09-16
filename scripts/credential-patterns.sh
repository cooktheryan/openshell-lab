#!/usr/bin/env bash
# Shared extended regular expressions for repository scanning and evidence redaction.
# shellcheck disable=SC2034 # Consumers use different subsets of these constants.

readonly OPENAI_SECRET_PATTERN='sk-[A-Za-z0-9_-]{20,}'
readonly AWS_ACCESS_KEY_ID_PATTERN='(AKIA|ASIA)[0-9A-Z]{16}'
readonly AWS_LABELED_SECRET_PATTERN='((AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)[[:space:]"]*[:=][[:space:]"]*)[^[:space:]",}]+'
readonly GITHUB_SECRET_PATTERN='(github_pat_[A-Za-z0-9_]{20,}|gh[opusr]_[A-Za-z0-9_]{20,})'
readonly PRIVATE_KEY_MARKER_PATTERN='-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----'
readonly AUTHORIZATION_VALUE_PATTERN='(Authorization: *(Bearer|Basic) +)[^[:space:]]+'
