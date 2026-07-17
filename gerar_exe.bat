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

echo Instalando a ferramenta de empacotamento...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade -r requirements-build.txt
if errorlevel 1 goto :error

echo.
echo Gerando AssistenteTI.exe...
"%PYTHON_EXE%" %PYTHON_ARGS% -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name AssistenteTI app.py
if errorlevel 1 goto :error

echo.
echo Concluido: dist\AssistenteTI.exe
pause
exit /b 0

:error
echo.
echo Nao foi possivel gerar o arquivo EXE.
pause
exit /b 1
