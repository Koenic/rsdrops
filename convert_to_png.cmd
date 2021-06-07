cd images
FOR /R %%a IN (*.pdf) DO pdftoppm -png "%%~a" "%%~dpna.png"
cd ..