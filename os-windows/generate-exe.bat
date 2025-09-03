@REM pip install pyinstaller

pyinstaller --onefile --hidden-import=win32timezone --name "MyService" run.py

@REM Générez un exécutable pour run.py :
@REM --onefile : Crée un exécutable unique.
@REM --hidden-import=win32timezone : Nécessaire pour les services Windows.
@REM --name "MyService" : Donne un nom à l'exécutable.
@REM Une fois terminé, l'exécutable sera généré dans le dossier dist sous le nom MyService.exe.