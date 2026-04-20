@echo off
:: ============================================================
::  BulmaFlix – Script de build para Windows (.exe)
::  Execute este arquivo como Administrador se necessário
:: ============================================================

echo.
echo  =============================================
echo   BulmaFlix – Gerando executavel (.exe)
echo  =============================================
echo.

:: 1. Instalar dependências
echo [1/3] Instalando dependencias...
pip install customtkinter Pillow requests pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

:: 2. Gerar o .exe com PyInstaller
echo [2/3] Compilando o executavel...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name BulmaFlix ^
    --add-data "static;static" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import PIL._imagingtk ^
    --hidden-import PIL.Image ^
    --collect-all customtkinter ^
    main.py

if %errorlevel% neq 0 (
    echo ERRO: Falha na compilacao.
    pause
    exit /b 1
)

:: 3. Resultado
echo.
echo [3/3] Concluido!
echo.
echo  O executavel foi gerado em:
echo  dist\BulmaFlix.exe
echo.
pause
