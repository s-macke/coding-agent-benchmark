set -e
(cd tools/space_carving && go build)
./tools/space_carving/voxelcarve -json ship_sprites_centered.json -images centered_images -resolution 128 -symmetry -mesh true -render

montage renders/view_*_comparison.png -tile 6x7 -geometry +2+2 -background black ../comparison_grid.png
