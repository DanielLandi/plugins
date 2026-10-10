#!/usr/bin/env bash
# Installer script for the "recreate-batatais-scene" skill across LLM Agent CLIs.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash -s -- --project
#   curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash -s -- --claude
#   curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash -s -- --gemini
#   curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash -s -- --codex
#   curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash -s -- --all

set -euo pipefail

SKILL_URL="https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/skills/recreate-batatais-scene/SKILL.md"
SKILL_NAME="recreate-batatais-scene"

say() { printf '\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

target="auto"
project_mode=0

for arg in "$@"; do
  case "$arg" in
    --claude) target="claude" ;;
    --gemini|--antigravity) target="gemini" ;;
    --codex|--chatgpt) target="codex" ;;
    --all) target="all" ;;
    --project) project_mode=1 ;;
    -h|--help)
      echo "Install the Batatais Procedural 3D Scene Skill into your AI Agent CLI."
      echo "Usage: curl -fsSL https://raw.githubusercontent.com/DanielLandi/plugins/main/batatais/install.sh | bash -s -- [options]"
      echo "Options: --claude, --gemini, --codex, --all, --project"
      exit 0
      ;;
  esac
done

say "Downloading Batatais Procedural Scene Skill..."
TMP_FILE=$(mktemp)
trap 'rm -f "$TMP_FILE"' EXIT

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$SKILL_URL" -o "$TMP_FILE"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$TMP_FILE" "$SKILL_URL"
else
  echo "Error: curl or wget required." >&2
  exit 1
fi

installed_any=0

install_to() {
  local dir="$1"
  local label="$2"
  mkdir -p "$dir"
  cp "$TMP_FILE" "$dir/SKILL.md"
  info "Installed for $label: $dir/SKILL.md"
  installed_any=1
}

if [ "$project_mode" = 1 ]; then
  install_to ".claude/skills/$SKILL_NAME" "Claude Code (Project)"
  install_to "skills/$SKILL_NAME" "General / Antigravity / Codex (Project)"
else
  if [ "$target" = "claude" ] || [ "$target" = "all" ] || { [ "$target" = "auto" ] && [ -d "$HOME/.claude" ]; }; then
    install_to "$HOME/.claude/skills/$SKILL_NAME" "Claude Code"
  fi

  if [ "$target" = "gemini" ] || [ "$target" = "all" ] || { [ "$target" = "auto" ] && [ -d "$HOME/.gemini" ]; }; then
    install_to "$HOME/.gemini/skills/$SKILL_NAME" "Antigravity / Gemini"
  fi

  if [ "$target" = "codex" ] || [ "$target" = "all" ] || { [ "$target" = "auto" ] && [ -d "$HOME/.codex" ]; }; then
    install_to "$HOME/.codex/skills/$SKILL_NAME" "Codex / ChatGPT"
  fi

  if [ "$installed_any" = 0 ]; then
    # Default fallback: install to current project directory
    warn "No global CLI directories found. Installing to local project directory..."
    install_to ".claude/skills/$SKILL_NAME" "Claude Code (Local)"
    install_to "skills/$SKILL_NAME" "Portable Skills (Local)"
  fi
fi

say "Done!"
echo ""
echo "To regenerate or iterate on the 3D scene, prompt your agent (Blender MCP is optional; background Blender also works):"
echo ""
echo '  "Use the recreate-batatais-scene skill to generate the procedural model from scratch."'
echo ""
