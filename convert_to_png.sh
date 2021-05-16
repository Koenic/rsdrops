cd images
find . -maxdepth 1 -type f -name '*.pdf' -exec pdftoppm -png {} {} \;
cd ..