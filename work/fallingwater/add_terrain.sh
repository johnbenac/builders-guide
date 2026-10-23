#!/bin/sh
# Test run of the terrain pipeline on the house: synthetic sloped ground stands in for the terrain source's patch.
# Real terrain comes from the terrain source; make_sample_terrain.py is for tests only.
set -e
cd "$(dirname "$0")/../.."
OUT=work/fallingwater/out
python3 tools/site_request.py $OUT/ifc/fallingwater-master.ifc --floor-elevation 412.0 --origin 0 0 \
  --profile work/fallingwater/profile-terrain.json --out $OUT/terrain/site-request.json
python3 tools/make_sample_terrain.py $OUT --request $OUT/terrain/site-request.json --slope-y 0.1 --pixel-size 0.25
python3 tools/terrain_import.py $OUT/terrain/patch.tif $OUT/terrain/patch.json $OUT/ifc/fallingwater-master.ifc \
  --request $OUT/terrain/site-request.json --out $OUT/ifc/fallingwater-terrain.ifc --profile work/fallingwater/profile-terrain.json
python3 tools/check_ifc.py $OUT/ifc/fallingwater-terrain.ifc --profile work/fallingwater/profile-terrain.json --report $OUT/report-terrain.json
