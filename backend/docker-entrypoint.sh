#!/bin/sh
set -e

# 迁移 + 首次空库自动灌 Demo 数据；有数据则跳过
python -m app.seed

exec "$@"
