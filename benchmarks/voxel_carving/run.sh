set -e
(cd tools/space_carving && go build)
./tools/space_carving/voxelcarve -json ship_sprites_centered.json -images centered_images -resolution 128 -symmetry -mesh true
