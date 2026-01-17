set -e

source venv/bin/activate
python3 -m tools.gs.sprite_to_3dgs --iterations 1000 --resolution 128 --num-gaussians 10000 --device cuda
python3 -m tools.gs.render_gaussians --device cuda
