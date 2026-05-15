# Sourced by GitHub Actions deploy steps on Windows (Git Bash). Do not write HOME to GITHUB_ENV.
set -euo pipefail
export PATH="/c/Program Files/Git/usr/bin:/c/Program Files/Git/bin:/usr/bin:$PATH"
if [ -n "${USERPROFILE:-}" ] && [ -z "${HOME:-}" ]; then
  export HOME="${USERPROFILE}"
fi
export HOME="${HOME:-${RUNNER_TEMP}}"

to_unix_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$1"
  else
    echo "$1" | sed 's|\\|/|g'
  fi
}
