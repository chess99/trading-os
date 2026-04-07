#!/usr/bin/env bash
# Restore vendor reference repos.
# Usage: bash vendor/clone.sh
#
# These repos are gitignored and not committed.
# Pinned to specific commits for reproducibility.
# Run this script after cloning trading-os on a new machine.

set -euo pipefail
cd "$(dirname "$0")"

clone_pinned() {
  local name="$1"
  local url="$2"
  local commit="$3"

  if [ -d "$name/.git" ]; then
    echo "  skip $name (already exists)"
    return
  fi

  echo "  cloning $name ..."
  git clone --quiet "$url" "$name"
  git -C "$name" checkout --quiet "$commit"
  echo "  ok $name @ ${commit:0:8}"
}

echo "Restoring vendor reference repos..."

clone_pinned "TradingAgents"      "https://github.com/TauricResearch/TradingAgents"    "10c136f49c82e11f0e324c9c50cda1638a8ed5a7"
clone_pinned "TradingAgents-CN"   "https://github.com/hsliuping/TradingAgents-CN"      "bd599607e83cd0d249482e57869216d52b1cb2aa"
clone_pinned "daily_stock_analysis" "https://github.com/ZhuLinsen/daily_stock_analysis" "e8f76b43974dd0522cdb73dba45d2b69e19ce33d"
clone_pinned "go-stock"           "https://github.com/arvinlovegood/go-stock"          "7ddfa9cae9cb939e74486beeac923d5226a44593"
clone_pinned "AI-Trader"          "https://github.com/HKUDS/AI-Trader"                 "d3d2e6da92b8e0f6d8d679d466f9229c709410e3"
clone_pinned "ai_quant_trade"     "https://github.com/charliedream1/ai_quant_trade"    "c27a2eddb3bef777f86ee547e6ea7a69769052a2"
clone_pinned "Qbot"               "https://github.com/UFund-Me/Qbot"                   "f0425ae4ae8bd02b79656b8f7039f4cd6874095e"

echo "Done. See docs/research/ for analysis of each repo."
