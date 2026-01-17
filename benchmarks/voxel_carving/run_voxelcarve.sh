set -e
(cd tools/space_carving && go build)
rm -f renders/*.png
./tools/space_carving/voxelcarve  \
  -json ship_sprites_centered.json  \
  -images centered_images         \
  -resolution 128                 \
  -min-votes 1                    \
  -extent 2.                      \
  -camera perspective             \
  -fov 60 -distance 5.0           \
  -mesh -render -symmetry         \
  -cardinal                       \
  -vox

# -cardinal

montage renders/view_*_comparison.png -tile 6x7 -geometry +2+2 -background black comparison_grid.png

#python tools/sprite_to_3dgs.py --iterations 1000 --resolution 128 --num-gaussians 10000 --device cuda

#python tools/render_gaussians.py