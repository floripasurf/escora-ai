#!/bin/zsh
# Battery of Part-2 analyses for one extracted tag. Usage: battery.sh TAG [DXF_PATH]
set -u
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
cd /Users/raphaellages/Desktop/escora-ai
export PYTHONPATH=.
TAG=$1
GEO=output/orguel_analysis/geo_$TAG.json
OUT=output/orguel_analysis/report_$TAG.txt
{
echo "########## $TAG ##########"
echo "---- CLUSTERS"
$PY scripts/orguel_cluster_stats.py $GEO output/orguel_analysis/clusters_$TAG.json
echo "---- SPACING (SCALE 0.01)"
$PY scripts/orguel_spacing.py $GEO 0.01
echo "---- TORRE LAYERS"
$PY scripts/orguel_torre_layers.py $GEO 0.01
for K in vm130 vm80; do
  echo "---- VMLINES $K"
  $PY scripts/orguel_vmlines.py $GEO 0.01 $K
  echo "---- ENDGAP $K"
  $PY scripts/orguel_vm_endgap.py $GEO 0.01 $K
done
if [ $# -gt 1 ]; then
  echo "---- SPACING TEXTS"
  $PY scripts/orguel_spacing_texts.py "$2"
fi
} > $OUT 2>&1
echo "done $TAG -> $OUT"
