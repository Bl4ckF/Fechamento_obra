@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "runtime\python.exe" (
 "runtime\python.exe" tools\instalar_leitor_fotos.py
 goto fim
)
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if not errorlevel 1 (
 py -3 tools\instalar_leitor_fotos.py
 goto fim
)
python tools\instalar_leitor_fotos.py
:fim
set "RESULTADO=%ERRORLEVEL%"
if not "%RESULTADO%"=="0" (
 echo FALHA NA INSTALACAO. Leia a mensagem acima.
) else (
 echo Instalacao concluida. Reinicie o programa.
)
pause
exit /b %RESULTADO%
