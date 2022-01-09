@echo off
setlocal EnableDelayedExpansion
cd images
FOR /R %%a IN (*.pdf) DO call :rename "%%a"
goto :end

:rename
SET "NAME=!%~1!"
SET NEWNAME=!NAME:.pdf=!
echo !NEWNAME!.pdf
pdftoppm -png -singlefile "!NAME!" "!NEWNAME!"
goto :eof

:end
cd ..