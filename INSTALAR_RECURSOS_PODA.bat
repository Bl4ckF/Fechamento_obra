@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "runtime\python.exe" (
 "runtime\python.exe" tools\instalar_poda.py
 goto fim
)
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if not errorlevel 1 (
 py -3 tools\instalar_poda.py
 goto fim
)
python tools\instalar_poda.py
:fim
set "RESULTADO=%ERRORLEVEL%"
echo Reinicie o programa se a instalacao terminou com sucesso.
pause
exit /b %RESULTADO%
