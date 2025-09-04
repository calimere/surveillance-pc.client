@REM pip install pyinstaller

@REM Générez un exécutable pour run.py :
@REM --onefile : Crée un exécutable unique.
@REM --hidden-import=win32timezone : Nécessaire pour les services Windows.
@REM --name "surveillance-pc" : Donne un nom à l'exécutable.
@REM Une fois terminé, l'exécutable sera généré dans le dossier dist sous le nom surveillance-pc.exe.
%USERPROFILE%\AppData\Roaming\Python\Python312\Scripts\pyinstaller --onefile --hidden-import=win32timezone --name "surveillance-pc" ../run.py



@REM Copier le fichier de configuration dans le dossier dist
COPY ..\config.ini .dist\config.ini