# Étape 3 : Créer un installeur avec NSIS
# Téléchargez et installez NSIS depuis nsis.sourceforge.io.

# Créez un fichier installer.nsi avec le contenu suivant :

OutFile "surveillance_pc_service.exe"
InstallDir "$PROGRAMFILES\\surveillance_pc"
RequestExecutionLevel admin

Section "Install"
    ; Crée le répertoire d'installation
    SetOutPath "$INSTDIR"

    ; Copie les exécutables dans le répertoire d'installation
    File "dist\surveillance_pc\surveillance_pc.exe"
    File "dist\surveillance_pc_service\surveillance_pc_service.exe"

    ; Copie le répertoire _internal et son contenu
    SetOutPath "$INSTDIR\_internal"
    File /r "dist\surveillance_pc\_internal\*.*"
    File /r "dist\surveillance_pc_service\_internal\*.*"

    ; Copie le fichier config.ini
    SetOutPath "$INSTDIR"
    File "dist\surveillance_pc\config.ini"
    File "dist\surveillance_pc_service\config.ini"

    ; Installe le service Windows
    Exec '"$INSTDIR\surveillance_pc_service.exe" install'

    ; Démarre le service
    Exec '"$INSTDIR\surveillance_pc_service.exe" start'

    ; Affiche un message de succès
    MessageBox MB_OK "Installation terminee !"
SectionEnd

Section "Uninstall"
    ; Arrête le service
    Exec '"$INSTDIR\surveillance_pc_service.exe" stop'

    ; Désinstalle le service
    Exec '"$INSTDIR\surveillance_pc_service.exe" remove'

    ; Supprime les fichiers
    Delete "$INSTDIR\surveillance_pc.exe"
    Delete "$INSTDIR\surveillance_pc_service.exe"

    ; Supprime le répertoire
    RMDir "$INSTDIR"

    ; Affiche un message de succès
    MessageBox MB_OK "Désinstallation terminée avec succès !"
SectionEnd


# Compilez le script NSIS :
    # Ouvrez NSIS et sélectionnez "Compile NSI Script".
    # Chargez le fichier installer.nsi et compilez-le.
    # Cela générera un fichier MyServiceInstaller.exe.

# Étape 4 : Tester l'installation

# Exécutez MyServiceInstaller.exe en tant qu'administrateur.
# Vérifiez que :
    # Le service est installé et démarre automatiquement.
    # Le service apparaît dans le gestionnaire de services Windows (services.msc).
    
# Résultat
# Vous avez maintenant un installeur .exe qui installe votre script Python en tant que service Windows, sans nécessiter Python sur les machines cibles. Si vous avez besoin d'aide supplémentaire, faites-le-moi savoir !