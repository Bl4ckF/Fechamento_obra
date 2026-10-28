@echo off
chcp 65001 >nul
title Engelmig - Poda e Fechamento
cd /d "%~dp0"
if exist "runtime\python.exe" (
  "runtime\python.exe" app.py
  goto fim
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if not errorlevel 1 (
  py -3 app.py
  goto fim
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if not errorlevel 1 (
  python app.py
  goto fim
)
echo.
echo Python 3.9 ou superior nao foi encontrado.
echo Instale o Python, marque Add Python to PATH e execute este arquivo novamente.
echo A operacao Poda usa Pillow e ReportLab. Execute INSTALAR_RECURSOS_PODA.bat uma vez.
:fim
set "ENGELMIG_CODE=%ERRORLEVEL%"
if "%ENGELMIG_CODE%"=="0" exit /b 0
echo.
echo O programa terminou com um erro. Pressione uma tecla para fechar.
pause
exit /b %ENGELMIG_CODE%
