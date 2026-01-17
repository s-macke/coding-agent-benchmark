set -e

CAMERA=orthographic
#CAMERA=perspective

source venv/bin/activate
python3 -m tools.gs.sprite_to_3dgs  \
  --iterations 2000                 \
  --resolution 128                  \
  --num-gaussians 10000             \
  --camera-type ${CAMERA}           \
  --pose-opt                        \
  --device cuda

python3 -m tools.gs.render_gaussians --camera-type ${CAMERA} --device cuda
