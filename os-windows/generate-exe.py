pyinstaller --onefile --hidden-import=win32timezone --name "MyService" run.py

# Générez un exécutable pour run.py :

# --onefile : Crée un exécutable unique.
# --hidden-import=win32timezone : Nécessaire pour les services Windows.
# --name "MyService" : Donne un nom à l'exécutable.
# Une fois terminé, l'exécutable sera généré dans le dossier dist sous le nom MyService.exe.