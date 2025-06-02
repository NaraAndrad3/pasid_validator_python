@echo off
set CONFIGS_DIR=..\config

echo Iniciando os Serviços...

start python run_service.py %CONFIGS_DIR%\service_2001.properties
start python run_service.py %CONFIGS_DIR%\service_2002.properties

start python run_service.py %CONFIGS_DIR%\service_3001.properties
start python run_service.py %CONFIGS_DIR%\service_3002.properties

timeout /t 2

echo Iniciando os Load Balancers...

start python run_loadbalancer.py %CONFIGS_DIR%\loadbalancer2.properties
timeout /t 1
start python run_loadbalancer.py %CONFIGS_DIR%\loadbalancer1.properties

timeout /t 1
echo Iniciando a Source...

start python run_source.py %CONFIGS_DIR%\source.properties
