@echo off
rem Localiza uma instalacao compativel do Python sem depender apenas do PATH.
rem As variaveis PYTHON_EXE e PYTHON_ARGS sao devolvidas ao arquivo chamador.

set "PYTHON_EXE="
set "PYTHON_ARGS="

rem Python Launcher tradicional ou Python Install Manager.
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    exit /b 0
)

rem Comando python disponivel diretamente no PATH.
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
    exit /b 0
)

rem Instalador classico por usuario, por exemplo Python314.
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do call :testar_executavel "%%~fD\python.exe"
if defined PYTHON_EXE exit /b 0

rem Novo Python Install Manager, quando os atalhos py/python nao estao no PATH.
for /d %%D in ("%LocalAppData%\Python\pythoncore-3.*") do call :testar_executavel "%%~fD\python.exe"
if defined PYTHON_EXE exit /b 0

rem Instalacao para todos os usuarios.
for /d %%D in ("%ProgramFiles%\Python3*") do call :testar_executavel "%%~fD\python.exe"
if defined PYTHON_EXE exit /b 0

exit /b 1

:testar_executavel
if defined PYTHON_EXE exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_EXE=%~1"
set "PYTHON_ARGS="
exit /b 0
