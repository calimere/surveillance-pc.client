# Étape 3 : Créer un installeur avec NSIS
# Téléchargez et installez NSIS depuis nsis.sourceforge.io.

# Créez un fichier installer.nsi avec le contenu suivant :

OutFile "MyServiceInstaller.exe"
InstallDir "$PROGRAMFILES\MyPythonService"
RequestExecutionLevel admin

Section "Install"
    ; Crée le répertoire d'installation
    SetOutPath "$INSTDIR"

    ; Copie les exécutables dans le répertoire d'installation
    File "dist\MyService.exe"
    File "dist\ServiceInstaller.exe"

    ; Installe le service Windows
    Exec '"$INSTDIR\ServiceInstaller.exe" install'

    ; Démarre le service
    Exec '"$INSTDIR\ServiceInstaller.exe" start'

    ; Affiche un message de succès
    MessageBox MB_OK "Installation terminée avec succès !"
SectionEnd

Section "Uninstall"
    ; Arrête le service
    Exec '"$INSTDIR\ServiceInstaller.exe" stop'

    ; Désinstalle le service
    Exec '"$INSTDIR\ServiceInstaller.exe" remove'

    ; Supprime les fichiers
    Delete "$INSTDIR\MyService.exe"
    Delete "$INSTDIR\ServiceInstaller.exe"

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