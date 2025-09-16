!include "MUI2.nsh"

OutFile "SurveillancePC-Setup.exe"
InstallDir "$PROGRAMFILES\SurveillancePC"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Installer SurveillancePC"

  SetOutPath "$INSTDIR"

  ; Copie des fichiers principaux
  File "dist\surveillance_pc\surveillance_pc.exe"
  File "dist\surveillance_pc\config.ini"

  ; Copie du répertoire _internal et son contenu
  SetOutPath "$INSTDIR\_internal"
  File /r "dist\surveillance_pc\_internal\*.*"

  ; Copie de NSSM
  SetOutPath "$INSTDIR"
  File "nssm-2.24\win64\nssm.exe"

  ; Crée le dossier de logs
  CreateDirectory "$INSTDIR\logs"

  ; Installer le service via NSSM
  ExecWait '"$INSTDIR\nssm.exe" install SurveillancePC "$INSTDIR\surveillance_pc.exe"'
  ExecWait '"$INSTDIR\nssm.exe" set SurveillancePC AppDirectory "$INSTDIR"'
  ExecWait '"$INSTDIR\nssm.exe" set SurveillancePC AppStdout "$INSTDIR\logs\SurveillancePC-out.log"'
  ExecWait '"$INSTDIR\nssm.exe" set SurveillancePC AppStderr "$INSTDIR\logs\SurveillancePC-err.log"'
  ExecWait '"$INSTDIR\nssm.exe" set SurveillancePC Start SERVICE_AUTO_START'
  ExecWait '"$INSTDIR\nssm.exe" set SurveillancePC AppRestartDelay 5000'

  ; Démarrage du service
  ExecWait '"$INSTDIR\nssm.exe" start SurveillancePC'

SectionEnd

Section "Uninstall"
  ; Stop et remove service
  ExecWait '"$INSTDIR\nssm.exe" stop SurveillancePC'
  ExecWait '"$INSTDIR\nssm.exe" remove SurveillancePC confirm'

  ; Supprime tous les fichiers
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\surveillance_pc.exe"
  Delete "$INSTDIR\config.ini"
  Delete "$INSTDIR\nssm.exe"
  RMDir /r "$INSTDIR\logs"
  RMDir "$INSTDIR"

SectionEnd
