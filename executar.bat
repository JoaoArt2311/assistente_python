@echo off
setlocal
cd /d "%~dp0"

call "%~dp0localizar_python.bat"
if errorlevel 1 (
    echo Python nao foi encontrado.
    echo.
    echo O sistema procurou pelos comandos py e python e tambem nas pastas
    echo padrao de instalacao do Windows.
    echo.
    echo Reinstale ou modifique o Python 3.10 ou superior e habilite:
    echo - Python Launcher ou Python Install Manager
    echo - Add Python to PATH
    pause
    exit /b 1
)

echo Python encontrado:
"%PYTHON_EXE%" %PYTHON_ARGS% --version
echo.

"%PYTHON_EXE%" %PYTHON_ARGS% app.py
if errorlevel 1 (
    echo.
    echo O programa terminou com um erro. Confira a mensagem exibida acima.
    pause
    exit /b 1
)

exit /b 0
