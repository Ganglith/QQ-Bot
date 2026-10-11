#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

PIP_INDEX="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
pip install --no-cache-dir -i "$PIP_INDEX" --upgrade pip
pip install --no-cache-dir -i "$PIP_INDEX" -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 .env，请填入 DEEPSEEK_API_KEY 后重新运行 ./run.sh"
  exit 1
fi

exec python main.py
