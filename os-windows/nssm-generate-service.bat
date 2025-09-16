@echo off
setlocal

:: Vérifie si on est admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Relance en mode administrateur...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set NSSM=C:\dev\surveillance-pc\os-windows\nssm-2.24\win64\nssm.exe
set SRVNAME=SurveillancePC
set EXEPATH=C:\dev\surveillance-pc\os-windows\dist\surveillance_pc\surveillance_pc.exe
set LOGDIR=C:\dev\surveillance-pc\logs

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [*] Suppression ancienne version du service...
%NSSM% stop %SRVNAME% >nul 2>&1
%NSSM% remove %SRVNAME% confirm >nul 2>&1

echo [*] Installation du service %SRVNAME%...
%NSSM% install %SRVNAME% "%EXEPATH%"

:: Configuration du service
%NSSM% set %SRVNAME% AppDirectory C:\dev\surveillance-pc\os-windows\dist\surveillance_pc
%NSSM% set %SRVNAME% AppStdout %LOGDIR%\%SRVNAME%-out.log
%NSSM% set %SRVNAME% AppStderr %LOGDIR%\%SRVNAME%-err.log
%NSSM% set %SRVNAME% AppRotateFiles 1
%NSSM% set %SRVNAME% AppRotateOnline 1
%NSSM% set %SRVNAME% AppRotateBytes 1048576
%NSSM% set %SRVNAME% Start SERVICE_AUTO_START
%NSSM% set %SRVNAME% AppRestartDelay 5000

echo [*] Démarrage du service...
%NSSM% start %SRVNAME%

echo [*] Terminé !
echo Les logs se trouvent ici : %LOGDIR%
pause
endlocal
