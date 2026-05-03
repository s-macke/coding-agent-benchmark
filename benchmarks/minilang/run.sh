set -e

(cd V2 && go build -o ../minilang)

mkdir -p build

./minilang -s examples/add.ml > build/add.s
as build/add.s -o build/add.o
ld build/add.o -o build/add
./build/add
