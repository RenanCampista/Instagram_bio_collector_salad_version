@echo off
REM Script para Windows para construir e fazer deploy da aplicação no SaladCloud

REM Configurações - MODIFIQUE ESTAS VARIÁVEIS
set DOCKER_USERNAME=renan2002
set IMAGE_NAME=instagram-bio-collector
set VERSION=latest
set FULL_IMAGE_NAME=%DOCKER_USERNAME%/%IMAGE_NAME%:%VERSION%

echo Construindo imagem Docker: %FULL_IMAGE_NAME%

REM Verificar se Docker está rodando
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Docker não está rodando. Inicie o Docker primeiro.
    pause
    exit /b 1
)

REM Construir a imagem
echo Construindo imagem...
docker build -t "%FULL_IMAGE_NAME%" .

if %errorlevel% neq 0 (
    echo ERRO: Erro ao construir imagem.
    pause
    exit /b 1
)

echo Imagem construída com sucesso!

REM Perguntar se deve fazer upload
set /p UPLOAD="Fazer upload para Docker Hub? (y/n): "
if /i "%UPLOAD%"=="y" (
    echo Fazendo upload para Docker Hub...
    
    REM Login no Docker Hub
    echo Faça login no Docker Hub:
    docker login
    
    REM Fazer upload
    docker push "%FULL_IMAGE_NAME%"
    
    if %errorlevel% neq 0 (
        echo ERRO: Erro ao fazer upload.
        pause
        exit /b 1
    )
    
    echo Upload concluído!
    echo.
    echo Informações para o SaladCloud:
    echo    Image: %FULL_IMAGE_NAME%
    echo    Command: python3 main_instaloader_salad.py nordvpn
    echo.
    echo Configure estas variáveis de ambiente no SaladCloud:
    echo    - MONGO_CONNECTION_STRING
    echo    - MONGO_DB
    echo    - MONGO_COLLECTION
    echo    - API_ROUTE
    echo    - SECRET_TOKEN
    echo    - VPN_SERVICE ^(opcional, padrão: nordvpn^)
) else (
    echo Upload cancelado. Para fazer upload mais tarde:
    echo    docker push %FULL_IMAGE_NAME%
)

echo.
echo Consulte SALAD_SETUP.md para instruções completas de configuração!
pause