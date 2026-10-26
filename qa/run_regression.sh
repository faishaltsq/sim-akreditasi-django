#!/bin/bash
# Regression baca: jalankan 2x, bandingkan per (akun,url) untuk deteksi flaky.
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django" || exit 1
mkdir -p qa/shards/regression

run_pass() {
  local pass=$1
  for i in $(seq 0 9); do
    .venv/Scripts/python.exe -m qa.runner --shard "$i" --total 13 \
      --mode regression --out "qa/shards/regression/p${pass}_shard$i.json" \
      > /dev/null 2>&1 &
  done
  wait
  for i in 10 11 12; do
    .venv/Scripts/python.exe -m qa.runner --shard "$i" --total 13 \
      --mode regression --out "qa/shards/regression/p${pass}_shard$i.json" \
      > /dev/null 2>&1 &
  done
  wait
}

echo "=== pass 1 ==="
run_pass 1
echo "=== pass 2 ==="
run_pass 2
echo "=== selesai ==="
ls qa/shards/regression/p*_shard*.json | wc -l
