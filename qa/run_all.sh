#!/bin/bash
# Jalankan 13 shard secara paralel dengan proses lokal (bukan subagent).
# Setiap proses memakai salinan DB sendiri, jadi aman paralel.
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django" || exit 1
MODE=${1:-smoke}
PARALLEL=${2:-10}
TOTAL=13
mkdir -p "qa/shards/$MODE"
rm -f "qa/shards/$MODE"/shard*.json

run_batch() {
  local start=$1 end=$2
  for i in $(seq "$start" "$end"); do
    .venv/Scripts/python.exe -m qa.runner --shard "$i" --total "$TOTAL" \
      --mode "$MODE" --out "qa/shards/$MODE/shard$i.json" \
      > "qa/shards/$MODE/_log$i.txt" 2>&1 &
  done
  wait
}

start=$(date +%s)
echo "=== batch 1: shard 0-$((PARALLEL-1)) ==="
run_batch 0 $((PARALLEL-1))
echo "=== batch 2: shard $PARALLEL-$((TOTAL-1)) ==="
run_batch "$PARALLEL" $((TOTAL-1))
end=$(date +%s)
echo "TOTAL_WALL=$((end-start))s MODE=$MODE"

# Verifikasi hasil dari JSON, bukan dari file log. Log bisa saja sudah
# dibersihkan; JSON adalah artefak sebenarnya yang harus ada.
echo "--- verifikasi shard ---"
missing=0
for i in $(seq 0 $((TOTAL-1))); do
  f="qa/shards/$MODE/shard$i.json"
  if [ -f "$f" ]; then
    .venv/Scripts/python.exe -c "
import json,sys
d=json.load(open(r'$f'))
print('  shard%-2d akun=%-4d req=%-6d %s' % (d['shard'], d['accounts'], d['requests'],
      ' '.join('%s=%s' % (k,v) for k,v in sorted(d['by_status'].items()))))
"
  else
    echo "  shard$i HILANG"
    missing=$((missing+1))
  fi
done

if [ "$missing" -gt 0 ]; then
  echo "GAGAL: $missing shard tidak menghasilkan output"
  exit 1
fi
echo "OK: $TOTAL/$TOTAL shard lengkap"
