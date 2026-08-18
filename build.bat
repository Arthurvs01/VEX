@echo off
setlocal

cd /d "%~dp0"

echo ==========================================
echo VEX - BUILD
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo.
    pause
    exit /b 1
)

echo [1/2] Compilando ONEDIR...
echo.

".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm "Vex - Gestor de Pedidos - onedir.spec"

if errorlevel 1 (
    echo.
    echo ==========================================
    echo ERRO NA COMPILACAO ONEDIR
    echo ==========================================
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] ONEDIR compilado com sucesso.
echo.

echo ==========================================
echo [2/2] Compilando ONEFILE...
echo ==========================================
echo.

".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm "Vex - Gestor de Pedidos - onefile.spec"

if errorlevel 1 (
    echo.
    echo ==========================================
    echo ERRO NA COMPILACAO ONEFILE
    echo ==========================================
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD CONCLUIDO COM SUCESSO
echo ==========================================
echo.
echo ONEDIR:
echo dist\Vex - Gestor de Pedidos - 1.0.9-beta\
echo.
echo ONEFILE:
echo dist\Vex - Gestor de Pedidos - 1.0.9-beta.exe
echo.
pause