@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
title Engelmig - Selecionar versao e preparar publicacao
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if not errorlevel 1 goto py
python -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 goto sem_python
python "%~dp0publicar.py"
set "RESULTADO=%ERRORLEVEL%"
goto fim
:py
py -3 "%~dp0publicar.py"
set "RESULTADO=%ERRORLEVEL%"
goto fim
:sem_python
echo Python 3.9 ou superior nao encontrado.
set "RESULTADO=1"
:fim
echo.
pause
exit /b %RESULTADO%
