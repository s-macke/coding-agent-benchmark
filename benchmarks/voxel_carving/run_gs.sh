set -e

#CAMERA=orthographic
CAMERA=perspective

#FOV=90
#DISTANCE=5
#loss=0.0458

#FOV=50
#DISTANCE=4.8
#loss=0.0334


#FOV=30
#DISTANCE=8
#loss=0.0326

# Best Fit so far
FOV=40
DISTANCE=8
#loss=0.0303

#FOV=40
#DISTANCE=9
#loss=0.0308

#FOV=40
#DISTANCE=7
##loss=ß-ß311


#FOV=50
#DISTANCE=8
#loss=0.0318

#FOV=45
#DISTANCE=8
#loss=0.0309

#FOV=15
#DISTANCE=16
#loss=0.0364

#FOV=3.75
#DISTANCE=64
#loss=0.0444

source venv/bin/activate

#python tools/generate_sprites_json.py --input-dir images/SHIP.V06
#python tools/generate_sprites_json.py --input-dir images/SHIP.V08
#python3 tools/center_sprites.py --input-dir images/SHIP.V06 --orthogonal-only

python3 -m tools.gs.sprite_to_3dgs  \
  --iterations 2000                 \
  --resolution 128                  \
  --num-gaussians 10000             \
  --loss-type l1_ssim               \
  --camera-type ${CAMERA}           \
  --fov ${FOV}                      \
  --train-mode splats               \
  --symmetric                       \
  --distance ${DISTANCE}            \
  --render                          \
  --device cuda

# --train-mode splats+camera
# --train-mode camera

# --pose-opt

python3 -m tools.gs.render_gaussians   \
  --camera-type ${CAMERA}              \
  --fov ${FOV}                         \
  --distance ${DISTANCE}               \
  --device cuda

