set -e

CAMERA=orthographic
#CAMERA=perspective
FOV=60
DISTANCE=4


source venv/bin/activate

python3 -m tools.gs.sprite_to_3dgs  \
  --iterations 10000                 \
  --resolution 128                  \
  --num-gaussians 20000             \
  --camera-type ${CAMERA}           \
  --fov ${FOV}                      \
  --distance ${DISTANCE}            \
  --pose-opt                        \
  --device cuda

python3 -m tools.gs.render_gaussians   \
  --camera-type ${CAMERA}              \
  --fov ${FOV}                         \
  --distance ${DISTANCE}               \
  --device cuda

